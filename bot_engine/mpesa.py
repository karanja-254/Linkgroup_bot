import requests
from django.conf import settings

def initiate_stk_push(phone_number, amount, account_reference="LinkBot"):
    """
    Triggers Paystack Charge.
    FORMAT RULE: Phone must be '+254xxxxxxxxx' (Must include PLUS sign).
    """
    url = "https://api.paystack.co/charge"
    
    # 1. CLEANING: Remove spaces and dashes
    raw = str(phone_number).replace(" ", "").replace("-", "").strip()
    
    # 2. FORMATTING: Force '+254'
    # If it starts with '0', remove it and add '+254' (0722 -> +254722)
    if raw.startswith("0"):
        clean_phone = "+254" + raw[1:]
    # If it starts with '254' (but no plus), add '+' (254722 -> +254722)
    elif raw.startswith("254"):
        clean_phone = "+" + raw
    # If it starts with '+254', keep it
    elif raw.startswith("+254"):
        clean_phone = raw
    # Fallback for '722...' -> '+254722'
    elif raw.startswith("7") or raw.startswith("1"):
        clean_phone = "+254" + raw
    else:
        clean_phone = raw

    # 3. Detect Carrier (Airtel vs M-Pesa)
    provider = "mpesa"
    # Airtel Prefixes: +25473, +25475, +25478, +25410, +25411
    if clean_phone.startswith(("+25473", "+25475", "+25478", "+25410", "+25411")):
        provider = "atl" # Try 'atl' first for Airtel

    print(f"🔥 FINAL FORMAT: Sending Phone={clean_phone} Provider={provider}")

    payload = {
        "email": f"customer{clean_phone.replace('+','')}@linkbot.karanja.ninja", 
        "amount": amount * 100,
        "currency": "KES",
        "mobile_money": {
            "phone": clean_phone,
            "provider": provider
        }
    }

    headers = {
        "Authorization": f"Bearer {settings.PAYSTACK_SECRET_KEY}",
        "Content-Type": "application/json"
    }

    try:
        response = requests.post(url, json=payload, headers=headers)
        res_json = response.json()

        if res_json.get("status") is True:
            data = res_json.get("data", {})
            return {
                "CheckoutRequestID": data.get("reference"),
                "ResponseCode": "0",
                "ResponseDescription": "Success"
            }
        else:
            return {"error": res_json.get("message", "Paystack Rejected Request")}

    except Exception as e:
        return {"error": str(e)}