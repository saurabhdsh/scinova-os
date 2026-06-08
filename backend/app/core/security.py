from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    if not hashed:
        return False
    # Legacy dev hashes from seed (sha256) — re-hash on next login if needed
    if len(hashed) == 64 and hashed.isalnum() and not hashed.startswith("$2"):
        import hashlib
        legacy = hashlib.sha256(f"scinova-dev-salt{plain}".encode()).hexdigest()
        return legacy == hashed
    return pwd_context.verify(plain, hashed)


def is_legacy_hash(hashed: str) -> bool:
    return bool(hashed) and len(hashed) == 64 and hashed.isalnum() and not hashed.startswith("$2")
