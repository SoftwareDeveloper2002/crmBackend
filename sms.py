from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from supabase import create_client, Client
from typing import Optional, List

# -----------------
# Supabase setup
# -----------------
SUPABASE_URL = "https://wwpuorqzzvzuslbpukil.supabase.co"
SUPABASE_SERVICE_ROLE_KEY = (
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9."
    "eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Ind3cHVvcnF6enZ6dXNsYnB1a2lsIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc1ODc1Njk0NiwiZXhwIjoyMDc0MzMyOTQ2fQ."
    "64t6V2e7_Wg085lwHFssNkAJrWNHMFLwSJwQkpmtKq4"
)
supabase: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)

router = APIRouter(prefix="/sms", tags=["SMS"])

# -----------------
# Pydantic Models
# -----------------
class SmsRequest(BaseModel):
    number: str
    message: str
    api_key: str

class QueueUpdate(BaseModel):
    sms_id: int
    status: str  # queued, sent, failed

# -----------------
# DB Helpers
# -----------------
def get_user_by_api_key(api_key: str) -> Optional[dict]:
    response = supabase.table("users").select("*").eq("api_key", api_key).execute()
    if response.data:
        return response.data[0]
    return None

def update_credits(user_id: str, new_credits: int) -> None:
    supabase.table("users").update({"credits": new_credits}).eq("user_id", user_id).execute()

# -----------------
# Endpoints
# -----------------
@router.post("/send")
def send_sms(req: SmsRequest):
    """
    Queue an SMS for delivery by the Android device.
    Deducts 1 credit per SMS.
    """
    user = get_user_by_api_key(req.api_key)
    if not user:
        raise HTTPException(status_code=403, detail="Invalid API key")

    credits = user.get("credits", 0)
    if credits <= 0:
        raise HTTPException(status_code=402, detail="Insufficient credits")

    # Deduct 1 credit
    update_credits(user["user_id"], credits - 1)

    # Insert SMS into queue
    response = supabase.table("sms_queue").insert({
        "user_id": user["user_id"],
        "number": req.number,
        "message": req.message,
        "status": "queued"
    }).execute()

    if response.error:
        raise HTTPException(status_code=500, detail="Failed to queue SMS")

    return {
        "status": "queued",
        "remaining_credits": credits - 1
    }

@router.post("/credits/add")
def add_credits(api_key: str, amount: int):
    """
    Add credits to a user account.
    """
    user = get_user_by_api_key(api_key)
    if not user:
        raise HTTPException(status_code=403, detail="Invalid API key")

    new_credits = user.get("credits", 0) + amount
    update_credits(user["user_id"], new_credits)

    return {
        "status": "success",
        "new_credits": new_credits
    }

@router.get("/queue/{user_id}")
def get_sms_queue(user_id: str, limit: int = 50):
    """
    Fetch queued SMS messages for the Android device.
    Optional `limit` parameter to fetch only a subset.
    """
    response = supabase.table("sms_queue")\
        .select("*")\
        .eq("user_id", user_id)\
        .eq("status", "queued")\
        .limit(limit)\
        .execute()
    
    if response.error:
        raise HTTPException(status_code=500, detail="Failed to fetch SMS queue")

    return response.data or []

@router.post("/queue/update_status")
def update_sms_status(update: QueueUpdate):
    """
    Update the status of an SMS in the queue.
    """
    response = supabase.table("sms_queue").update({"status": update.status})\
        .eq("id", update.sms_id)\
        .execute()

    if response.error:
        raise HTTPException(status_code=500, detail="Failed to update SMS status")

    return {"status": "updated", "sms_id": update.sms_id, "new_status": update.status}
