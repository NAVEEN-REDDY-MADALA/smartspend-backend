from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def _truncate_for_bcrypt(password: str) -> str:
    return password.encode("utf-8")[:72].decode("utf-8", errors="ignore")

def hash_password(password: str) -> str:
    safe_password = _truncate_for_bcrypt(password)
    return pwd_context.hash(safe_password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    safe_password = _truncate_for_bcrypt(plain_password)
    return pwd_context.verify(safe_password, hashed_password)