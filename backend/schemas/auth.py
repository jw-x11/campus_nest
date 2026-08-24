from pydantic import BaseModel,ConfigDict, Field
from schemas.users import UserInfoResponse
from typing import Annotated


class AuthRegisterRequest(BaseModel):
    email: str
    password: str
    username: str


class AuthLoginRequest(BaseModel):
    email: str
    password: str

class AuthLoginResponse(BaseModel):
    user_info: Annotated[UserInfoResponse, Field(..., alias="userInfo")]
    token: str

    model_config = ConfigDict(
        populate_by_name=True,
        form_attributes=True
    )

class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str