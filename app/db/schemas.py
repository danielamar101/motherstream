# This file defines the pydantic models

from pydantic import BaseModel

class UserBase(BaseModel):
    stream_key: str
    email: str
    ip_address: str

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