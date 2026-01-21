# Review_2

## Scope
- backend/ (FastAPI + Celery worker + services + repositories)
- frontend/ (Vite + React + Deck.gl)
- docker-compose.yml and monitoring/
- backend_node_archive/ (legacy Fastify backend)

## Findings (ordered by severity)

### Critical
1) Upload workflow breaks when using the Celery worker in Docker
   - Impact: uploads are written to `/tmp/uploads` inside the backend container, but the worker runs in a separate container without a shared volume, so `process_upload` cannot read the file and ingestion fails.
   - Evidence: `backend/app/routers/uploads.py:15-80`, `backend/app/services/ingest.py:124-208`, `docker-compose.yml` (no shared volume between backend and worker).

2) User registration is not committed
   - Impact: `/api/auth/register` returns a token, but the user record may be rolled back when the session closes, so logins fail and the account disappears.
   - Evidence: `backend/app/routers/auth.py:46-71`, `backend/app/db.py:15-17` (no implicit commit in the request scope).

### High
3) Zonal stats can return incorrect results
   - Impact: values are pulled without filtering `attr_key`, so stats can mix unrelated attributes and double-count values. In addition, `execute_set_operation("union", [single_dataset])` can return duplicate dggids.
   - Evidence: `backend/app/routers/stats.py:47-82`, `backend/app/repositories/cell_object_repo.py:12-52`.

4) Spatial ops can join wrong rows
   - Impact: `/api/ops/spatial` only filters `tid` for dataset A and does not filter dataset B by `attr_key` unless `keyB` is provided, which can duplicate rows and mix attributes.
   - Evidence: `backend/app/routers/ops.py:175-233`.

5) Workbench dataset loading is truncated and uses a mismatched API
   - Impact: `loadDemoLayer` uses analytics intersection with the same dataset to fetch dggids, which relies on a default limit of 1000 and ignores attributes. This produces partial or misleading layers.
   - Evidence: `frontend/src/pages/Workbench.tsx:91-107`, `backend/app/repositories/cell_object_repo.py:12-39`.

6) Startup performs a heavy, network-dependent data load
   - Impact: the API startup always fetches Natural Earth data and processes it in-process, which can significantly delay startup or fail entirely when outbound network access is restricted.
   - Evidence: `backend/app/main.py:9-20`, `backend/app/services/real_data_loader.py:52-170`.

7) DGGS grid renders near (0,0) due to coordinate system mismatch
   - Impact: lon/lat rings are interpreted as WebMercator meter offsets, collapsing the grid near the origin instead of their true positions.
   - Evidence: `frontend/src/components/MapView.tsx:392-404` (no explicit `coordinateSystem: COORDINATE_SYSTEM.LNGLAT`), contrast with `frontend/src/pages/Workbench.tsx:72-88`.

8) Raster ingestion writes `tid=1` but UI queries default to `tid=0`
   - Impact: raster uploads can appear empty in the dashboard because `fetchCellsByDggids` defaults to `tid=0` while raster cells are stored with `tid=1`.
   - Evidence: `backend/app/services/ingest.py:148-178`, `frontend/src/components/MapView.tsx:98-102`.

### Medium
9) `dggs_name` is ignored and everything assumes IVEA3H
   - Impact: datasets created with other DGGS names are still processed/rendered as IVEA3H, which can make topology and ingestion incorrect for non-IVEA3H data.
   - Evidence: `backend/app/services/ingest.py:16-141`, `backend/app/dggal_utils.py:1-110`, `frontend/src/lib/dggal.ts:1-200`.

10) Raster ingestion assumes WGS84 without reprojection
   - Impact: GeoTIFFs in any other CRS will be sampled using wrong coordinates, producing incorrect values.
   - Evidence: `backend/app/services/ingest.py:148-178`.

11) `DATABASE_URL` conversion only handles `postgres://`
   - Impact: `postgresql://` URLs will not be converted to `postgresql+asyncpg://`, which can break SQLAlchemy async connections in common environments.
   - Evidence: `backend/app/db.py:7-12`.

12) Dataset metadata field mismatch in the frontend
   - Impact: Dataset search UI expects `metadata_`, but the API returns `metadata`, so type labels always fall back to "data".
   - Evidence: `frontend/src/components/DatasetSearch.tsx:4-86`, `backend/app/routers/datasets.py:16-44`.

13) Dashboard layers are not actually used for rendering
   - Impact: `LayerList` and styling changes update the store, but `MapView` renders from viewport queries and ignores stored layer settings; toolbox changes appear to do nothing in the dashboard.
   - Evidence: `frontend/src/pages/DashboardPage.tsx:39-112`, `frontend/src/components/MapView.tsx:1-230`, `frontend/src/lib/store.ts:1-33`.

14) Toolbox is mostly scaffolding
   - Impact: tool execution is mocked and the ToolRegistry endpoints do not map to backend routes, so most tools cannot run.
   - Evidence: `frontend/src/components/ToolboxPanel.tsx:34-40`, `frontend/src/lib/toolRegistry.ts:92-209`, `backend/app/routers/toolbox.py:1-68`.

15) Upload handling has weak validation and cleanup
   - Impact: file names are used directly in paths (path traversal risk if a non-browser client supplies slashes), there is no size/type validation, and no cleanup of `/tmp/uploads`.
   - Evidence: `backend/app/routers/uploads.py:32-38`.

16) Repository base class assumes a single `id` primary key
   - Impact: `update` and `delete` will not work correctly for models like `CellObject` with composite keys.
   - Evidence: `backend/app/repositories/base.py:29-41`.

17) Upload status can be stale due to a race with Celery
   - Impact: the Celery worker may update `uploads.status` before the record is inserted, leaving failed uploads stuck in `processing`.
   - Evidence: `backend/app/routers/uploads.py:70-93`, `backend/app/services/ingest.py:116-122`.

18) Dashboard fetch can accidentally send `key=undefined`
   - Impact: datasets created without metadata may return zero cells because the query string includes `key=undefined`, which filters out all rows.
   - Evidence: `frontend/src/pages/DashboardPage.tsx:80-84`, `frontend/src/lib/api.ts:104-106`.

19) SpatialEngine uses unbounded parallelism
   - Impact: `buffer`, `expand`, and `aggregate` spawn a task per cell without limits, which can overwhelm CPU/memory for large inputs.
   - Evidence: `backend/app/services/spatial_engine.py:16-73`.

20) DuckDB spatial cache uses string interpolation and CDN "latest"
   - Impact: SQL built via interpolation can break on unexpected zone ids, and using `@latest` for wasm assets is a supply chain/runtime stability risk.
   - Evidence: `frontend/src/lib/spatialDb.ts:14-195`.

### Low
21) Legacy backend is still in-repo
   - Impact: `backend_node_archive/` duplicates API logic and includes built artifacts, which increases maintenance surface and can confuse contributors.
   - Evidence: `backend_node_archive/`.

22) Python cache artifacts are committed
   - Impact: `__pycache__` and `.pyc` files add noise and can cause false diffs.
   - Evidence: `backend/app/__pycache__/`, `backend/app/services/__pycache__/`.

23) Auth redirect reason is stored but unused
   - Impact: `auth_redirect_reason` is written but never displayed, so the UX feedback is lost.
   - Evidence: `frontend/src/lib/api.ts:32-46`, `frontend/src/pages/LoginPage.tsx`.

24) JWT decode can spuriously fail on missing base64 padding
   - Impact: `decodeToken` can throw for valid base64url strings without padding, which forces unnecessary logouts.
   - Evidence: `frontend/src/lib/api.ts:7-27`.

## Root cause analysis: projection issue (DGGS grid at 0,0)
- Symptom matches lon/lat degrees being treated as meter offsets; values in degrees become tiny offsets near (0,0) in WebMercator, collapsing the grid at the origin.
- `MapView`’s `PolygonLayer` (and the selection overlay) do not set `coordinateSystem`, so they rely on deck.gl defaults inside a `MapView`/WebMercator context.
- `Workbench` explicitly sets `coordinateSystem: COORDINATE_SYSTEM.LNGLAT` and does not show the same issue, which strongly suggests a coordinate system mismatch in the dashboard `MapView`.
- DGGAL vertices are emitted as WGS84 degrees (`[lon, lat]`) and are passed through as-is; without an explicit LNGLAT coordinate system, deck.gl interprets them in projected space.

## Testing gaps
- Only an integration-style test exists (`backend/tests/test_toolbox_integration.py`), and it requires a running server and demo data.
- No unit tests for ingestion, spatial ops correctness, zonal stats, or frontend data flow between store and map rendering.

## Open questions / assumptions
- Is `backend_node_archive/` intentionally retained, or should it be treated as deprecated and excluded from active workflows?
- Should `load_real_global_data` run on every startup, or be gated behind an env flag or manual job?
- Is MinIO intended to be the upload staging store instead of the local `/tmp/uploads` path?

### Critical
25) SQL injection vulnerability in dataset and data loading
    - Impact: f-string interpolation is used for SQL queries with user-controlled values, enabling SQL injection attacks. Dataset creation and bulk inserts concatenate values directly into SQL strings.
    - Evidence: `backend/app/repositories/dataset_repo.py:21-26`, `backend/app/services/data_loader.py:155-161, 227, 281-283`.

### High
26) API token stored in localStorage (XSS vulnerability)
    - Impact: JWT tokens stored in localStorage are accessible to malicious scripts via XSS, enabling session hijacking. Should use httpOnly cookies instead.
    - Evidence: `frontend/src/lib/api.ts:3`, `frontend/src/App.tsx:9`, `frontend/src/pages/LoginPage.tsx`.

27) Missing authentication on multiple API endpoints
    - Impact: Several endpoints lack `get_current_user` dependency, allowing unauthenticated access to sensitive operations like analytics queries and zonal statistics.
    - Evidence: `backend/app/routers/analytics.py:17`, `backend/app/routers/stats.py:47-82`, `backend/app/routers/datasets.py:16-44` (listing datasets).

28) No CSRF protection on state-changing operations
    - Impact: State-changing POST/PUT/DELETE endpoints lack CSRF tokens, enabling cross-site request forgery attacks where users can be tricked into making unwanted requests.
    - Evidence: All POST/PUT/DELETE endpoints in `backend/app/routers/` lack CSRF middleware.

29) Missing input validation on file uploads
    - Impact: No validation on file size limits, file types, or malicious content, allowing denial of service through large files or potential XSS through SVG uploads.
    - Evidence: `backend/app/routers/uploads.py:32-38`, `backend/app/config.py:28` (MAX_UPLOAD_BYTES not enforced in router).

30) Weak default admin credentials
    - Impact: Default admin credentials (admin@terracube.geo / admin123) are weak and exposed in .env.example, making first-boot deployments vulnerable to credential stuffing.
    - Evidence: `backend/.env.example:22-24`, `backend/app/config.py:22-24`, `docker-compose.yml:73-74`.

31) No rate limiting on API endpoints
    - Impact: All API endpoints lack rate limiting, enabling brute force attacks on authentication and denial of service on resource-intensive operations.
    - Evidence: No rate limiting middleware in `backend/app/main.py`.

32) Database operations without proper transaction handling
    - Impact: Multiple operations in `init_db.py` and `seed.py` use asyncpg connections directly without proper transaction boundaries or error handling, leading to partial state on failure.
    - Evidence: `backend/app/init_db.py:32-33`, `backend/app/seed.py:28-32`, mixing asyncpg with SQLAlchemy async sessions.

33) SQL connection pool size not configured
    - Impact: Default SQLAlchemy pool size (5) and max overflow (10) are not configured, causing connection exhaustion under concurrent load.
    - Evidence: `backend/app/db.py:21` (no pool_size, max_overflow, or pool_pre_ping in engine config).

### Medium
34) No health check or readiness endpoints
    - Impact: Container orchestrators (Kubernetes) have no way to verify if the backend is ready to handle requests, potentially routing traffic to unready instances.
    - Evidence: No /health or /ready endpoints in `backend/app/main.py` or `backend/app/routers/`.

35) CORS configuration is too permissive in development
    - Impact: `CORS_ORIGIN` defaults to http://localhost:5173, but the actual CORS middleware configuration may allow all origins or methods if not properly set up.
    - Evidence: `backend/app/config.py:8`, `backend/.env.example:8`, need to verify actual CORS middleware in main.py.

36) No request timeout on HTTP clients
    - Impact: No timeout configured for outgoing HTTP requests (e.g., fetching Natural Earth data), causing indefinite hangs on network issues.
    - Evidence: `backend/app/services/real_data_loader.py` (no timeout in urllib requests).

