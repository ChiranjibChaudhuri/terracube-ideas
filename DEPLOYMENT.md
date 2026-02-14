# TerraCube IDEAS - Production Deployment Checklist

This checklist covers all steps required to deploy TerraCube IDEAS to production.

## Pre-Deployment Checklist

### 1. Configuration Review

- [ ] **Environment Variables**
  - [ ] Set `DATABASE_URL` to production PostgreSQL instance
  - [ ] Set `JWT_SECRET` to strong random string (min 32 characters)
  - [ ] Set `CORS_ORIGIN` to specific frontend domain (not `*`)
  - [ ] Set `MINIO_ENDPOINT`, `MINIO_PORT` to production MinIO
  - [ ] Set `MINIO_ACCESS_KEY`, `MINIO_SECRET_KEY` to strong values
  - [ ] Set `MINIO_BUCKET` to unique bucket name
  - [ ] Set `REDIS_HOST`, `REDIS_PORT` to production Redis

- [ ] **Security Settings**
  - [ ] Change default admin password
  - [ ] Set secure `ADMIN_EMAIL`
  - [ ] Review and update rate limits if needed

- [ ] **Feature Flags**
  - [ ] Set `LOAD_REAL_DATA` appropriately
  - [ ] Configure `RESULT_TTL_HOURS` for operation cleanup

### 2. Database Setup

- [ ] Run database schema: `psql -f db/db/schema.sql`
- [ ] **Critical:** Populate topology table:
  ```bash
  docker compose exec backend python -m app.scripts.init_database.py --levels 7 --dggs IVEA3H
  ```
- [ ] Verify topology population:
  ```bash
  docker compose exec backend python -c "
  from app.db import get_db_pool
  import asyncio
  async def check():
      pool = await get_db_pool()
      async with pool.acquire() as conn:
          result = await conn.fetchrow('SELECT COUNT(*) FROM dgg_topology')
          print(f'Topology rows: {result[0]}')
  asyncio.run(check())
  "
  ```
- [ ] Create database backups schedule
- [ ] Configure connection pooling limits

### 3. Infrastructure Setup

- [ ] **PostgreSQL**
  - [ ] Use managed PostgreSQL service (RDS, Cloud SQL, etc.)
  - [ ] Enable automated backups
  - [ ] Set connection pool size appropriate for instance
  - [ ] Enable SSL/TLS for connections

- [ ] **Redis**
  - [ ] Use managed Redis (ElastiCache, etc.)
  - [ ] Enable AOF for durability
  - [ ] Set max memory policy

- [ ] **MinIO**
  - [ ] Use managed MinIO/S3
  - [ ] Enable versioning on bucket
  - [ ] Set lifecycle policies for old files

### 4. SSL/Termination

