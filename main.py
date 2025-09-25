from fastapi import FastAPI, Depends, HTTPException, Header, Body, BackgroundTasks, Query
from fastapi.middleware.cors import CORSMiddleware
from supabase import create_client, Client
from pydantic import BaseModel, EmailStr
from typing import Optional
from fastapi.responses import JSONResponse
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import smtplib
import os

# =======================
#   Email Config
# =======================
SMTP_SERVER = "smtp.gmail.com"   # e.g., Gmail SMTP
SMTP_PORT = 587
SMTP_USER = "robbyroda09@gmail.com"
SMTP_PASS = "srsk ests yvzu kklg"  # Use an App Password if using Gmail


# =======================
#   FastAPI App Setup
# =======================
app = FastAPI(title="Freelancer CRM API")
origins = [
    "http://localhost:4200",
    "https://r-techon.vercel.app",
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
    
def send_invoice_email(invoice: dict, recipient: str):
    """Send invoice email via SMTP"""
    try:
        # Build email
        msg = MIMEMultipart("alternative")
        msg["From"] = SMTP_USER
        msg["To"] = recipient
        msg["Subject"] = f"Invoice #{invoice['invoice_id']}"

        # Plain text + HTML versions
        text = f"""
        Hello,

        Please find your invoice below:

        Invoice ID: {invoice['invoice_id']}
        Amount: {invoice['amount']}
        Status: {invoice['status']}

        Thank you!
        """
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8" />
            <title>Invoice #{invoice['invoice_id']}</title>
        </head>
        <body style="margin:0; padding:0; background-color:#f9fafb; font-family:Arial, sans-serif;">
            <div style="max-width:600px; margin:20px auto; background:#ffffff; border-radius:12px; box-shadow:0 4px 6px rgba(0,0,0,0.1); overflow:hidden;">
            
            <!-- Header -->
            <div style="background:#4f46e5; color:#ffffff; padding:20px; text-align:center;">
                <h1 style="margin:0; font-size:24px; font-weight:bold;">Invoice #{invoice['invoice_id']}</h1>
            </div>

            <!-- Body -->
            <div style="padding:24px; color:#111827; font-size:16px; line-height:1.5;">
                <p style="margin-bottom:16px;">Hello,</p>
                <p style="margin-bottom:16px;">Please find your invoice details below:</p>

                <table style="width:100%; border-collapse:collapse; margin-bottom:24px;">
                <tr>
                    <td style="padding:12px; border:1px solid #e5e7eb; background:#f9fafb;"><b>Invoice ID</b></td>
                    <td style="padding:12px; border:1px solid #e5e7eb;">{invoice['invoice_id']}</td>
                </tr>
                <tr>
                    <td style="padding:12px; border:1px solid #e5e7eb; background:#f9fafb;"><b>Amount</b></td>
                    <td style="padding:12px; border:1px solid #e5e7eb;">₱{invoice['amount']:,}</td>
                </tr>
                <tr>
                    <td style="padding:12px; border:1px solid #e5e7eb; background:#f9fafb;"><b>Status</b></td>
                    <td style="padding:12px; border:1px solid #e5e7eb; color:{'green' if invoice['status']=='paid' else 'red'};">
                    {invoice['status'].capitalize()}
                    </td>
                </tr>
                <tr>
                    <td style="padding:12px; border:1px solid #e5e7eb; background:#f9fafb;"><b>Due Date</b></td>
                    <td style="padding:12px; border:1px solid #e5e7eb;">{invoice.get('due_date','N/A')}</td>
                </tr>
                </table>

                <p style="margin-bottom:24px;">To settle this invoice, you may use the following payment options:</p>

                <!-- Payment Options -->
                <div style="background:#f9fafb; padding:16px; border-radius:8px; margin-bottom:24px; border:1px solid #e5e7eb;">
                    <h3 style="margin:0 0 12px 0; font-size:18px; font-weight:bold; color:#4f46e5;">Bank & E-Wallet Details</h3>
                    <p style="margin:4px 0;"><b>UnionBank:</b> 1096 6083 8564<br>Account Name: Robby Roda</p>
                    <p style="margin:4px 0;"><b>GCash:</b> 09217017064<br>Account Name: Robby Roda</p>
                    <p style="margin:4px 0;"><b>GoTyme:</b> 0105589471951<br>Account Name: Robby Roda</p>
                </div>

                <p style="margin-bottom:16px;">📩 After payment, please send your receipt to:</p>
                <p style="font-weight:bold; color:#4f46e5; margin-bottom:24px;">robbyroda09@gmail.com</p>

                <p style="margin-bottom:24px;">If you have any questions regarding this invoice, feel free to contact us.</p>
            </div>

            <!-- Footer -->
            <div style="background:#f3f4f6; padding:16px; text-align:center; font-size:14px; color:#6b7280;">
                <p style="margin:0;">Thank you for your business! 🚀</p>
            </div>
            </div>
        </body>
        </html>
        """


        msg.attach(MIMEText(text, "plain"))
        msg.attach(MIMEText(html, "html"))

        # Send email
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASS)
            server.sendmail(SMTP_USER, recipient, msg.as_string())

    except Exception as e:
        print("Email sending failed:", e)
        raise HTTPException(status_code=500, detail="Error sending invoice email")
    
# =======================
#   Pydantic Models
# =======================
class InvoiceEmailRequest(BaseModel):
    invoice_id: str
    recipient: EmailStr

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


# =======================
#   Auth Endpoints
# =======================


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
    return response.data

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
def send_invoice(invoice_id: str, request: InvoiceEmailRequest, background_tasks: BackgroundTasks, user=Depends(get_current_user)):
    # Fetch invoice
    response = supabase.table("invoices").select("*").eq("invoice_id", invoice_id).execute()
    if not response.data:
        raise HTTPException(status_code=404, detail="Invoice not found")

    invoice = response.data[0]

    # Send email in background
    background_tasks.add_task(send_invoice_email, invoice, request.recipient)

    return {"message": f"Invoice {invoice_id} is being sent to {request.recipient}"}