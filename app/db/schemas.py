# This file defines the pydantic models

from typing import Type
from pydantic import BaseModel
# from .database import Base

class UserBase(BaseModel):
    stream_key: str
    email: str
    ip_address: str
    dj_name: str

    class Config:
        orm_model = True

# For creating users
class UserCreate(UserBase):
    password: str
    pass
#For interacting with already created users
class User(UserBase):
    id: int

    class Config:
        orm_model = True

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