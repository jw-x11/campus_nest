from typing import Annotated

from pydantic import AfterValidator, BaseModel, ConfigDict, EmailStr, Field, field_validator

from schemas.users import UserInfoResponse

MIN_PASSWORD_LENGTH = 8
MAX_PASSWORD_LENGTH = 72  # bcrypt only hashes the first 72 bytes
MAX_USERNAME_LENGTH = 50


def _within_bcrypt_limit(password: str) -> str:
    if len(password.encode("utf-8")) > MAX_PASSWORD_LENGTH:
        raise ValueError(f"password must be at most {MAX_PASSWORD_LENGTH} bytes")
    return password


class AuthRegisterRequest(BaseModel):
    email: EmailStr
    password: Annotated[
        str,
        Field(min_length=MIN_PASSWORD_LENGTH, max_length=MAX_PASSWORD_LENGTH),
        AfterValidator(_within_bcrypt_limit),
    ]
    username: Annotated[str, Field(min_length=1, max_length=MAX_USERNAME_LENGTH)]

    @field_validator("email", "username", mode="before")
    @classmethod
    def strip_text(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip()
        return value


class AuthLoginRequest(BaseModel):
    email: EmailStr
    password: Annotated[
        str,
        Field(min_length=1, max_length=MAX_PASSWORD_LENGTH),
        AfterValidator(_within_bcrypt_limit),
    ]

    @field_validator("email", mode="before")
    @classmethod
    def strip_email(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip()
        return value

class AuthLoginResponse(BaseModel):
    user_info: Annotated[UserInfoResponse, Field(alias="userInfo")]
    token: str

    model_config = ConfigDict(
        populate_by_name=True,
        form_attributes=True
    )

class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: Annotated[
        str,
        Field(min_length=MIN_PASSWORD_LENGTH, max_length=MAX_PASSWORD_LENGTH),
        AfterValidator(_within_bcrypt_limit),
    ]