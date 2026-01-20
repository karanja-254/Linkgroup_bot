import requests
from django.conf import settings

def initiate_stk_push(phone_number, amount, account_reference="LinkBot"):
    """
    Triggers Paystack Charge.
    Detects M-Pesa vs Airtel based on prefixes.
    """
    url = "https://api.paystack.co/charge"
    
    # 1. Sanitize Phone
    clean_phone = phone_number
    if clean_phone.startswith("+254"):
        clean_phone = "0" + clean_phone[4:]
    elif clean_phone.startswith("254"):
        clean_phone = "0" + clean_phone[3:]
    
    # 2. Detect Carrier (Airtel Prefixes in Kenya)
    # Airtel: 073x, 075x, 078x, 010x
    provider = "mpesa" # Default
    if clean_phone.startswith(("073", "075", "078", "010")):
        provider = "airtel-money"
        print(f"📶 Detected Airtel Number: {clean_phone}")
    else:
        print(f"Mzitu Detected M-Pesa Number: {clean_phone}")

    # 3. Prepare for Paystack (Format 254...)
    paystack_phone = "254" + clean_phone[1:]

    payload = {
        "email": f"customer{paystack_phone}@linkbot.karanja.ninja", 
        "amount": amount * 100,  # Cents
        "currency": "KES",
        "mobile_money": {
            "phone": paystack_phone,
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
            # Print the EXACT error from Paystack so we can debug
            print(f"❌ Paystack Refused: {res_json}")
            return {"error": res_json.get("message", "Unknown Error")}

    except Exception as e:
        print(f"Connection Error: {e}")
        return {"error": str(e)}