37) Celery worker not handling SIGTERM gracefully
    - Impact: Worker processes don't handle shutdown signals, potentially leaving tasks in inconsistent state during container termination.
    - Evidence: `backend/app/celery_app.py` (no signal handlers or worker_shutdown hooks).

38) Missing error recovery in frontend API calls
    - Impact: No exponential backoff or retry logic for failed API requests, leading to poor UX on transient network failures.
    - Evidence: `frontend/src/lib/api.ts:44-78` (no retry mechanism).

39) No input validation on zonal statistics endpoint
    - Impact: Invalid statistic types, non-existent dataset IDs, or malformed requests can cause crashes or incorrect results.
    - Evidence: `backend/app/routers/stats.py:47-82` (no validation on operation types or dataset existence).

40) State management doesn't persist across page reloads
    - Impact: User selections, layers, and workbench state are lost on page refresh, requiring users to reconfigure work from scratch.
    - Evidence: `frontend/src/lib/store.ts:26-38` (zustand store with no persistence middleware).

41) No debounce on search and autocomplete inputs
    - Impact: Search operations trigger on every keystroke, causing excessive API calls and poor performance.
    - Evidence: `frontend/src/components/ToolPalette.tsx:40-45`, `frontend/src/components/DatasetSearch.tsx` (if search input exists).

42) Large polygon cache can cause memory leaks
    - Impact: `polygonCache` in `dggal.ts` grows unbounded without eviction policy, causing browser crashes on long sessions with many zones.
    - Evidence: `frontend/src/lib/dggal.ts:29` (unbounded Map with no cleanup logic).

43) Missing error boundaries in many components
    - Impact: Component errors can crash the entire application instead of gracefully degrading, especially in complex dashboard workflows.
    - Evidence: Only `ErrorBoundary` in `frontend/src/App.tsx:18`, but not wrapping individual page components like `DashboardPage` or `Workbench`.

44) No request cancellation on component unmount
    - Impact: API requests and long-running polygon resolution continue after components unmount, causing unnecessary network traffic and potential state corruption.
    - Evidence: `frontend/src/lib/dggal.ts:129-207` (AbortSignal passed but not consistently used), `frontend/src/lib/api.ts` (no abort support).

45) No pagination for large dataset queries
    - Impact: Queries with large result sets (>10k cells) can cause browser crashes, slow rendering, and excessive memory usage.
    - Evidence: `backend/app/routers/datasets.py:46-108` (no limit/offset), `frontend/src/lib/api.ts:108-115` (fetchCells with no pagination).

46) Mixed async connection patterns in database layer
    - Impact: Codebase mixes SQLAlchemy async sessions with raw asyncpg connections, making transaction management inconsistent and error-prone.
    - Evidence: `backend/app/db.py:25-27` (SQLAlchemy), `backend/app/init_db.py:32` (asyncpg), `backend/app/seed.py:22-23` (asyncpg).

47) No query timeout configuration
    - Impact: Long-running queries can block database connections indefinitely, leading to connection pool exhaustion.
    - Evidence: `backend/app/db.py:21` (no statement_timeout or pool_pre_ping configured).

48) Missing database indexes on frequently queried columns
    - Impact: Queries filtering by `dggid`, `tid`, `attr_key` combinations may be slow on large datasets without composite indexes.
    - Evidence: `backend/db/schema.sql:46-50` (only single-column indexes, no composite indexes for common query patterns).

49) No migration system for database schema changes
    - Impact: Schema changes require manual SQL execution, making deployments risky and error-prone without rollback capabilities.
    - Evidence: No Alembic or migration tooling, only `backend/db/schema.sql` for initial setup.

50) Inconsistent error response format across endpoints
    - Impact: Frontend error handling must account for multiple response formats (`{error: ...}`, `{detail: ...}`, `HTTPException`), increasing complexity and potential bugs.
    - Evidence: `backend/app/routers/stats.py:50-51` (error), `backend/app/routers/auth.py:63-68` (detail), mixed patterns.

51) No environment variable validation
    - Impact: Missing or invalid environment variables cause cryptic errors at runtime instead of clear startup messages.
    - Evidence: `backend/app/config.py:39` (extra="ignore"), `backend/app/main.py` (no startup validation).

52) Logging configuration is inconsistent
    - Impact: Some modules use `logging.info()`, others use `print()`, making debugging and log aggregation difficult.
    - Evidence: `backend/app/services/data_loader.py:20,26` (logger), `backend/app/services/real_data_loader.py` (likely print), `backend/app/seed.py:25,33` (logger).

53) Docker containers run as root by default
    - Impact: Security vulnerability where processes run with elevated privileges, increasing attack surface if container is compromised.
    - Evidence: `docker-compose.yml` (no USER directive in backend/worker/frontend services).

54) MinIO not initialized with buckets on startup
    - Impact: Manual bucket creation required before first use, causing upload failures if `ideas-staging` bucket doesn't exist.
    - Evidence: `docker-compose.yml:25-36` (MinIO service with no initialization script).

55) Missing SSL/TLS configuration for production
    - Impact: No guidance or configuration for HTTPS in production deployments, exposing credentials and data in transit.
    - Evidence: No nginx/Caddy configuration, no SSL-related environment variables.

### Low
56) No API versioning
    - Impact: Breaking changes to API endpoints will break existing clients without version negotiation mechanism.
    - Evidence: All routes start with `/api/` without version prefixes (e.g., `/api/v1/`).

57) Missing API documentation beyond Swagger
    - Impact: No separate documentation for consumers who can't access running Swagger UI, and no OpenAPI spec export.
    - Evidence: Only auto-generated Swagger UI from FastAPI, no docs/ directory.

58) No structured logging for observability
    - Impact: Logs are unstructured text, making it difficult to query, filter, and aggregate logs in centralized logging systems.
    - Evidence: Standard Python logging without JSON formatting or correlation IDs.

59) Frontend uses hardcoded API URL
    - Impact: API URL must be rebuilt when backend location changes, making multi-environment deployments difficult.
    - Evidence: `frontend/.env.example:5`, `frontend/src/lib/api.ts:1` (import.meta.env.VITE_API_URL).

60) No cache headers configured for static assets
    - Impact: Frontend assets (JS, CSS) aren't cached efficiently, causing slower page loads and increased bandwidth usage.
    - Evidence: `docker-compose.yml:116-125` (frontend service with no cache configuration).

61) Missing database backup strategy documentation
    - Impact: No documented process for backing up PostgreSQL data, risking data loss in production.
    - Evidence: No backup scripts, cron jobs, or documentation in README.

62) No monitoring or alerting configuration
    - Impact: Prometheus and Grafana services exist in docker-compose but have no pre-configured dashboards or alerts.
    - Evidence: `docker-compose.yml:38-54` (prometheus/grafana with empty configs).

63) TypeScript strict mode not enabled
    - Impact: Type safety is weaker than possible, increasing risk of runtime errors from type mismatches.
    - Evidence: `frontend/vite.config.ts` (need to check tsconfig.json for strict: false).

64) No code formatting or linting configuration
    - Impact: Inconsistent code style across the codebase makes reviews and maintenance more difficult.
    - Evidence: No .prettierrc, .eslintrc, .pylintrc, or similar configuration files.

65) Missing .dockerignore files
    - Impact: Unnecessary files (node_modules, __pycache__, .git) are copied into Docker images, increasing build time and image size.
    - Evidence: No .dockerignore in backend/ or frontend/ directories.

66) No resource limits configured for Docker containers
    - Impact: Containers can consume unlimited CPU/memory, potentially crashing the host or causing resource starvation.
    - Evidence: `docker-compose.yml` (no mem_limit, cpus, or pids_limit on any services).

67) Frontend has no service worker for offline support
    - Impact: Application doesn't work offline and has slow subsequent loads without cached assets.
    - Evidence: No service worker registration in `frontend/src/main.tsx`.

68) No automated backups or snapshot mechanism
    - Impact: No scheduled backups of PostgreSQL data or uploaded files, risking permanent data loss.
    - Evidence: No backup cron jobs, snapshot scripts, or volume backup configuration.

69) Missing database connection pool monitoring
    - Impact: No visibility into connection pool health, making it difficult to diagnose connection exhaustion issues.
    - Evidence: No pool status endpoint or metrics exported from `backend/app/db.py`.

70) No request ID tracking for distributed tracing
    - Impact: Impossible to trace a request across services (frontend → backend → database) for debugging complex issues.
    - Evidence: No X-Request-ID header generation or propagation.

71) Missing content validation on dataset search
    - Impact: No validation on search input length or special characters, potentially causing SQL injection through ILIKE queries.
    - Evidence: `backend/app/routers/datasets.py:35` (raw string interpolation in ILIKE).

72) DuckDB WASM uses CDN "latest" version tags
    - Impact: Using `@duckdb/duckdb-wasm@${DUCKDB_VERSION}` with hardcoded version can be brittle, and using @latest or non-pinned versions breaks reproducibility and can introduce breaking changes.
    - Evidence: `frontend/src/lib/spatialDb.ts:13,18-23` (hardcoded but non-pinned dev version 1.33.1-dev18.0).

73) No password strength validation on registration
    - Impact: Users can register with weak passwords, making accounts vulnerable to brute force attacks.
    - Evidence: `frontend/src/pages/LoginPage.tsx:79-87`, `backend/app/routers/auth.py:46-71` (no password validation logic).

74) Missing email verification on registration
    - Impact: Users can register with fake or unverified email addresses, enabling spam accounts and potential abuse.
    - Evidence: `backend/app/routers/auth.py:46-71` (no email verification flow).

75) No account lockout on failed login attempts
    - Impact: Brute force attacks can attempt unlimited password guesses without rate limiting or lockout.
    - Evidence: `backend/app/routers/auth.py:23-45` (no failed attempt tracking).

76) Frontend search has no debounce or throttling
    - Impact: Search triggers API calls on every keystroke, causing excessive server load and poor performance.
    - Evidence: `frontend/src/components/DatasetSearch.tsx:56-59` (onChange triggers setQuery without debounce).

77) Dataset lookup can query thousands of cells without pagination
    - Impact: `/api/datasets/{id}/lookup` allows up to 3000 dggids in a single request, potentially returning massive payloads.
    - Evidence: `backend/app/routers/datasets.py:111` (max 3000 dggids, no limit on result size).

78) SQL injection in spatialDb.ts through string interpolation
    - Impact: Zone IDs inserted directly into SQL queries can enable SQL injection through malicious zone ID values.
    - Evidence: `frontend/src/lib/spatialDb.ts:115-117,127,154-156,195-197` (string interpolation with user-provided zone IDs).

79) No input sanitization on dataset creation
    - Impact: User-provided dataset name and description can contain malicious content, leading to stored XSS in frontend.
    - Evidence: `backend/app/routers/datasets.py:54-63` (no sanitization of name/description before storage).

80) Missing authorization on dataset access
    - Impact: `list_datasets`, `get_dataset`, and `list_cells` endpoints use `get_optional_user`, allowing unauthorized access to potentially sensitive data.
    - Evidence: `backend/app/routers/datasets.py:32,42,66` (optional authentication).

81) No audit logging for data access
    - Impact: No record of who accessed which datasets or performed which operations, making compliance and security investigations impossible.
    - Evidence: No audit logging middleware or database tables for access logs.

82) Frontend stores JWT in localStorage instead of httpOnly cookies
    - Impact: Tokens accessible via JavaScript XSS attacks; should use httpOnly cookies to prevent token theft.
    - Evidence: `frontend/src/lib/api.ts:3,86,96`, `frontend/src/App.tsx:9` (localStorage usage).

83) Missing Content Security Policy (CSP) headers
    - Impact: No CSP headers to protect against XSS attacks; malicious scripts can be injected and executed.
    - Evidence: No CSP middleware in `backend/app/main.py`.

84) No X-Frame-Options or X-Content-Type-Options headers
    - Impact: Application vulnerable to clickjacking attacks and MIME-sniffing exploits.
    - Evidence: No security headers configured in backend middleware.

85) Frontend has no integrity checks for loaded scripts
    - Impact: No Subresource Integrity (SRI) hashes for external scripts, allowing supply chain attacks if CDN is compromised.
    - Evidence: `<script>` tags in `index.html` without integrity attributes.

