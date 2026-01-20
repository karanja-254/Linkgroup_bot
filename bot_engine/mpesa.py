import requests
from django.conf import settings

def initiate_stk_push(phone_number, amount, account_reference="LinkBot"):
    """
    Triggers Paystack Charge with aggressive phone number cleaning.
    """
    url = "https://api.paystack.co/charge"
    
    # 1. AGGRESSIVE CLEANING
    # Remove spaces, plus signs, dashes
    clean_phone = str(phone_number).replace(" ", "").replace("+", "").replace("-", "").strip()
    
    # Force into 254 format
    if clean_phone.startswith("0"):
        clean_phone = "254" + clean_phone[1:]  # 0722 -> 254722
    elif clean_phone.startswith("7") or clean_phone.startswith("1"):
        clean_phone = "254" + clean_phone      # 722 -> 254722
    # If it already starts with 254, leave it.

    # 2. Detect Carrier (Airtel Prefixes)
    provider = "mpesa"
    # Airtel prefixes: 073, 075, 078, 010, 011
    # Since we converted to 254, check 25473, 25410, etc.
    if clean_phone.startswith(("25473", "25475", "25478", "25410", "25411")):
        provider = "airtel-money"

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
            return {"error": res_json.get("message", "Paystack Rejected Request")}

    except Exception as e:
        return {"error": str(e)}