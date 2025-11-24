from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, EmailStr
from datetime import datetime
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail
import smtplib
import os
import uuid
import secrets
import firebase_admin
from collections import Counter, defaultdict
from datetime import datetime
from firebase_admin import credentials, db
# Import routers
from sms import sms_router
from payment import payment_router
from forget import forget_router
from adm_login import admin_router
# Import shared Supabase + Auth helpers
from core import supabase, get_current_user

# =======================
#   Email Config
# =======================
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
SMTP_USER = "robbyroda09@gmail.com"
SMTP_PASS = "srsk ests yvzu kklg"  # Use Gmail App Password
TEMPLATE_DIR = "templates"
SEND_GRID_API = "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"

# =======================
#   FastAPI App Setup
# =======================
app = FastAPI(title="R-Techon SMS", version="1.3.0")
app = FastAPI(
    title="R-Techon SMS",
    version="1.3.0",
    description="""
R-Techon SMS API

This API allows you to:

- Send SMS via `/api/sms/send`

---

### Endpoints

**1. Send SMS**

`POST http://3.27.40.236/api/sms/send`

Request body (JSON):

```json
{
  "api_key": "your_api_key",
  "number": "09123123456",
  "message": "Hello World Ngani!"
}
""")

if not firebase_admin._apps:
    cred = credentials.Certificate("serviceAccount.json")
    firebase_admin.initialize_app(cred, {
        "databaseURL": "https://rtechon-c3fa0-default-rtdb.asia-southeast1.firebasedatabase.app"
    })

rtdb = db

origins = [
    "https://r-techon.vercel.app",
    "http://localhost:4200",
    "http://127.0.0.1:4200",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(sms_router)
app.include_router(payment_router)
app.include_router(forget_router)
app.include_router(admin_router)

# =======================
#   Email Helper
# =======================
def render_template(template_name: str, context: dict) -> str:
    """Render an HTML email template with placeholder replacements."""
    template_path = os.path.join(TEMPLATE_DIR, template_name)

    if not os.path.exists(template_path):
        raise HTTPException(status_code=400, detail=f"Template '{template_name}' not found")

    with open(template_path, "r", encoding="utf-8") as f:
        html = f.read()

    for key, value in context.items():
        html = html.replace(f"{{{{{key}}}}}", str(value))

    return html


# =======================
#   Pydantic Models
# =======================
class RegisterModel(BaseModel):
    username: str
    email: EmailStr
    password: str
    confirm_password: str


class LoginModel(BaseModel):
    email: EmailStr
    password: str


# =======================
#   Utility Endpoints
# =======================

@app.get("/", include_in_schema=False)
def root():
    """Root endpoint."""
    return {"I’m still here, but not really.": "aHR0cDovL2NvZGVybGlzdC5mcmVlLm5mL3NvcnJ5LnR4dA=="}

@app.get("/analytics", include_in_schema=False)
async def get_user_analytics(user=Depends(get_current_user)):
    try:
        user_id = user.user.id

        ref = db.reference(f"/queue/{user_id}")
        data = ref.get() or {}

        messages = list(data.values())

        if not messages:
            return {
                "success": True,
                "analytics": {
                    "total_messages": 0,
                    "sent": 0,
                    "queued": 0,
                    "failed": 0,
                    "percentages": {},
                    "per_number": {},
                    "most_sent_number": None,
                    "per_day": {},
                    "overtime_graph": {}
                }
            }

        total = len(messages)
        sent = sum(1 for m in messages if m.get("status", "").lower() == "sent")
        queued = sum(1 for m in messages if m.get("status", "").lower() == "queued")
        failed = sum(1 for m in messages if m.get("status", "").lower() in ["failed", "error"])
        percentages = {
            "sent_percentage": round((sent / total) * 100, 2),
            "queued_percentage": round((queued / total) * 100, 2),
            "failed_percentage": round((failed / total) * 100, 2),
            "success_rate": round((sent / total) * 100, 2)
        }
        per_number = Counter(m.get("number") for m in messages)
        most_sent_number = per_number.most_common(1)[0] if per_number else None
        per_day = Counter(
            datetime.fromtimestamp(m.get("timestamp") / 1000).strftime("%Y-%m-%d")
            for m in messages
        )
        overtime = defaultdict(lambda: {"sent": 0, "failed": 0, "queued": 0})

        for m in messages:
            day = datetime.fromtimestamp(m.get("timestamp") / 1000).strftime("%Y-%m-%d")
            status = m.get("status", "").lower()

            if status == "sent":
                overtime[day]["sent"] += 1
            elif status == "queued":
                overtime[day]["queued"] += 1
            elif status in ["failed", "error"]:
                overtime[day]["failed"] += 1
        overtime_sorted = dict(sorted(overtime.items(), key=lambda x: x[0]))

        return {
            "success": True,
            "analytics": {
                "total_messages": total,
                "sent": sent,
                "queued": queued,
                "failed": failed,
                "percentages": percentages,
                "per_number": dict(per_number),
                "most_sent_number": {
                    "number": most_sent_number[0],
                    "count": most_sent_number[1]
                } if most_sent_number else None,
                "per_day": dict(per_day),
                "overtime_graph": overtime_sorted
            }
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
@app.get("/health", include_in_schema=False)
def health_check():
    """Check API health status."""
    return {"status": "ok", "message": "R-Techon API is running. aHR0cDovL2NvZGVybGlzdC5mcmVlLm5mL3NvcnJ5LnR4dA=="}


@app.get("/test-smtp", include_in_schema=False)
def test_smtp():
    """Test SMTP connection using Gmail App Password."""
    try:
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT, timeout=10) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASS)
        return {"success": True, "message": "SMTP connection successful"}
    except Exception as e:
        return {"success": False, "error": str(e)}