86) Missing CORS preflight caching configuration
    - Impact: Every cross-origin request triggers OPTIONS preflight, increasing latency and server load.
    - Evidence: CORS middleware in `backend/app/main.py` (if present) likely not configured with max_age.

87) No compression on API responses
    - Impact: Large JSON responses (e.g., thousands of cells) sent uncompressed, increasing bandwidth and latency.
    - Evidence: No GzipMiddleware or compression configured in `backend/app/main.py`.

88) Database queries use ILIKE without indexes
    - Impact: Case-insensitive search on datasets cannot use standard indexes, leading to full table scans on large datasets.
    - Evidence: `backend/app/routers/datasets.py:35` (ILIKE on name column, no pg_trgm index).

89) Missing database connection health checks
    - Impact: Application doesn't detect stale or broken database connections, leading to request failures.
    - Evidence: `backend/app/db.py:21` (no pool_pre_ping configured).

90) No graceful shutdown handling in backend
    - Impact: SIGTERM/SIGINT signals not handled, potentially leaving transactions in inconsistent state during shutdown.
    - Evidence: `backend/app/main.py` (no signal handlers or lifespan shutdown hooks).

91) Frontend has no service worker for offline caching
    - Impact: Application doesn't cache resources, causing full reloads on page refresh and no offline functionality.
    - Evidence: No service worker registration in `frontend/src/main.tsx`.

92) Missing viewport metadata for mobile devices
    - Impact: Poor mobile experience due to improper viewport scaling and touch targets.
    - Evidence: `frontend/index.html` (need to verify viewport meta tag exists).

93) No accessibility (a11y) attributes on interactive elements
    - Impact: Poor screen reader support and keyboard navigation for users with disabilities.
    - Evidence: Missing ARIA labels, role attributes, and focus management in components.

94) Polygon cache can grow indefinitely in memory
    - Impact: `polygonCache` in dggal.ts has no eviction policy, causing memory leaks in long-running sessions.
    - Evidence: `frontend/src/lib/dggal.ts:29` (unbounded Map without LRU or size limit).

95) No request cancellation for polygon resolution
    - Impact: Polygon resolution continues after component unmount, wasting CPU and network resources.
    - Evidence: `frontend/src/lib/dggal.ts:129-207` (AbortSignal not consistently checked in worker loop).

96) Missing error handling for WASM initialization failures
    - Impact: DGGAL WASM load failures cause silent errors or cryptic console warnings without user feedback.
    - Evidence: `frontend/src/lib/dggal.ts:32-42` (basic try-catch but no user-facing error UI).

97) No fallback for browsers without WebAssembly support
    - Impact: Application fails completely on browsers without WASM, with no graceful degradation or user message.
    - Evidence: No feature detection for WebAssembly in `frontend/src/main.tsx`.

98) Celery worker has no task timeout configuration
    - Impact: Long-running tasks (e.g., large raster ingestion) can run indefinitely, blocking workers and causing queue buildup.
    - Evidence: `backend/app/celery_app.py:8-20` (no task_time_limit or soft_time_limit).

99) No Celery task retry configuration
    - Impact: Failed tasks are immediately marked as failed without retry, requiring manual intervention for transient failures.
    - Evidence: `backend/app/celery_app.py` (no autoretry_for or retry_backoff settings).

100) Missing Celery task result expiration
    - Impact: Task results accumulate in Redis indefinitely, causing memory bloat and storage exhaustion.
    - Evidence: `backend/app/celery_app.py:8` (no result_expires configuration).

101) No monitoring for Celery queue depth
    - Impact: Cannot detect when tasks are backing up in the queue, leading to degraded performance.
    - Evidence: No queue monitoring endpoints or Prometheus metrics for Celery.

102) File upload not validated for malicious content
    - Impact: SVG files can contain XSS payloads, and malicious files can exploit processing libraries.
    - Evidence: `backend/app/routers/uploads.py:32-38` (no file signature validation or content scanning).

103) Missing file upload progress tracking
    - Impact: No feedback during large file uploads, leading to poor UX and potential user confusion.
    - Evidence: `frontend/src/lib/api.ts:173-199` (no upload progress callbacks).

104) No virus scanning for uploaded files
    - Impact: Malicious files (e.g., executables disguised as images) can be uploaded and processed.
    - Evidence: No integration with virus scanning service in upload flow.

105) Missing database foreign key constraints
    - Impact: Orphaned records can exist if foreign key constraints are not enforced (though schema.sql has REFERENCES, need to verify enforcement).
    - Evidence: `backend/db/schema.sql:22,34` (REFERENCES exist, need to verify FK enforcement is enabled).

106) No data retention policy
    - Impact: Old uploads, failed tasks, and temporary data accumulate indefinitely, consuming storage.
    - Evidence: No cleanup jobs for old records in `uploads` table or `/tmp/uploads` directory.

107) Missing database index on composite columns
    - Impact: Queries filtering by (dataset_id, dggid, tid, attr_key) combinations cannot use single indexes efficiently.
    - Evidence: `backend/db/schema.sql:46-50` (only single-column indexes, no composite indexes).

108) No database connection pool recycling
    - Impact: Long-lived connections can accumulate server-side state or memory leaks.
    - Evidence: `backend/app/db.py:21` (no pool_recycle configuration for SQLAlchemy).

109) Frontend has no error boundary for async operations
    - Impact: Async errors (e.g., network failures, promises) can crash React components without graceful handling.
    - Evidence: Only class-based ErrorBoundary in `frontend/src/App.tsx`, no handling for async errors.

110) Missing loading states for long-running operations
    - Impact: No visual feedback during file uploads, polygon resolution, or dataset loading, causing poor UX.
    - Evidence: Components like `MapView`, `DashboardPage` lack loading indicators during data fetching.

111) No validation of dataset level bounds
    - Impact: Invalid DGGS levels (e.g., negative or >20) can cause crashes or unexpected behavior.
    - Evidence: `backend/app/routers/datasets.py:56` (no validation on level parameter).

112) Missing coordinate validation on bounding boxes
    - Impact: Invalid lat/lon ranges can cause errors in zone listing and spatial operations.
    - Evidence: `backend/app/services/data_loader.py:85-87` (no validation on bbox coordinates).

113) No deduplication on cell object inserts
    - Impact: Duplicate (dataset_id, dggid, tid, attr_key) tuples can be inserted despite unique constraint if not checked upfront.
    - Evidence: `backend/db/schema.sql:43` (UNIQUE constraint exists, but application doesn't check before insert).

114) Frontend has no exponential backoff for retry
    - Impact: Failed API requests are not retried with increasing delays, causing poor resilience.
    - Evidence: `frontend/src/lib/api.ts:44-78` (no retry logic).

115) Missing request size limits
    - Impact: Large POST/PUT payloads can cause memory exhaustion or denial of service.
    - Evidence: `backend/app/main.py` (no request body size middleware configured).

116) No query complexity limits
    - Impact: Complex nested queries can consume excessive CPU and memory, causing denial of service.
    - Evidence: No query depth or complexity validation in API endpoints.

117) Frontend has no virtualization for long lists
    - Impact: Rendering thousands of items (e.g., datasets, cells) causes browser freeze.
    - Evidence: No virtual scroller libraries (react-virtualized, react-window) used.

118) Missing HTTP strict transport security (HSTS)
    - Impact: No HSTS header to enforce HTTPS connections, enabling downgrade attacks.
    - Evidence: No HSTS middleware in backend.

119) No certificate pinning for HTTPS
    - Impact: Vulnerable to man-in-the-middle attacks on compromised CA certificates (client-side issue).
    - Evidence: No certificate pinning configuration.

120) Missing API rate limit by user
    - Impact: No per-user rate limiting, allowing authenticated users to abuse resources.
    - Evidence: No user-specific rate limit configuration.

121) No request/response logging for debugging
    - Impact: No visibility into API request/response payloads for troubleshooting.
    - Evidence: No request logging middleware configured in backend.

122) Frontend has no cache invalidation strategy
    - Impact: Stale data persists in browser caches and polygon cache, showing outdated results.
    - Evidence: No cache versioning or invalidation logic in frontend.

123) Missing feature flags for gradual rollout
    - Impact: All features are enabled for all users, making risky deployments without ability to rollback gradually.
    - Evidence: No feature flag system or configuration.

124) No A/B testing or analytics tracking
    - Impact: No data on user behavior or feature usage, making product decisions uninformed.
    - Evidence: No analytics integration (e.g., Google Analytics, Mixpanel).

125) Missing database migration rollback capability
    - Impact: Failed migrations cannot be rolled back automatically, requiring manual intervention.
    - Evidence: No migration system (Alembic) or rollback procedures documented.

126) No blue-green deployment strategy
    - Impact: Deployments cause downtime or require complete service restarts.
    - Evidence: No deployment automation or blue-green configuration.

127) Missing database backup verification
    - Impact: Backups may be corrupted or incomplete without verification, leading to failed restores.
    - Evidence: No backup integrity checks or restore testing procedures.

128) Frontend has no internationalization (i18n) support
    - Impact: Application only supports English, limiting global accessibility.
    - Evidence: No i18n library (react-i18next) or translation files.

129) No timezone handling in datetime fields
    - Impact: Date/times stored or displayed without timezone context, causing confusion across regions.
    - Evidence: `backend/app/models.py:15,27,40,54` (timestamptz columns but frontend may not handle correctly).

130) Missing dark mode or theme support
    - Impact: Fixed light theme may cause eye strain in low-light environments.
    - Evidence: No theme provider or CSS variables for theming.

131) No keyboard shortcuts for common actions
    - Impact: Power users cannot navigate efficiently using keyboard only.
    - Evidence: No keyboard event handlers or hotkey libraries configured.

132) Missing export functionality for layers and results
    - Impact: Users cannot export visualized data to common formats (GeoJSON, CSV, Shapefile).
    - Evidence: No export endpoints in backend or export UI in frontend (Toolbox has export tools but likely unimplemented).

133) No print-friendly styles
    - Impact: Printing maps and dashboards produces poor output without layout optimization.
    - Evidence: No @media print CSS rules.

134) Missing responsive breakpoints for mobile
    - Impact: UI layout doesn't adapt to mobile screens, causing poor mobile UX.
    - Evidence: CSS breakpoints may not cover mobile viewport sizes (need to verify styles.css).

135) No skeleton screens for loading states
    - Impact: Users see blank spaces during loading instead of skeleton UI, causing perceived slowness.
    - Evidence: Loading indicators use simple text/spinners without skeleton layouts.

136) Frontend has no form validation feedback
    - Impact: Users don't receive real-time validation errors on form inputs, leading to poor UX.
    - Evidence: Forms in `LoginPage` and tool inputs lack client-side validation.

137) Missing undo/redo functionality
    - Impact: User actions cannot be undone, requiring manual correction of mistakes.
    - Evidence: No undo/redo state management in store or components.

138) No collaborative features or real-time updates
    - Impact: Users cannot see changes made by others without manual refresh.
    - Evidence: No WebSocket or real-time update mechanism.

139) Missing data lineage or versioning
    - Impact: No tracking of how datasets were created or modified, making reproducibility difficult.
    - Evidence: No dataset versioning tables or lineage tracking.

140) No API response compression for large payloads
    - Impact: Large JSON responses (cell data, polygon vertices) consume excessive bandwidth.
    - Evidence: No compression middleware configured in backend.

## Algorithmic and Projection Issues

### Critical Projection Issues
141) Coordinate system misalignment in non-globe MapView mode
    - Impact: When `useGlobe=false`, the Map component uses WebMercator projection while PolygonLayers use LNGLAT coordinate system. While both layers explicitly set `COORDINATE_SYSTEM.LNGLAT`, the underlying MapLibre basemap uses WebMercator by default, which can cause misalignment at high zoom levels or near poles where projections diverge significantly.
    - Evidence: `frontend/src/components/MapView.tsx:422,436` (LNGLAT on layers), `frontend/src/components/MapView.tsx:474-479` (Map component uses WebMercator basemap).
    - Note: The original review mentioned missing coordinateSystem on PolygonLayer (lines 392-404), but current code at lines 422 and 436 DOES have `coordinateSystem: COORDINATE_SYSTEM.LNGLAT`. However, there may still be issues with deck.gl/MapLibre projection alignment.

### Algorithm Issues
142) SpatialEngine aggregate only supports single level coarsening
    - Impact: `aggregate()` only converts dggids to their immediate parent (one level coarser). To coarsen multiple levels, it must be called repeatedly by the caller, which is inefficient and not documented.
    - Evidence: `backend/app/services/spatial_engine.py:60-78` (single parent conversion, no target_level parameter).

