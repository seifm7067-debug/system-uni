import argparse
import getpass
import os
import sys

from app.database import SessionLocal
from app.models.user import User, UserRole
from app.security.password import hash_password
from sqlalchemy import select
from sqlalchemy.orm import Session


def create_admin(email: str | None, username: str | None, password: str | None) -> None:
    # Resolve from environment variables if not supplied via arguments
    email = email or os.getenv("ADMIN_EMAIL")
    username = username or os.getenv("ADMIN_USERNAME")
    password = password or os.getenv("ADMIN_PASSWORD")

    # Prompt interactively for password if running in interactive terminal and password is missing
    if not password and sys.stdin.isatty():
        try:
            password = getpass.getpass("Enter admin password: ")
        except Exception:  # noqa: BLE001
            password = None

    missing = []
    if not email:
        missing.append("ADMIN_EMAIL / --email")
    if not username:
        missing.append("ADMIN_USERNAME / --username")
    if not password:
        missing.append("ADMIN_PASSWORD / --password")

    if missing:
        print(
            f"[CLI ERROR] Missing required parameters: {', '.join(missing)}",
            file=sys.stderr,
        )
        sys.exit(1)

    db: Session = SessionLocal()
    try:
        # Check for existing user with same email or username (Idempotent check)
        existing_user = db.execute(
            select(User).where((User.email == email) | (User.username == username))
        ).scalar_one_or_none()

        if existing_user:
            print(
                f"[CLI INFO] User with email '{email}' or username '{username}' already exists. Skipping creation."
            )
            sys.exit(0)

        # Create new admin user
        hashed = hash_password(password)
        new_admin = User(
            username=username,
            email=email,
            password_hash=hashed,
            role=UserRole.ADMIN,
        )
        db.add(new_admin)
        db.commit()
        db.refresh(new_admin)
        print(
            f"[CLI SUCCESS] Admin user '{username}' ({email}) created successfully with ID {new_admin.id}."
        )
        sys.exit(0)
    except Exception as e:  # noqa: BLE001
        db.rollback()
        print(f"[CLI ERROR] Failed to create admin user: {e}", file=sys.stderr)
        sys.exit(1)
    finally:
        db.close()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="University Management System CLI Tools"
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    admin_parser = subparsers.add_parser(
        "create-admin", help="Bootstrap initial admin user"
    )
    admin_parser.add_argument("--email", help="Admin email address")
    admin_parser.add_argument("--username", help="Admin username")
    admin_parser.add_argument("--password", help="Admin password")

    args = parser.parse_args()

    if args.command == "create-admin":
        create_admin(email=args.email, username=args.username, password=args.password)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
