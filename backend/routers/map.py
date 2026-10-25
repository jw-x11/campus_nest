from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query

from crud.map import GeocodeUnavailable, autocomplete_address, geocode_address
from schemas.users import UserInfoResponse
from utils.deps import get_current_user_info
from utils.rate_limit import rate_limit
from utils.response import success_response

# Router: /api/map
# Each request may call the geocoder, so map has its own lower limit.
api_map = APIRouter(dependencies=[Depends(rate_limit("map"))])


# Preview where an address lands on the map, for example before the listing form is submitted.
@api_map.get("/geocode")
async def geocode(
    user: Annotated[UserInfoResponse, Depends(get_current_user_info)],
    address: Annotated[str, Query(min_length=1, max_length=255)],
    city: Annotated[str, Query(min_length=1, max_length=100)],
    state: Annotated[str | None, Query(min_length=1, max_length=100)] = None,
    postal_code: Annotated[str | None, Query(min_length=1, max_length=10)] = None,
):
    try:
        coordinates = await geocode_address(address, city, state, postal_code)
    except GeocodeUnavailable:
        raise HTTPException(status_code=503, detail="GEOCODER_UNAVAILABLE")
    if coordinates is None:
        raise HTTPException(status_code=400, detail="GEOCODE_FAILED")

    latitude, longitude = coordinates
    return success_response(message="Location found", data={"latitude": latitude, "longitude": longitude})


# Street-address suggestions for the listing form while the user types.
@api_map.get("/autocomplete")
async def autocomplete(
    user: Annotated[UserInfoResponse, Depends(get_current_user_info)],
    text: Annotated[str, Query(min_length=3, max_length=255)],
):
    try:
        suggestions = await autocomplete_address(text)
    except GeocodeUnavailable:
        raise HTTPException(status_code=503, detail="GEOCODER_UNAVAILABLE")
    return success_response(message="Suggestions found", data={"suggestions": suggestions})
