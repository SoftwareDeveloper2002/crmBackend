from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from supabase import create_client, Client
from typing import Optional, List
import logging
from fastapi.middleware.cors import CORSMiddleware
from fastapi import FastAPI

logging.basicConfig(level=logging.INFO)

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

# -----------------
# FastAPI app & CORS
# -----------------
app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:4200"],  # Angular dev server
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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
    try:
        response = supabase.table("users").select("*").eq("api_key", api_key).execute()
        if response.data:
            return response.data[0]
    except Exception as e:
        logging.error(f"Supabase get_user_by_api_key error: {str(e)}")
    return None

def update_credits(user_id: str, new_credits: int) -> None:
    try:
        supabase.table("users").update({"credits": new_credits}).eq("user_id", user_id).execute()
    except Exception as e:
        logging.error(f"Supabase update_credits error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to update user credits")

# -----------------
# Endpoints
# -----------------
@router.post("/send")
def send_sms(req: SmsRequest):
    logging.info(f"Received SMS request: {req.dict()}")

    user = get_user_by_api_key(req.api_key)
    if not user:
        raise HTTPException(status_code=403, detail="Invalid API key")

    credits = user.get("credits", 0)
    if credits <= 0:
        raise HTTPException(status_code=402, detail="Insufficient credits")

    # Deduct 1 credit
    update_credits(user["user_id"], credits - 1)

    try:
        response = supabase.table("sms_queue").insert({
            "user_id": user["user_id"],
            "number": req.number,
            "message": req.message,
            "status": "queued"
        }).execute()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Supabase insert failed: {str(e)}")

    if not response.data:
        raise HTTPException(status_code=500, detail="Failed to insert SMS into queue")

    return {
        "status": "queued",
        "remaining_credits": credits - 1,
        "insert_response": response.data
    }

@router.post("/credits/add")
def add_credits(api_key: str, amount: int):
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
    try:
        response = supabase.table("sms_queue")\
            .select("*")\
            .eq("user_id", user_id)\
            .eq("status", "queued")\
            .limit(limit)\
            .execute()
    except Exception as e:
        logging.error(f"Supabase fetch queue error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch SMS queue")

    return response.data or []

@router.post("/queue/update_status")
def update_sms_status(update: QueueUpdate):
    try:
        response = supabase.table("sms_queue").update({"status": update.status})\
            .eq("id", update.sms_id)\
            .execute()
    except Exception as e:
        logging.error(f"Supabase update status error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to update SMS status")

    if not response.data:
        raise HTTPException(status_code=500, detail="No SMS updated")

    return {"status": "updated", "sms_id": update.sms_id, "new_status": update.status}

# -----------------
# Mount router
# -----------------