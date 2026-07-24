from fastapi import APIRouter, Depends, UploadFile, File
from pydantic import BaseModel
from routers.deps import get_current_user

api_users = APIRouter()


class UserResponse(BaseModel):
    id: str
    email: str
    full_name: str
    phone: str | None
    university: str | None
    is_verified: bool
    avatar_url: str | None


class UpdateUserRequest(BaseModel):
    full_name: str | None = None
    phone: str | None = None
    university: str | None = None


@api_users.get("/me", response_model=UserResponse)
async def get_me(user_id: str = Depends(get_current_user)):
    """
    Returns the authenticated user's full profile.
    Requires a valid JWT. Used to populate the profile page on the frontend.
    """
    # TODO: fetch user from DB by user_id
    pass


@api_users.put("/me", response_model=UserResponse)
async def update_me(body: UpdateUserRequest, user_id: str = Depends(get_current_user)):
    """
    Updates the authenticated user's editable fields (name, phone, university).
    Email is excluded — changing email requires a separate verification flow.
    """
    # TODO: update user fields in DB
    pass


@api_users.post("/me/avatar", response_model=UserResponse)
async def upload_avatar(file: UploadFile = File(...), user_id: str = Depends(get_current_user)):
    """
    Uploads a new avatar image to SeaweedFS and updates the user's avatar_url.
    Replaces any previously uploaded avatar.
    """
    # TODO: upload file to SeaweedFS, save URL to user.avatar_url
    pass


@api_users.get("/{user_id}", response_model=UserResponse)
async def get_user(user_id: str):
    """
    Returns the public profile of any user by ID.
    Used on space listing pages to show lister info to potential renters.
    No auth required — profile data shown here should be non-sensitive.
    """
    # TODO: fetch public profile from DB
    pass
