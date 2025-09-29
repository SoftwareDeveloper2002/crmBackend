from fastapi import FastAPI, Depends, HTTPException, Header, Body, BackgroundTasks, Query
from fastapi.middleware.cors import CORSMiddleware
from supabase import create_client, Client
from pydantic import BaseModel, EmailStr
from typing import Optional
from fastapi.responses import JSONResponse
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail
from typing import List
from datetime import datetime
import smtplib
import os

# =======================
#   Email Config
# =======================
SMTP_SERVER = "smtp.gmail.com"   # e.g., Gmail SMTP
SMTP_PORT = 587
SMTP_USER = "robbyroda09@gmail.com"
SMTP_PASS = "srsk ests yvzu kklg"  # Use an App Password if using Gmail
TEMPLATE_DIR = "templates"

# =======================
#   FastAPI App Setup
# =======================
app = FastAPI(title="Freelancer CRM API")
origins = [
    "https://r-techon.vercel.app",
    "http://localhost:4200",
    "http://127.0.0.1:4200"
]
# CORS for frontend integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,  # change to frontend domain later
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# =======================
#   Supabase Setup
# =======================
SEND_GRID_API = "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"
SUPABASE_URL = "https://wwpuorqzzvzuslbpukil.supabase.co"
SUPABASE_SERVICE_ROLE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Ind3cHVvcnF6enZ6dXNsYnB1a2lsIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc1ODc1Njk0NiwiZXhwIjoyMDc0MzMyOTQ2fQ.64t6V2e7_Wg085lwHFssNkAJrWNHMFLwSJwQkpmtKq4"
#SUPABASE_KEY = os.getenv("SUPABASE_KEY", "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Ind3cHVvcnF6enZ6dXNsYnB1a2lsIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NTg3NTY5NDYsImV4cCI6MjA3NDMzMjk0Nn0.CkZxQnv4TESaKiBWIVclYcXF6fb-FpBK0TswTuLJ7jU")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)

# =======================
#   Auth Helpers
# =======================
def get_current_user(authorization: Optional[str] = Header(None)):
    if not authorization:
        raise HTTPException(status_code=401, detail="Unauthorized")

    token = authorization.replace("Bearer ", "")
    try:
        user = supabase.auth.get_user(token)
        if not user or not user.user:
            raise HTTPException(status_code=401, detail="Unauthorized")
        return user
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

def render_template(template_name: str, context: dict) -> str:
    template_path = os.path.join(TEMPLATE_DIR, template_name)
    
    if not os.path.exists(template_path):
        raise HTTPException(status_code=400, detail=f"Template '{template_name}' not found")
    
    with open(template_path, "r", encoding="utf-8") as f:
        html = f.read()
    
    # Replace placeholders
    for key, value in context.items():
        html = html.replace(f"{{{{{key}}}}}", str(value))
    
    return html

def send_invoice_email(invoice: dict, recipient: str, template_name: str, user_id: str):
    """
    Send an invoice email via SendGrid, dynamically including payment methods.
    """
    try:
        # Fetch user payment methods
        pm_response = supabase.table("payment_methods").select("*").eq("user_id", user_id).execute()
        payments = pm_response.data or []

        # Build HTML snippet for payment methods
        payments_html = ""
        for pm in payments:
            payments_html += f"<p>{pm['payment_type']}: {pm['account_name']} - {pm['account_number']}</p>"

        # Render template with dynamic placeholders
        html_content = render_template(template_name, {
            "invoice_id": invoice['invoice_id'],
            "amount": f"{invoice['amount']:,}",
            "status": invoice['status'].capitalize(),
            "due_date": invoice.get('due_date', 'N/A'),
            "payment_methods": payments_html
        })

        message = Mail(
            from_email="admin@iskolardev.online",
            to_emails=recipient,
            subject=f"Invoice #{invoice['invoice_id']}",
            html_content=html_content
        )
        sg = SendGridAPIClient(SEND_GRID_API)
        response = sg.send(message)
        print(f"[SUCCESS] Email sent to {recipient}, status code: {response.status_code}")
    except Exception as e:
        print(f"[ERROR] Failed to send invoice email to {recipient}: {e}")


# =======================
#   Pydantic Models
# =======================

class PaymentMethodModel(BaseModel):
    paymentType: str
    accountNumber: str
    accountName: str

class PaymentMethodsRequest(BaseModel):
    payments: List[PaymentMethodModel]
class InvoiceEmailRequest(BaseModel):
    recipient: EmailStr
    template: Optional[str] = "invoice_basic.html"

class RegisterModel(BaseModel):
    username: str
    email: EmailStr
    password: str
    confirm_password: str

class LoginModel(BaseModel):
    email: EmailStr
    password: str

