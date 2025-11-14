import csv
import os
from datetime import datetime, timedelta
from typing import Optional
from fastapi import APIRouter, HTTPException, Form
from jose import jwt
from passlib.context import CryptContext

# =====================================================
#  Router Setup
# =====================================================
admin_router = APIRouter(prefix="/admin", tags=["Admin Login"])

# =====================================================
#  Configuration
# =====================================================
ADMIN_CSV_FILE = "admins.csv"
SECRET_KEY = os.getenv("ADMIN_SECRET_KEY", "super_admin_secret_123")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# =====================================================
#  Helper Functions
# =====================================================

def hash_password(password: str) -> str:
    """Hash a plain password"""
    return pwd_context.hash(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plain password against its hash"""
    return pwd_context.verify(plain_password, hashed_password)

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Generate JWT access token"""
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def ensure_csv_exists():
    """Create admin CSV if it doesn't exist, with default credentials"""
    if not os.path.exists(ADMIN_CSV_FILE):
        with open(ADMIN_CSV_FILE, mode="w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=["username", "password_hash"])
            writer.writeheader()
            writer.writerow({
                "username": "admin",
                "password_hash": hash_password("potanginamo")
            })
        print("✅ Created admin CSV with default credentials (admin / potanginamo)")

def read_admins_from_csv():
    """Load all admin accounts from CSV"""
    ensure_csv_exists()
    admins = []
    with open(ADMIN_CSV_FILE, mode="r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            admins.append(row)
    return admins

# =====================================================
#  API Endpoints
# =====================================================

@admin_router.post("/login", include_in_schema=False)
async def admin_login(username: str = Form(...), password: str = Form(...)):
    """
    Admin login using CSV file for credentials.
    """
    try:
        admins = read_admins_from_csv()

        for admin in admins:
            if admin["username"].lower() == username.lower():
                if verify_password(password, admin["password_hash"]):
                    token = create_access_token({"sub": username, "role": "admin"})
                    print(f"✅ Admin '{username}' logged in successfully.")
                    return {
                        "success": True,
                        "message": "Admin login successful",
                        "access_token": token,
                        "token_type": "bearer",
                    }
                else:
                    print(f"❌ Incorrect password for '{username}'")
                    raise HTTPException(status_code=401, detail="Incorrect password")

        print(f"❌ No admin account found for username: {username}")
        raise HTTPException(status_code=404, detail="Admin account not found")

    except HTTPException as e:
        raise e
    except Exception as e:
        print("❌ Error in admin_login:", e)
        raise HTTPException(status_code=500, detail="Internal server error")


@admin_router.get("/verify-token", include_in_schema=False)
async def verify_admin_token(token: str):
    """
    Verify if the provided admin token is valid.
    """
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username = payload.get("sub")
        role = payload.get("role")

        if not username or role != "admin":
            raise HTTPException(status_code=403, detail="Invalid or unauthorized token")

        return {"valid": True, "username": username, "role": role}
    except Exception as e:
        print("❌ Token verification failed:", e)
        raise HTTPException(status_code=401, detail="Invalid or expired token")