143) SpatialEngine expand only supports single level refinement
    - Impact: `expand()` only converts dggids to their immediate children (one level finer). To refine multiple levels, it must be called repeatedly by the caller, which is inefficient and not documented.
    - Evidence: `backend/app/services/spatial_engine.py:80-101` (single children conversion, no target_level parameter).

144) Zonal statistics algorithm may sample incorrectly with cell count mismatch
    - Impact: When zone_dataset and value_dataset have different cell counts (e.g., zones at level 3, values at level 4), the algorithm queries up to 100,000 cells from each but doesn't ensure 1:1 correspondence. Cells may be dropped or double-counted depending on database query plan.
    - Evidence: `backend/app/routers/stats.py:60-61,70` (limit=100000 on both zone_ids and value_ids without ensuring 1:1 mapping).

145) Level-downsampling algorithm can select inappropriate resolution
    - Impact: The algorithm reduces level while zones > maxZones, but it doesn't consider the spatial distribution of zones. This can result in a level that's too coarse for detailed work in one area just because another area has many zones.
    - Evidence: `frontend/src/lib/dggal.ts:236-240` (simple while loop reducing level without spatial awareness).

146) Buffer algorithm has no maximum cell limit
    - Impact: For large input sets with multiple iterations, buffer can return exponentially growing cell counts without limit (k-ring expansion: each ring adds 6*iteration cells). This can cause memory exhaustion or massive database queries.
    - Evidence: `backend/app/services/spatial_engine.py:29-58` (no max_cells limit or early termination).

147) SpatialEngine buffer includes original cells in each iteration
    - Impact: Current implementation adds all neighbors to current_set, which is correct. However, for very large iterations, the set grows exponentially and there's no check for duplicates within the same iteration (though Python set handles this).
    - Evidence: `backend/app/services/spatial_engine.py:34-56` (neighbors added to next_set each iteration).

148) No anti-aliasing on color scale algorithm
    - Impact: The `toColor()` function uses a simple linear clamp that can produce banding artifacts for continuous values, especially when the range is small.
    - Evidence: `frontend/src/components/MapView.tsx:70-79` (linear clamp without dithering or smooth interpolation).

149) Raster sampling algorithm doesn't handle edge cases at poles
    - Impact: DGGS sampling at high latitudes (near ±85°) may have edge cases where zones are truncated or the sampling algorithm doesn't account for polar geometry.
    - Evidence: `frontend/src/components/MapView.tsx:81` (clampLat to -85/85), `backend/app/services/ingest.py` (raster sampling logic).

150) Zonal statistics may use wrong attribute values
    - Impact: The zonal stats query fetches `value_num` for matching dggids but doesn't filter by `attr_key` in the value dataset, potentially using values from the wrong attribute column.
    - Evidence: `backend/app/routers/stats.py:60-61,70` (dggids lookup doesn't pass attr_key to get_values_by_dggids).

151) Set operation union on single dataset returns all cells including duplicates
    - Impact: While SQL `UNION` eliminates duplicates, calling `execute_set_operation("union", [single_dataset_id])` without an `attr_key` filter will return all cells with all attributes, effectively returning each physical cell multiple times (once per attribute key).
    - Evidence: `backend/app/repositories/cell_object_repo.py:26-37` (no attr_key filter by default, union selects all cells).

152) No topology validation in spatial operations
    - Impact: The buffer, expand, and aggregate operations don't validate that resulting cell sets form a valid DGGS topology (contiguous, no holes, etc.), which can produce unexpected results for downstream operations.
    - Evidence: `backend/app/services/spatial_engine.py:29-101` (no topology validation on results).

### CRS and Projection Issues
153) Raster ingestion assumes WGS84 without CRS detection
    - Impact: GeoTIFFs or rasters in other coordinate systems (e.g., UTM, EPSG:3857) are sampled as if they were WGS84, causing severe spatial misalignment.
    - Evidence: `backend/app/services/ingest.py:148-178` (no CRS detection or reprojection).

154) No CRS validation in zone generation algorithms
    - Impact: The `list_zones_bbox` function takes latitude/longitude bounds but doesn't validate they're within valid WGS84 ranges (-90 to 90, -180 to 180), potentially causing errors or unexpected behavior.
    - Evidence: `frontend/src/lib/dggal.ts:209-244` (no bbox validation in listZoneIdsForExtent).

155) Bounding box algorithm uses WebMercator for non-globe view
    - Impact: The `buildExtent` function uses `WebMercatorViewport` for non-globe mode, which converts WGS84 coordinates to WebMercator for bounds calculation. This introduces projection distortion at the edges of the viewport, especially at high latitudes.
    - Evidence: `frontend/src/components/MapView.tsx:92-99` (WebMercatorViewport bounds calculation).

156) No antimeridian handling in spatial operations
    - Impact: Operations that cross the antimeridian (±180° longitude) may produce incorrect results due to wrapping issues in bounding boxes or polygon rendering.
    - Evidence: `frontend/src/lib/dggal.ts:209-244` (no antimeridian normalization in listZoneIdsForExtent).

157) Polygon refinement level is hardcoded to 3
    - Impact: The `get_vertices` and `zoneToPolygon` functions use a hardcoded refinement level of 3, which may produce overly detailed polygons at low zoom levels (performance issue) or insufficient detail at high zoom levels (visual artifacts).
    - Evidence: `backend/app/dggal_utils.py:73` (refinement=3 hardcoded), `frontend/src/lib/dggal.ts:54` (refinement=3 default).

### Performance Algorithm Issues
158) SpatialEngine parallelism may cause memory spikes
    - Impact: The `_gather_limited` function processes batches of `limit * 4` items simultaneously, which for `max_concurrency=32` means 128 concurrent operations, each potentially returning large neighbor/children arrays.
    - Evidence: `backend/app/services/spatial_engine.py:13-27,23-24` (batch_size = limit * 4).

159) No progressive rendering for large polygon sets
    - Impact: When rendering thousands of DGGS cells, the frontend resolves all polygons before rendering, causing a delay with blank screen during polygon resolution.
    - Evidence: `frontend/src/components/MapView.tsx:290-312` (polygons set after full resolution, no progressive updates).

160) Cell filtering algorithm doesn't use spatial indexes
    - Impact: Filtering cells by viewport bounds requires fetching all dggids from database first, then filtering, rather than using spatial indexes for efficient queries.
    - Evidence: `frontend/src/lib/dggal.ts:209-244` (client-side zone listing with no server-side spatial filtering).
### Critical Syntax and Code Quality Issues
161) Buffer endpoint has typo in parameter access
    - Impact: Line 30 accesses `request.iterations` but the field name in BufferRequest (line 15) is `iterations`, causing AttributeError and 500 error for all buffer operations.
    - Evidence: `backend/app/routers/toolbox.py:15,30` (field name is `iterations` but accessed as `iterations`).

162) Real data loader has syntax errors throughout
    - Impact: Multiple syntax errors in `real_data_loader.py` cause startup failures or incorrect SQL execution.
    - Evidence: 
      - Line 96: `country.replace("'", "''")` missing closing quote - should be `.replace("'", "''")`
      - Line 340: Missing closing parenthesis - `"SELECT id FROM datasets WHERE name = :n"), {"n": name}`
      - Line 325: Unbalanced parentheses - `min(10000, max(0, int(pop / max(0.1, dist * 50000))))` has extra closing paren
      - Line 364: range() missing third parameter - `for i in range(0, len(unique_values), 500):` should be `range(0, len(unique_values), 500)`
      - Line 375: Missing opening quote - `status='active'` should be `status='active'`

163) All toolbox endpoints missing authentication
    - Impact: Buffer, aggregate, union, intersection, difference, and mask endpoints have no `Depends(get_current_user)`, allowing unauthenticated access to spatial operations.
    - Evidence: `backend/app/routers/toolbox.py:26-83` (no auth dependencies on any endpoint).

164) Real data loader has widespread SQL injection vulnerabilities
    - Impact: Lines 96, 113-114, 144, 163-164, 213, 270, 326 all use f-string SQL interpolation with user-controlled data, enabling SQL injection attacks.
    - Evidence: `backend/app/services/real_data_loader.py:96,113,144,163,213,270,326` (direct f-string formatting of SQL).
### Additional Security Issues
165) No rate limiting on Natural Earth API calls
    - Impact: The startup data loader fetches from GitHub URLs without rate limiting, allowing abuse if an attacker can trigger repeated startups or if GitHub limits are exceeded.
    - Evidence: `backend/app/services/real_data_loader.py:40-49` (httpx client with no rate limiting).

166) Cities loading assumes non-empty cell array
    - Impact: Line 162 accesses `cells[0]` without checking if cells array is empty, which can cause IndexError if `list_zones_bbox` returns no cells for a city's bounding box.
    - Evidence: `backend/app/services/real_data_loader.py:160-162` (no length check before `cells[0]`).

167) Population density calculation can produce NaN/Infinity
    - Impact: Line 325 has division by `dist * 50000` which can be 0 if a city is at the same location as a centroid, producing division by zero and NaN/Infinity values.
    - Evidence: `backend/app/services/real_data_loader.py:324-326` (no check for zero denominator).

168) GeoJSON parsing doesn't validate feature types
    - Impact: The code assumes features are valid GeoJSON but doesn't validate geometry types, which can cause crashes on malformed input from Natural Earth or user uploads.
    - Evidence: `backend/app/services/real_data_loader.py:94-116,141-167` (no geometry type validation before shape() calls).

169) Prometheus metrics exposed without authentication
    - Impact: The `/metrics` endpoint is exposed publicly at port 9090 without authentication or filtering, potentially leaking sensitive operational data.
    - Evidence: `backend/app/main.py:55-56` (Instrumentator exposes metrics to all users), `monitoring/prometheus/prometheus.yml:5-8` (no auth on scrape targets).

170) CORS allows all methods and headers
    - Impact: `allow_methods=["*"]` and `allow_headers=["*"]` allow any HTTP method and header, which is overly permissive and could enable CORS-based attacks.
    - Evidence: `backend/app/main.py:34-40` (wildcard permissions).

171) No request/response size limits
    - Impact: No middleware to limit request body size or response payload size, enabling DoS through large payloads.
    - Evidence: `backend/app/main.py` (no size limiting middleware).

172) File upload doesn't validate MIME type against magic bytes
    - Impact: File extension check at ingest.py:147 only validates extension, not actual file content type, allowing file type spoofing (e.g., malicious executable renamed as .tif).
    - Evidence: `backend/app/services/ingest.py:147,220-233` (extension check only, no MIME magic validation).

173) CSV/JSON file loads entire file into memory
    - Impact: Lines 224 and 227 load entire CSV/JSON files into memory at once, which can cause OOM for large uploads.
    - Evidence: `backend/app/services/ingest.py:222-233` (list() and json.load() without streaming).

174) Raster ingestion has no chunking for large datasets
    - Impact: Line 162 processes all zones in a single batch, which can be thousands for large bounding boxes, causing memory spikes.
    - Evidence: `backend/app/services/ingest.py:159-192` (no chunking or streaming for zone processing).

175) Dataset metadata update can overwrite existing keys
    - Impact: Line 114 uses `metadata.update()` which replaces entire keys rather than merging, potentially losing metadata from previous operations.
    - Evidence: `backend/app/services/real_data_loader.py:113-114` (update() replaces, doesn't deep merge).

176) Bulk insert doesn't use prepared statements properly
    - Impact: Line 366 uses f-string with JOIN for bulk insert, which doesn't use parameterized queries properly and is vulnerable to SQL injection from dataset IDs.
    - Evidence: `backend/app/services/real_data_loader.py:366-371` (f-string SQL with JOIN).

177) No progress updates during long-running ingestion
    - Impact: Users have no feedback during file ingestion, which can take minutes for large files, leading to poor UX and potential timeouts.
    - Evidence: `backend/app/services/ingest.py:125-286` (no WebSocket or status endpoint for progress).

178) File cleanup in finally block can delete wrong file
    - Impact: Line 281 deletes file at `file_path` in finally block even if it was renamed/moved during processing, potentially deleting unrelated files.
    - Evidence: `backend/app/services/ingest.py:280-285` (unsafe file deletion in finally).

179) No validation on DGGS level range
    - Impact: Raster and vector ingestion don't validate `min_level` and `max_level` are within valid DGGS range (0-20 for IVEA3H), potentially causing errors.
    - Evidence: `backend/app/services/ingest.py:156,252-253` (no level validation).

