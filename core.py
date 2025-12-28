from fastapi import Header, HTTPException
from fastapi.concurrency import run_in_threadpool
from supabase import Client

def get_current_user(authorization: str = Header(None)):
    if not authorization:
        raise HTTPException(status_code=401, detail="Unauthorized")

    token = authorization.replace("Bearer ", "")

    try:
        # Run blocking Supabase call in thread pool
        user_response = run_in_threadpool(
            lambda: supabase.auth.get_user(token)
        )

        # run_in_threadpool returns a coroutine → await it
        if hasattr(user_response, "__await__"):
            import asyncio
            user_response = asyncio.get_event_loop().run_until_complete(user_response)

        if not user_response or not getattr(user_response, "user", None):
            raise HTTPException(status_code=401, detail="Invalid token")

        return user_response

    except Exception as e:
        raise HTTPException(
            status_code=401,
            detail=f"Invalid or expired token: {str(e)}"
        )