class ClientModel(BaseModel):
    name: str
    email: EmailStr
    phone: Optional[str] = None
    company: Optional[str] = None
    notes: Optional[str] = None

class ProjectModel(BaseModel):
    client_id: str
    title: str
    description: Optional[str] = None
    start_date: Optional[str] = None
    due_date: Optional[str] = None

class TaskModel(BaseModel):
    project_id: str
    title: str
    deadline: Optional[str] = None

class InvoiceModel(BaseModel):
    project_id: str
    amount: float
    due_date: Optional[str] = None
    status: Optional[str] = None

class ChangeEmailModel(BaseModel):
    new_email: EmailStr

# =======================
#   Auth Endpoints
# =======================
# =======================
# Health Check Endpoint
# =======================
@app.get("/health")
def health_check():
    """
    Simple health check endpoint for monitoring.
    Returns a 200 OK with a JSON response.
    """
    return {"status": "ok", "message": "Freelancer CRM API is running"}

@app.get("/test-smtp")
def test_smtp():
    try:
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT, timeout=10) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASS)
        return {"success": True, "message": "SMTP connection successful"}
    except Exception as e:
        return {"success": False, "error": str(e)}


@app.post("/register")
def register(user: RegisterModel):
    # 1️⃣ Password confirmation
    print("data:", user.dict())
    if user.password != user.confirm_password:
        return JSONResponse(
            status_code=400,
            content={"success": False, "message": "Passwords do not match"}
        )

    try:
        # 2️⃣ Check if email or username already exists
        existing = supabase.table("users").select("*").or_(
            f"email.eq.{user.email},username.eq.{user.username}"
        ).execute()

        if existing.data:
            return JSONResponse(
                status_code=400,
                content={"success": False, "message": "Email or username already exists"}
            )

        # 3️⃣ Create user in Supabase Auth
        res = supabase.auth.sign_up({"email": user.email, "password": user.password})
        if not res.user:
            return JSONResponse(
                status_code=400,
                content={"success": False, "message": "Could not create user in Supabase Auth"}
            )

        # 4️⃣ Insert into Postgres users table
        insert_res = supabase.table("users").insert({
            "user_id": res.user.id,
            "email": user.email,
            "username": user.username
        }).execute()

        if not insert_res.data:
            # Rollback auth user if insert fails
            supabase.auth.admin.delete_user(res.user.id)
            return JSONResponse(
                status_code=400,
                content={"success": False, "message": "Failed to insert user into database"}
            )

        # ✅ Success
        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "message": "User registered successfully",
                "user_id": res.user.id
            }
        )

    except Exception as e:
        return JSONResponse(
            status_code=400,
            content={"success": False, "message": str(e)}
        )

@app.post("/login")
def login(user: LoginModel):
    try:
        res = supabase.auth.sign_in_with_password({
            "email": user.email,
            "password": user.password
        })

        # If no session returned, check verification
        if not res or not getattr(res, "session", None):
            # Check if user exists
            user_info = supabase.auth.admin.get_user_by_email(user.email)
            if user_info.user and not user_info.user.email_confirmed_at:
                raise HTTPException(status_code=401, detail="Account not verified")
            raise HTTPException(status_code=401, detail="Invalid credentials")

        return {
            "success": True,
            "message": "Login successful",
            "session": res.session
        }

    except Exception as e:
        # Log e if needed
        raise HTTPException(status_code=401, detail="Invalid credentials or server error")

# =======================
#   Clients Endpoints
# =======================
@app.get("/clients")
def list_clients(user=Depends(get_current_user)):
    response = supabase.table("clients").select("*").eq("user_id", user.user.id).execute()
    return response.data

@app.post("/clients")
def add_client(client: ClientModel, user=Depends(get_current_user)):
    """
    Add a new client for the currently authenticated user.
    The user is already validated via get_current_user.
    """
    try:
        response = supabase.table("clients").insert({
            **client.dict(),
            "user_id": user.user.id  # must match clients.user_id FK
        }).execute()

        if response.data:
            return {"message": "Client added", "client": response.data[0]}
        else:
            raise HTTPException(status_code=400, detail="Error adding client")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.put("/clients/{client_id}")
def update_client(client_id: str, client: ClientModel, user=Depends(get_current_user)):
    updates = client.dict(exclude_unset=True)
    response = supabase.table("clients").update(updates).eq("client_id", client_id).eq("user_id", user.user.id).execute()
    if response.data:
        return {"message": "Client updated", "client": response.data[0]}
    raise HTTPException(status_code=404, detail="Client not found")