- [ ] Configure reverse proxy (nginx/Caddy) with:
  - [ ] SSL certificate (Let's Encrypt or commercial)
  - [ ] HTTP to HTTPS redirect
  - [ ] Proper CORS headers
  - [ ] Rate limiting at proxy level
  - [ ] Request size limits
  - [ ] Timeouts for uploads

### 5. Monitoring Setup

- [ ] Enable structured JSON logging
- [ ] Configure log aggregation (ELK, CloudWatch, etc.)
- [ ] Set up alerts for:
  - [ ] Database connection failures
  - [ ] High error rates
  - [ ] High memory/CPU usage
  - [ ] Failed Celery tasks
- [ ] Configure Prometheus metrics scraping
- [ ] Set up dashboard (Grafana, etc.)

## Deployment Steps

### 1. Build and Deploy

```bash
# Build frontend
cd frontend
npm run build

# Build Docker images
docker compose build

# Tag for production
docker tag terracube-ideas-backend:latest terracube-ideas-backend:prod-$(git rev-parse --short HEAD)
docker tag terracube-ideas-frontend:latest terracube-ideas-frontend:prod-$(git rev-parse --short HEAD)
```

### 2. Database Migration

```bash
# If using existing database, run any migrations
# (Currently no migration system - schema is applied directly)
docker compose exec backend psql -f db/schema.sql
```

### 3. Initialize Data

```bash
# Populate topology (REQUIRED for spatial operations)
docker compose exec backend python -m app.scripts.init_database.py

# Optionally load real data
docker compose exec backend python -m app.scripts.load_real_data.py
```

### 4. Start Services

```bash
docker compose up -d
```

### 5. Verify Deployment

- [ ] Check health endpoint: `GET /api/health`
  - [ ] Status is "ok"
  - [ ] `topology_populated` is true
  - [ ] `topology_rows` > 0

- [ ] Check OpenAPI spec: `GET /openapi.json`
- [ ] Test authentication:
  ```bash
  curl -X POST http://your-domain/api/auth/register \
    -H "Content-Type: application/json" \
    -d '{"email":"test@example.com","password":"testpass123","name":"Test User"}'
  ```
- [ ] Test spatial operation (requires auth):
  ```bash
  curl -X POST http://your-domain/api/ops/spatial \
    -H "Authorization: Bearer YOUR_TOKEN" \
    -H "Content-Type: application/json" \
    -d '{"type":"union","datasetAId":"UUID","keyA":"value"}'
  ```

## Post-Deployment

### 1. Create Admin User

```bash
# Use registration endpoint or directly in database
curl -X POST http://your-domain/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@yourdomain.com","password":"STRONG_PASSWORD","name":"Administrator"}'
```

### 2. Configure Backups

- [ ] Database: Daily full backups, hourly incremental
- [ ] MinIO: Versioning enabled + lifecycle policy
- [ ] Redis: AOF + RDB snapshots

### 3. Set Up Log Retention

- [ ] Application logs: 30 days
- [ ] Audit logs: 1 year
- [ ] Access logs: 90 days

### 4. Document APIs

- [ ] Generate API documentation
- [ ] Document authentication flow
- [ ] Provide example scripts
- [ ] Document rate limits

## Monitoring and Maintenance

### Daily Checks

- [ ] Review error logs
- [ ] Check disk space
- [ ] Verify Celery worker processing
- [ ] Review operation result cleanup

### Weekly Tasks

- [ ] Review and optimize slow queries
- [ ] Clean up failed uploads
- [ ] Review user growth and capacity
- [ ] Security updates

### Monthly Tasks

- [ ] Database maintenance (VACUUM, analyze)
- [ ] Review and update topology if needed
- [ ] Capacity planning
- [ ] Security audit

## Rollback Procedures

### If Database Migration Fails

```bash
# 1. Stop writes
docker compose stop backend

# 2. Restore from backup
pg_restore -d database_name -f backup.dump

# 3. Verify data integrity
docker compose exec backend python -m app.scripts.init_database.py --check-only
```

### If New Deployment Fails

```bash
# 1. Revert to previous Docker image
docker compose pull terracube-ideas-backend:prod-PREVIOUS_COMMIT

# 2. Restart services
docker compose up -d

# 3. Investigate logs
docker compose logs backend --tail=500
```

## Security Considerations

### Required for Production

1. **Authentication**
   - All mutation endpoints require valid JWT
   - Tokens expire after configured duration
   - Passwords are bcrypt hashed

2. **Rate Limiting**
   - 200 requests/minute per IP
   - Exempt: health, metrics, docs, static assets

3. **CORS**
   - Specific origin only (no wildcard)
   - Credentials allowed for auth

4. **Input Validation**
   - UUID format validation
   - Dataset existence verification
   - DGGID sanitization
   - File size/type limits on upload

5. **SQL Injection**
   - Parameterized queries only
   - No string concatenation in SQL

6. **Secrets Management**
   - Use vault/secrets manager
   - Rotate JWT_SECRET periodically
   - Never log secrets

## Troubleshooting

### Spatial Operations Return Empty Results

**Cause:** Topology table not populated

**Fix:**
```bash
docker compose exec backend python -m app.scripts.init_database.py --levels 7
```

### High Memory Usage

**Cause:** Large viewport queries returning too many cells

**Fix:**
- Reduce max zoom level in client
- Add server-side limit to zone count
- Enable pagination

### Upload Processing Fails

**Cause:** Celery worker not running or file too large

**Fix:**
```bash
# Check worker status
docker compose logs celery-worker --tail=50

# Check file size limits in config
```

### Slow Queries

**Cause:** Missing indexes or large dataset scans

**Fix:**
- Run `VACUUM ANALYZE` on cell_objects tables
- Add composite indexes for common query patterns
- Consider partitioning for very large datasets

## Support Contacts

For deployment issues, check:
1. `/api/health` endpoint status
2. Application logs: `docker compose logs -f`
3. Database connection logs
4. This checklist and DEPLOYMENT.md
