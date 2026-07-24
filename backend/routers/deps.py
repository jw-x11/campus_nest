from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

bearer = HTTPBearer()


async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(bearer)):
    # TODO: decode JWT, validate against Redis blacklist, return user_id
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail="Auth not implemented yet")
