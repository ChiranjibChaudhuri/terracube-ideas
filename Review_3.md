# Review_3

## Scope
- backend/ (FastAPI + Celery worker + services + repositories)
- frontend/ (Vite + React + Deck.gl)
- docker-compose.yml and monitoring/
- backend_node_archive/ (legacy Fastify backend)

## Findings (ordered by severity)

### Critical
1) JWT tokens stored in localStorage (XSS vulnerability)
   - Impact: JWT tokens stored in localStorage are accessible to any malicious script running on the page (XSS), allowing attackers to hijack user sessions. Should use httpOnly cookies.
   - Evidence: frontend/src/lib/api.ts:3,86,95,100; frontend/src/App.tsx:9

2) SQL injection in partition table creation
   - Impact: Direct SQL string interpolation with dataset names/IDs allows crafted values to inject malicious SQL, potentially leading to data corruption, privilege escalation, or data exfiltration.
   - Evidence: backend/app/repositories/dataset_repo.py:21-26

3) SQL injection in bulk data insertion
   - Impact: Unsanitized dggid, attr_key, and class values interpolated into SQL INSERT statements in multiple locations, enabling arbitrary SQL execution.
   - Evidence: backend/app/services/data_loader.py:206,272,326-330

4) SQL injection in ops.py
   - Impact: Raw SQL with f-string interpolation allows attackers to execute arbitrary SQL through spatial operations endpoint.
   - Evidence: backend/app/routers/ops.py:199-210

5) Missing authentication on sensitive dataset operations
   - Impact: Unauthenticated users can access, list, query, and look up cells from all datasets, potentially exposing sensitive geospatial data.
   - Evidence: backend/app/routers/datasets.py:32-52 (list_datasets, get_dataset), backend/app/routers/datasets.py:68-103 (list_cells), backend/app/routers/datasets.py:106-140 (lookup_cells) - all missing get_current_user dependency

6) Missing authentication on operations endpoint
   - Impact: Unauthenticated users can perform database queries and spatial operations on the system.
   - Evidence: backend/app/routers/ops.py:51-134 (/api/ops/query), backend/app/routers/ops.py:155-246 (/api/ops/spatial) - missing authentication

7) Default admin password in configuration
   - Impact: Admin account can be compromised using widely-known default credential "admin123" exposed in source code and docker-compose.yml.
   - Evidence: docker-compose.yml:74, backend/.env.example:23, backend/app/config.py:22-23

8) Default MinIO credentials exposed
   - Impact: Object storage can be fully compromised with default "minioadmin/minioadmin" credentials exposed in multiple config files.
   - Evidence: docker-compose.yml:30-31,68-69,102-103, backend/.env.example:17-18, backend/app/config.py:17-18

9) Default PostgreSQL credentials exposed
   - Impact: Database can be accessed with default "ideas_user/ideas_password" credentials visible in configuration.
   - Evidence: docker-compose.yml:6-7, backend/.env.example:6

10) Default JWT secret hardcoded
    - Impact: JWT tokens can be forged/decoded with predictable "change-me-in-production" secret exposed in docker-compose.
    - Evidence: docker-compose.yml:62,97, backend/.env.example:7

11) No SSL/TLS for database connections
    - Impact: Database credentials and data transmitted in plaintext, susceptible to interception and man-in-the-middle attacks.
    - Evidence: docker-compose.yml:61, backend/app/db.py:5 (no sslmode parameter in DATABASE_URL)

12) No SSL/TLS for MinIO connections
    - Impact: Object storage credentials and data transmitted in plaintext, vulnerable to interception.
    - Evidence: docker-compose.yml:66-69, backend/app/config.py:15-18 (no secure=True or HTTPS configuration)

