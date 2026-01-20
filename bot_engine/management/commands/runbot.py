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
            link_pattern = r"(http|https|www\.|t\.me|\.com|\.co\.ke|\.org)"
            if message.text and re.search(link_pattern, message.text, re.IGNORECASE):
                try:
                    await message.delete()
                    await message.answer(
                        f"🚫 Links are not allowed here, {message.from_user.first_name}!\n\n"
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

        # UPDATED: More flexible phone checker (Allows 07xx, 254xx, +254xx)
        @dp.message(F.chat.type == "private", F.text.regexp(r'^[\d\+\s]{9,15}$'))
        async def process_payment(message: types.Message):
            phone = message.text
            user_id = message.from_user.id
            
            # 1. Retrieve the Ad
            try:
                user = await asyncio.to_thread(TelegramUser.objects.get, telegram_id=user_id)
                last_ad = await asyncio.to_thread(
                    lambda: PendingAd.objects.filter(user=user, is_posted=False).last()
                )
            except TelegramUser.DoesNotExist:
                await message.answer("Please type /start first.")
                return

            # FAILSAFE: If no ad found, ASK for it nicely.
            if not last_ad:
                await message.answer("⚠️ I don't see your ad yet. Please send the **Link** first, THEN the phone number.")
                return

            # 2. Calculate Price
            premium_pattern = r"(t\.me|telegram\.me|chat\.whatsapp\.com)"
            if re.search(premium_pattern, last_ad.message_text, re.IGNORECASE):
                amount = 250
            else:
                amount = 30

            await message.answer(f"⌛ Sending request to {phone} for {amount} KES...")
            
            try:
                # 3. Trigger Payment
                response = await asyncio.to_thread(
                    initiate_stk_push, 
                    phone_number=phone, 
                    amount=amount
                )
                
                checkout_id = response.get('CheckoutRequestID')
                
                if checkout_id:
                    await asyncio.to_thread(
                        Transaction.objects.create,
                        user=user,
                        checkout_request_id=checkout_id,
                        amount=amount, 
                        phone_number=phone
                    )
                    await message.answer("📲 **Check your phone and enter PIN!**")
                else:
                    error_msg = response.get('error', 'Unknown Error')
                    await message.answer(f"❌ Payment Failed.\nReason: {error_msg}")
                    
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

            # Check for Link
            link_pattern = r"(http|https|www\.|t\.me|\.com)"
            if re.search(link_pattern, text, re.IGNORECASE):
                
                try:
                    user = await asyncio.to_thread(TelegramUser.objects.get, telegram_id=user_id)
                except TelegramUser.DoesNotExist:
                     await message.answer("Please type /start first.")
                     return

                # Save Ad
                await asyncio.to_thread(
                    PendingAd.objects.create,
                    user=user,
                    message_text=text,
                    is_posted=False
                )

                # Pricing Alert
                premium_pattern = r"(t\.me|telegram\.me|chat\.whatsapp\.com)"
                if re.search(premium_pattern, text, re.IGNORECASE):
                    price = 250
                    reason = "Premium Link (WhatsApp/Telegram)."
                else:
                    price = 30
                    reason = "Standard Link."

                await message.answer(
                    f"✅ **Ad Accepted!**\n"
                    f"💰 Price: **{price} KES**\n"
                    f"ℹ️ Reason: {reason}\n\n"
                    "Reply with your **M-Pesa/Airtel Number** (e.g., 0712...) to pay."
                )
            else:
                await message.answer("Please send the link you want to advertise.")

        async def main():
            print("🤖 Bot is Online...")
            await dp.start_polling(bot)

        asyncio.run(main())