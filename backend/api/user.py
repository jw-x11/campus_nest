from fastapi import APIRouter

api_user = APIRouter()

@api_user.get('/')
def get_user():
    return {'user': 'hello'}