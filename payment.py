from fastapi import APIRouter, File, Form, UploadFile, Depends, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse
from datetime import datetime
from supabase import create_client, Client
import shutil, os, uuid
from typing import Optional

# Import helpers from your main app
from core import supabase, get_current_user, send_invoice_email


# =======================
#   Router Setup
# =======================
payment_router = APIRouter(prefix="/api/checkout", tags=["Checkout"])


# =======================
#   Checkout Endpoint
# =======================
@payment_router.post("/checkout")
async def checkout(
    background_tasks: BackgroundTasks,
    plan: str = Form(...),
    amount: float = Form(...),
    payment_method: str = Form(...),
    receipt: UploadFile = File(...),
    user=Depends(get_current_user)
):
    """
    Handles the checkout process for purchasing points.
    Accepts receipt upload, saves transaction in Supabase,
    and sends an invoice email.
    """
    try:
        # Generate unique invoice ID
        invoice_id = f"INV-{uuid.uuid4().hex[:10].upper()}"

        # Directory to save uploaded receipts
        uploads_dir = "uploads/receipts"
        os.makedirs(uploads_dir, exist_ok=True)
        file_path = os.path.join(uploads_dir, f"{invoice_id}_{receipt.filename}")

        # Save the uploaded file
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(receipt.file, buffer)

        # Save transaction in Supabase
        transaction = {
            "invoice_id": invoice_id,
            "user_id": user.user.id,
            "plan": plan,
            "amount": amount,
            "payment_method": payment_method,
            "receipt_url": file_path,
            "status": "pending",
            "created_at": datetime.utcnow().isoformat(),
        }

        supabase.table("transactions").insert(transaction).execute()

        # Send invoice email
        background_tasks.add_task(
            send_invoice_email,
            invoice=transaction,
            recipient=user.user.email,
            template_name="invoice_template.html",
            user_id=user.user.id,
        )

        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "message": "Checkout submitted successfully. Awaiting verification.",
                "invoice_id": invoice_id,
            },
        )

    except Exception as e:
        print("[ERROR] Checkout failed:", e)
        raise HTTPException(status_code=500, detail=str(e))



# =======================
#   ✅ Get Current User's Payments
# =======================
@payment_router.get("/my-payments")
async def get_user_payments(user=Depends(get_current_user)):
    """
    Returns all transactions for the currently logged-in user.
    """
    try:
        response = supabase.table("transactions") \
            .select("*") \
            .eq("user_id", user.user.id) \
            .order("created_at", desc=True) \
            .execute()

        payments = response.data or []
        return {"success": True, "count": len(payments), "payments": payments}

    except Exception as e:
        print("[ERROR] Failed to fetch user payments:", e)
        raise HTTPException(status_code=500, detail=str(e))



# =======================
#   Optional: Verify Payment (Admin)
# =======================
@payment_router.post("/verify")
async def verify_payment(invoice_id: str = Form(...), status: str = Form(...)):
    """
    Admin endpoint to verify or reject payment.
    If approved, credits are added to the user's account.
    """
    try:
        # Fetch transaction
        txn = supabase.table("transactions").select("*").eq("invoice_id", invoice_id).single().execute()
        if not txn.data:
            raise HTTPException(status_code=404, detail="Transaction not found")

        transaction = txn.data

        # Update transaction status
        supabase.table("transactions").update({"status": status}).eq("invoice_id", invoice_id).execute()

        # If approved, credit the user
        if status.lower() == "approved":
            points = 10000 if transaction["plan"].lower() == "standard" else 0
            supabase.rpc("increment_user_credits", {"user_id": transaction["user_id"], "amount": points}).execute()

        return {"success": True, "message": f"Payment {status} for {invoice_id}"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
