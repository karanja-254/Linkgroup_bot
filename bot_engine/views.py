import json
import logging
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from bot_engine.models import Transaction, TelegramUser
from bot_engine.management.commands.runbot import bot 
# ^ We import the bot to send a message when payment succeeds!

logger = logging.getLogger(__name__)

@csrf_exempt
def mpesa_callback(request):
    """M-Pesa hits this URL when payment is done"""
    if request.method == "POST":
        body = json.loads(request.body)
        logger.info(f"M-Pesa Callback: {body}")
        
        # 1. Parse Data
        stk_callback = body.get('Body', {}).get('stkCallback', {})
        merchant_request_id = stk_callback.get('MerchantRequestID')
        result_code = stk_callback.get('ResultCode') # 0 means success
        
        # 2. Find the Transaction in our DB
        try:
            transaction = Transaction.objects.get(checkout_request_id=merchant_request_id)
        except Transaction.DoesNotExist:
            return JsonResponse({"status": "error", "message": "Transaction not found"})

        # 3. Handle Success
        if result_code == 0:
            transaction.is_completed = True
            transaction.save()
            
            # Give Credits
            user = transaction.user
            user.credits += 1
            user.save()
            
            # NOTIFY USER ON TELEGRAM (Optional but cool)
            # We will handle this in the bot logic, but DB is updated now.
            print(f"✅ Payment Confirmed for {user.username}!")
            
        else:
            print(f"❌ Payment Failed for {transaction.user.username}")

        return JsonResponse({"status": "ok"})