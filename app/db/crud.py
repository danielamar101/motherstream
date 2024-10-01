from sqlalchemy.orm import Session

from . import models, schemas

import bcrypt


def get_user(db: Session, user_id: int):
    return db.query(models.User).filter(models.User.id == user_id).first()

def get_user_by_stream_key(db: Session, stream_key: int):
    return db.query(models.User).filter(models.User.stream_key == stream_key).first()


def get_user_by_email(db: Session, email: str):
    return db.query(models.User).filter(models.User.email == email).first()


def get_users(db: Session, skip: int = 0, limit: int = 100):
    return db.query(models.User).offset(skip).limit(limit).all()


def create_user(db: Session, user: schemas.User):
    password = user.password
    salt = bcrypt.gensalt()
    hashed_password = bcrypt.hashpw(password.encode('utf-8'),salt)

    db_user = models.User(email=user.email, hashed_password=hashed_password, stream_key=user.stream_key, ip_address=user.ip_address, dj_name=user.dj_name)
    
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
        salt = bcrypt.gensalt()
        hashed_password = bcrypt.hashpw(password.encode('utf-8'), salt)
        db_user.hashed_password = hashed_password
    
    if user.stream_key:
        db_user.stream_key = user.stream_key
    
    if user.ip_address:
        db_user.ip_address = user.ip_address

    if user.email:
        db_user.email = user.email

    db.commit()
    db.refresh(db_user)

    return db_user
