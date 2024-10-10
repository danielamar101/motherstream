from datetime import timedelta
import time
from typing import Optional

from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session

import os
import jwt
import logging

logger = logging.getLogger()

from . import schemas, crud
from .main import get_db

# Secret key to encode JWT
JWT_SECRET = os.environ.get("JWT_SECRET",None)
if not JWT_SECRET:
    raise Exception("JWT_SECRET env var is required.")

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

from argon2 import PasswordHasher, exceptions
ph = PasswordHasher()



def authenticate_user(db: Session, email: str, password: str):

    user = crud.get_user_by_email(db, email=email)

    try:
        if not user:
            return False
        if not ph.verify(user.password, password):
            return False
    except exceptions.VerifyMismatchError as e:
        logger.exception(f"Error finding user or verifying password.")
        return False
    return user

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    expire = time.time() + (expires_delta.total_seconds() if expires_delta else timedelta(minutes=15).total_seconds())
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, JWT_SECRET, algorithm=ALGORITHM)
    return encoded_jwt

from fastapi.security import OAuth2PasswordBearer

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/login/access-token")

def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            raise credentials_exception
    except Exception as e:
        raise credentials_exception
    user = crud.get_user_by_email(db, email=email)
    if user is None:
        raise credentials_exception
    return schemas.User.model_validate(user)