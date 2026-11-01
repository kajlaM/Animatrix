"""
auth.py
Authentication and security module.
Handles password hashing with PBKDF2-SHA256, JWT token generation,
and token validation via FastAPI's HTTPBearer dependency.

Resume Claim Backed:
"Implemented JWT authentication middleware to enforce strict data separation
 and secure user access to generated assets."
"""

import os
import datetime
from dotenv import load_dotenv
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from passlib.context import CryptContext
from sqlalchemy.orm import Session
from database import get_db
from models import User

# Load environment variables from .env file
load_dotenv()

# JWT Configuration
# SECRET_KEY must be supplied via the environment variable JWT_SECRET_KEY.
# If missing, fail fast with a descriptive error to prevent insecure defaults.
SECRET_KEY = os.getenv("JWT_SECRET_KEY")
if not SECRET_KEY:
    raise RuntimeError(
        "CRITICAL SECURITY CONFIGURATION ERROR:\n"
        "JWT_SECRET_KEY environment variable is not set.\n"
        "Please generate a secure secret key using:\n"
        "    python -c \"import secrets; print(secrets.token_hex(32))\"\n"
        "and add it to your .env file as JWT_SECRET_KEY=<key>"
    )

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60

# Password hashing context using PBKDF2-SHA256
# We explicitly avoid bcrypt to eliminate native C-binding compatibility issues
# while maintaining NIST-recommended cryptographic security.
pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")

# HTTPBearer scheme extracts the "Authorization: Bearer <token>" header from requests
security_bearer = HTTPBearer(auto_error=True)


def get_password_hash(password: str) -> str:
    """
    Hashes a plain text password using PBKDF2-SHA256 with a unique salt.
    """
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verifies that a plain text password matches the stored PBKDF2-SHA256 hash.
    """
    return pwd_context.verify(plain_password, hashed_password)


def create_access_token(data: dict) -> str:
    """
    Creates a signed JSON Web Token (JWT) with HS256 algorithm.
    Includes the 'sub' claim (username) and a timezone-aware expiration timestamp (exp).
    """
    to_encode = data.copy()

    # Timezone-aware UTC timestamp for expiration
    now_utc = datetime.datetime.now(datetime.timezone.utc)
    expire = now_utc + datetime.timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)

    to_encode.update({"exp": expire})

    # Encode and sign the JWT
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security_bearer),
    db: Session = Depends(get_db)
) -> User:
    """
    JWT authentication dependency / middleware.

    Resume Claim Backed:
    "Implemented JWT authentication middleware to enforce strict data separation
     and secure user access to generated assets."

    This dependency runs before protected route handlers. It extracts the Bearer token,
    decodes and verifies the signature using SECRET_KEY, extracts the username ('sub' claim),
    and queries the database for the matching User record.

    If the token is invalid, expired, or the user does not exist, it raises an HTTP 401 Unauthorized.
    """
    token = credentials.credentials
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        # Decode and verify token signature and expiration
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired. Please log in again.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.InvalidTokenError:
        raise credentials_exception

    # Look up user in database
    user = db.query(User).filter(User.username == username).first()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user

