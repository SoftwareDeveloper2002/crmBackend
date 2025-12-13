from fastapi import Header, HTTPException
from supabase import create_client, Client
import os

SUPABASE_URL = "https://wwpuorqzzvzuslbpukil.supabase.co"
SUPABASE_SERVICE_ROLE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Ind3cHVvcnF6enZ6dXNsYnB1a2lsIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc1ODc1Njk0NiwiZXhwIjoyMDc0MzMyOTQ2fQ.64t6V2e7_Wg085lwHFssNkAJrWNHMFLwSJwQkpmtKq4"

supabase: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)

def get_current_user(authorization: str = Header(None)):
    """
    Get the currently authenticated user using the Bearer token.
    Raises 401 if missing, invalid, or expired.
    """
    if not authorization:
        raise HTTPException(status_code=401, detail="Unauthorized")

    token = authorization.replace("Bearer ", "")

    try:
        user_response = supabase.auth.get_user(token)
        if not user_response or not getattr(user_response, "user", None):
            raise HTTPException(status_code=401, detail="Unauthorized")
        return user_response
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Invalid or expired token: {e}")
