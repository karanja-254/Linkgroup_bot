import asyncio
import logging
from django.core.management.base import BaseCommand
from django.conf import settings
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command as TGCommand
from bot_engine.models import TelegramUser, Transaction
from bot_engine.mpesa import initiate_stk_push

# Configure logging
logging.basicConfig(level=logging.INFO)

class Command(BaseCommand):
    help = 'Runs the Telegram Bot'

    def handle(self, *args, **options):
        # 1. Initialize Bot
        bot = Bot(token=settings.TELEGRAM_BOT_TOKEN)
        dp = Dispatcher()

        # --- HANDLERS ---

        # /start Command
        @dp.message(TGCommand("start"))
        async def cmd_start(message: types.Message):
            user_id = message.from_user.id
            username = message.from_user.username or "Unknown"
            
            # Save user to Database
            user, created = await asyncio.to_thread(
                TelegramUser.objects.get_or_create,
                telegram_id=user_id,
                defaults={'username': username}
            )
            
            if created:
                welcome_text = (
                    f"Welcome {message.from_user.first_name}! 🚀\n"
                    "I am the Link Warden. DM me a link, pay 30 KES, "
                    "and I will post it to the group for you."
                )
            else:
                welcome_text = "Welcome back! Send me the text you want to post."

            await message.answer(welcome_text)

        # Phone Number Listener (Regex for Kenyan numbers)
        # Handles 07xx, 01xx, or +254xx
        @dp.message(F.text.regexp(r'^(07|01|\+254)\d{8}$'))
        async def process_payment(message: types.Message):
            phone = message.text
            user_id = message.from_user.id
            
            # Get User from DB
            try:
                user = await asyncio.to_thread(TelegramUser.objects.get, telegram_id=user_id)
            except TelegramUser.DoesNotExist:
                await message.answer("Please type /start first.")
                return
            
            await message.answer(f"⌛ Sending STK Push to {phone} for KES 1 (Test)...")
            
            # Trigger M-Pesa
            try:
                # We use asyncio.to_thread because requests is synchronous
                response = await asyncio.to_thread(
                    initiate_stk_push, 
                    phone_number=phone, 
                    amount=1 # Test with 1 KES first
                )
                
                checkout_id = response.get('MerchantRequestID')
                response_code = response.get('ResponseCode')
                
                if response_code == "0":
                    # Save "Pending" transaction to DB
                    await asyncio.to_thread(
                        Transaction.objects.create,
                        user=user,
                        checkout_request_id=checkout_id,
                        amount=1, 
                        phone_number=phone
                    )
                    await message.answer("📲 Check your phone and enter PIN!")
                else:
                    error_message = response.get('errorMessage', 'Unknown error')
                    await message.answer(f"❌ Failed to send STK Push: {error_message}")
                    
            except Exception as e:
                print(f"Error: {e}")
                await message.answer("❌ System Error connecting to M-Pesa.")

        # Text/Link Validator
        @dp.message()
        async def handle_messages(message: types.Message):
            text = message.text
            
            if not text:
                return

            # Basic Validation
            if "http" in text or ".com" in text or "t.me" in text:
                link_count = text.count("http") + text.count("t.me")
                if link_count > 1:
                    await message.answer("❌ Error: Only 1 link allowed per post.")
                    return
                
                if len(text) > 100:
                    await message.answer(f"❌ Error: Text is too long ({len(text)}/100 chars).")
                    return
                
                # If valid:
                await message.answer(
                    "✅ Ad Validated!\n"
                    "Please reply with your **M-Pesa Phone Number** (e.g., 0712345678) to pay."
                )
            else:
                await message.answer("Please send the text with the link you want to advertise.")

        # --- START LOOP ---
        async def main():
            print("🤖 Bot is Online and Listening...")
            await dp.start_polling(bot)

        asyncio.run(main())