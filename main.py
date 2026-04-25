import os
import json
import re
import httpx
from fastapi import FastAPI, Depends, HTTPException, Security, status
from fastapi.security import APIKeyHeader
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import firebase_admin
from firebase_admin import credentials, db
from datetime import datetime

# Load Environment Variables safely
firebase_cred_string = os.getenv("FIREBASE_CREDENTIALS")
database_url = "https://payment-verify-ri-default-rtdb.firebaseio.com"

try:
    if not firebase_admin._apps:
        if firebase_cred_string:
            # Vercel Production Environment
            cred_dict = json.loads(firebase_cred_string)
            cred = credentials.Certificate(cred_dict)
        else:
            # Local Environment Fallback
            cred = credentials.Certificate("serviceAccountKey.json")
            
        firebase_admin.initialize_app(cred, {
            'databaseURL': database_url
        })
except Exception as e:
    print(f"Firebase Init Error: {e}")

app = FastAPI(title="Payment Verification API")

# CORS setup
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Security Config (Load from ENV in production)
API_KEY = os.getenv("API_KEY", "Secure_API_Key_For_Android_App_123!")
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)

# Telegram Config (Load from ENV in production)
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "YOUR_TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "YOUR_TELEGRAM_CHAT_ID")

def get_api_key(api_key_header: str = Security(api_key_header)):
    if api_key_header != API_KEY:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Could not validate credentials")
    return api_key_header

class SMSPayload(BaseModel):
    sender: str
    message: str
    timestamp: int

class VerifyRequest(BaseModel):
    method: str
    amount: float
    trx_id: str

async def send_telegram_notification(text: str):
    if TELEGRAM_BOT_TOKEN == "YOUR_TELEGRAM_BOT_TOKEN":
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": text, "parse_mode": "HTML"}
    async with httpx.AsyncClient() as client:
        try:
            await client.post(url, json=payload)
        except Exception as e:
            print(f"Telegram Error: {e}")

def parse_mfs_sms(sender: str, message: str):
    trx_id, amount, method = None, None, "Unknown"
    sender_lower = sender.lower()
    
    if "bkash" in sender_lower:
        method = "bKash"
        trx_match = re.search(r'TrxID (\w+)', message)
        amt_match = re.search(r'Tk ([\d.]+)', message)
    elif "nagad" in sender_lower:
        method = "Nagad"
        trx_match = re.search(r'TxnID: (\w+)', message)
        amt_match = re.search(r'Amount: Tk ([\d.]+)', message)
    elif "rocket" in sender_lower:
        method = "Rocket"
        trx_match = re.search(r'TxnId: (\w+)', message)
        amt_match = re.search(r'Tk ([\d.]+)', message)
    else:
        return None

    if trx_match and amt_match:
        return {
            "trx_id": trx_match.group(1),
            "amount": float(amt_match.group(1)),
            "method": method
        }
    return None

@app.post("/api/sms-webhook")
async def receive_sms(payload: SMSPayload, api_key: str = Depends(get_api_key)):
    parsed_data = parse_mfs_sms(payload.sender, payload.message)
    if not parsed_data:
        return {"status": "ignored", "reason": "Not a valid MFS format"}

    trx_id = parsed_data["trx_id"]
    ref = db.reference(f'transactions/{trx_id}')
    
    if ref.get():
        return {"status": "exists", "trx_id": trx_id}

    transaction_data = {
        "trx_id": trx_id,
        "amount": parsed_data["amount"],
        "method": parsed_data["method"],
        "status": "UNCLAIMED",
        "timestamp": payload.timestamp,
        "raw_message": payload.message
    }
    
    ref.set(transaction_data)
    return {"status": "success", "trx_id": trx_id}

@app.post("/api/verify")
async def verify_payment(req: VerifyRequest):
    ref = db.reference(f'transactions/{req.trx_id}')
    data = ref.get()

    if not data:
        raise HTTPException(status_code=404, detail="Transaction not found. Wait 1-2 minutes.")
    
    if data["status"] == "VERIFIED":
        raise HTTPException(status_code=400, detail="Transaction already used!")

    if float(data["amount"]) != req.amount or data["method"].lower() != req.method.lower():
        raise HTTPException(status_code=400, detail="Amount or Method mismatch.")

    ref.update({"status": "VERIFIED", "claimed_at": int(datetime.now().timestamp())})
    
    msg = f"✅ <b>Payment Verified</b>\nMethod: {req.method}\nAmount: ৳{req.amount}\nTrxID: {req.trx_id}"
    await send_telegram_notification(msg)

    return {"status": "success", "message": "Payment verified successfully!"}
