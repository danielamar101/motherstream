from fastapi import FastAPI

from sqlalchemy import Boolean, Column, Integer, String

from .database import Base


app = FastAPI()


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    stream_key = Column(String, unique=True)
    email = Column(String, unique=True, index=True)
    timezone = Column(String, default="")
    profile_picture = Column(String, nullable=True)
    dj_name = Column(String, unique=True)

    password = Column(String)

    is_active = Column(Boolean, default=True)
    is_superuser = Column(Boolean, default=False)
    is_superduper_user = Column(Boolean, default=False)