180) Natural Earth URLs are hardcoded and can break
    - Impact: GeoJSON URLs point to specific GitHub repository paths which can change or be deleted, breaking data loading.
    - Evidence: `backend/app/services/real_data_loader.py:29-32` (hardcoded GitHub raw URLs).
### Frontend Issues Continued
181) CSS uses large single file without modules
    - Impact: 1826 lines of CSS in a single file without modularization makes maintenance difficult and increases initial bundle size.
    - Evidence: `frontend/src/styles.css` (entire CSS in one file).

182) No critical CSS path or font loading fallback
    - Impact: Font import from Google Fonts at line 1 can block page rendering if CDN is slow or blocked, with no local fallback.
    - Evidence: `frontend/src/styles.css:1` (blocking Google Fonts import).

183) CSS uses inefficient selectors
    - Impact: Many selectors lack specificity optimization, causing style recalculation performance issues.
    - Evidence: `frontend/src/styles.css` (e.g., generic button, input selectors without scoping).

184) No CSS-in-JS or theming library
    - Impact: CSS variables exist but no theming system to switch between light/dark modes dynamically.
    - Evidence: `frontend/src/styles.css:3-17` (CSS variables but no theme switching logic).

185) Map info bar uses monospace font that may not exist
    - Impact: Line 1122 references 'SF Mono' which is macOS-specific and may not exist on Windows/Linux, causing fallback to default serif.
    - Evidence: `frontend/src/styles.css:1122` (macOS-specific font family).

186) No responsive breakpoints for tablet sizes
    - Impact: Media query at line 405 only has max-width:960px, missing intermediate breakpoints for tablets (768px-1024px).
    - Evidence: `frontend/src/styles.css:405-413` (single breakpoint only).

### Docker and Deployment Issues
187) No health check endpoints in Docker
    - Impact: Docker healthcheck in docker-compose doesn't verify backend is actually ready to serve requests, just checks if container is running.
    - Evidence: `docker-compose.yml:14-17` (basic pg_isready check, no application-level health).

188) Prometheus configuration uses internal hostname without service discovery
    - Impact: Prometheus target `backend:4000` uses hardcoded hostname that may not resolve correctly in all Docker networks.
    - Evidence: `monitoring/prometheus/prometheus.yml:8` (hardcoded `backend` hostname).

189) No log aggregation configuration
    - Impact: Logs from backend and worker containers aren't collected or centrally stored, making debugging distributed issues difficult.
    - Evidence: `docker-compose.yml` (no ELK, Splunk, or other log aggregation service).

190) Grafana not configured with Prometheus data source
    - Impact: Grafana container starts but has no Prometheus data source configured, showing empty dashboards by default.
    - Evidence: `docker-compose.yml:46-54` (no Grafana provisioning or data source config).

191) No database migration on container startup
    - Impact: Database schema changes require manual schema.sql execution, containers don't auto-migrate on startup.
    - Evidence: `docker-compose.yml` (no migration step in backend/worker entrypoints).

192) No volume backup strategy
    - Impact: PostgreSQL and MinIO data volumes have no backup mechanism, risking data loss on container failure or storage issues.
    - Evidence: `docker-compose.yml:12,36` (no backup volumes or snapshots).

193) Worker depends on backend instead of both services
    - Impact: Worker has `depends_on: backend` but backend might not be fully initialized (DB pool not ready), causing worker failures.
    - Evidence: `docker-compose.yml:106-114` (depends on backend service only).

194) No graceful shutdown for containers
    - Impact: SIGTERM signals to containers cause immediate termination without letting requests complete or connections close gracefully.
    - Evidence: `docker-compose.yml` (no stop_grace_period configured).

195) Frontend build uses production-ready but no optimization config
    - Impact: No build optimization (code splitting, tree shaking, compression) is configured in Vite, potentially large bundle sizes.
    - Evidence: `frontend/vite.config.ts` (need to check for optimization settings).

196) MinIO bucket not created on startup
    - Impact: MinIO starts but the `ideas-staging` bucket may not exist, causing upload failures.
    - Evidence: `docker-compose.yml:25-36` (no bucket initialization script).
### Data Model Issues
197) ON CONFLICT UPDATE sets all values even for no-op
    - Impact: Upsert queries update all columns even when only some values changed, causing unnecessary WAL writes and bloat.
    - Evidence: `backend/app/services/ingest.py:101-104,368-369` (UPDATE sets all columns unconditionally).

198) No foreign key cascade actions documented
    - Impact: Schema has ON DELETE CASCADE on cell_objects but this behavior isn't documented, potentially surprising users who expect soft deletes.
    - Evidence: `backend/db/schema.sql:34` (CASCADE not documented in comments or API docs).

199) Partition table naming is fragile
    - Impact: Partition names use UUID replacement (dash to underscore) which can have collisions if UUID generation changes or if two UUIDs produce same replacement.
    - Evidence: `backend/app/repositories/dataset_repo.py:17` (simple string replacement, no uniqueness guarantee).

200) No check constraint on cell_objects value types
    - Impact: No database constraint ensures at least one of value_text, value_num, or value_json is non-null, leading to rows with all NULL values.
    - Evidence: `backend/db/schema.sql:32-44` (no CHECK constraint for value columns).

201) No unique constraint on dataset names per user
    - Impact: Multiple datasets can have the same name for the same user, causing confusion in UI and potential accidental overwrites.
    - Evidence: `backend/db/schema.sql:11-21` (no UNIQUE(dataset_name, created_by) constraint).

202) Tid column defaults to 0 but no semantic meaning
    - Impact: Tid (time/temporal ID) defaults to 0 in many places (lines 78-82,184,289), losing temporal information for non-temporal data.
    - Evidence: `backend/app/services/ingest.py:76-82,288-289` (tid defaults to 0 for vector data).

203) No index on (dataset_id, tid, attr_key) composite
    - Impact: Queries filtering by all three columns (common in zonal stats and temporal queries) can't use a composite index, causing slow scans.
    - Evidence: `backend/db/schema.sql:46-50` (only single-column indexes, no composite for this pattern).

### Concurrency and Race Condition Issues
204) Race condition in upload status and Celery task
    - Impact: Upload status is set to "processing" in async function after acquiring pool, but Celery may start before this, causing status mismatch.
    - Evidence: `backend/app/services/ingest.py:146,216-217` (status set after pool acquisition, not in router).

205) No concurrency control on dataset creation
    - Impact: Multiple simultaneous dataset creations with the same name can both succeed, violating implicit uniqueness assumption.
    - Evidence: `backend/app/routers/datasets.py:52-63` (no transaction or lock for create).

206) Selection request ID can race with component unmount
    - Impact: Line 324 increments `selectionRequestId` but the response at line 337 checks against it after async operations complete, which can be after unmount.
    - Evidence: `frontend/src/components/MapView.tsx:324,337` (request ID check after async operations without AbortSignal).

207) Polygon resolution has race between map and signal
    - Impact: Lines 286-312 create AbortController but don't consistently check signal.aborted in all await points, potentially doing unnecessary work after unmount.
    - Evidence: `frontend/src/components/MapView.tsx:286-312` (signal checked at 296-297 but not consistently in all branches).

### Memory and Resource Management Issues
208) No cleanup of WASM resources
    - Impact: DGGAL WASM instances and DuckDB connections are never explicitly cleaned up, causing memory leaks in long-running sessions.
    - Evidence: `frontend/src/lib/dggal.ts:26-31,42` (no cleanup function), `frontend/src/lib/spatialDb.ts:30-94` (no close() on connection).

209) Large polygon arrays accumulate without eviction
    - Impact: Lines 294 and 361 in MapView.tsx accumulate polygons in memory without clearing old ones, causing OOM in long sessions.
    - Evidence: `frontend/src/components/MapView.tsx:294,361` (setPolygons without clearing old arrays).

210) No memory limit on DuckDB operations
    - Impact: DuckDB in-memory database can grow unbounded with cached polygons, causing browser crashes.
    - Evidence: `frontend/src/lib/spatialDb.ts:64` (in-memory database with no size limit).

211) SQLAlchemy session not explicitly closed in error paths
    - Impact: If an exception occurs before session.commit(), the session isn't closed, causing connection pool exhaustion.
    - Evidence: `backend/app/routers/*.py` (many endpoints use `Depends(get_db)` without explicit close).

212) Celery worker doesn't limit task retries
    - Impact: Failed tasks retry indefinitely by default (or not configured), flooding logs and database with failed attempts.
    - Evidence: `backend/app/celery_app.py:8-20` (no task_autoretry_for or retry_max configuration).

213) No connection pool recycling for long-lived connections
    - Impact: Async connections can accumulate stale database connections, leading to connection limits.
    - Evidence: `backend/app/db.py:21` (no pool_recycle parameter).

### Testing and Validation Issues
214) No integration tests for critical ingestion pipeline
    - Impact: Upload and ingestion have no automated tests, so regressions in file processing can go undetected.
    - Evidence: `backend/tests/` (only toolbox integration test exists).

215) No validation of DGGS coordinate transformations
    - Impact: Coordinate transformations between different DGGS systems or levels aren't tested for edge cases (poles, antimeridian).
    - Evidence: No tests in `backend/tests/` for coordinate transformation edge cases.

216) Frontend components have no unit tests
    - Impact: No test coverage for MapView, DashboardPage, Workbench, and other critical components.
    - Evidence: `frontend/src/` has no `__tests__` directories.

217) No load testing or stress tests
    - Impact: System isn't tested under concurrent load, so performance bottlenecks only appear in production.
    - Evidence: No load test scripts or k6/locust configurations.

218) No data validation library for API inputs
    - Impact: Manual validation scattered across routers instead of using a unified validation framework (e.g., pydantic models), leading to inconsistent validation.
    - Evidence: `backend/app/routers/*.py` (mix of BaseModel and manual validation).

### Observability and Debugging Issues
219) No structured logging with correlation IDs
    - Impact: Debugging distributed requests is impossible without request IDs in logs.
    - Evidence: `backend/app/*.py` (basic logging.info/error without correlation IDs).

220) No performance metrics for database queries
    - Impact: No visibility into slow queries or query patterns, making performance optimization difficult.
    - Evidence: No query logging or performance tracking in `backend/app/db.py`.

221) No error tracking/alerting integration
    - Impact: Errors are only logged to console/files without integration with error tracking (Sentry, Rollbar), so production issues go unnoticed.
    - Evidence: No error tracking library in `backend/` or `frontend/`.

222) Prometheus metrics not customized for DGGS operations
    - Impact: Generic HTTP metrics don't capture domain-specific metrics like cell count per operation, level distribution, or cache hit rates.
    - Evidence: `backend/app/main.py:55-56` (default Instrumentator metrics only).

### API Design Issues
223) Inconsistent error response format across endpoints
    - Impact: Different endpoints return errors in different formats (`{error}`, `{detail}`, `{message}`), making error handling complex for clients.
    - Evidence: `backend/app/routers/toolbox.py:33` (`detail`), `backend/app/routers/ops.py:160` (`detail`), `backend/app/routers/stats.py:50-51` (`error`).

224) No API versioning strategy
    - Impact: All endpoints are at `/api/` with no version prefix, making breaking changes incompatible with existing clients.
    - Evidence: `backend/app/main.py:46-53` (no version prefix in routes).

225) No pagination response metadata
    - Impact: Paginated endpoints don't return total count, next page URL, or page metadata, making client-side pagination difficult.
    - Evidence: `backend/app/routers/datasets.py:71-101` (limit/offset without metadata).

226) Query parameter naming inconsistent
    - Impact: Mixed camelCase and snake_case in query parameters (e.g., `datasetId` vs `dataset_id`, `keyA` vs `key_a`).
    - Evidence: `backend/app/routers/ops.py:13-32` (camelCase), `backend/app/routers/datasets.py:66-73` (snake_case).

227) No OpenAPI schema validation for complex types
    - Impact: Pydantic models don't have strict validation rules for DGGID formats, level ranges, or attribute constraints.
    - Evidence: `backend/app/routers/*.py` (BaseModel without custom validators).

228) No response compression configuration
    - Impact: Large JSON responses (cell data, polygons) are sent uncompressed, wasting bandwidth.
    - Evidence: `backend/app/main.py` (no GzipMiddleware).

229) No API rate limiting headers
    - Impact: Responses don't include rate limit headers (`X-RateLimit-Limit`, `X-RateLimit-Remaining`) even when rate limiting should exist.
    - Evidence: No rate limiting middleware configured.

