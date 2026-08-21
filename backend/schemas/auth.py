from pydantic import BaseModel


class AuthRegisterRequest(BaseModel):
    email: str
    password: str
    full_name: str


class AuthLoginRequest(BaseModel):
    email: str
    password: str
