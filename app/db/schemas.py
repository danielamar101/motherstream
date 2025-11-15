# This file defines the pydantic models

from typing import Type, Optional
from pydantic import BaseModel
# from .database import Base

class UserBase(BaseModel):
    email: str
    password: str
    dj_name: str
    timezone: str
    profile_picture: Optional[str] = None


    class Config:
        orm_model = True

class OAuth2Login(BaseModel):
    email: str
    password: str

# For creating users
class UserCreate(UserBase):
    stream_key: str
        
    is_active: bool
    is_superuser: bool
    pass
#For interacting with already created users
class User(UserCreate):
    id: int

    model_config = {
        'from_attributes': True
    }

# For returning paginated users list
class UsersPublic(BaseModel):
    data: list[User]
    count: int
    
class UserUpdateMe(BaseModel):
    dj_name: Optional[str] = None
    stream_key: Optional[str] = None
    email: Optional[str] = None
    password: Optional[str] = None
    timezone: Optional[str] = None
    profile_picture: Optional[str] = None

# # Function to convert SQLAlchemy model to Pydantic model
# def sqlalchemy_to_pydantic(instance: Type[Base], pydantic_model: Type[BaseModel]) -> BaseModel:
#     # Extract fields from the SQLAlchemy instance and map them to the Pydantic model
#     model_dict = {
#         'id': instance.id,
#         'stream_key': instance.stream_key,
#         'email': instance.email,
#         'dj_name': instance.dj_name,
#         'ip_address': instance.ip_address,
#         'timezone': instance.timezone,
#         'is_active': instance.is_active
#     }
#     # Return the Pydantic model instance
#     return pydantic_model(**model_dict)


class Token(BaseModel):
    access_token: str
    token_type: str

# Message Schema
class Message(BaseModel):
    message: str

# Password Reset Schemas
class NewPassword(BaseModel):
    token: str
    new_password: str

class UpdatePassword(BaseModel):
    current_password: str
    new_password: str