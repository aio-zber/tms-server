#!/usr/bin/env python3
"""
Migration runner for deployment.
Runs Alembic migrations to upgrade database schema.
"""
import subprocess
import sys


def run_migrations():
    """Run alembic upgrade head."""
    print("=" * 80)
    print("🔄 Running database migrations...")
    print("=" * 80)

    try:
        result = subprocess.run(
            ["alembic", "upgrade", "head"],
            check=True,
            capture_output=True,
            text=True
        )

        print(result.stdout)
        if result.stderr:
            print("STDERR:", result.stderr)

        print("\n" + "=" * 80)
        print("✅ Migrations completed successfully!")
        print("=" * 80)
        return 0

    except subprocess.CalledProcessError as e:
        print("\n" + "=" * 80)
        print("❌ Migration failed!")
        print("=" * 80)
        print("STDOUT:", e.stdout)
        print("STDERR:", e.stderr)
        return 1
    except Exception as e:
        print("\n" + "=" * 80)
        print(f"❌ Unexpected error: {e}")
        print("=" * 80)
        return 1


if __name__ == "__main__":
    sys.exit(run_migrations())