13) No SSL/TLS for Redis
    - Impact: Celery task data and results transmitted in plaintext, exposing task metadata and potentially sensitive data.
    - Evidence: docker-compose.yml:64-65, backend/app/celery_app.py:6 (redis:// not rediss://)

14) No SSL/TLS for frontend/backend API
    - Impact: API calls, authentication tokens, and data transmitted in plaintext over the network.
    - Evidence: frontend/nginx.conf:2 (listen 80), frontend/nginx.conf:19 (proxy_pass http://), backend/app/main.py:73 (uvicorn without SSL configuration)

15) Grafana admin password exposed
    - Impact: Grafana monitoring dashboard can be compromised with default "admin" password in configuration.
    - Evidence: docker-compose.yml:52

16) Database port exposed publicly
    - Impact: PostgreSQL directly accessible from network at port 5433, bypassing application layer controls.
    - Evidence: docker-compose.yml:10 (ports 5433:5432)

17) Redis exposed without authentication
    - Impact: Redis accessible without password for read/write/delete operations, allowing unauthorized data access and manipulation.
    - Evidence: docker-compose.yml:19-23 (ports 6379:6379, no REDIS_PASSWORD configured)

18) MinIO console exposed publicly
    - Impact: MinIO management interface accessible from network at ports 9000 and 9001 without additional access controls.
    - Evidence: docker-compose.yml:33-34 (ports 9000:9000 and 9001:9001)

19) No database backup mechanism
    - Impact: Data loss is catastrophic with no automated backup or recovery options configured.
    - Evidence: No backup scripts in backend/, no backup volumes or cron jobs in docker-compose.yml

20) Missing Content Security Policy (CSP) Headers
    - Impact: No CSP headers configured, allowing inline scripts, unsafe eval, and arbitrary external resources. This increases surface area for XSS attacks and code injection.
    - Evidence: frontend/vite.config.ts:1-10; frontend/index.html:1-14 (no meta CSP tags or build configuration)

21) Missing foreign key constraint on cell_objects.attr_key
    - Impact: Orphaned cell records possible if attributes entry is deleted; referential integrity not enforced at DB level.
    - Evidence: backend/db/schema.sql:23-30,37

22) No transaction isolation for partition operations
    - Impact: If partition creation succeeds but dataset insert fails, orphaned partition table remains; if dataset insert succeeds but partition creation fails, usable dataset cannot store cells.
    - Evidence: backend/app/repositories/dataset_repo.py:11-29

23) Unbounded asyncpg connection pool
    - Impact: Under high load, unlimited connection growth can exhaust database resources, causing connection failures and service outage.
    - Evidence: backend/app/db.py:42 (unbounded pool_size in SQLAlchemy config)

### High
24) Missing rate limiting on authentication endpoints
    - Impact: Attackers can brute-force credentials or perform account enumeration attacks without rate limiting.
    - Evidence: backend/app/routers/auth.py:20-46 (login endpoint) - no rate limiting configured

25) Missing rate limiting on all API endpoints
    - Impact: APIs vulnerable to DoS attacks, brute force, and resource exhaustion.
    - Evidence: No rate limiting middleware configured in backend/app/main.py or any routers

26) Overly permissive CORS configuration
    - Impact: `allow_methods=["*"]` and `allow_headers=["*"]` allow any HTTP method and header, increasing attack surface.
    - Evidence: backend/app/main.py:35-41

27) No password complexity requirements
    - Impact: Users can set weak passwords, increasing risk of account compromise through credential stuffing.
    - Evidence: backend/app/routers/auth.py:48-79 (register endpoint) - no password validation

28) Verbose error messages exposing system details
    - Impact: Error details in responses can reveal database structure, file paths, and implementation details that aid attackers.
    - Evidence: backend/app/routers/auth.py:45-46 (returns str(e)), backend/app/routers/ops.py:33 (returns str(e)), multiple routers return raw exception messages

29) Missing authentication on analytics endpoint
    - Impact: Unauthenticated users can execute set operations on dataset data through analytics endpoint.
    - Evidence: backend/app/routers/analytics.py:17-38

