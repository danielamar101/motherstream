from fastapi import FastAPI
from pydantic import BaseModel, EmailStr


app = FastAPI()


class DJObject(BaseModel):
    stream_key: str
    email: EmailStr
    password: str
    ip_address: str
    full_name: str | None = None