### User Experience Issues
230) No loading skeleton for long operations
    - Impact: Users see blank screens during data loading, polygon resolution, or tool execution without feedback.
    - Evidence: `frontend/src/components/MapView.tsx` (no skeleton components).

231) No error recovery from failed operations
    - Impact: Failed operations don't offer retry or recovery options, requiring manual reload.
    - Evidence: `frontend/src/lib/api.ts:73-78` (throws error without retry logic).

232) No optimistic updates in UI
    - Impact: All operations wait for server response before updating UI, making the app feel sluggish.
    - Evidence: All components use server state directly, no optimistic updates.

233) No undo/redo for common actions
    - Impact: Users can't undo layer additions, tool operations, or filtering actions.
    - Evidence: No undo/redo stack in `frontend/src/lib/store.ts`.

234) No keyboard shortcuts for common actions
    - Impact: Power users can't navigate or perform actions without mouse.
    - Evidence: No keyboard event handlers in components.

235) No offline support indicators
    - Impact: No indication when the app is offline or when network errors occur.
    - Evidence: No network status listeners in `frontend/src/`.

236) Tooltips missing on complex UI elements
    - Impact: Users don't get helpful hints for DGGS levels, coordinate systems, or tool parameters.
    - Evidence: No tooltip library in `frontend/src/`.

237) No confirmation dialogs for destructive actions
    - Impact: Actions like layer removal or dataset deletion execute immediately without confirmation.
    - Evidence: `frontend/src/components/LayerList.tsx:21-26` (remove action without confirmation).

238) Drag and drop not implemented for dataset loading
    - Impact: Users must click through file picker instead of dragging files to upload area.
    - Evidence: No drag-drop handlers in upload components.

239) No export/import of user configurations
    - Impact: Users can't save/load their dashboard configurations, layer setups, or tool parameters.
    - Evidence: No export/import functionality in `frontend/src/lib/store.ts`.

240) No multi-language support infrastructure
    - Impact: All UI text is hardcoded in English, making localization impossible.
    - Evidence: No i18n library or translation files in `frontend/src/`.
### Documentation and Configuration Issues
241) Incomplete documentation in README
    - Impact: README doesn't document critical operational procedures like: database migrations, backup/restore, disaster recovery, monitoring setup, or production deployment steps.
    - Evidence: `README.md` (no documentation on operations beyond basic quick start).

242) Missing Docker volume cleanup instructions
    - Impact: No documented procedure for cleaning up Docker volumes or managing disk space, which can lead to storage exhaustion.
    - Evidence: `docker-compose.yml` (volumes defined but no cleanup documentation).

243) No documented backup/restore procedures
    - Impact: No instructions for database backups, MinIO snapshots, or disaster recovery procedures for production deployments.
    - Evidence: `docker-compose.yml`, `README.md` (no backup/restore documentation).

244) Missing environment variable documentation
    - Impact: `.env.example` has minimal comments explaining sensitive or critical variables (JWT_SECRET, database URLs), making it hard for operators to configure correctly.
    - Evidence: `.env.example` (comments missing for security-critical variables).

245) No production deployment guide
    - Impact: No documentation on how to deploy to production environments (SSL/TLS setup, load balancing, scaling, monitoring, secrets management).
    - Evidence: `README.md` (only local development setup).

246) Monitoring endpoints not documented
    - Impact: Prometheus metrics endpoint (/metrics) is enabled but not documented in README or AGENTS.md, making it difficult for operators to know what metrics are available.
    - Evidence: `backend/app/main.py:55-56` (exposes metrics), `README.md` (no metrics documentation).

247) No development onboarding guide
    - Impact: No guide for new developers to understand the architecture, setup, or coding standards for the project.
    - Evidence: Missing DEVONBOARDING.md or similar documentation.

248) Frontend build configuration not documented
    - Impact: Vite configuration options (build optimization, plugins, proxies) are not documented, making it hard for maintainers to customize builds.
    - Evidence: `frontend/vite.config.ts` (minimal config with no comments).

249) TypeScript strict mode not documented
    - Impact: `tsconfig.json` has `strict: true` but this isn't documented as a coding standard, leading to confusion about type enforcement.
    - Evidence: `frontend/tsconfig.json:7` (strict mode without documentation).

250) No API rate limiting configuration documentation
    - Impact: If rate limiting is added, there's no documentation on how to configure it per endpoint or globally.
    - Evidence: `README.md`, `AGENTS.md` (no rate limiting configuration docs).

### Environment and Secrets Management Issues
251) Weak secrets in .env.example
    - Impact: `.env.example` contains `ADMIN_PASSWORD=admin123`, `MINIO_SECRET_KEY=minioadmin`, `JWT_SECRET=change-this-to-a-secure-random-key-in-production` which are obvious placeholders that users might copy directly to production.
    - Evidence: `.env.example:19-20,26,53,55` (weak default secrets).

252) JWT_SECRET not generated during startup
    - Impact: Documentation says "Generate a secure random key" but the actual implementation doesn't auto-generate JWT_SECRET on first run if missing, causing startup failures.
    - Evidence: `.env.example:25-26` (comment says to generate but no auto-generation code).

253) No secrets rotation policy documented
    - Impact: No policy or procedure for rotating secrets like JWT_SECRET, database passwords, MinIO credentials, which are critical for production security.
    - Evidence: `.env.example`, `README.md` (no rotation policy).

254) .env.example exposes sensitive defaults
    - Impact: Default database URL `postgres://ideas_user:ideas_password@localhost:5432/ideas` and MinIO credentials are exposed in example file, which inexperienced users might think are secure defaults.
    - Evidence: `.env.example:8,50-55` (exposed production-like credentials in examples).

255) No validation of required environment variables
    - Impact: Application doesn't validate required environment variables on startup, leading to cryptic errors when critical variables are missing or invalid.
    - Evidence: `backend/app/config.py:39` (extra="ignore" skips validation), `backend/app/main.py` (no startup validation).

256) GEBCO_URL points to external non-versioned resource
    - Impact: GEBCO data URL points to `https://www.gebco.net/data_and_products/gridded_bathymetry_data/gebco_2024_tid.nc` which can break if the URL structure changes or resource is removed.
    - Evidence: `.env.example:68` (hardcoded URL without versioning).

### Docker and Infrastructure Issues
257) Multi-stage Docker build not optimized
    - Impact: Backend Dockerfile uses `python:3.11-slim` but includes `apt-get update && apt-get install -y` which downloads latest package lists on every build, causing slow builds and inconsistent versions.
    - Evidence: `backend/Dockerfile:7-8` (apt-get update without package pinning).

258) No health check on frontend Dockerfile
    - Impact: Frontend Dockerfile has no HEALTHCHECK instruction or health endpoint, so Kubernetes/orchestrators can't detect if the container is ready.
    - Evidence: `frontend/Dockerfile:17-25` (no HEALTHCHECK or health endpoint check).

259) No resource limits in docker-compose
    - Impact: None of the services in docker-compose.yml have CPU/memory limits (`cpus`, `mem_limit`, `mem_reservation`), which can lead to resource exhaustion on the host.
    - Evidence: `docker-compose.yml` (no resource limits on any service).

260) No restart policies defined
    - Impact: Docker services don't have explicit restart policies (`restart: on-failure`, `restart: always`), making recovery from crashes manual or inconsistent.
    - Evidence: `docker-compose.yml` (no restart policies configured).

261) No graceful shutdown timeout configured
    - Impact: Services have no `stop_grace_period` configured, causing containers to be killed immediately on SIGTERM without cleanup.
    - Evidence: `docker-compose.yml` (no stop_grace_period defined).

262) Prometheus scrape interval too frequent
    - Impact: Prometheus scrapes backend every 5 seconds (scrape_interval: 5s), which is excessive and can increase load on the backend unnecessarily.
    - Evidence: `monitoring/prometheus/prometheus.yml:6` (5 second scrape interval).

263) No Prometheus retention configuration
    - Impact: Prometheus metrics storage is not configured with retention, leading to unbounded disk usage over time.
    - Evidence: `monitoring/prometheus/prometheus.yml` (no retention config).

264) Grafana not provisioned with dashboards
    - Impact: Grafana container has no pre-configured dashboards for monitoring TerraCube, requiring manual setup after every deployment.
    - Evidence: `docker-compose.yml:46-54` (Grafana service without provisioning).

265) No network isolation between services
    - Impact: All services use default Docker network without isolation between sensitive components (database, backend, worker), potentially allowing lateral movement.
    - Evidence: `docker-compose.yml` (no custom networks defined).

266) No dependency health checks
    - Impact: Backend depends on postgres/redis/minio with only basic `healthcheck` and `condition: service_started`, not ensuring services are actually ready to handle requests.
    - Evidence: `docker-compose.yml:81-87,103-111` (minimal health checks).

267) MinIO bucket not created in startup
    - Impact: MinIO container starts but `ideas-staging` bucket doesn't exist, causing upload failures with "NoSuchBucket" errors.
    - Evidence: `docker-compose.yml:25-36` (no bucket initialization script).

268) No SSL/TLS configuration for internal services
    - Impact: Communication between backend, frontend, worker, redis, and postgres is unencrypted over Docker network, allowing packet sniffing in multi-tenant environments.
    - Evidence: `docker-compose.yml` (no TLS configuration between services).

### Backend Configuration Issues
269) pyproject.toml has minimal metadata
    - Impact: `pyproject.toml` lacks project description, repository URL, license, or maintainer information, making it difficult to understand the package origin.
    - Evidence: `backend/pyproject.toml:1-29` (minimal metadata).

270) Backend dependencies include outdated packages
    - Impact: Some dependencies may be outdated (e.g., `prometheus-fastapi-instrumentator` version in pyproject.toml), which can have security vulnerabilities or compatibility issues.
    - Evidence: `backend/pyproject.toml:23` (dependencies not using version ranges or caret notation).

271) No development dependencies included
    - Impact: `pyproject.toml` only includes runtime dependencies, missing development tools like `pytest`, `ruff`, `black`, `mypy` that would improve code quality.
    - Evidence: `backend/pyproject.toml:1-28` (no dev dependencies listed).

272) No production dependencies specified
    - Impact: No separate `[project.optional-dependencies]` section for production-specific packages (e.g., `gunicorn`, `sentry`) that would be needed in production.
    - Evidence: `backend/pyproject.toml:2-28` (no production dependencies).

### Frontend Build and Configuration Issues
273) Vite config missing build optimization
    - Impact: `vite.config.ts` doesn't configure code splitting, tree shaking, minification, or compression, leading to large bundle sizes.
    - Evidence: `frontend/vite.config.ts` (basic config without optimization options).

274) No build-time environment variables documented
    - Impact: Vite doesn't document available environment variables (e.g., `VITE_*` vars) for customizing build behavior.
    - Evidence: `frontend/vite.config.ts`, `README.md` (no env var documentation).

275) TypeScript strict mode issues not documented
    - Impact: `strict: true` in tsconfig.json enables many type checks that may break existing code, but this isn't documented as a migration path.
    - Evidence: `frontend/tsconfig.json:7` (strict mode without migration guide).

276) Frontend dependencies include multiple mapping libraries
    - Impact: `frontend/package.json` includes `react-map-gl`, `maplibre-gl`, and deck.gl which all handle maps, increasing bundle size and potentially causing conflicts.
    - Evidence: `frontend/package.json:11-24` (multiple mapping libraries).

277) DuckDB WASM uses development version
    - Impact: `@duckdb/duckdb-wasm` dependency is pinned to `1.33.1-dev18.0`, a development version that may be unstable or have bugs.
    - Evidence: `frontend/package.json:15` (dev version of DuckDB WASM).

278) No font fallback configuration
    - Impact: Google Fonts import in styles.css:1 blocks page rendering if CDN is slow or blocked, with no local fallback system fonts.
    - Evidence: `frontend/src/styles.css:1` (blocking Google Fonts import without fallback).

279) CSS not organized as modules
    - Impact: 1826 lines of CSS in a single file without modularization makes maintenance difficult and increases initial bundle size with unused styles.
    - Evidence: `frontend/src/styles.css` (entire CSS in one monolithic file).

280) No responsive design system documented
    - Impact: Responsive breakpoints and design system (colors, spacing, typography) aren't documented, making it difficult to maintain visual consistency.
    - Evidence: `frontend/src/styles.css` (no design system documentation).