30) Missing authentication on topology endpoint
    - Impact: Unauthenticated users can perform DGGS topology operations.
    - Evidence: backend/app/routers/topology.py:15-40 - no get_current_user dependency

31) File upload path traversal vulnerability
    - Impact: Malicious filenames could attempt directory traversal when constructing file paths in `/tmp/uploads`.
    - Evidence: backend/app/routers/uploads.py:36 (os.path.basename on filename but combined path not validated), backend/app/routers/uploads.py:40 (file_path construction)

32) Insufficient input validation on dggsName parameter
    - Impact: Invalid or malicious DGGS system names could cause unexpected behavior in DGGS operations.
    - Evidence: backend/app/routers/toolbox.py:28, backend/app/routers/topology.py:16 - dggsName passed directly without validation

33) Dataset creation missing name validation
    - Impact: Long or malformed dataset names could cause issues or be used for injection attacks.
    - Evidence: backend/app/routers/datasets.py:55-65 (name parameter not validated for length, special characters)

34) No file content validation beyond extension
    - Impact: Files with malicious content could be uploaded and processed, allowing potential exploits.
    - Evidence: backend/app/routers/uploads.py:38-39 (only checks file extension, not actual file content or magic bytes)

35) Missing indexes on frequently queried columns
    - Impact: Full table scans on user lookups by email, dataset searches, and dataset queries by created_by degrade query performance as data grows.
    - Evidence: backend/db/schema.sql:3-9,11-21 (no indexes on users.email, datasets.name, datasets.created_by)

36) No unique constraint on dataset name
    - Impact: Multiple datasets can have identical names, causing user confusion and potential data integrity issues.
    - Evidence: backend/db/schema.sql:11-21 (no UNIQUE constraint on datasets.name)

37) Partial transaction commits create inconsistent state
    - Impact: If Celery task fails after upload record created but before processing, orphaned upload record remains; no rollback mechanism.
    - Evidence: backend/app/routers/uploads.py:85-94

38) Missing database constraints for status enums
    - Impact: Invalid status values can be inserted into datasets and uploads tables, causing application errors.
    - Evidence: backend/db/schema.sql:18,62 (no CHECK constraints on status fields)

39) Manual updated_at management
    - Impact: Upload records may have stale updated_at timestamps if manual updates are not performed correctly.
    - Evidence: backend/db/schema.sql:65 (DEFAULT NOW() on updated_at, but application must trigger updates)

40) No migration or rollback system
    - Impact: Schema changes cannot be versioned, deployed, or rolled back reliably, making production schema evolution risky.
    - Evidence: No Alembic, migrations directory, or migration tooling configured

41) Weak client-side input validation
    - Impact: Login form inputs (email, password, name) lack client-side validation before submission, allowing potentially malformed or malicious data.
    - Evidence: frontend/src/pages/LoginPage.tsx:51-87 (no validation on email format, password strength, or name length)

42) Insufficient sanitization in SQL-like queries
    - Impact: While basic SQL literal sanitization exists, the spatial database builds dynamic SQL queries using string interpolation. Zone IDs could bypass basic sanitization.
    - Evidence: frontend/src/lib/spatialDb.ts:33,128,143,169,211-218 (dynamic SQL query building with sanitized but user-controlled values)

43) Containers running as root
    - Impact: Container compromise gives root access to host system, significantly increasing attack surface.
    - Evidence: backend/Dockerfile:1 (no USER directive), frontend/Dockerfile:1 (node user not specified for runtime), docker-compose.yml (no user: directive for any service)

44) No container resource limits
    - Impact: Single container can exhaust host memory/CPU causing DoS and affecting other containers.
    - Evidence: docker-compose.yml (no deploy.resources.limits for any service)

45) No health checks for critical services
    - Impact: Unhealthy services won't be detected or restarted automatically, leading to degraded service availability.
    - Evidence: docker-compose.yml (no healthcheck for backend, worker, frontend, redis, minio, prometheus, grafana)

