from fastapi import APIRouter, HTTPException, Form
from pydantic import EmailStr
from core import supabase
import os

# ========================
#  Router Setup
# ========================
forget_router = APIRouter(prefix="/auth", tags=["Forgot Password"])

# ========================
#  Configuration
# ========================
RESET_REDIRECT_URL = "https://r-techon.vercel.app/resetpass/setnew"

# ========================
#  API Endpoints
# ========================

@forget_router.post("/forgot-password", include_in_schema=False)
async def forgot_password(email: EmailStr = Form(...)):
    """
    Send Supabase's built-in password reset email
    """
    try:
        # ✅ Get all users
        users = supabase.auth.admin.list_users()
        
        # ✅ Check if email exists in Supabase Auth
        if isinstance(users, list):
            user_list = users
        elif hasattr(users, "users"):
            user_list = users.users
        else:
            user_list = []
        
        target_user = next((u for u in user_list if getattr(u, "email", None) == email), None)
        if not target_user:
            raise HTTPException(status_code=404, detail="Email not found")

        # ✅ Send Supabase reset email
        supabase.auth.reset_password_email(
            email=email,
            options={"redirect_to": RESET_REDIRECT_URL}
        )

        print(f"📧 Sent Supabase password reset link to {email}")
        return {"success": True, "message": "Password reset link sent to your email."}

    except HTTPException:
        raise
    except Exception as e:
        print("❌ Error in forgot_password:", e)
        raise HTTPException(status_code=500, detail=str(e))


@forget_router.post("/reset-password", include_in_schema=False)
async def reset_password(access_token: str = Form(...), new_password: str = Form(...)):
    """
    Complete the password reset using Supabase access token.
    """
    try:
        print("🟡 Received reset request with access_token:", access_token[:30], "...")

        # ✅ Update password using Supabase Admin API
        response = supabase.auth.admin.update_user(
            attributes={"password": new_password},
            access_token=access_token
        )

        print("✅ Password reset successful.")
        return {"success": True, "message": "Password reset successful."}

    except Exception as e:
        print("❌ Error in reset_password:", e)
        raise HTTPException(status_code=500, detail=str(e))
