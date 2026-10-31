"""Password hashing and validation using industry-standard bcrypt."""
import bcrypt


def hash_password(plain_password: str) -> str:
    """Hash a plaintext password with salted bcrypt.
    Never stores or returns plaintext passwords.
    """
    if not plain_password:
        raise ValueError("Password cannot be empty")
    salt = bcrypt.gensalt(rounds=12)
    hashed = bcrypt.hashpw(plain_password.encode("utf-8"), salt)
    return hashed.decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a candidate password against the bcrypt hash."""
    if not plain_password or not hashed_password:
        return False
    try:
        return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))
    except Exception:
        return False