46) No graceful shutdown for Celery workers
    - Impact: In-progress tasks may be interrupted/corrupted on restart without proper task acknowledgment and soft timeout handling.
    - Evidence: backend/app/celery_app.py (no task_acks_late, no worker_prefetch_multiplier, no graceful shutdown handlers)

47) Prometheus metrics unauthenticated
    - Impact: System metrics exposed without authentication, potentially revealing sensitive operational information.
    - Evidence: backend/app/main.py:57 (Instrumentator().expose(app)), monitoring/prometheus/prometheus.yml (no authentication on scrape targets)

48) No alerting configuration
    - Impact: System issues go unnoticed until manual discovery, delaying response to failures.
    - Evidence: monitoring/prometheus/prometheus.yml (no alertmanager config or alerting rules)

49) No network segmentation
    - Impact: All containers on same network with no firewall rules between services, allowing lateral movement if compromised.
    - Evidence: docker-compose.yml (no networks definition, all services on default bridge network)

50) No read-only root filesystem
    - Impact: Compromised container can write to filesystem, increasing persistence capability for attackers.
    - Evidence: docker-compose.yml (no read_only: true for any service)

51) MinIO without bucket policies or encryption
    - Impact: No data-at-rest encryption or granular access control on object storage.
    - Evidence: docker-compose.yml:25-36 (no MINIO_SERVER_ENCRYPTION_CONFIG or bucket policies)

52) No Celery task timeouts
    - Impact: Long-running tasks can hang workers indefinitely, causing queue buildup.
    - Evidence: backend/app/celery_app.py:10-17 (no task_soft_time_limit or task_time_limit configured)

53) Database connection pool not tuned for production
    - Impact: May exhaust connections under load or be inefficient for production workloads.
    - Evidence: backend/app/db.py:24-27 (pool_size=10, max_overflow=20 - no production sizing)

54) Missing CSRF protection
    - Impact: Cross-site request forgery attacks possible on state-changing endpoints.
    - Evidence: backend/app/main.py:33-41 (no CSRF middleware configured)

55) Generic exception handling exposes internal errors
    - Impact: Stack traces and internal errors leaked to clients, aiding attacks and providing reconnaissance information.
    - Evidence: backend/app/routers/toolbox.py:32-73 (catch Exception and return str(e))

56) Bare except clause in ingest.py
    - Impact: Silent failures make debugging difficult and may mask security issues.
    - Evidence: backend/app/services/ingest.py:277 (except Exception: without specific handling)

### Medium
57) Long JWT token expiry (60 minutes)
    - Impact: Longer window for token abuse if compromised; should be shorter for better security.
    - Evidence: backend/app/auth.py:10 (ACCESS_TOKEN_EXPIRE_MINUTES = 60)

58) Login error message reveals user existence
    - Impact: Enables account enumeration attacks by distinguishing between bad password vs non-existent user.
    - Evidence: backend/app/routers/auth.py:30 ("Invalid credentials" message doesn't vary)

59) Missing input sanitization for query parameters
    - Impact: Special characters in search/filter parameters could cause unexpected behavior or potential injection.
    - Evidence: backend/app/routers/datasets.py:37 (ilike with string concatenation), backend/app/routers/ops.py:102 (direct comparison of value_text)

60) No authorization checks on dataset access
    - Impact: Any authenticated user can access any dataset regardless of ownership, allowing unauthorized data access.
    - Evidence: backend/app/routers/datasets.py:44-52,68-103 (no check comparing dataset.created_by with user.id)

61) Background task not validating dataset ownership
    - Impact: Users could trigger processing on datasets they don't own.
    - Evidence: backend/app/routers/uploads.py:51-94 (no ownership check on existing dataset before processing)

62) No input length limits on text fields
    - Impact: Potential DoS via oversized string values in dataset names or descriptions.
    - Evidence: backend/app/routers/datasets.py:56-57 (name, description as Form fields without length limits)

