import asyncio
import logging
import re
from django.core.management.base import BaseCommand
from django.conf import settings
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command as TGCommand
from bot_engine.models import TelegramUser, Transaction, PendingAd
from bot_engine.mpesa import initiate_stk_push

# Set logging to see errors in the black terminal
logging.basicConfig(level=logging.INFO)

class Command(BaseCommand):
    help = 'Runs the Telegram Bot'

    def handle(self, *args, **options):
        # Initialize Bot
        bot = Bot(token=settings.TELEGRAM_BOT_TOKEN)
        dp = Dispatcher()

        # --- 1. POLICEMAN (Group Handler) ---
        @dp.message(F.chat.type.in_({"group", "supergroup"}))
        async def handle_group_messages(message: types.Message):
            
            # Print to terminal so you know the bot "sees" the message
            print(f"👀 Group msg from {message.from_user.first_name}: {message.text}")

            # Check for links (Standard Regex)
            link_pattern = r"(http|https|www\.|t\.me|\.com|\.co\.ke|\.org)"
            
            if message.text and re.search(link_pattern, message.text, re.IGNORECASE):
                print(f"👮 Policeman: Deleting link from {message.from_user.first_name}")
                
                # 1. Delete the Spam
                try:
                    await message.delete()
                    print("✅ Message deleted successfully.")
                except Exception as e:
                    print(f"❌ Delete Failed (Check Admin Rights): {e}")

                # 2. Send the Warning (PLAIN TEXT to prevent crashes)
                try:
                    # We use first_name to be safe.
                    name = message.from_user.first_name
                    
                    # ERROR FIX: We removed 'parse_mode="Markdown"' so names with "_" don't crash the bot.
                    await message.answer(
                        f"🚫 Links are not allowed here, {name}!\n\n"
                        "Want to advertise? I can post it for you.\n"
                        "👉 DM me: @Linkgrouperbot\n"
                        "(Max 100 characters)"
                    )
                    print("✅ Warning sent.")
                except Exception as e:
                    print(f"⚠️ Warning Failed: {e}")

        # --- 2. CASHIER (DM Handler) ---
        # Only works in Private DMs

        @dp.message(F.chat.type == "private", TGCommand("start"))
        async def cmd_start(message: types.Message):
            user_id = message.from_user.id
            username = message.from_user.username or "Unknown"
            
            # Save user to DB
            await asyncio.to_thread(
                TelegramUser.objects.get_or_create,
                telegram_id=user_id,
                defaults={'username': username}
            )
            
            await message.answer(
                f"Welcome {message.from_user.first_name}! 🚀\n"
                "I am the Link Warden.\n\n"
                "How to Post:\n"
                "1. Send me your link/text here (Max 100 chars).\n"
                "2. Pay 30 KES via M-Pesa.\n"
                "3. I will automatically post it to the group for you!"
            )

        @dp.message(F.chat.type == "private", F.text.regexp(r'^(07|01|\+254)\d{8}$'))
        async def process_payment(message: types.Message):
            phone = message.text
            user_id = message.from_user.id
            
            # Verify User Exists
            try:
                user = await asyncio.to_thread(TelegramUser.objects.get, telegram_id=user_id)
            except TelegramUser.DoesNotExist:
                await message.answer("Please type /start first.")
                return
            
            await message.answer(f"⌛ Sending STK Push to {phone} for KES 1 (Test)...")
            
            try:
                # Trigger M-Pesa STK Push
                response = await asyncio.to_thread(
                    initiate_stk_push, 
                    phone_number=phone, 
                    amount=1
                )
                
                checkout_id = response.get('MerchantRequestID') or response.get('CheckoutRequestID')
                
                if checkout_id:
                    # Save Transaction as 'Pending'
                    await asyncio.to_thread(
                        Transaction.objects.create,
                        user=user,
                        checkout_request_id=checkout_id,
                        amount=1, 
                        phone_number=phone
                    )
                    await message.answer("📲 Check your phone and enter PIN!")
                else:
                    await message.answer("❌ Connection Error. Ensure your Ngrok URL is updated in .env")
                    print(f"M-Pesa Error: {response}")
                    
            except Exception as e:
                print(f"Error: {e}")
                await message.answer("❌ System Error.")

        @dp.message(F.chat.type == "private")
        async def handle_dm_messages(message: types.Message):
            text = message.text
            user_id = message.from_user.id
            
            if not text: return

            # --- RULE: MAX 100 CHARACTERS ---
            if len(text) > 100:
                await message.answer(
                    f"❌ Too long! ({len(text)}/100 chars)\n"
                    "Please shorten your ad to under 100 characters."
                )
                return

            # Check for Link
            link_pattern = r"(http|https|www\.|t\.me|\.com)"
            if re.search(link_pattern, text, re.IGNORECASE):
                
                try:
                    user = await asyncio.to_thread(TelegramUser.objects.get, telegram_id=user_id)
                except TelegramUser.DoesNotExist:
                     await message.answer("Please type /start first.")
                     return

                # Save Pending Ad
                await asyncio.to_thread(
                    PendingAd.objects.create,
                    user=user,
                    message_text=text,
                    is_posted=False
                )

                await message.answer(
                    "✅ Ad Accepted!\n\n"
                    "Reply with your M-Pesa Number (e.g., 0712345678) to complete payment."
                )
            else:
                await message.answer("Please send the link you want to advertise.")

        async def main():
            print("🤖 Bot is Online and Listening...")
            await dp.start_polling(bot)

        asyncio.run(main())