from fastapi import APIRouter, Depends, HTTPException

from app.core.supabase import supabase
from app.core.dependencies import get_current_user
from app.modules.auth.schema import UserLogin


router = APIRouter(
    prefix="/auth",
    tags=["Authentication"]
)


@router.get("/me")
def get_me(
    current_user=Depends(get_current_user)
):
    return {
        "id": current_user.id,
        "email": current_user.email,
        "name": current_user.user_metadata.get("name")
    }


@router.post("/login")
def login(user_data: UserLogin):
    
    try:
        response = supabase.auth.sign_in_with_password({
            "email": user_data.email,
            "password": user_data.password
        })
    except Exception:
        raise HTTPException(
            status_code=401,
            detail="Incorrect email or password"
        )

    if response.session is None:
        raise HTTPException(
            status_code=401,
            detail="Could not sign in"
        )

    return {
        "access_token": response.session.access_token,
        "refresh_token": response.session.refresh_token,
        "token_type": "bearer"
    }