@app.delete("/clients/{client_id}")
def delete_client(client_id: str, user=Depends(get_current_user)):
    response = supabase.table("clients").delete().eq("client_id", client_id).eq("user_id", user.user.id).execute()
    if response.data:
        return {"message": "Client deleted"}
    raise HTTPException(status_code=404, detail="Client not found")


# =======================
#   Projects Endpoints
# =======================
@app.get("/projects")
def list_projects(user=Depends(get_current_user)):
    response = supabase.table("projects").select("*").eq("user_id", user.user.id).execute()
    return response.data

@app.post("/projects")
def add_project(project: ProjectModel, user=Depends(get_current_user)):
    response = supabase.table("projects").insert({
        **project.dict(),
        "user_id": user.user.id
    }).execute()
    if response.data:
        return {"message": "Project created", "project": response.data[0]}
    raise HTTPException(status_code=400, detail="Error creating project")

@app.put("/projects/{project_id}")
def update_project(project_id: str, project: ProjectModel, user=Depends(get_current_user)):
    updates = project.dict(exclude_unset=True)
    response = supabase.table("projects").update(updates).eq("project_id", project_id).eq("user_id", user.user.id).execute()
    if response.data:
        return {"message": "Project updated", "project": response.data[0]}
    raise HTTPException(status_code=404, detail="Project not found")

@app.delete("/projects/{project_id}")
def delete_project(project_id: str, user=Depends(get_current_user)):
    response = supabase.table("projects").delete().eq("project_id", project_id).eq("user_id", user.user.id).execute()
    if response.data:
        return {"message": "Project deleted"}
    raise HTTPException(status_code=404, detail="Project not found")


@app.get("/projects/{project_id}")
def get_project(project_id: str, user=Depends(get_current_user)):
    response = supabase.table("projects").select("*").eq("project_id", project_id).execute()
    if response.data:
        return response.data[0]
    raise HTTPException(status_code=404, detail="Project not found")


# =======================
#   Tasks Endpoints
# =======================
@app.get("/tasks/{project_id}")
def list_tasks(project_id: str, user=Depends(get_current_user)):
    response = supabase.table("tasks").select("*").eq("project_id", project_id).execute()
    return response.data

@app.post("/tasks")
def add_task(task: TaskModel, user=Depends(get_current_user)):
    response = supabase.table("tasks").insert(task.dict()).execute()
    if response.data:
        return {"message": "Task created", "task": response.data[0]}
    raise HTTPException(status_code=400, detail="Error creating task")

@app.put("/tasks/{task_id}")
def update_task(task_id: str, task: TaskModel, user=Depends(get_current_user)):
    updates = task.dict(exclude_unset=True)
    response = supabase.table("tasks").update(updates).eq("task_id", task_id).execute()
    if response.data:
        return {"message": "Task updated", "task": response.data[0]}
    raise HTTPException(status_code=404, detail="Task not found")

@app.delete("/tasks/{task_id}")
def delete_task(task_id: str, user=Depends(get_current_user)):
    response = supabase.table("tasks").delete().eq("task_id", task_id).execute()
    if response.data:
        return {"message": "Task deleted"}
    raise HTTPException(status_code=404, detail="Task not found")


# =======================
#   Invoices Endpoints
# =======================
@app.get("/invoices/{project_id}")
def list_invoices(project_id: str, user=Depends(get_current_user)):
    response = supabase.table("invoices").select("*").eq("project_id", project_id).execute()
    invoices = response.data

    # Compute overdue status
    for inv in invoices:
        if inv["status"] == "unpaid" and inv.get("due_date"):
            due = datetime.fromisoformat(inv["due_date"])
            if due < datetime.now():
                inv["status"] = "overdue"

    return invoices

# --------------------------
# Invoices: public search + protected CRUD
# --------------------------

# public invoice search - must be declared BEFORE the dynamic project route
@app.get("/invoice/search")
def search_invoice_by_id(invoice_id: Optional[str] = None):
    """
    Public: return a single invoice by invoice_id.
    Uses the Supabase *service role key* to bypass RLS for this read-only lookup.
    Must provide invoice_id query param; otherwise returns 400.
    """
    if not invoice_id:
        raise HTTPException(status_code=400, detail="invoice_id query parameter is required")

    # create a service-role client (or reuse a pre-created one)
    supabase_service = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)

    resp = supabase_service.table("invoices").select("*").eq("invoice_id", invoice_id).execute()

    # resp.data will be [] when not found
    if not resp.data or len(resp.data) == 0:
        raise HTTPException(status_code=404, detail="Invoice not found")

    return resp.data[0]   # return a single invoice object


@app.post("/invoices")
def add_invoice(invoice: InvoiceModel, user=Depends(get_current_user)):
    response = supabase.table("invoices").insert(invoice.dict()).execute()
    if response.data:
        return {"message": "Invoice created", "invoice": response.data[0]}
    raise HTTPException(status_code=400, detail="Error creating invoice")

