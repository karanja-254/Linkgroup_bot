import asyncio
import logging
import re
from django.core.management.base import BaseCommand
from django.conf import settings
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command as TGCommand
from bot_engine.models import TelegramUser, Transaction, PendingAd
from bot_engine.mpesa import initiate_stk_push

logging.basicConfig(level=logging.INFO)

class Command(BaseCommand):
    help = 'Runs the Telegram Bot'

    def handle(self, *args, **options):
        bot = Bot(token=settings.TELEGRAM_BOT_TOKEN)
        dp = Dispatcher()

        # --- 1. POLICEMAN (Group Handler) ---
        @dp.message(F.chat.type.in_({"group", "supergroup"}))
        async def handle_group_messages(message: types.Message):
            
            # Print msg to terminal
            print(f"👀 Group msg from {message.from_user.first_name}: {message.text}")

            link_pattern = r"(http|https|www\.|t\.me|\.com|\.co\.ke|\.org)"
            
            if message.text and re.search(link_pattern, message.text, re.IGNORECASE):
                print(f"👮 Policeman: Deleting link from {message.from_user.first_name}")
                
                try:
                    await message.delete()
                except Exception:
                    pass

                try:
                    name = message.from_user.first_name
                    # --- NEW TEXT REQUESTED BY USER ---
                    await message.answer(
                        f"🚫 Links are not allowed here, {name}!\n\n"
                        "Want to advertise? I can post it for you.\n"
                        "👉 DM me: @Linkgrouperbot"
                    )
                except Exception:
                    pass

        # --- 2. CASHIER (DM Handler) ---

        @dp.message(F.chat.type == "private", TGCommand("start"))
        async def cmd_start(message: types.Message):
            user_id = message.from_user.id
            username = message.from_user.username or "Unknown"
            
            await asyncio.to_thread(
                TelegramUser.objects.get_or_create,
                telegram_id=user_id,
                defaults={'username': username}
            )
            
            await message.answer(
                f"Welcome {message.from_user.first_name}! 🚀\n"
                "I am the Link Warden.\n\n"
                "📝 **Pricing:**\n"
                "• Regular Link: 30 KES\n"
                "• WhatsApp/Telegram Link: 250 KES\n\n"
                "Send me your link to start!"
            )

        @dp.message(F.chat.type == "private", F.text.regexp(r'^(07|01|\+254)\d{8}$'))
        async def process_payment(message: types.Message):
            phone = message.text
            user_id = message.from_user.id
            
            # 1. Get User & Last Ad
            try:
                user = await asyncio.to_thread(TelegramUser.objects.get, telegram_id=user_id)
                # Get the latest unposted ad
                last_ad = await asyncio.to_thread(
                    lambda: PendingAd.objects.filter(user=user, is_posted=False).last()
                )
            except TelegramUser.DoesNotExist:
                await message.answer("Please type /start first.")
                return

            if not last_ad:
                await message.answer("⚠️ Please send me your ad text/link FIRST, then send the phone number.")
                return

            # 2. DETERMINE PRICE (Dynamic Pricing)
            # Check for "Premium" links (WhatsApp or Telegram)
            premium_pattern = r"(t\.me|telegram\.me|chat\.whatsapp\.com)"
            is_premium = re.search(premium_pattern, last_ad.message_text, re.IGNORECASE)

            if is_premium:
                amount_to_charge = 1 # CHANGE THIS TO 250 WHEN READY FOR REAL MONEY
                ad_type = "Premium (WhatsApp/Telegram)"
            else:
                amount_to_charge = 1 # CHANGE THIS TO 30 WHEN READY
                ad_type = "Standard"

            await message.answer(f"⌛ Sending request to {phone}...\nType: {ad_type}\nPrice: {amount_to_charge} KES")
            
            try:
                # 3. Trigger Payment
                response = await asyncio.to_thread(
                    initiate_stk_push, 
                    phone_number=phone, 
                    amount=amount_to_charge
                )
                
                checkout_id = response.get('CheckoutRequestID')
                
                if checkout_id:
                    await asyncio.to_thread(
                        Transaction.objects.create,
                        user=user,
                        checkout_request_id=checkout_id,
                        amount=amount_to_charge, 
                        phone_number=phone
                    )
                    await message.answer("📲 **Check your phone and enter PIN!**")
                else:
                    # Show the exact error from Paystack
                    error_msg = response.get('error', 'Unknown Error')
                    await message.answer(f"❌ Payment Request Failed.\nReason: {error_msg}")
                    
            except Exception as e:
                print(f"Error: {e}")
                await message.answer("❌ System Error.")

        @dp.message(F.chat.type == "private")
        async def handle_dm_messages(message: types.Message):
            text = message.text
            user_id = message.from_user.id
            
            if not text: return

            if len(text) > 200:
                await message.answer(f"❌ Too long! ({len(text)}/200 chars)")
                return

            # Accept Any Link (We price it later in process_payment)
            link_pattern = r"(http|https|www\.|t\.me|\.com)"
            
            if re.search(link_pattern, text, re.IGNORECASE):
                try:
                    user = await asyncio.to_thread(TelegramUser.objects.get, telegram_id=user_id)
                except TelegramUser.DoesNotExist:
                     await message.answer("Please type /start first.")
                     return

                # Save the ad
                await asyncio.to_thread(
                    PendingAd.objects.create,
                    user=user,
                    message_text=text,
                    is_posted=False
                )

                # --- NEW TEXT REQUESTED BY USER ---
                await message.answer(
                    "✅ Ad Accepted!\n\n"
                    "Reply with your M-Pesa/Airtel money Number (e.g., 0712345678) to complete payment."
                )
            else:
                await message.answer("Please send the link you want to advertise.")

        async def main():
            print("🤖 Bot is Online...")
            await dp.start_polling(bot)

        asyncio.run(main())