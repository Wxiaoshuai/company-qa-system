import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.core.auth_store import auth_store


def main() -> None:
    auth_store.init_db()
    auth_store.ensure_admin_user()
    print("Admin user initialization completed.")


if __name__ == "__main__":
    main()
