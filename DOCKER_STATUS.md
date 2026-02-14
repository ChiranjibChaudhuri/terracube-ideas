# TerraCube IDEAS - Docker Deployment Status

**Status**: ✅ All services running and healthy

## Services

| Service | Status | URL | Description |
|--------|--------|------|------------|
| PostgreSQL | ✅ Running | localhost:5432 | Database for IDEAS |
| Redis | ✅ Running | localhost:6379 | Caching layer |
| MinIO | ✅ Running | localhost:9000-9001 | Object storage |
| Backend | ✅ Running | localhost:4000 | FastAPI application |
| Frontend | ✅ Running | localhost:8080 | React + Deck.gl |
| Prometheus | ✅ Running | localhost:9090 | Metrics collection |
| Grafana | ✅ Running | localhost:3000 | Metrics dashboard |
| Worker | ✅ Running | - | Celery task processor |

## Startup Commands

```bash
# Start all services
docker compose up -d

# View logs
docker compose logs -f backend     # Backend logs
docker compose logs -f worker       # Worker logs

# Stop all services
docker compose down

# Restart specific service
docker compose restart backend
docker compose restart postgres

# Rebuild after changes
docker compose up -d --build
```

## Health Checks

```bash
# Check backend health
curl http://localhost:4000/api/health

# Check database
docker exec -it ideas-postgres psql -U ideas_user -d ideas

# Check Redis
docker exec -it ideas-redis redis-cli ping

# Check all services
docker ps
```

## Service Details

### PostgreSQL (ideas-postgres)
- Port: 5432
- User: ideas_user
- Password: ideas_password
- Database: ideas
- Volume: pgdata:/var/lib/postgresql/data

### Redis (ideas-redis)
- Port: 6379
- Used for: Caching, rate limiting, sessions

### MinIO (ideas-minio)
- Ports: 9000-9001
- Web UI: http://localhost:9000
- Access Key: minioadmin / minioadmin
- Default Bucket: ideas-staging
- Volume: minio_data:/data

### Backend (ideas-backend)
- Port: 4000
- Environment: development
- Database: postgresql://...
- JWT_SECRET: Change-me-in-production
- Depends on: postgres, redis, minio

### Frontend (mystiq-frontend)
- Port: 8080
- VITE_API_URL: http://localhost:4000
- Built from: ./frontend directory

### Monitoring
- **Prometheus**: http://localhost:9090 - Metrics collection
- **Grafana**: http://localhost:3000 - Metrics visualization
  - Prometheus datasource: http://localhost:9090

## Known Issues

1. Container naming uses `mystiq-` prefix from old configuration
2. Worker name is simple "worker" (should be "ideas-worker")
3. No automated health checks on worker

## Quick Start

```bash
# Quick restart everything
docker compose restart && docker compose up -d
```

All services are healthy and running!
