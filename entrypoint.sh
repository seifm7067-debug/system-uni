#!/usr/bin/env sh
set -e

echo "[ENTRYPOINT] Waiting for database readiness..."

python3 - << 'EOF'
import sys
import time
import os
from sqlalchemy import create_engine, text

db_url = os.getenv("DATABASE_URL")
if not db_url:
    print("[ENTRYPOINT ERROR] DATABASE_URL environment variable is not set.", file=sys.stderr)
    sys.exit(1)

max_attempts = 30
for attempt in range(1, max_attempts + 1):
    try:
        engine = create_engine(db_url, connect_args={"connect_timeout": 3})
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        print(f"[ENTRYPOINT SUCCESS] Database is ready (attempt {attempt}/{max_attempts}).")
        sys.exit(0)
    except Exception as e:
        print(f"[ENTRYPOINT INFO] Database not ready yet (attempt {attempt}/{max_attempts}): {e}")
        time.sleep(1)

print("[ENTRYPOINT ERROR] Database connection timed out after max attempts.", file=sys.stderr)
sys.exit(1)
EOF

if [ "${RUN_MIGRATIONS:-true}" = "true" ]; then
    echo "[ENTRYPOINT] Running Alembic database migrations..."
    uv run alembic upgrade head
    echo "[ENTRYPOINT] Migration successful."
fi

echo "[ENTRYPOINT] Starting application process..."
exec "$@"
