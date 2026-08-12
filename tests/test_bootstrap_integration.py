import pytest
from app.cli import create_admin
from app.database import SessionLocal
from app.models.user import User, UserRole
from app.security.password import verify_password
from sqlalchemy import select


def test_cli_create_admin_bootstrap():
    test_email = "unique_bootstrap_admin@test.com"
    test_username = "unique_bootstrap_admin"
    test_password = "SecureAdminPass123!"

    # Clean up any pre-existing test user
    db = SessionLocal()
    try:
        existing = (
            db.execute(
                select(User).where(
                    (User.email == test_email) | (User.username == test_username)
                )
            )
            .scalars()
            .all()
        )
        for u in existing:
            db.delete(u)
        db.commit()
    finally:
        db.close()

    # Execute CLI bootstrap command - expect SystemExit(0)
    with pytest.raises(SystemExit) as exc_info:
        create_admin(email=test_email, username=test_username, password=test_password)
    assert exc_info.value.code == 0

    # Verify created user in database
    db = SessionLocal()
    try:
        user = db.execute(
            select(User).where(User.email == test_email)
        ).scalar_one_or_none()

        assert user is not None
        assert user.username == test_username
        assert user.role == UserRole.ADMIN
        assert verify_password(test_password, user.password_hash)
    finally:
        db.close()

    # Re-run CLI to test Idempotency - expect SystemExit(0) without error
    with pytest.raises(SystemExit) as exc_info_idempotent:
        create_admin(email=test_email, username=test_username, password=test_password)
    assert exc_info_idempotent.value.code == 0

    # Count users to ensure no duplicate created
    db2 = SessionLocal()
    try:
        count = len(
            db2.execute(select(User).where(User.email == test_email)).scalars().all()
        )
        assert count == 1
    finally:
        db2.close()