# =======================
#   Auth Endpoints
# =======================
@app.post("/api/register", include_in_schema=False)
async def register(user: RegisterModel):
    """Register a new user in Supabase Auth and local users table."""
    try:
        res = supabase.auth.sign_up({"email": user.email, "password": user.password})

        if not res.user:
            return JSONResponse(status_code=400, content={"success": False, "message": "Registration failed"})

        api_key = f"roda_{secrets.token_hex(16)}"
        device_id = str(uuid.uuid4())

        supabase.table("users").insert({
            "user_id": res.user.id,
            "email": user.email,
            "username": user.username,
            "api_key": api_key,
            "device_id": device_id,
            "credits": 500,
            "role": "users",
            "created_at": datetime.utcnow().isoformat(),
        }).execute()

        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "message": "User registered successfully",
                "user_id": res.user.id,
                "api_key": api_key,
                "device_id": device_id,
            },
        )
    except Exception as e:
        return JSONResponse(status_code=500, content={"success": False, "message": str(e)})


@app.post("/api/login", include_in_schema=False)
async def login(user: LoginModel):
    """Authenticate a user and return Supabase session."""
    try:
        res = supabase.auth.sign_in_with_password({"email": user.email, "password": user.password})

        if not res.session:
            return JSONResponse(status_code=401, content={"success": False, "message": "Invalid credentials"})

        token = res.session.access_token
        user_id = res.user.id

        user_data = (
            supabase.table("users")
            .select("user_id, email, username, api_key, device_id, role, credits, created_at")
            .eq("user_id", user_id)
            .single()
            .execute()
        )

        if not user_data.data:
            return JSONResponse(status_code=404, content={"success": False, "message": "User profile not found"})

        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "message": "Login successful",
                "session": {"access_token": token, "user": user_data.data},
            },
        )
    except Exception as e:
        return JSONResponse(status_code=500, content={"success": False, "message": str(e)})


@app.get("/user/me", include_in_schema=False)
def get_current_user_info(user=Depends(get_current_user)):
    """Retrieve the current authenticated user info."""
    try:
        auth_user = {
            "user_id": user.user.id,
            "email": user.user.email,
            "username": getattr(user.user, "user_metadata", {}).get("username", ""),
        }

        db_user = supabase.table("users").select("*").eq("user_id", user.user.id).single().execute()

        if db_user.data:
            auth_user.update({
                "api_key": db_user.data.get("api_key"),
                "deviceId": db_user.data.get("device_id"),
            })

        return auth_user
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/user/credits", include_in_schema=False)
def get_user_credits(user=Depends(get_current_user)):
    """Return the user’s credit balance."""
    try:
        user_record = supabase.table("users").select("credits").eq("user_id", user.user.id).single().execute()
        if not user_record.data:
            raise HTTPException(status_code=404, detail="User not found")
        return {"credits": user_record.data.get("credits", 0)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
