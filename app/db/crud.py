from sqlalchemy.orm import Session
import string
import random

from . import models, schemas
from .security import ph
from .models import User

def get_user(db: Session, user_id: int):
    return db.query(models.User).filter(models.User.id == user_id).first()

def get_user_by_stream_key(db: Session, stream_key: int):
    return db.query(models.User).filter(models.User.stream_key == stream_key).first()


def get_user_by_email(db: Session, email: str):
    return db.query(models.User).filter(models.User.email == email).first()


def get_users(db: Session, skip: int = 0, limit: int = 100):
    return db.query(models.User).offset(skip).limit(limit).all()


def create_user(db: Session, user: schemas.UserBase):
    password = user.password
    hashed_password = ph.hash(password)

    stream_key = ''.join(random.choices(string.ascii_uppercase + string.digits, k=10))

    db_user = models.User(
        email=user.email,
        password=hashed_password,
        stream_key=stream_key,
        dj_name=user.dj_name,
        timezone=user.timezone,
        profile_picture=user.profile_picture or None,
    )
    
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user

def edit_user(db: Session, user_id: int, user: schemas.User):
    # Fetch the existing user from the database
    db_user = db.query(models.User).filter(models.User.id == user_id).first()

    # Update fields as needed
    if user.email:
        db_user.email = user.email

    if user.password:
        password = user.password 
        hashed_password = ph.hash(password.encode('utf-8'))
        db_user.hashed_password = hashed_password
    
    if user.stream_key:
        db_user.stream_key = user.stream_key
    
    if user.ip_address:
        db_user.ip_address = user.ip_address

    if user.email:
        db_user.email = user.email
    if user.timezone:
        db_user.timezone = user.timezone
    if user.profile_picture is not None:
        db_user.profile_picture = user.profile_picture or None

    db.commit()
    db.refresh(db_user)

    return db_user

def update_user_me(db: Session, user_id: int, user_update: schemas.UserUpdateMe):
    db_user = get_user(db, user_id)
    if db_user:
        db_user.dj_name = user_update.dj_name or db_user.dj_name
        db_user.email = user_update.email or db_user.email
        db_user.stream_key = user_update.stream_key or db_user.stream_key
        db_user.timezone = user_update.timezone or db_user.timezone
        if user_update.profile_picture is not None:
            db_user.profile_picture = user_update.profile_picture or None

        db.commit()
        db.refresh(db_user)
    return db_user

def update_password_me(db: Session, user_id: int, update_password: schemas.UpdatePassword):
    user = get_user(db, user_id=user_id)

    try:
        if not ph.verify(user.password,update_password.current_password):
            raise Exception("Incorrect current password")
        new_hashed_password = ph.hash(update_password.new_password)
        user.password = new_hashed_password
        db.commit()
    except Exception as e:
        print(f"Error updating password: {e}")
        return False
    
def delete_user(db: Session, user_id: int):
    db_user = get_user(db, user_id)
    if db_user:
        db.delete(db_user)
        db.commit()
    return