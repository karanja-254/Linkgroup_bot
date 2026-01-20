import json
import logging
import requests
import hmac
import hashlib
from django.conf import settings
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from bot_engine.models import Transaction, TelegramUser, PendingAd

logger = logging.getLogger(__name__)

@csrf_exempt
def mpesa_callback(request):
    """
    Paystack Webhook Listener.
    Triggers when payment is completed.
    """
    if request.method == "POST":
        try:
            # 1. Security Check (Verify it's actually Paystack)
            secret = settings.PAYSTACK_SECRET_KEY
            signature = request.headers.get('x-paystack-signature')
            
            if not signature:
                return HttpResponse(status=400) # Reject fake requests

            body_bytes = request.body
            expected_signature = hmac.new(
                key=secret.encode(), 
                msg=body_bytes, 
                digestmod=hashlib.sha512
            ).hexdigest()

            if signature != expected_signature:
                print("⚠️ Security Alert: Invalid Paystack Signature")
                return HttpResponse(status=400)

            # 2. Parse Data
            event = json.loads(body_bytes)
            event_type = event.get('event')
            data = event.get('data', {})

            print(f"🔔 Paystack Event: {event_type}")

            if event_type == 'charge.success':
                reference = data.get('reference') # This links back to our Transaction
                
                # Paystack sends amount in cents, convert to KES
                amount_paid = data.get('amount') / 100 

                # 3. Find Transaction
                try:
                    transaction = Transaction.objects.get(checkout_request_id=reference)
                except Transaction.DoesNotExist:
                    print(f"❌ Transaction not found for ref: {reference}")
                    return JsonResponse({"status": "error"})

                # 4. Fulfill Order
                if not transaction.is_completed:
                    transaction.is_completed = True
                    transaction.save()

                    user = transaction.user
                    user.credits += 1
                    user.save()
                    
                    print(f"✅ Payment Confirmed: {amount_paid} KES by {user.username}")

                    # --- POST TO GROUP ---
                    ad = PendingAd.objects.filter(user=user, is_posted=False).last()
                    
                    if ad:
                        sponsor_name = f"@{user.username}" if user.username else "an Anonymous User"
                        
                        bot_token = settings.TELEGRAM_BOT_TOKEN
                        group_id = settings.TELEGRAM_GROUP_ID
                        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"

                        # Message to Group
                        final_message = (
                            f"{ad.message_text}\n\n"
                            f"📢 **Sponsored by {sponsor_name}**"
                        )
                        requests.post(url, json={
                            "chat_id": group_id, 
                            "text": final_message, 
                            "parse_mode": "Markdown"
                        })

                        ad.is_posted = True
                        ad.save()

                        # Confirmation DM
                        requests.post(url, json={
                            "chat_id": user.telegram_id, 
                            "text": "✅ **PAYMENT RECEIVED!**\nYour ad is live on the group."
                        })
                    else:
                        print("⚠️ Paid, but no ad found.")

            return JsonResponse({"status": "ok"})
            
        except Exception as e:
            print(f"Error processing webhook: {e}")
            return HttpResponse(status=500)
            
    return HttpResponse(status=200)