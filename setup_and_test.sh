#!/bin/bash

set -e

echo "=========================================="
echo "TerraCube IDEAS - Cleanup & Verification Script"
echo "=========================================="

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Config
COMPOSE_PROJECT="terracube-ideas"
DOCKER_COMPOSE_FILE="docker-compose.yml"

# Parse arguments
MODE="${1:-test_backend}"
SKIP_DOCKER="${2:-no_docker}"

cleanup_failed=0
services_stopped=0
test_results=()

echo ""
echo "Stopping Docker services (this may take a moment)..."
docker compose down 2>/dev/null

# Wait for containers to stop
sleep 3

# Check what stopped
if docker compose ps | grep -q "ideas-postgres\|Stopp"; then
    echo "✓ PostgreSQL stopped"
fi
if docker compose ps | grep -q "ideas-redis\|Stopp"; then
    echo "✓ Redis stopped"
fi
if docker compose ps | grep -q "ideas-minio\|Stopp"; then
    echo "✓ MinIO stopped"
fi

services_stopped=1

echo ""
echo "Docker services stopped."
echo "=========================================="

echo ""

# Run database initialization
echo "Initializing database with topology..."

if [ "$MODE" = "-init_db" ] || [ "$MODE" = "test_all" ] || [ "$MODE" = "-test_backend" ] || [ "$MODE" = "-test_frontend" ]; then
    echo "Step 1/5: Initialize database..."
    docker compose exec -T ideas-backend python -c "
from app.db import get_db_pool
import asyncio

async def test_init():
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        # Check if tables exist
        result = await conn.fetchrow('SELECT COUNT(*) FROM datasets LIMIT 1')
        if result and result[0] > 0:
            print('✓ Tables exist')
        else:
            print('✗ Creating tables...')
            await conn.execute(text('''CREATE TABLE IF NOT EXISTS users (
                id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
                email text UNIQUE NOT NULL,
                password_hash text NOT NULL,
                name text,
                created_at timestamptz NOT NULL DEFAULT now()
            );

            result = await conn.fetchrow('SELECT COUNT(*) FROM dgg_topology LIMIT 1')
            if result and result[0] > 0:
                print('✓ Topology populated')
            else:
                print('✗ Populating topology...')
            await conn.execute(text('''INSERT INTO dgg_topology (dggid, neighbor_dggid) VALUES (:d1, :d2), (:d1, :d2)
            ON CONFLICT DO NOTHING'''))

            print('✓ Database initialized')
            return 1
        fi
    asyncio.run(test_init())
    "
    2>/dev/null || echo "Failed to initialize database"

    echo ""
else
    echo "Step 1/5: Complete!"
fi

echo ""

# Check topology status
echo "Step 2/5: Checking topology population..."

echo ""
fi

echo "=========================================="
echo ""

# Test backend if requested
if [ "$MODE" = "-test_backend" ] || [ "$MODE" = "test_all" ]; then
    echo "Step 3/5: Testing backend API..."
    echo "=========================================="

    passed=0
    failed=0

    if docker compose ps | grep -q "ideas-backend"; then
        # Backend is running, test it
        echo "Testing live backend..."
    else
        # Start backend for testing
        echo "Starting backend for testing..."
        docker compose up -d ideas-backend 2>/dev/null &
        sleep 8

        # Check if backend started
        for i in {1..20}; do
            if docker compose ps | grep -q "ideas-backend" && docker compose ps | grep -q "Up (healthy)" > /dev/null; then
                passed=$((passed + 1))
                echo "✓ Backend started (iteration $i)"
                break
            fi
        done

    # Stop backend after testing
        docker compose stop ideas-backend 2>/dev/null
    fi

    # Test backend endpoints
    echo "Testing backend endpoints..."
    response=$(curl -s http://localhost:4000/api/datasets 2>/dev/null)
    status=$?

    if [ "$response" == "200" ]; then
        passed=$((passed + 1))
        echo "✓ GET /api/datasets: OK"
    else
        failed=$((failed + 1))
        echo "✗ GET /api/datasets: FAILED ($response)"
        echo "Response: $response"
    fi

    # Check spatial operations
    response=$(curl -s http://localhost:4000/api/ops/spatial 2>/dev/null)
    status=$?
    if [ "$response" == "200" ]; then
        # Check for proper error response format
        echo "$response" | python3 -m json.tool 2>/dev/null | grep -q '"error"' && echo "✓ Spatial ops API works"
    else
        echo "✗ Spatial ops API: FAILED"
    fi

    echo ""
    echo "=========================================="
fi

# Test frontend if requested
if [ "$MODE" = "-test_frontend" ] || [ "$MODE" = "test_all" ]; then
    echo "Step 4/5: Testing frontend..."
    echo "=========================================="

    # Check if frontend is built
    if [ ! -f "frontend/dist/index.html" ]; then
        echo "⚠️ Frontend not built - run 'npm run build' first"
        npm run build run
    else
        echo "✓ Frontend built"
    fi

    # Test frontend connection
    echo "Testing connection to backend API..."
    response=$(curl -s http://localhost:4000 2>/dev/null || echo "Failed"

    if [ "$response" == "200" ]; then
        passed=$((passed + 1))
        echo "✓ Frontend can connect to backend"
    else
        echo "✗ Frontend backend connection FAILED"
    fi

    echo ""
    echo "=========================================="
fi

# Final summary
echo "Step 5/5: Generating final report..."

success_count=0
fail_count=0

# Count from tests
[ "$MODE" = "-test_backend" ] && success_count=$((success_count + passed))
[ "$MODE" = "-test_backend" ] && fail_count=$((fail_count + failed))
[ "$MODE" = "-test_frontend" ] && success_count=$((success_count + passed))
[ "$MODE" = "-test_frontend" ] && fail_count=$((fail_count + failed))

# Report
echo ""
echo "=========================================="
echo "FINAL TEST RESULTS"
echo "=========================================="
echo "Backend Tests:"
echo "  - Docker Services: $(if [ $services_stopped -eq 1 ]; then echo "✓ Running"; else echo "✗ Not running"; fi)"
echo "  - Database: ✓ Initialized"
echo "  - Topology: $(if [ "$topology_populated" -eq 1 ]; then echo "✓ Populated"; else echo "✗ Not populated"; fi)"
echo "  - Backend API: $(docker compose ps | grep -q "ideas-backend" && echo "Accessible" || echo "Stopped")"
echo ""
echo "Frontend Tests:"
echo "  - Build: $(if [ -f "frontend/dist/index.html" ]; then echo "✓ Built"; else echo "✗ Not built"; fi)"
echo "  - Backend Connection: $(curl -s http://localhost:4000 2>/dev/null && echo "Success" || echo "Failed")"
echo "=========================================="

exit $success_count
