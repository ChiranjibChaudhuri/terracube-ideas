#!/usr/bin/env python3
"""
Migration management script for TerraCube IDEAS.

Usage:
    python scripts/run_migrations.py              # Show current version
    python scripts/run_migrations.py current         # Show current version
    python scripts/run_migrations.py upgrade         # Run migrations
    python scripts/run_migrations.py downgrade --revision=001 # Downgrade to revision
"""
import sys
import os

# Add backend to path so we can import app modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

from alembic import command
from alembic.config import main

if __name__ == "__main__":
    # Change to migrations directory
    os.chdir("backend/migrations")

    alembic_args = [
        "upgrade", "head",
    "--raiseerr",
    "-c", "backend/migrations/alembic.ini",
    *sys.argv[1:]
    ]

    try:
        main(alembic_args)
    except Exception as e:
        print(f"Migration failed: {e}")
        sys.exit(1)
