from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from .. import schemas, crud
from ..security import get_current_user, ph
from ..main import get_db

user_router = APIRouter()

@user_router.get("/users/", response_model=list[schemas.User])
def read_users(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    users = crud.get_users(db, skip=skip, limit=limit)
    return users


@user_router.get("/users/{user_id}", response_model=schemas.User)
def read_user(user_id: int, db: Session = Depends(get_db)):
    db_user = crud.get_user(db, user_id=user_id)
    if db_user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return db_user

@user_router.put("/user/{user_id}", response_model=schemas.User)
def edit_user(user_id: int, db:Session = Depends(get_db)):
    db_user = crud.get_user(db, user_id=user_id)
    if db_user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return crud.edit_user(db=db,user=db_user)

@user_router.get("/", response_model=schemas.User)
def read_users(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    users = crud.get_users(db, skip=skip, limit=limit)
    return {"users": users}

@user_router.get("/api/v1/users/me", response_model=schemas.User)
def read_user_me(current_user: schemas.User = Depends(get_current_user)):
    return current_user

@user_router.delete("/api/v1/users/me", response_model=schemas.Message)
def delete_user_me(current_user: schemas.User = Depends(get_current_user), db: Session = Depends(get_db)):
    crud.delete_user(db, user_id=current_user.id)
    return {"message": "User deleted successfully"}

@user_router.patch("/api/v1/users/me", response_model=schemas.User)
def update_user_me(user_update: schemas.UserUpdateMe, current_user: schemas.User = Depends(get_current_user), db: Session = Depends(get_db)):
    updated_user = crud.update_user_me(db, user_id=current_user.id, user_update=user_update)
    return updated_user

@user_router.patch("/api/v1/users/me/password", response_model=schemas.Message)
def update_password_me(update_password: schemas.UpdatePassword, current_user: schemas.User = Depends(get_current_user), db: Session = Depends(get_db)):

    try:
        crud.update_password_me(db,user_id=current_user.id,update_password=update_password)
    except Exception as e:
        raise HTTPException(status_code=400, detail="Incorrect current password")
    return {"message": "Password updated successfully"}

@user_router.post("/api/v1/users/signup", response_model=schemas.User)
def register_user(user_register: schemas.UserBase, db: Session = Depends(get_db)):
    db_user = crud.get_user_by_email(db, email=user_register.email)
    if db_user:
        raise HTTPException(status_code=400, detail="Email already registered")
    user = crud.create_user(db=db, user=schemas.UserBase(email=user_register.email, password=user_register.password, dj_name=user_register.dj_name,timezone=user_register.timezone))
    return user

@user_router.get("/{user_id}", response_model=schemas.User)
def read_user_by_id(user_id: int, db: Session = Depends(get_db)):
    db_user = crud.get_user(db, user_id=user_id)
    if db_user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return schemas.User.model_validate(db_user)

@user_router.patch("/{user_id}", response_model=schemas.User)
def update_user(user_id: int, user_update: schemas.UserUpdateMe, db: Session = Depends(get_db)):
    db_user = crud.get_user(db, user_id=user_id)
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")
    # Implement update logic
    if user_update.email:
        db_user.email = user_update.email
    if user_update.dj_name:
        db_user.dj_name = user_update.dj_name
    # TODO: More logic
    db.commit()
    db.refresh(db_user)
    return schemas.User.model_validate(db_user)

@user_router.delete("/{user_id}", response_model=schemas.Message)
def delete_user(user_id: int, db: Session = Depends(get_db)):
    db_user = crud.get_user(db, user_id=user_id)
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")
    crud.delete_user(db, user_id=user_id)
    return {"message": "User deleted successfully"}