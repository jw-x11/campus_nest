from typing import Annotated
from pydantic import BaseModel, ConfigDict, field_validator, StringConstraints
from datetime import datetime

MAX_DESCRIPTION_WORDS = 200

class UserInfoResponse(BaseModel):
    id: str
    email: str
    username: str
    phone: str | None = None
    university: str | None = None
    description: Annotated[str | None, StringConstraints(max_length=MAX_DESCRIPTION_WORDS)] = None
    avatar_url: str | None = None
    is_verified: bool = False
    created_at: datetime
    updated_at: datetime 

    model_config = ConfigDict(
        populate_by_name=True,
        from_attributes=True
    )

    @field_validator("id", mode="before")
    @classmethod
    def coerce_id_to_str(cls, v):
        return str(v)

class UserUpdateRequest(BaseModel):
    id: str | None = None
    email: str | None = None
    username: str | None = None
    phone: str | None = None
    university: str | None = None
    description: Annotated[str | None, StringConstraints(max_length=MAX_DESCRIPTION_WORDS)] = None
    avatar_url: str | None = None
    is_verified: bool = False

    