63) File deletion on error could fail silently
    - Impact: Temporary files may accumulate if removal fails, filling disk space.
    - Evidence: backend/app/services/ingest.py:281-285 (file deletion in finally block with broad exception handling)

64) Missing AbortController cleanup in MapView Component
    - Impact: AbortControllers for API requests created but may not be properly cleaned up on unmount, causing memory leaks.
    - Evidence: frontend/src/components/MapView.tsx:140-141,230-232,291-293

65) Silent error handling in Workbench
    - Impact: Errors in loadDemoLayer are silently caught without user feedback.
    - Evidence: frontend/src/pages/Workbench.tsx:101-103 (empty catch block)

66) DuckDB Worker Memory Leak Potential
    - Impact: DuckDB worker created and stored in global variables but never explicitly terminated, could accumulate worker threads.
    - Evidence: frontend/src/lib/spatialDb.ts:28-29,72 (worker created but no cleanup function)

67) Unbounded State in MapView Component
    - Impact: Multiple state objects and refs without cleanup could accumulate memory, especially for large datasets.
    - Evidence: frontend/src/components/MapView.tsx:127-152

68) Missing Input Validation for Numeric Fields
    - Impact: Number inputs in ToolModal don't validate ranges (e.g., negative values where only positive valid).
    - Evidence: frontend/src/components/ToolModal.tsx:66-71,196-202

69) No validation on min_level/max_level range
    - Impact: Invalid ranges could cause unexpected behavior in DGGS operations.
    - Evidence: backend/app/routers/uploads.py:27-28

70) No validation of dataset name uniqueness case sensitivity
    - Impact: Case variations could create confusion and potential security issues.
    - Evidence: backend/app/routers/datasets.py:64 (no uniqueness check on name field)

71) JWT token expiry fixed at 60 minutes
    - Impact: Cannot be adjusted per environment or security requirements.
    - Evidence: backend/app/auth.py:10 (hardcoded ACCESS_TOKEN_EXPIRE_MINUTES)

72) No request/response size limits
    - Impact: Large payloads could exhaust memory (though MAX_UPLOAD_BYTES exists for uploads).
    - Evidence: backend/app/main.py (no max_request_size in uvicorn config)

73) No logging configuration
    - Impact: Insufficient visibility for troubleshooting and security auditing.
    - Evidence: backend/app/main.py (no structured logging, no log levels configured)

74) No container restart policies defined
    - Impact: Services won't auto-restart on failure, reducing availability.
    - Evidence: docker-compose.yml (no restart: policy for any service)

75) Database volumes not backed up to external storage
    - Impact: Data loss if host fails, no disaster recovery.
    - Evidence: docker-compose.yml:129-132 (volumes defined but no backup strategy)

76) No secrets rotation mechanism
    - Impact: Compromised credentials remain valid indefinitely.
    - Evidence: No secret management tools (Vault, AWS Secrets Manager) integrated

77) Prometheus scrapes at 5s interval
    - Impact: May create unnecessary load on backend.
    - Evidence: monitoring/prometheus/prometheus.yml:6 (scrape_interval: 5s)

78) No intrusion detection or security monitoring
    - Impact: Security incidents go undetected.
    - Evidence: No security-focused monitoring (fail2ban, auditd, WAF) configured

79) No input validation on GEBCO_URL
    - Impact: Potential SSRF if URL accepts user input or is misconfigured.
    - Evidence: backend/app/config.py:31 (GEBCO_URL: Optional[str] = None, no URL validation)

80) No database user privilege separation
    - Impact: All database operations use same user with full permissions, violating principle of least privilege.
    - Evidence: backend/db/schema.sql (single user model, no read-only users)

81) No security headers in nginx
    - Impact: Missing protections against XSS, clickjacking, MIME sniffing.
    - Evidence: frontend/nginx.conf (no X-Frame-Options, X-Content-Type-Options, CSP)

