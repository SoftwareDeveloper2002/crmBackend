from fastapi import Header, HTTPException
from supabase import create_client, Client
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail
import os

# =======================
# Supabase Setup
# =======================
SUPABASE_URL = "https://wwpuorqzzvzuslbpukil.supabase.co"
SUPABASE_SERVICE_ROLE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Ind3cHVvcnF6enZ6dXNsYnB1a2lsIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc1ODc1Njk0NiwiZXhwIjoyMDc0MzMyOTQ2fQ.64t6V2e7_Wg085lwHFssNkAJrWNHMFLwSJwQkpmtKq4"
SEND_GRID_API = "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"
TEMPLATE_DIR = "templates"

supabase: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)

# =======================
# Auth Helper
# =======================
def get_current_user(authorization: str = Header(None)):
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

# =======================
# Email Helper
# =======================
def render_template(template_name: str, context: dict) -> str:
    template_path = os.path.join(TEMPLATE_DIR, template_name)
    if not os.path.exists(template_path):
        raise HTTPException(status_code=400, detail=f"Template '{template_name}' not found")

    with open(template_path, "r", encoding="utf-8") as f:
        html = f.read()

    for key, value in context.items():
        html = html.replace(f"{{{{{key}}}}}", str(value))

    return html


def send_invoice_email(invoice: dict, recipient: str, template_name: str, user_id: str):
    """
    Send invoice email via SendGrid, dynamically including payment methods.
    """
    try:
        # Fetch payment methods for this user
        pm_response = supabase.table("payment_methods").select("*").eq("user_id", user_id).execute()
        payments = pm_response.data or []

        # Build payment methods HTML
        payments_html = ""
        for pm in payments:
            payments_html += f"<p>{pm['payment_type']}: {pm['account_name']} - {pm['account_number']}</p>"

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
        print(f"[ERROR] Failed to send invoice email: {e}")
