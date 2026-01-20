import requests
from django.conf import settings

def initiate_stk_push(phone_number, amount, account_reference="LinkBot"):
    """
    Triggers Paystack Charge.
    Forces phone number into '07xx' or '01xx' format.
    """
    url = "https://api.paystack.co/charge"
    
    # 1. CLEANING: Remove spaces, +, -
    raw_phone = str(phone_number).replace(" ", "").replace("+", "").replace("-", "").strip()
    
    # 2. FORMATTING: Convert international (254) to local (0)
    if raw_phone.startswith("254"):
        clean_phone = "0" + raw_phone[3:]  # 254722 -> 0722
    elif raw_phone.startswith("7") or raw_phone.startswith("1"):
        clean_phone = "0" + raw_phone      # 722 -> 0722
    else:
        clean_phone = raw_phone            # Already starts with 0 (or invalid)

    # 3. Detect Carrier (Airtel Prefixes)
    provider = "mpesa"
    # Airtel: 073, 075, 078, 010, 011
    if clean_phone.startswith(("073", "075", "078", "010", "011")):
        provider = "airtel-money"

    # Debug Print (So we can see what we are sending)
    print(f"📡 Sending to Paystack: Phone={clean_phone}, Provider={provider}, Amount={amount}")

    payload = {
        "email": f"customer{clean_phone}@linkbot.karanja.ninja", 
        "amount": amount * 100,  # Cents
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
            # Return the exact error message from Paystack
            return {"error": res_json.get("message", "Paystack Rejected Request")}

    except Exception as e:
        return {"error": str(e)}