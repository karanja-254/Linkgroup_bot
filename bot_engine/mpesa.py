import requests
import base64
from datetime import datetime
from django.conf import settings

def get_access_token():
    """Generates the temporary password to talk to Safaricom"""
    consumer_key = settings.MPESA_CONSUMER_KEY
    consumer_secret = settings.MPESA_CONSUMER_SECRET
    api_URL = "https://sandbox.safaricom.co.ke/oauth/v1/generate?grant_type=client_credentials"
    
    r = requests.get(api_URL, auth=(consumer_key, consumer_secret))
    return r.json()['access_token']

def initiate_stk_push(phone_number, amount, account_reference="LinkBot"):
    """Sends the pop-up to the user's phone"""
    access_token = get_access_token()
    api_url = "https://sandbox.safaricom.co.ke/mpesa/stkpush/v1/processrequest"
    
    # Format timestamp
    timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
    
    # Create Password
    passkey = settings.MPESA_PASSKEY
    shortcode = settings.MPESA_SHORTCODE
    password_str = f"{shortcode}{passkey}{timestamp}"
    password = base64.b64encode(password_str.encode()).decode('utf-8')
    
    # Sanitize Phone Number (Must start with 254)
    if phone_number.startswith("0"):
        phone_number = "254" + phone_number[1:]
    elif phone_number.startswith("+254"):
        phone_number = phone_number[1:]
        
    payload = {
        "BusinessShortCode": shortcode,
        "Password": password,
        "Timestamp": timestamp,
        "TransactionType": "CustomerPayBillOnline",
        "Amount": amount,
        "PartyA": phone_number,
        "PartyB": shortcode,
        "PhoneNumber": phone_number,
        "CallBackURL": settings.MPESA_CALLBACK_URL,
        "AccountReference": account_reference,
        "TransactionDesc": "Link Payment"
    }
    
    headers = { "Authorization": f"Bearer {access_token}" }
    
    response = requests.post(api_url, json=payload, headers=headers)
    return response.json()