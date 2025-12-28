from fastapi import Header, HTTPException
from fastapi.concurrency import run_in_threadpool
from supabase import Client

# IMPORTANT: this function MUST be async
async def get_current_user(authorization: str = Header(None)):
    if not authorization:
        raise HTTPException(status_code=401, detail="Unauthorized")

    token = authorization.replace("Bearer ", "")

    try:
        # Run blocking Supabase call safely in threadpool
        user_response = await run_in_threadpool(
            lambda: supabase.auth.get_user(token)
        )

        if not user_response or not getattr(user_response, "user", None):
            raise HTTPException(status_code=401, detail="Invalid token")

        return user_response

    except Exception as e:
        raise HTTPException(
            status_code=401,
            detail=f"Invalid or expired token: {str(e)}"
        )