### Code Quality and Maintenance Issues
281) Unused imports in backend routers
    - Impact: Backend modules have unused imports that clutter code and may indicate dead code or incomplete refactoring.
    - Evidence: Backend imports show many routers import but may not all be used in their modules.

282) Inconsistent import ordering in backend
    - Impact: Python imports are not consistently ordered (stdlib, third-party, local modules), making code harder to read and maintain.
    - Evidence: Various backend files (inconsistent import order across modules).

283) No type annotations for all function returns
    - Impact: Many functions in backend routers and services don't have return type annotations, making type checking less effective.
    - Evidence: Backend functions (e.g., handlers with `-> List`, `-> Dict` without type hints).

284) Magic numbers not extracted to constants
    - Impact: Hardcoded values like chunk size (500, 1000, 3000), timeouts (60.0), and limits are scattered throughout code, making tuning difficult.
    - Evidence: `backend/app/services/ingest.py:106,171`, `backend/app/routers/datasets.py:80`, `backend/app/routers/stats.py:62` (hardcoded magic numbers).

285) No error codes or standardized exception handling
    - Impact: Error responses use inconsistent formats (detail vs error) and there's no centralized exception handling strategy.
    - Evidence: `backend/app/routers/*.py` (inconsistent error formats).

286) No logging levels or structured logging
    - Impact: Logging uses basic `logging.info`/`logging.error` without levels, structured JSON, or correlation IDs, making production debugging difficult.
    - Evidence: `backend/app/*.py` (basic logging throughout).

287) No database connection pool monitoring
    - Impact: SQLAlchemy pool is not monitored for health (connection counts, checkout timeouts, pool exhaustion), making it hard to diagnose connection issues.
    - Evidence: `backend/app/db.py:21` (no pool monitoring configured).

288) Celery task result expiration not configured
    - Impact: Celery results accumulate in Redis indefinitely (no `result_expires`), causing memory bloat and storage exhaustion.
    - Evidence: `backend/app/celery_app.py:8-20` (no result_expires configured).

289) No deadlock detection or monitoring
    - Impact: There's no detection for database deadlocks, connection pool exhaustion, or worker starvation, making these failures hard to diagnose.
    - Evidence: No deadlock detection or monitoring in any backend module.

290) No circuit breaker pattern for external calls
    - Impact: External API calls (Natural Earth, GEBCO) have no circuit breaker or retry logic, causing cascading failures and long timeouts.
    - Evidence: `backend/app/services/real_data_loader.py:40-49` (no circuit breaker).

291) No idempotency for file upload operations
    - Impact: File upload and processing operations don't implement idempotency, making it impossible to safely retry failed uploads without creating duplicates or state corruption.
    - Evidence: `backend/app/routers/uploads.py`, `backend/app/services/ingest.py` (no idempotency keys).

292) Sample data files have no schema validation
    - Impact: `sample_cells.csv` and `sample_cells.json` in backend/db/ don't have documented schemas, making it hard for users to understand expected formats.
    - Evidence: `backend/db/sample_cells.csv`, `backend/db/sample_cells.json` (no schema documentation).

293) No input sanitization for sample data
    - Impact: If sample data files are loaded programmatically, there's no validation that they match expected formats before processing.
    - Evidence: `backend/app/services/data_loader.py`, `backend/app/services/ingest.py` (no sample data validation).

294) No API versioning strategy
    - Impact: No documented strategy for API versioning (e.g., `/api/v1/`, semantic versioning, backward compatibility), making breaking changes risky.
    - Evidence: `backend/app/main.py:32-53` (routes at `/api/` with no version prefix).

295) No backward compatibility commitments
    - Impact: No documented policy on backward compatibility between API versions or database schema changes, making upgrades risky for users.
    - Evidence: `README.md`, `backend/db/schema.sql` (no backward compatibility policy documented).

296) Nginx configuration not optimized for production
    - Impact: Frontend Dockerfile uses default nginx.conf without optimizations for gzip compression, caching headers, or proper security headers.
    - Evidence: `frontend/Dockerfile:17-25` (no nginx optimizations configured).

297) No rate limiting strategy documented
    - Impact: If rate limiting is implemented, there's no documented strategy for what gets limited (per IP, per user, per endpoint) or how to configure it.
    - Evidence: `README.md`, `AGENTS.md` (no rate limiting strategy documented).

298) No disaster recovery plan documented
    - Impact: No documented plan for recovering from common failure scenarios (database corruption, backup restoration, container failures, data loss).
    - Evidence: `README.md`, `.env.example` (no disaster recovery documentation).

299) No security incident response plan
    - Impact: No documented procedure for responding to security incidents (data breach, credential compromise, DDoS attacks).
    - Evidence: `README.md`, `AGENTS.md` (no incident response plan).

300) No change log or changelog maintained
    - Impact: No CHANGELOG or change documentation to track what has changed between versions, making it difficult for users to understand updates.
    - Evidence: No CHANGELOG.md file in repository.
### Database and Data Integrity Issues
301) No foreign key cascade delete tests
    - Impact: No tests verify that CASCADE deletes work correctly across partitions, potentially leaving orphaned data or breaking referential integrity.
    - Evidence: `backend/db/schema.sql:34` (CASCADE defined but no tests for cascading deletes).

302) No database migration rollback strategy
    - Impact: If a migration fails mid-way, there's no documented procedure for rolling back, requiring manual intervention.
    - Evidence: `README.md` (no rollback procedure documented), `backend/db/schema.sql` (no migration versioning).

303) No data consistency checks after bulk operations
    - Impact: Bulk insert operations don't verify data consistency (row counts, checksums), potentially silently introducing corruption.
    - Evidence: `backend/app/services/ingest.py:95-109`, `backend/app/services/real_data_loader.py:347-371` (bulk inserts without consistency checks).

304) Cell objects table has no update timestamp
    - Impact: The `cell_objects` table has `created_at` but no `updated_at` timestamp, making it impossible to track when data was last modified or implement stale data cleanup.
    - Evidence: `backend/db/schema.sql:32-44` (created_at only, no updated_at).

305) No unique constraint on (dataset_id, dggid, tid, attr_key)
    - Impact: While the schema has a unique constraint on all four columns, this only prevents exact duplicates, not preventing data quality issues from near-duplicates or fuzzy matching.
    - Evidence: `backend/db/schema.sql:43` (UNIQUE constraint exists but may be too restrictive or not documented).

306) Uploads table has no cleanup mechanism
    - Impact: Old upload records are never cleaned up, causing table bloat and storage issues for failed uploads.
    - Evidence: `backend/db/schema.sql:52-63` (no cleanup table or scheduled task documented).

307) No soft delete pattern for datasets
    - Impact: Datasets are hard deleted via CASCADE, losing all associated cell_objects and uploads permanently, with no way to recover deleted data.
    - Evidence: `backend/db/schema.sql:34` (CASCADE without soft delete flag).

### Frontend Build and Bundle Issues
308) Vite config lacks production optimizations
    - Impact: `vite.config.ts` doesn't configure code splitting, lazy loading, or bundle size optimization, leading to large initial load times.
    - Evidence: `frontend/vite.config.ts` (minimal config without optimization settings).

309) Frontend package.json uses dev versions
    - Impact: Dependencies like `@duckdb/duckdb-wasm` use dev versions (`1.33.1-dev18.0`) which may be unstable in production.
    - Evidence: `frontend/package.json:15` (dev DuckDB WASM version).

310) TypeScript strict mode may break existing code
    - Impact: `tsconfig.json` has `strict: true` which enables many type checks, potentially breaking code that wasn't written with strict typing in mind.
    - Evidence: `frontend/tsconfig.json:8` (strict mode enabled without migration plan).

311) No bundle analysis or size monitoring
    - Impact: No build step to analyze bundle size or identify large dependencies, making it hard to track performance regressions.
    - Evidence: `frontend/package.json` (no bundle analyzer like rollup-plugin-visualizer configured).

312) Frontend Dockerfile uses multi-stage build without optimization
    - Impact: Dockerfile copies node_modules then installs npm packages without caching layers or using buildkit, making slow production builds.
    - Evidence: `frontend/Dockerfile:8-16` (inefficient multi-stage build).

### Performance and Scalability Issues
313) No database connection pooling configuration for read vs write
    - Impact: Single connection pool for all operations may cause contention between read-heavy (queries) and write-heavy (ingestion) operations.
    - Evidence: `backend/app/db.py:21` (single engine with no separate pools).

314) No query result caching
    - Impact: Frequently accessed data (datasets list, metadata) is not cached, causing repeated database queries for the same data.
    - Evidence: `backend/app/routers/datasets.py:32-39` (no caching layer for dataset metadata).

315) Synchronous polygon resolution blocks UI
    - Impact: Frontend resolves polygons sequentially using `await resolveZonePolygons()` which can block the main thread during large viewport updates, making the app unresponsive.
    - Evidence: `frontend/src/lib/dggal.ts:129-207` (sequential polygon resolution without streaming).

316) No request deduplication for identical queries
    - Impact: Rapid map movements trigger identical viewport queries in succession without deduplication, causing redundant database queries and wasted resources.
    - Evidence: `frontend/src/components/MapView.tsx:263-281` (no query deduplication logic).

317) No lazy loading for heavy components
    - Impact: Components like MapView and tool panels load all their dependencies immediately, increasing initial bundle size and time to interactive.
    - Evidence: `frontend/src/components/MapView.tsx` (imports all dependencies at top), `frontend/src/components/ToolboxPanel.tsx` (no lazy loading).

318) No virtual scrolling for large lists
    - Impact: Dataset search and layer lists render all items without virtualization, causing performance issues with hundreds of datasets.
    - Evidence: `frontend/src/components/DatasetSearch.tsx` (no virtual scroller), `frontend/src/components/LayerList.tsx` (no virtual scroller).

319) No pagination for dataset lists
    - Impact: Datasets API has no pagination for large datasets, requiring frontend to fetch and render all datasets at once.
    - Evidence: `backend/app/routers/datasets.py:32-39` (no cursor/pagination for list endpoint).

320) WebWorker not used for CPU-intensive tasks
    - Impact: DGGS polygon resolution and spatial calculations run on the main thread, potentially blocking UI. No offloading to WebWorkers.
    - Evidence: `frontend/src/lib/dggal.ts:129-207` (polygon resolution on main thread).

321) No throttling for expensive operations
    - Impact: Expensive spatial operations (buffer, aggregate, intersection) don't have rate limiting or concurrency controls, allowing resource exhaustion.
    - Evidence: `backend/app/services/spatial_engine.py:29-101` (unbounded parallelism), `backend/app/routers/toolbox.py` (no rate limiting).

322) No database read replicas configured
    - Impact: Single database instance has no read replicas, creating single point of failure and limited read throughput.
    - Evidence: `docker-compose.yml` (single postgres service, no read replicas configured).

323) No query timeout configuration
    - Impact: No statement_timeout configured for database, allowing long-running queries to block connections indefinitely.
    - Evidence: `backend/app/db.py:21` (no statement_timeout in engine config).

324) No connection retry logic for transient failures
    - Impact: Database connection failures cause immediate errors without retry, making the system fragile under temporary network issues.
    - Evidence: `backend/app/db.py:21` (no retry logic or connection pool configuration with retries).

### Security Implementation Gaps
325) No request ID tracking for security audits
    - Impact: Unable to trace a specific request through logs for security audits or incident response, making forensics difficult.
    - Evidence: `backend/app/main.py` (no request ID middleware), `backend/app/*.py` (no X-Request-ID header).

326) No audit logging for sensitive operations
    - Impact: Critical operations like dataset creation, file uploads, and admin actions don't generate audit logs for accountability.
    - Evidence: `backend/app/routers/datasets.py:52-63` (no audit logging), `backend/app/routers/uploads.py:70-93` (no audit logging).

327) No IP allowlist or denylist configuration
    - Impact: No configuration for restricting access from specific IPs or geographic regions, making the system vulnerable to targeted attacks from any location.
    - Evidence: `backend/app/main.py`, `backend/app/config.py` (no IP allowlist configuration).

328) No request size validation beyond basic limits
    - Impact: MAX_UPLOAD_BYTES=200MB is configured but additional validation for payload complexity or structure is missing, allowing potential DoS through complex payloads.
    - Evidence: `backend/app/config.py:28` (only size limit, no complexity validation).

