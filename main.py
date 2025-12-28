from fastapi import FastAPI, Depends, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, EmailStr
from datetime import datetime
import smtplib
import os
from types import SimpleNamespace
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
import supabase
from core import get_current_user
from typing import Optional
# =======================
#   Email Config
# =======================
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
SMTP_USER = "robbyroda09@gmail.com"
SMTP_PASS = "srsk ests yvzu kklg"

# =======================
#   FastAPI App Setup
# =======================
app = FastAPI(
    title="R-Techon SMS",
    version="1.0.1",
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
        user_id = user.get("id")

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
@app.post("/register", include_in_schema=False)
async def register(user: RegisterModel):
    # 1️⃣ Validate password confirmation
    if user.password != user.confirm_password:
        return JSONResponse(
            status_code=400,
            content={"success": False, "message": "Passwords do not match."}
        )

    # 2️⃣ Attempt to sign up with Supabase Auth
    try:
        auth_res = supabase.auth.sign_up({
            "email": user.email,
            "password": user.password,
            "options": {"data": {"username": user.username}}
        })
    except Exception as e:
        # Handle rate-limiting explicitly
        if "429" in str(e) or "Too Many Requests" in str(e):
            return JSONResponse(
                status_code=429,
                content={
                    "success": False,
                    "message": "Too many requests. Please wait a minute before trying again."
                }
            )
        return JSONResponse(
            status_code=500,
            content={"success": False, "message": f"Auth error: {str(e)}"}
        )

    # 3️⃣ If user requires email confirmation, return pending message
    if getattr(auth_res.user, "confirmation_sent_at", None) is not None:
        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "message": "Please check your email to confirm your account.",
                "pending": True
            }
        )

    # 4️⃣ Generate API key and device ID
    user_id = auth_res.user.id
    api_key = f"roda_{secrets.token_hex(16)}"
    device_id = str(uuid.uuid4())

    # 5️⃣ Insert user record into Supabase table
    try:
        insert_res = supabase.table("users").insert({
            "user_id": user_id,
            "email": user.email,
            "username": user.username,
            "api_key": api_key,
            "device_id": device_id,
            "credits": 10,
            "role": "users",
            "created_at": datetime.utcnow().isoformat(),
        }).execute()

        if not insert_res.data:
            return JSONResponse(
                status_code=500,
                content={"success": False, "message": "User registration failed: no data returned."}
            )
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"success": False, "message": f"Database error: {str(e)}"}
        )

    # 6️⃣ Return success response
    return JSONResponse(
        status_code=201,
        content={
            "success": True,
            "message": "User registered successfully. Please check your email to confirm your account.",
            "user_id": user_id,
            "api_key": api_key,
            "device_id": device_id,
        }
    )

@app.post("/login", include_in_schema=False)
async def login(user: LoginModel):
    try:
        res = supabase.auth.sign_in_with_password({
            "email": user.email,
            "password": user.password
        })

        if not res.session:
            return JSONResponse(
                status_code=401,
                content={"success": False, "message": "Invalid credentials"}
            )

        token = res.session.access_token
        user_id = res.user.id

        # Try to fetch user profile safely
        user_data_res = (
            supabase.table("users")
            .select("user_id, email, username, api_key, device_id, role, credits, created_at")
            .eq("user_id", user_id)
            .execute()
        )

        if not user_data_res.data:
            # Auto-create user row
            new_row = {
                "user_id": user_id,
                "email": user.email,
                "username": res.user.user_metadata.get("username", ""),
                "api_key": f"roda_{secrets.token_hex(16)}",
                "device_id": str(uuid.uuid4()),
                "credits": 500,
                "role": "users",
                "created_at": datetime.utcnow().isoformat(),
            }
            supabase.table("users").insert(new_row).execute()
            # Wrap in a simple object to mimic .data
            user_data = SimpleNamespace(data=new_row)
        else:
            user_data = SimpleNamespace(data=user_data_res.data[0])

        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "message": "Login successful",
                "session": {
                    "access_token": token,
                    "user": user_data.data,
                },
            },
        )

    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"success": False, "message": str(e)}
        )
    
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


@app.get("/user/credits")
def get_user_credits(
    api_key: Optional[str] = None,
    authorization: Optional[str] = Header(None)
):
    try:
        if authorization:
            user = get_current_user(authorization)
            user_id = user.user.id

            result = (
                supabase.table("users")
                .select("credits")
                .eq("user_id", user_id)
                .single()
                .execute()
            )

            if getattr(result, "error_message", None):
                raise HTTPException(status_code=404, detail=result.error_message)

            if not result.data:
                raise HTTPException(status_code=404, detail="User not found")

            return {"credits": result.data.get("credits", 0)}

        if api_key:
            result = (
                supabase.table("users")
                .select("credits")
                .eq("api_key", api_key)
                .single()
                .execute()
            )

            if getattr(result, "error_message", None) or not result.data:
                raise HTTPException(status_code=404, detail="Invalid API key")

            return {"credits": result.data.get("credits", 0)}

        raise HTTPException(status_code=400, detail="Missing authentication")

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
