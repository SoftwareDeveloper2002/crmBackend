from fastapi import APIRouter, HTTPException, FastAPI
from pydantic import BaseModel
from supabase import create_client, Client
from typing import Optional
import logging
from fastapi.middleware.cors import CORSMiddleware
import uuid
import jwt
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

SECRET_KEY = "supersecret"  # change this later
ALGORITHM = "HS256"

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

class DeviceLoginRequest(BaseModel):
    device_id: str
    token: str   # replaced api_key with token

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
# New: Generate QR payload
# -----------------
@router.get("/generate_qr")
def generate_qr(api_key: str):
    """
    Generate a device_id + signed token for QR code
    Frontend will turn this into a QR image.
    """
    user = get_user_by_api_key(api_key)
    if not user:
        raise HTTPException(status_code=403, detail="Invalid API key")

    device_id = str(uuid.uuid4())
    token = jwt.encode(
        {"user_id": user["user_id"], "device_id": device_id, "exp": time.time() + 600},
        SECRET_KEY,
        algorithm=ALGORITHM,
    )

    return {"device_id": device_id, "token": token}

# -----------------
# SMS Endpoints
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

    return {"status": "queued", "remaining_credits": credits - 1, "insert_response": response.data}

# -----------------
# Device Register via QR
# -----------------
@router.post("/add_device")
def add_device(req: DeviceLoginRequest):
    """
    Register device using QR token
    """
    try:
        decoded = jwt.decode(req.token, SECRET_KEY, algorithms=[ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="QR token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid QR token")

    if decoded["device_id"] != req.device_id:
        raise HTTPException(status_code=400, detail="Device ID mismatch")

    user_id = decoded["user_id"]

    try:
        response = supabase.table("devices").upsert({
            "user_id": user_id,
            "device_id": req.device_id
        }, on_conflict="device_id").execute()
    except Exception as e:
        logging.error(f"Supabase add_device error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to register device")

    if not response.data:
        raise HTTPException(status_code=500, detail="Device registration failed")

    return {"status": "success", "message": "Device registered", "user_id": user_id}

# -----------------
# Device fetch queued SMS
# -----------------
@router.get("/queue/fetch/{device_id}")
def fetch_sms_queue(device_id: str, limit: int = 50):
    try:
        device_resp = supabase.table("devices").select("user_id").eq("device_id", device_id).execute()
        if not device_resp.data:
            raise HTTPException(status_code=404, detail="Device not registered")
        user_id = device_resp.data[0]["user_id"]

        sms_resp = supabase.table("sms_queue")\
            .select("*")\
            .eq("user_id", user_id)\
            .eq("status", "queued")\
            .limit(limit)\
            .execute()
    except Exception as e:
        logging.error(f"Supabase fetch queue error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch SMS queue")

    return [
        {
            "sms_id": sms.get("id"),
            "number": sms.get("number"),
            "message": sms.get("message"),
            "status": sms.get("status")
        }
        for sms in sms_resp.data or []
    ]
