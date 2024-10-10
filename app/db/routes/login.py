from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException, status, Form
from sqlalchemy.orm import Session


from .. import schemas, security
from ..security import authenticate_user, create_access_token
from ..main import get_db

login_router = APIRouter()

@login_router.post("/api/v1/login/access-token")
def login_access_token(
    username: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db)):
    
    form_data = schemas.OAuth2Login(email=username, password=password)

    user = authenticate_user(db, email=form_data.email, password=form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token_expires = timedelta(minutes=security.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.email}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}

@login_router.post("/test-token")
def test_token(current_user: schemas.User = Depends(security.get_current_user)):
    return current_user
