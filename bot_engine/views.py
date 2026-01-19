import json
import logging
import requests
from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from bot_engine.models import Transaction, TelegramUser, PendingAd

logger = logging.getLogger(__name__)

@csrf_exempt
def mpesa_callback(request):
    """M-Pesa hits this URL when payment is done"""
    if request.method == "POST":
        try:
            body = json.loads(request.body)
            logger.info(f"M-Pesa Callback: {body}")
            
            # 1. Parse Data
            stk_callback = body.get('Body', {}).get('stkCallback', {})
            merchant_request_id = stk_callback.get('MerchantRequestID')
            result_code = stk_callback.get('ResultCode') # 0 means success
            
            # 2. Find the Transaction
            try:
                transaction = Transaction.objects.get(checkout_request_id=merchant_request_id)
            except Transaction.DoesNotExist:
                return JsonResponse({"status": "error", "message": "Transaction not found"})

            # 3. Handle Success
            if result_code == 0:
                transaction.is_completed = True
                transaction.save()
                
                user = transaction.user
                user.credits += 1
                user.save()
                
                print(f"✅ Payment Confirmed for {user.username}!")

                # --- NEW: POST TO GROUP WITH SPONSOR TAG ---
                ad = PendingAd.objects.filter(user=user, is_posted=False).last()
                
                if ad:
                    # Get the username (handle @None case)
                    sponsor_name = f"@{user.username}" if user.username else "an Anonymous User"

                    bot_token = settings.TELEGRAM_BOT_TOKEN
                    group_id = settings.TELEGRAM_GROUP_ID
                    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
                    
                    # The New Message Format
                    final_message = (
                        f"{ad.message_text}\n\n"
                        f"📢 **Sponsored by {sponsor_name}**"
                    )

                    payload = {
                        "chat_id": group_id,
                        "text": final_message,
                        "parse_mode": "Markdown" # Allows clickable links
                    }
                    
                    try:
                        requests.post(url, json=payload)
                        print(f"🚀 Ad Posted to Group {group_id}!")
                        
                        ad.is_posted = True
                        ad.save()
                    except Exception as e:
                        print(f"❌ Failed to post to Telegram: {e}")
                else:
                    print("⚠️ Payment received, but no pending ad found.")
                
            else:
                print(f"❌ Payment Failed for {transaction.user.username}")

            return JsonResponse({"status": "ok"})
            
        except Exception as e:
            print(f"Error processing callback: {e}")
            return JsonResponse({"status": "error", "message": str(e)})
            
    return JsonResponse({"status": "ignored"})