82) Dockerfiles use latest tag
    - Impact: Unpredictable updates, potential breaking changes, security risks.
    - Evidence: docker-compose.yml:26 (minio/minio:latest), docker-compose.yml:39 (prom/prometheus:latest), docker-compose.yml:47 (grafana/grafana:latest)

83) No dependency vulnerability scanning
    - Impact: Vulnerable packages may be deployed.
    - Evidence: No pipeline for pip-audit, npm audit, or Snyk

84) No container image scanning
    - Impact: Vulnerable base images may be used.
    - Evidence: No trivy, grype, or similar scanning configured

85) No automatic dependency updates
    - Impact: Security patches may be delayed.
    - Evidence: No Dependabot, Renovate, or similar tools configured

86) Prometheus not persisted
    - Impact: Metrics lost on restart.
    - Evidence: docker-compose.yml:38-44 (no volumes for prometheus)

87) Grafana not persisted
    - Impact: Dashboards and settings lost on restart.
    - Evidence: docker-compose.yml:46-54 (no volumes for grafana)

88) No container resource requests
    - Impact: Poor scheduling in orchestration environments like Kubernetes.
    - Evidence: docker-compose.yml (no deploy.resources.requests for any service)

89) No explicit container version pinning
    - Impact: Inconsistent deployments, potential breaking changes.
    - Evidence: docker-compose.yml (postgres:16, redis:7 use major version only)

90) Unpaginated list queries
    - Impact: get_all() in base repository returns all rows without pagination, can return entire tables.
    - Evidence: backend/app/repositories/base.py:13-16, backend/app/routers/datasets.py:31-41

91) Missing indexes on partition-pruning columns
    - Impact: Queries without dataset_id in WHERE clause may scan all partitions instead of pruning.
    - Evidence: backend/db/schema.sql:49-53

92) Potential N+1 query pattern in dataset lookups
    - Impact: Multiple SELECT queries for datasets in one operation without caching or batch loading.
    - Evidence: backend/app/routers/ops.py:160-161

93) Large in-memory dataset loading without limits
    - Impact: Zonal stats loads up to 100,000 dggids into memory per dataset; could cause OOM errors.
    - Evidence: backend/app/routers/stats.py:62-67

94) Unpaginated spatial queries
    - Impact: Spatial join queries on large datasets without pagination can return excessive rows.
    - Evidence: backend/app/routers/ops.py:178-210,233-244

95) Missing composite index for common multi-column queries
    - Impact: Queries filtering by dataset_id + dggid + attr_key cannot efficiently use single-column indexes.
    - Evidence: backend/db/schema.sql:49-53 (no composite index on dataset_id, dggid, attr_key)

96) Inconsistent default value enforcement
    - Impact: ORM models specify defaults but DB schema uses DEFAULT constraints; discrepancies possible.
    - Evidence: backend/app/models.py:12,22,25,37 vs backend/db/schema.sql:15,18,62

97) Inconsistent error handling across routers
    - Impact: Unpredictable error responses make debugging and client error handling difficult.
    - Evidence: backend/app/routers/auth.py:42-46 vs backend/app/routers/toolbox.py:32-73 (different error handling patterns)

### Low
98) Missing ARIA Labels on Interactive Elements
    - Impact: Buttons and inputs lack proper ARIA labels, making application less accessible to screen reader users.
    - Evidence: frontend/src/pages/LoginPage.tsx:92-103; frontend/src/components/LayerList.tsx:21-26

99) Missing Keyboard Navigation Support
    - Impact: Interactive elements like dataset search dropdown and tool palette may not be fully keyboard navigable.
    - Evidence: frontend/src/components/DatasetSearch.tsx:58-106

100) Inconsistent Error Handling Across API Calls
    - Impact: Some API calls throw errors while others fail silently, creating unpredictable behavior.
    - Evidence: frontend/src/lib/dggal.ts:63-130 (returns null on errors); frontend/src/components/MapView.tsx:311-315

