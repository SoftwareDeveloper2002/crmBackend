from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from supabase import create_client, Client
import logging
import firebase_admin
from firebase_admin import credentials, db
import time

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
# Firebase setup
# -----------------
cred = credentials.Certificate("fbs.json")
firebase_admin.initialize_app(cred, {
    'databaseURL': 'https://rtechon-c3fa0-default-rtdb.asia-southeast1.firebasedatabase.app/'
})

# -----------------
# Router setup
# -----------------
sms_router = APIRouter(prefix="/sms", tags=["SMS"])

# -----------------
# Pydantic model
# -----------------
class SmsRequest(BaseModel):
    api_key: str
    number: str
    message: str

# -----------------
# Helper: validate API key and get user
# -----------------
def get_user_by_api_key(api_key: str):
    try:
        resp = supabase.table("users").select("*").eq("api_key", api_key).execute()
        if resp.data:
            return resp.data[0]
    except Exception as e:
        logging.error(f"Supabase error: {str(e)}")
    return None

# -----------------
# Endpoint: Send SMS
# -----------------
@sms_router.post("/send")
def send_sms(req: SmsRequest):
    logging.info(f"Received request: {req.dict()}")

    # Validate user via API key
    user = get_user_by_api_key(req.api_key)
    if not user:
        raise HTTPException(status_code=403, detail="Invalid API key")

    # Check credits
    credits = user.get("credits", 0)
    if credits <= 0:
        raise HTTPException(status_code=402, detail="Insufficient credits")

    # Ensure user has a device
    device_id = user.get("device_id")
    if not device_id:
        raise HTTPException(status_code=400, detail="No device registered")

    # Timestamp in milliseconds for Firebase
    timestamp_ms = int(time.time() * 1000)

    # -----------------
    # Queue SMS in Supabase (optional, can be skipped if using Firebase only)
    # -----------------
    try:
        response = supabase.table("sms_queue").insert({
            "user_id": user["user_id"],
            "number": req.number,
            "message": req.message,
            "status": "queued",
            "created_at": timestamp_ms  # store as integer for consistency
        }).execute()
        if not response.data:
            logging.warning("Failed to insert SMS into Supabase queue")
    except Exception as e:
        logging.error(f"Supabase insert failed: {e}")

    # -----------------
    # Push SMS to Firebase
    # -----------------
    try:
        ref = db.reference(f"devices/{device_id}/queue")
        new_sms_ref = ref.push({
            "api_key": req.api_key,
            "number": req.number,
            "message": req.message,
            "status": "queued",
            "timestamp": timestamp_ms
        })
        logging.info(f"Pushed SMS to Firebase with key: {new_sms_ref.key}")
    except Exception as e:
        logging.error(f"Failed to push SMS to Firebase: {e}")
        raise HTTPException(status_code=500, detail="Failed to queue SMS in Firebase")

    # -----------------
    # Deduct credits in Supabase
    # -----------------
    try:
        supabase.table("users").update({"credits": credits - 1}).eq("user_id", user["user_id"]).execute()
    except Exception as e:
        logging.error(f"Failed to deduct credits: {e}")

    return {"status": "queued", "remaining_credits": credits - 1}
