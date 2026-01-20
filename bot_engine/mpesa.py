import requests
from django.conf import settings

def initiate_stk_push(phone_number, amount, account_reference="LinkBot"):
    """
    Triggers a Payment Request via Paystack (Charge API).
    """
    url = "https://api.paystack.co/charge"
    
    # 1. Format Phone: Paystack prefers 2547...
    if phone_number.startswith("0"):
        phone_number = "254" + phone_number[1:]
    elif phone_number.startswith("+"):
        phone_number = phone_number[1:]

    # 2. Prepare Payload
    # We create a dummy email because Paystack requires one
    payload = {
        "email": f"customer{phone_number}@linkbot.karanja.ninja", 
        "amount": amount * 100,  # Paystack uses CENTS (100 cents = 1 KES)
        "currency": "KES",
        "mobile_money": {
            "phone": phone_number,
            "provider": "mpesa"
        }
    }

    headers = {
        "Authorization": f"Bearer {settings.PAYSTACK_SECRET_KEY}",
        "Content-Type": "application/json"
    }

    try:
        response = requests.post(url, json=payload, headers=headers)
        res_json = response.json()

        # 3. Check if the prompt was sent
        if res_json.get("status") is True:
            data = res_json.get("data", {})
            return {
                "CheckoutRequestID": data.get("reference"), # We use Paystack Reference as the ID
                "ResponseCode": "0",
                "ResponseDescription": "Success"
            }
        else:
            print(f"Paystack Error: {res_json}")
            return {}

    except Exception as e:
        print(f"Connection Error: {e}")
        return {}