101) No Rate Limiting on Client-Side API Requests
    - Impact: Rapid viewport changes or user actions could trigger excessive API requests without throttling.
    - Evidence: frontend/src/components/MapView.tsx:268-286 (350ms debounce is minimal for complex operations)

102) Missing Loading State on Some Operations
    - Impact: Users may not receive feedback during long-running operations like polygon resolution.
    - Evidence: frontend/src/lib/dggal.ts:141-219; frontend/src/components/MapView.tsx:290-318

103) Logging potentially sensitive information
    - Impact: Logs may contain sensitive user data or query details.
    - Evidence: backend/app/routers/auth.py:24 (logs email), backend/app/services/ingest.py:136 (logs file paths)

104) Default CORS origin is localhost only
    - Impact: May need configuration for production deployment with different origins.
    - Evidence: backend/app/config.py:8 (CORS_ORIGIN defaults to "http://localhost:5173")

105) Database pool credentials in URL
    - Impact: Database connection URL contains credentials visible in environment variables and process listings.
    - Evidence: backend/app/config.py:6 (DATABASE_URL string includes credentials)

106) Excessive use of TypeScript 'any' type
    - Impact: Type safety compromised, defeats purpose of TypeScript strict mode.
    - Evidence: frontend/src/components/ToolModal.tsx:8,13,14,25,29; frontend/src/lib/toolRegistry.ts:13; frontend/src/pages/Workbench.tsx:19,63

107) Missing type hints in Python backend
    - Impact: Reduced code maintainability, IDE support limited.
    - Evidence: backend/app/services/spatial_engine.py:26-55 (no return types), backend/app/dggal_utils.py:42-52

108) Logger initialization inside functions
    - Impact: Performance overhead, poor logging practice.
    - Evidence: backend/app/routers/auth.py:22-23 (logger created per request)

109) No input validation on topology operations
    - Impact: Invalid input can cause crashes or undefined behavior.
    - Evidence: backend/app/routers/topology.py:14-16 (no Pydantic validation for dggid format)

110) Missing ESLint/Prettier configuration
    - Impact: Inconsistent code style, potential bugs.
    - Evidence: frontend/ lacks .eslintrc.json and .prettierrc files

111) Outdated npm packages with security implications
    - Impact: Known vulnerabilities remain unfixed.
    - Evidence: frontend/package.json - react 18.3.1 (latest 19.2.3), vite 5.4.21 (latest 7.3.1), framer-motion 11.18.2 (latest 12.28.1)

112) Build artifacts committed to repository
    - Impact: Bloated repository, security risk, deployment confusion.
    - Evidence: frontend/dist/ directory present, frontend/dist/assets/

113) Python cache files in repository
    - Impact: Repository bloat, false positives in git status.
    - Evidence: backend/app/routers/__pycache__/, backend/app/services/__pycache__/

114) Missing .env.example entries
    - Impact: Configuration changes not documented, deployment issues.
    - Evidence: backend/.env.example missing MINIO_BUCKET, GEBCO_MAX_IMAGE_PIXELS, LOAD_REAL_DATA

115) No API versioning
    - Impact: Breaking changes difficult, backward compatibility issues.
    - Evidence: backend/app/main.py:47-54 (all routes under /api/ without version prefix)

116) Missing unit tests
    - Impact: Code quality unverified, refactoring risky.
    - Evidence: backend/tests/ has only integration test; frontend/ has no test files

117) Inconsistent code indentation
    - Impact: Reduced readability, cognitive load for developers.
    - Evidence: backend/ uses 4-space indentation, frontend/ uses 2-space (though both specified in AGENTS.md)

118) Missing docstrings and JSDoc
    - Impact: Poor code documentation, maintenance difficulty.
    - Evidence: backend/app/routers/stats.py:24-129; frontend/src/components/MapView.tsx (no JSDoc)

119) Hardcoded DGGS name "IVEA3H"
    - Impact: Limited flexibility, magic numbers throughout codebase.
    - Evidence: backend/app/routers/toolbox.py:28, frontend/src/lib/dggal.ts:61

