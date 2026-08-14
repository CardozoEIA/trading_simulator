from fastapi import APIRouter, HTTPException

from app.core.supabase import supabase
from app.modules.users.schema import UserCreate


router = APIRouter(
    prefix="/users",
    tags=["Users"]
)


@router.post("/")
def create_user(user_data: UserCreate):

    try:
        response = supabase.auth.sign_up({
            "email": user_data.email,
            "password": user_data.password,
            "options": {
                "data": {
                    "name": user_data.name
                }
            }
        })

    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=str(e)
        )

    if response.user is None:
        raise HTTPException(
            status_code=400,
            detail="No se pudo crear el usuario"
        )

    return {
        "id": response.user.id,
        "email": response.user.email,
        "name": response.user.user_metadata.get("name")
    }