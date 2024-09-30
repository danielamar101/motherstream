from fastapi import FastAPI

from sqlalchemy import Boolean, Column, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from .database import Base
from pydantic import BaseModel, EmailStr


app = FastAPI()


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    stream_key = Column(String, unique=True)
    email = Column(String, unique=True, index=True)
    timezone = Column(String, default='')
    
    ip_address = Column(String, default='')

    hashed_password = Column(String)
    
    is_active = Column(Boolean, default=True)