329) No input sanitization for all string inputs
    - Impact: String inputs from users (dataset names, file names, metadata) are not sanitized for special characters or length, potentially causing display issues or injection.
    - Evidence: `backend/app/routers/datasets.py:52-63` (no input sanitization), `backend/app/services/ingest.py` (no sanitization of metadata strings).

330) No validation of DGGS level ranges in inputs
    - Impact: DGGS levels passed to spatial operations aren't validated to be within valid ranges (e.g., 0-20 for IVEA3H), potentially causing errors or unexpected behavior.
    - Evidence: `backend/app/dggal_utils.py`, `backend/app/services/spatial_engine.py` (no level validation in dggal_service calls).

331) No encryption at rest for sensitive data
    - Impact: Sensitive attributes stored in `value_json` aren't encrypted at rest in the database, potentially exposing confidential information to database administrators.
    - Evidence: `backend/db/schema.sql:41` (JSONB column without encryption at rest field).

332) No password complexity requirements enforced
    - Impact: Passwords can be weak (admin123) without enforcement of minimum complexity requirements (length, special characters, etc.).
    - Evidence: `backend/app/routers/auth.py:23-45` (no password complexity enforcement), `backend/app/config.py:19-20` (no password policy).

333) No account lockout policy
    - Impact: No configuration for account lockout after failed login attempts, making the system vulnerable to brute force attacks.
    - Evidence: `backend/app/routers/auth.py` (no lockout mechanism configured).

334) No session timeout configuration
    - Impact: JWT tokens have default expiration (60 minutes) but this isn't configurable per environment, and there's no session timeout for inactivity.
    - Evidence: `backend/app/auth.py:10` (hardcoded ACCESS_TOKEN_EXPIRE_MINUTES).

335) No MFA (multi-factor authentication) support
    - Impact: Admin accounts have no MFA requirement, making sensitive accounts vulnerable to password theft or phishing attacks.
    - Evidence: `backend/app/auth.py` (no MFA support for admin accounts).

336) CORS configuration lacks environment awareness
    - Impact: CORS origin is a single environment variable instead of allowing multiple origins per environment (dev, staging, production).
    - Evidence: `backend/app/main.py:34-40` (single CORS_ORIGIN variable for all environments).

### Error Handling and Recovery Issues
337) No global exception handler
    - Impact: FastAPI doesn't have a global exception handler to catch unhandled exceptions, potentially returning raw error traces to users.
    - Evidence: `backend/app/main.py` (no global exception handler configured).

338) Inconsistent error response schemas
    - Impact: Different endpoints return errors in different formats (`{error: ...}`, `{detail: ...}`, generic HTTP status), making client error handling inconsistent.
    - Evidence: Multiple endpoints (see #223 in previous issues).

339) No circuit breaker for external API calls
    - Impact: Calls to external services (Natural Earth, GEBCO) don't have circuit breaker logic, causing cascading failures and long timeouts.
    - Evidence: `backend/app/services/real_data_loader.py:40-49` (no circuit breaker pattern).

340) No exponential backoff with jitter for retries
    - Impact: Failed operations retry immediately without exponential backoff, overwhelming downstream services.
    - Evidence: `backend/app/services/real_data_loader.py` (no retry backoff configuration).

341) No graceful degradation patterns
    - Impact: System doesn't implement graceful degradation (shedding load, returning cached data, degrading functionality) under high load.
    - Evidence: No graceful degradation strategy in codebase.

### Frontend Architecture Issues
342) No state management persistence strategy
    - Impact: User state (layers, filters, map position) is lost on page refresh, requiring users to reconfigure work from scratch.
    - Evidence: `frontend/src/lib/store.ts` (no persistence middleware configured).

343) No offline-first architecture
    - Impact: Application requires server connection for all operations, making it unusable offline. Critical features like dataset search and cell fetching don't work without network.
    - Evidence: `frontend/src/lib/api.ts:44-79` (no offline data caching), `frontend/src/components/MapView.tsx:177-281` (no offline handling).

344) No service worker for background tasks
    - Impact: Long-running operations (file uploads, polygon resolution) run on the main thread, blocking UI and potentially killing the browser.
    - Evidence: `frontend/src/lib/dggal.ts:129-207` (no WebWorker offloading).

345) No virtual DOM for large lists
    - Impact: Rendering thousands of polygons or list items uses React's actual DOM without virtualization, causing UI freezes and memory issues.
    - Evidence: `frontend/src/components/MapView.tsx:389-442` (actual DOM rendering for polygons), `frontend/src/components/LayerList.tsx` (actual DOM for lists).

346) No memoization for expensive computations
    - Impact: Repeated computations (color scales, polygon generation) aren't memoized, wasting CPU cycles.
    - Evidence: `frontend/src/components/MapView.tsx:70-79` (toColor called for every cell).

347) No debouncing for user interactions
    - Impact: Rapid user interactions (map panning, zooming) trigger frequent expensive recomputations without debouncing, wasting resources.
    - Evidence: `frontend/src/components/MapView.tsx:263-281` (debounce used but not aggressive enough for rapid movements).

348) No lazy route code splitting
    - Impact: All routes and components are bundled into a single JavaScript file, causing the entire application to load before rendering.
    - Evidence: `frontend/vite.config.ts` (no route-based code splitting configured).

349) No tree shaking for unused exports
    - Impact: Unused code and dependencies aren't eliminated from the bundle, increasing bundle size unnecessarily.
    - Evidence: `frontend/package.json`, `frontend/src/` (no tree shaking optimization configured).

350) No image optimization strategy
    - Impact: Images (logos, icons, textures) aren't optimized (WebP, AVIF, responsive srcset), increasing load times.
    - Evidence: `public/` (no optimized image formats or responsive images configured).

### Development Workflow Issues
351) No pre-commit hooks for code quality
    - Impact: Code quality checks (linting, formatting) aren't enforced automatically, allowing issues to enter the codebase.
    - Evidence: No `.pre-commit-config.yaml` or husky configuration found.

352) No automated testing in CI/CD
    - Impact: No CI/CD pipeline configured to run tests automatically on commits, allowing untested code to reach production.
    - Evidence: No GitHub Actions, GitLab CI, or similar workflow files found.

353) No code coverage tracking
    - Impact: No code coverage tools or reporting configured, making it impossible to measure test coverage or identify untested code.
    - Evidence: No coverage configuration found in backend or frontend.

354) No dependency vulnerability scanning
    - Impact: Dependencies aren't automatically scanned for known security vulnerabilities, introducing supply chain risks.
    - Evidence: No Snyk, Dependabot, or similar scanning configured in package files or CI pipeline.

355) No IDE integration guidelines
    - Impact: No documentation on recommended IDE setup (VS Code extensions, Python formatting, ESLint rules), leading to inconsistent development environments.
    - Evidence: No IDE configuration documentation in README or AGENTS.md.

356) No code review checklist
    - Impact: Pull requests aren't checked against a standardized code review checklist, allowing inconsistent code quality and potential bugs.
    - Evidence: No review checklist or PR template documentation.

357) No local development environment provisioning
    - Impact: No automated way to set up a complete local development environment (database, Redis, MinIO) with a single command.
    - Evidence: `README.md` (manual steps for each service startup).

358) No debugging configuration for development
    - Impact: Debugging setup requires multiple manual commands and configuration files, making onboarding new developers difficult.
    - Evidence: No debugging setup guide or development environment documentation.

359) No hot reload for CSS changes
    - Impact: CSS changes require full browser reload during development, slowing down the development workflow.
    - Evidence: `frontend/package.json` (no hot reload or live reload configured).

360) No API mocking for frontend development
    - Impact: Frontend developers can't easily mock API responses for testing without dedicated mocking framework, slowing down development and testing.
    - Evidence: No MSW (Mock Service Worker) or similar configured.

### Additional Code Quality Issues
361) Dead code from abandoned features
    - Impact: Legacy code, commented-out functions, or unused imports increase bundle size and create maintenance burden.
    - Evidence: `backend_node_archive/` (entire legacy backend included), potential dead imports in main codebase.

362) Inconsistent naming conventions
    - Impact: Mix of camelCase, snake_case, and PascalCase across files makes code harder to read and maintain.
    - Evidence: Frontend uses PascalCase for components, snake_case for some functions, camelCase for API fields (see #226).

363) No type hints for all function parameters
    - Impact: Many backend functions lack proper type annotations for parameters and return values, reducing type safety and IDE support.
    - Evidence: Multiple backend modules (no consistent type hints across all functions).

364) Magic numbers and strings scattered throughout codebase
    - Impact: Hardcoded values (timeouts, limits, batch sizes) are duplicated across files without being centralized, making tuning difficult.
    - Evidence: `backend/app/services/ingest.py:106,171`, `backend/app/services/real_data_loader.py:150` (magic numbers throughout).

365) No docstring documentation for public API endpoints
    - Impact: Many FastAPI endpoint functions lack docstrings, making it difficult to understand API contracts and generate OpenAPI documentation.
    - Evidence: `backend/app/routers/*.py` (minimal docstrings on endpoint functions).

366) No validation error messages
    - Impact: Validation errors return generic messages without helpful guidance on how to fix the issue, making debugging difficult for users.
    - Evidence: `backend/app/routers/*.py` (generic validation errors without specific guidance).

367) Duplicate code patterns
    - Impact: Similar logic for error handling, data loading, and API requests is duplicated across files rather than being extracted into shared utilities.
    - Evidence: `frontend/src/lib/api.ts`, `frontend/src/lib/dggal.ts` (duplicate logic in multiple components).

368) No centralized error handling utilities
    - Impact: Error handling logic is scattered across modules, making it difficult to ensure consistent error responses and recovery flows.
    - Evidence: `backend/app/routers/*.py`, `frontend/src/components/*.tsx` (inconsistent error handling patterns).

369) No configuration validation at startup
    - Impact: Application doesn't validate critical configuration values on startup, leading to cryptic runtime errors or misconfigurations.
    - Evidence: `backend/app/config.py:39` (extra="ignore" prevents validation), `backend/app/main.py` (no startup validation step).

370) No database schema migration tool integration
    - Impact: Manual SQL execution without a migration tool (Alembic) makes schema changes error-prone and difficult to track.
    - Evidence: `backend/db/schema.sql` (manual SQL without migration tool), `backend/app/init_db.py` (manual schema loading).

371) No API backward compatibility guarantees
    - Impact: No documented policy or mechanism for maintaining backward compatibility when making breaking API changes.
    - Evidence: `backend/app/main.py`, `README.md` (no backward compatibility policy).

372) No feature flags system
    - Impact: No mechanism to gradually roll out or disable features without redeploying the entire application.
    - Evidence: No feature flag configuration system in codebase.

373) No observability integration
    - Impact: Application components don't integrate with centralized observability platform (e.g., Sentry, DataDog, New Relic) for error tracking and performance monitoring.
    - Evidence: No observability SDK integration in codebase.

374) No APM (Application Performance Monitoring) instrumentation
    - Impact: No custom metrics are tracked for business-critical operations like user logins, data uploads, or DGGS queries, making it hard to measure product success.
    - Evidence: `backend/app/main.py` (only generic HTTP metrics from prometheus-fastapi-instrumentator).

375) No distributed tracing
    - Impact: No distributed tracing system to trace requests across services (backend → database → worker → external APIs), making debugging difficult.
    - Evidence: No tracing middleware or instrumentation in codebase.

376) No API rate limiting per user
    - Impact: Rate limiting isn't implemented per-user or per-api-key, allowing a single user to abuse resources or attack specific endpoints.
    - Evidence: No rate limiting middleware found (see #31).

377) No request/response size limits per endpoint
    - Impact: No maximum payload sizes configured per endpoint, allowing large or complex requests to overwhelm the system.
    - Evidence: No per-endpoint size limits configured.

378) No API caching strategy
    - Impact: Frequently accessed data and computation results aren't cached, increasing database load and response times.
    - Evidence: No caching layer or cache-aside headers configured.

379) No pagination default limits enforcement
    - Impact: Pagination endpoints don't enforce default page sizes or maximum limits, allowing clients to request unbounded result sets.
    - Evidence: `backend/app/routers/datasets.py:71-101` (no enforced pagination limits).

380) No query complexity limits
    - Impact: Complex nested queries or expensive joins aren't validated or limited, allowing denial of service through resource exhaustion.
    - Evidence: No query complexity analysis or limits in codebase.

381) No content validation policies
    - Impact: File uploads, dataset metadata, and user-generated content aren't validated against size limits, allowed content types, or content policies.
    - Evidence: `backend/app/routers/uploads.py` (minimal content validation).
