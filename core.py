# core.py
from fastapi import Header, HTTPException
from fastapi.concurrency import run_in_threadpool
import os
import requests

SUPABASE_URL = os.getenv("SUPABASE_URL", "https://wwpuorqzzvzuslbpukil.supabase.co")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")


async def get_current_user(authorization: str = Header(None)):
    """
    FastAPI dependency to fetch the current authenticated user from Supabase.
    Uses the REST API to validate JWT tokens.
    """
    if not authorization:
        raise HTTPException(status_code=401, detail="Unauthorized")

    token = authorization.replace("Bearer ", "")

    def fetch_user():
        url = f"{SUPABASE_URL}/auth/v1/user"
        headers = {
            "Authorization": f"Bearer {token}",
            "apikey": SUPABASE_SERVICE_ROLE_KEY
        }
        resp = requests.get(url, headers=headers, timeout=10)
        if resp.status_code != 200:
            raise HTTPException(status_code=401, detail="Invalid or expired token")
        return resp.json()

    try:
        user_response = await run_in_threadpool(fetch_user)
        return user_response
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Invalid or expired token: {str(e)}")
