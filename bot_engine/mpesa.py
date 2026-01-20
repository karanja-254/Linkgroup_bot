import requests
from django.conf import settings

def initiate_stk_push(phone_number, amount, account_reference="LinkBot"):
    """
    Triggers Paystack Charge.
    FORMAT RULE: Phone must be '254xxxxxxxxx' (International format, no +).
    """
    url = "https://api.paystack.co/charge"
    
    # 1. CLEANING: Remove spaces, +, -
    raw_phone = str(phone_number).replace(" ", "").replace("+", "").replace("-", "").strip()
    
    # 2. FORMATTING: Ensure it starts with 254
    if raw_phone.startswith("254"):
        clean_phone = raw_phone
    elif raw_phone.startswith("0"):
        clean_phone = "254" + raw_phone[1:]  # 0722 -> 254722
    elif raw_phone.startswith("7") or raw_phone.startswith("1"):
        clean_phone = "254" + raw_phone      # 722 -> 254722
    else:
        # Fallback: Send as-is if it doesn't match known patterns
        clean_phone = raw_phone

    # 3. Detect Carrier
    # Default to mpesa (Safaricom)
    provider = "mpesa"
    
    # Check for Airtel prefixes (073, 075, 078, 010, 011)
    # Note: We check the "254" version of these prefixes
    if clean_phone.startswith(("25473", "25475", "25478", "25410", "25411")):
        # Paystack code for Airtel Money is often 'atl' or 'airtel-money'.
        # We will try 'atl' based on documentation, but 'mpesa' is safer for your 0723 number.
        provider = "atl" 

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
            # Return the exact error message from Paystack so you see it in Telegram
            return {"error": res_json.get("message", "Paystack Rejected Request")}

    except Exception as e:
        return {"error": str(e)}