@app.put("/invoices/{invoice_id}")
def update_invoice(invoice_id: str, invoice: InvoiceModel, user=Depends(get_current_user)):
    updates = invoice.dict(exclude_none=True)
    
    if not updates:
        raise HTTPException(status_code=400, detail="No fields provided to update")
    response = supabase.table("invoices").update(updates).eq("invoice_id", invoice_id).execute()
    if response.data and len(response.data) > 0:
        return {"message": "Invoice updated successfully", "invoice": response.data[0]}
    raise HTTPException(status_code=404, detail="Invoice not found")

@app.delete("/invoices/{invoice_id}")
def delete_invoice(invoice_id: str, user=Depends(get_current_user)):
    response = supabase.table("invoices").delete().eq("invoice_id", invoice_id).execute()
    if response.data:
        return {"message": "Invoice deleted"}
    raise HTTPException(status_code=404, detail="Invoice not found")


# =======================
#   New Endpoint
# =======================
@app.post("/invoices/{invoice_id}/send-email")
def send_invoice(
    invoice_id: str,
    request: InvoiceEmailRequest,
    background_tasks: BackgroundTasks,
    user=Depends(get_current_user)
):
    """
    Send an invoice email in the background using the selected template.
    Expects JSON body:
    {
        "recipient": "client@example.com",
        "template": "invoice_basic.html"  # optional
    }
    """

    # Fetch the invoice from Supabase
    response = supabase.table("invoices").select("*").eq("invoice_id", invoice_id).execute()
    if not response.data or len(response.data) == 0:
        raise HTTPException(status_code=404, detail="Invoice not found")

    invoice = response.data[0]

    # Use default template if none specified
    template_file = request.template if request.template else "invoice_basic.html"

    # Add background task to send the email
    background_tasks.add_task(send_invoice_email, invoice, request.recipient, template_file, user.user.id)

    return {"message": f"Invoice {invoice_id} is being sent to {request.recipient} using template {template_file}"}


@app.post("/payment-methods")
def save_payment_methods(
    request: PaymentMethodsRequest,
    user=Depends(get_current_user)
):
    """
    Save multiple payment methods for the authenticated user.
    This will delete old methods and insert the new ones.
    """
    try:
        # Remove old payment methods for this user
        supabase.table("payment_methods").delete().eq("user_id", user.user.id).execute()

        # Insert new payment methods
        data_to_insert = [
            {
                "user_id": user.user.id,
                "payment_type": pm.paymentType,
                "account_number": pm.accountNumber,
                "account_name": pm.accountName
            }
            for pm in request.payments
        ]

        response = supabase.table("payment_methods").insert(data_to_insert).execute()

        if response.data:
            return {"success": True, "message": "Payment methods saved", "data": response.data}
        else:
            raise HTTPException(status_code=400, detail="Failed to save payment methods")

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/payment-methods")
def get_payment_methods(user=Depends(get_current_user)):
    """
    Retrieve all payment methods for the authenticated user.
    """
    try:
        response = supabase.table("payment_methods").select("*").eq("user_id", user.user.id).execute()
        return {"success": True, "payments": response.data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.put("/user/email")
def update_email(data: ChangeEmailModel, user=Depends(get_current_user)):
    try:
        # 🚫 Prevent change for a specific email
        if user.user.email == "rtechondemo@gmail.com":
            raise HTTPException(status_code=403, detail="This email cannot be changed")

        # 1️⃣ Check duplicate email
        existing = supabase.table("users").select("*").eq("email", data.new_email).execute()
        if existing.data:
            raise HTTPException(status_code=400, detail="Email already in use")

        # 2️⃣ Use admin client for email update
        supabase_admin = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)
        res = supabase_admin.auth.admin.update_user_by_id(
            user.user.id,
            {"email": data.new_email}
        )

        if not res.user:
            raise HTTPException(status_code=400, detail="Failed to update email in Auth")

        # 3️⃣ Update Postgres users table
        update_res = supabase.table("users").update({"email": data.new_email}).eq("user_id", user.user.id).execute()
        if not update_res.data:
            raise HTTPException(status_code=400, detail="Failed to update email in database")

        return {"success": True, "message": "Email updated successfully", "new_email": data.new_email}

    except HTTPException:
        raise
    except Exception as e:
        print(f"[ERROR] Failed to update email: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.get("/user/me")
def get_current_user_info(user=Depends(get_current_user)):
    """
    Returns the authenticated user's info.
    """
    return {
        "user_id": user.user.id,
        "email": user.user.email,
        "username": getattr(user.user, "user_metadata", {}).get("username", "")
    }