120) Duplicated serialization logic
    - Impact: Code duplication, maintenance overhead.
    - Evidence: backend/app/routers/datasets.py:19-29 (serialize_dataset)

121) Minimal Vite configuration
    - Impact: Suboptimal build performance and bundle size.
    - Evidence: frontend/vite.config.ts:4-9

122) No request size limits documented
    - Impact: Users unaware of upload limits.
    - Evidence: backend/app/config.py:27-28 (MAX_UPLOAD_BYTES not in .env.example)

123) Unused imports detected
    - Impact: Code bloat, potential confusion.
    - Evidence: frontend/src/components/MapView.tsx:4 (_GlobeView import unused)

124) Missing health check documentation
    - Impact: Monitoring setup unclear.
    - Evidence: backend/app/main.py:59-69 (health endpoint undocumented)

125) No content validation on file uploads
    - Impact: Malicious files can be uploaded if extension check bypassed.
    - Evidence: backend/app/routers/uploads.py:38-39 (only extension check, no magic number validation)

126) Basic SQL literal escaping in spatialDb.ts
    - Impact: Incomplete SQL injection protection in DuckDB queries.
    - Evidence: frontend/src/lib/spatialDb.ts:33 (single quote replacement only)

127) No database transaction rollback on errors
    - Impact: Data inconsistency on failures during upload processing.
    - Evidence: backend/app/routers/uploads.py:94 (await db.commit() without try/except rollback)

128) Missing Prometheus metrics documentation
    - Impact: Monitoring unclear.
    - Evidence: backend/app/main.py:56-57 (Instrumentator used but no metrics docs)

129) Duplicate entries in .gitignore
    - Impact: Confusing gitignore configuration.
    - Evidence: .gitignore:12-16 (node_modules, __pycache__, *.pyc duplicated)

130) PostgreSQL extensions installed without specific version
    - Impact: Potential compatibility issues or vulnerabilities.
    - Evidence: backend/db/schema.sql:1 (CREATE EXTENSION IF NOT EXISTS "pgcrypto" - no version pin)

131) Production console logging in frontend
    - Impact: Performance degradation, information leakage in production.
    - Evidence: frontend/src/lib/dggal.ts:78-107, frontend/src/lib/spatialDb.ts:62-85,102

132) Database password in connection URL
    - Impact: Credentials visible in process listings, logs, and docker inspect.
    - Evidence: docker-compose.yml:61, backend/.env.example:6, backend/app/db.py:6

## Testing Gaps
- Only one integration test exists (backend/tests/test_toolbox_integration.py)
- No unit tests for ingestion logic correctness
- No unit tests for spatial operations (buffer, expand, aggregate)
- No unit tests for zonal statistics correctness
- No frontend tests for components, store, or API integration
- No tests for security vulnerabilities (SQL injection, XSS, CSRF)
- No performance or load tests

## Open Questions / Assumptions
- Is backend_node_archive/ intentionally retained for backward compatibility, or should it be removed?
- Should default credentials be removed entirely and require explicit configuration for first deployment?
- Is SSL/TLS configuration intentionally omitted for development, or is this acceptable for production?
- Should MinIO be replaced with cloud-native storage (S3, GCS) for production deployments?
- Should database backup automation be implemented before production use?

## Comparison to Review_2
This review identifies several critical issues not captured in Review_2:
- SQL injection in ops.py (finding #4)
- SQL injection in partition table creation (finding #2)
- Missing foreign key on cell_objects.attr_key (finding #21)
- Unbounded connection pool (finding #23)
- No SSL/TLS for all services (findings #11-14)
- Database port exposed publicly (finding #16)
- No database backup mechanism (finding #19)
- Missing CSP headers (finding #20)
- No transaction isolation for partition operations (finding #22)

Additionally, this review provides more comprehensive infrastructure security findings and operational issues that impact production readiness.
