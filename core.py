# core.py
from fastapi import Header, HTTPException
from fastapi.concurrency import run_in_threadpool
import os
import requests
from types import SimpleNamespace
from supabase import create_client
from dotenv import load_dotenv  # load environment variables from .env

# -----------------------
# Load environment variables early
# -----------------------
load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY")  # optional, for client-side operations

# Optional debug prints (remove in production)
print("SUPABASE_URL =", SUPABASE_URL)
print("SUPABASE_SERVICE_ROLE_KEY =", SUPABASE_SERVICE_ROLE_KEY[:10], "...")
print("SUPABASE_ANON_KEY =", SUPABASE_ANON_KEY[:10], "...")

# -----------------------
# FastAPI Dependency: Get current user
# -----------------------
async def get_current_user(authorization: str = Header(None)):
    """
    Fetch the current authenticated user from Supabase.
    Returns a SimpleNamespace object with a .user attribute.
    """
    if not authorization:
        raise HTTPException(status_code=401, detail="Unauthorized")

    token = authorization.replace("Bearer ", "")

    def fetch_user():
        url = f"{SUPABASE_URL}/auth/v1/user"
        headers = {
            "Authorization": f"Bearer {token}",
            "apikey": SUPABASE_SERVICE_ROLE_KEY  # optional; can remove if using normal JWT
        }
        resp = requests.get(url, headers=headers, timeout=10)
        if resp.status_code != 200:
            raise HTTPException(status_code=401, detail="Invalid or expired token")
        return resp.json()

    try:
        user_data = await run_in_threadpool(fetch_user)
        return SimpleNamespace(user=SimpleNamespace(**user_data))
    except HTTPException:
        raise
    except Exception as e:
        msg = str(e)
        # Explicitly handle invalid JWT errors returned by Supabase
        if "invalid_grant" in msg or "Invalid JWT Signature" in msg:
            raise HTTPException(status_code=401, detail="Invalid or expired access token")
        # Fallback for other unexpected errors
        raise HTTPException(status_code=500, detail=msg)

# -----------------------
# Supabase Client Factory
# -----------------------
def get_supabase_client(service_role: bool = False):
    """
    Returns a Supabase client instance.
    - service_role=True uses the SERVICE_ROLE_KEY (full access, server-side)
    - Otherwise uses the ANON_KEY (restricted, client-level)
    """
    key = SUPABASE_SERVICE_ROLE_KEY if service_role else SUPABASE_ANON_KEY
    if not SUPABASE_URL or not key:
        raise RuntimeError("Supabase URL or API key not set in environment variables")
    return create_client(SUPABASE_URL, key)
