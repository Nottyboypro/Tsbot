# main.py (updated)
import os
import io
import re
import asyncio
import zipfile
import logging
from typing import Optional, Any
from pyrogram import Client, filters, idle
from pyrogram.types import (
    Message, InlineKeyboardMarkup,
    InlineKeyboardButton, CallbackQuery
)
from config import *
from database import db
from payment_gateway import RazorpayPayment

# -------------- Logging --------------
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize bot
app = Client("session_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# Initialize payment gateway
razorpay = RazorpayPayment(RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET)


# ---------------- Helper functions ----------------
def _safe_get(d: dict, key: str, default: Any = 0):
    return d.get(key, default) if isinstance(d, dict) else default


async def generate_qr_code(url: str) -> io.BytesIO:
    """
    Generate a QR code PNG in-memory and return BytesIO (seeked to 0).
    """
    try:
        import qrcode
    except Exception as e:
        logger.exception("qrcode module not available: %s", e)
        raise

    img = qrcode.make(url)
    bio = io.BytesIO()
    img.save(bio, format="PNG")
    bio.seek(0)
    # Provide a name attribute so pyrogram treats it like a file
    bio.name = "qr.png"
    return bio


async def extract_number_from_zip(file_data: bytes) -> Optional[str]:
    """
    Given bytes of a ZIP file (or raw text), try to extract a phone number string.
    This implementation:
     - Opens ZIP in-memory and searches text-like files for phone-number patterns.
     - If file_data is not a zip, tries to decode and find the first pattern.
    Returns the first matched phone number or None.
    """
    phone_patterns = [
        r"\+?\d{10,15}",          # international or local 10-15 digits
        r"\d{3}[-\s]\d{3}[-\s]\d{4}",  # 123-456-7890 style
    ]
    try:
        # Try as ZIP
        bio = io.BytesIO(file_data)
        with zipfile.ZipFile(bio) as z:
            for name in z.namelist():
                # Only inspect reasonable text files or small files
                if name.endswith((".txt", ".csv", ".json", ".log", ".data")) or len(name) < 50:
                    try:
                        with z.open(name) as f:
                            content_bytes = f.read(2000)  # read first chunk
                            try:
                                text = content_bytes.decode(errors="ignore")
                            except Exception:
                                text = str(content_bytes)
                            for pat in phone_patterns:
                                m = re.search(pat, text)
                                if m:
                                    return m.group(0)
            # If not found inside those files, scan filenames as fallback
            for name in z.namelist():
                for pat in phone_patterns:
                    m = re.search(pat, name)
                    if m:
                        return m.group(0)
    except zipfile.BadZipFile:
        # Not a zip - try to decode raw bytes
        try:
            text = file_data.decode(errors="ignore")
            for pat in phone_patterns:
                m = re.search(pat, text)
                if m:
                    return m.group(0)
        except Exception:
            pass
    except Exception as e:
        logger.exception("extract_number_from_zip error: %s", e)

    return None


async def read_otp_from_file(file_data: bytes) -> Optional[str]:
    """
    Search zip/text bytes for OTP-like patterns (4-6 digit codes).
    Returns the first found OTP string or None.
    """
    otp_pattern = r"\b(\d{4,6})\b"  # common OTP lengths
    try:
        bio = io.BytesIO(file_data)
        with zipfile.ZipFile(bio) as z:
            # search all files (limited read)
            for name in z.namelist():
                try:
                    with z.open(name) as f:
                        content = f.read(4000).decode(errors="ignore")
                        # look for 4-6 digit groups; filter out sequences that are obviously phone numbers
                        for m in re.finditer(otp_pattern, content):
                            code = m.group(1)
                            # ignore if it's part of a longer number (like phone with country code)
                            if len(code) in (4, 5, 6):
                                return code
                except Exception:
                    continue
    except zipfile.BadZipFile:
        # treat as plain text
        try:
            text = file_data.decode(errors="ignore")
            m = re.search(otp_pattern, text)
            if m:
                return m.group(1)
        except Exception:
            pass
    except Exception as e:
        logger.exception("read_otp_from_file error: %s", e)

    return None


# ---------------- Bot Handlers ----------------

# Start Command
@app.on_message(filters.command("start"))
async def start_command(client, message: Message):
    user = message.from_user or message.sender_chat
    user_id = getattr(user, "id", None)
    username = getattr(user, "username", None)
    first_name = getattr(user, "first_name", "User")

    if user_id is None:
        await message.reply_text("Unable to identify user.")
        return

    # Add user to database (db.add_user should be async)
    try:
        await db.add_user(user_id, username, first_name)
    except Exception as e:
        logger.exception("db.add_user failed: %s", e)

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("👤 Profile", callback_data="profile"),
         InlineKeyboardButton("🔢 Get Number", callback_data="get_number")],
        [InlineKeyboardButton("💰 Balance", callback_data="balance"),
         InlineKeyboardButton("📞 Support", url=SUPPORT_GROUP)],
        [InlineKeyboardButton("ℹ️ How to Use", callback_data="how_to_use")]
    ])

    try:
        await message.reply_photo(
            photo="https://telegra.ph/file/random.jpg",
            caption="**🤖 Welcome to Session Bot!**\n\n"
                    "Create Telegram sessions easily with our advanced bot.\n\n"
                    "**Features:**\n"
                    "• Easy Session Generation\n"
                    "• Automatic OTP Reading\n"
                    "• Secure Payment System\n"
                    "• 24/7 Support\n\n"
                    "Select an option below to get started:",
            reply_markup=keyboard
        )
    except Exception:
        # fallback to text if photo fails
        await message.reply_text(
            "Welcome to Session Bot!\n\n"
            "Use /start to see options.",
            reply_markup=keyboard
        )


# Profile Callback
@app.on_callback_query(filters.regex("^profile$"))
async def profile_callback(client, callback_query: CallbackQuery):
    user_id = callback_query.from_user.id
    user = await db.get_user(user_id) or {}

    profile_text = f"""
**👤 User Profile**

**🆔 User ID:** `{user_id}`
**👤 Name:** {callback_query.from_user.first_name}
**💰 Wallet Balance:** ₹{_safe_get(user, 'wallet_balance', 0)}
**📊 Total Spent:** ₹{_safe_get(user, 'total_spent', 0)}
**👥 Referrals:** {_safe_get(user, 'referral_count', 0)} users
**🔗 Referral Code:** `{_safe_get(user, 'referral_code', 'N/A')}`
**🎁 Referral Bonus:** ₹0.5 per user

**Invite friends and earn money!**
    """

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔙 Back", callback_data="main_menu")]
    ])

    await callback_query.edit_message_text(
        profile_text,
        reply_markup=keyboard
    )


# Get Number Flow
@app.on_callback_query(filters.regex("^get_number$"))
async def get_number_callback(client, callback_query: CallbackQuery):
    user_id = callback_query.from_user.id
    user = await db.get_user(user_id) or {}

    if user.get('banned'):
        await callback_query.answer("❌ You are banned from using this bot!", show_alert=True)
        return

    platforms = await db.db.numbers.distinct("platform", {"used": False})
    if not platforms:
        await callback_query.answer("❌ No numbers available currently!", show_alert=True)
        return

    keyboard_buttons = []
    for platform in platforms:
        keyboard_buttons.append([InlineKeyboardButton(
            f"📱 {str(platform).title()}",
            callback_data=f"platform_{platform}"
        )])

    keyboard_buttons.append([InlineKeyboardButton("🔙 Back", callback_data="main_menu")])
    keyboard = InlineKeyboardMarkup(keyboard_buttons)

    await callback_query.edit_message_text(
        "**🔢 Get Number**\n\n"
        "Select platform:",
        reply_markup=keyboard
    )


# Platform Selection
@app.on_callback_query(filters.regex("^platform_"))
async def platform_selection(client, callback_query: CallbackQuery):
    # split only once after prefix to support underscores in platform names
    platform = callback_query.data[len("platform_"):]

    countries = await db.db.numbers.distinct("country", {
        "platform": platform,
        "used": False
    })

    if not countries:
        await callback_query.answer("❌ No numbers available for this platform!", show_alert=True)
        return

    keyboard_buttons = []
    for country in countries:
        number = await db.db.numbers.find_one({
            "platform": platform,
            "country": country,
            "used": False
        })
        price = _safe_get(number, "price", "N/A")
        keyboard_buttons.append([InlineKeyboardButton(
            f"{country.title()} - ₹{price}",
            callback_data=f"country_{platform}_{country}"
        )])

    keyboard_buttons.append([InlineKeyboardButton("🔙 Back", callback_data="get_number")])
    keyboard = InlineKeyboardMarkup(keyboard_buttons)

    await callback_query.edit_message_text(
        f"**📱 {platform.upper()} Numbers**\n\n"
        "Select country:",
        reply_markup=keyboard
    )


# Country Selection and Number Assignment
@app.on_callback_query(filters.regex("^country_"))
async def country_selection(client, callback_query: CallbackQuery):
    data = callback_query.data.split("_", 2)  # platform may contain underscores
    if len(data) < 3:
        await callback_query.answer("❌ Invalid selection.", show_alert=True)
        return

    platform = data[1]
    country = data[2]
    user_id = callback_query.from_user.id
    user = await db.get_user(user_id) or {}

    number_data = await db.get_available_number(platform, country)
    if not number_data:
        await callback_query.answer("❌ No numbers available for this country!", show_alert=True)
        return

    price = _safe_get(number_data, "price", 0)
    if _safe_get(user, "wallet_balance", 0) < price:
        insufficient_text = f"""
**❌ Insufficient Balance!**

**Number Price:** ₹{price}
**Your Balance:** ₹{_safe_get(user, 'wallet_balance', 0)}

Please recharge your wallet to continue.
        """
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("💰 Recharge Wallet", callback_data="recharge")],
            [InlineKeyboardButton("🔙 Back", callback_data=f"platform_{platform}")]
        ])
        await callback_query.edit_message_text(insufficient_text, reply_markup=keyboard)
        return

    # Deduct balance and mark number used (assumes db functions exist)
    try:
        await db.update_wallet(user_id, -price)
        await db.mark_number_used(number_data['_id'], user_id)
    except Exception:
        logger.exception("Failed to charge user or mark number used")

    # Extract number (best-effort)
    phone_number = await extract_number_from_zip(number_data.get('file_data', b"")) or "Unknown"

    remaining_balance = _safe_get(user, "wallet_balance", 0) - price

    success_text = f"""
**✅ Number Assigned Successfully!**

**📞 Your Number:** `{phone_number}`
**📱 Platform:** {platform}
**🌍 Country:** {country}
**💰 Deducted:** ₹{price}
**💳 Remaining Balance:** ₹{remaining_balance}

**📝 Instructions:**
1. Open original Telegram app (from Play Store)
2. Request OTP on this number
3. Click 'I Requested OTP' button below
4. Get your OTP code automatically

⚠️ **Note:** Use only official Telegram apps.
    """

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("📲 I Requested OTP", callback_data=f"read_otp_{str(number_data['_id'])}")],
        [InlineKeyboardButton("🔄 Get Another Number", callback_data="get_number")]
    ])

    await callback_query.edit_message_text(success_text, reply_markup=keyboard)

    # Send log to channel (guard in case LOG_CHANNEL is not set)
    try:
        if LOG_CHANNEL:
            await client.send_message(
                LOG_CHANNEL,
                f"**📊 Number Purchased**\n\n"
                f"**👤 User:** {callback_query.from_user.mention}\n"
                f"**🆔 ID:** `{user_id}`\n"
                f"**📞 Number:** `{phone_number}`\n"
                f"**📱 Platform:** {platform}\n"
                f"**💰 Price:** ₹{price}\n"
                f"**💳 Balance Left:** ₹{remaining_balance}"
            )
    except Exception:
        logger.exception("Failed to send purchase log")


# Read OTP Functionality
@app.on_callback_query(filters.regex("^read_otp_"))
async def read_otp_callback(client, callback_query: CallbackQuery):
    # get id after prefix "read_otp_"
    number_id = callback_query.data[len("read_otp_"):]
    number_data = await db.db.numbers.find_one({"_id": number_id})

    if not number_data:
        await callback_query.answer("❌ Number data not found!", show_alert=True)
        return

    otp_code = await read_otp_from_file(number_data.get('file_data', b""))

    if otp_code:
        otp_text = f"""
**✅ OTP Code Found!**

**📞 Number:** `{await extract_number_from_zip(number_data.get('file_data', b''))}`
**📱 Platform:** {number_data.get('platform', 'N/A')}
**🔢 OTP Code:** `{otp_code}`

**⚠️ Important:**
- Use this OTP within 5 minutes
- Don't share with anyone
- Complete your login process
        """
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔄 Get Another Number", callback_data="get_number")],
            [InlineKeyboardButton("🏠 Main Menu", callback_data="main_menu")]
        ])
    else:
        otp_text = """
**❌ OTP Not Found!**

Please wait for OTP to arrive or request again.
        """
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔄 Try Again", callback_data=callback_query.data)],
            [InlineKeyboardButton("📞 Support", url=SUPPORT_GROUP)]
        ])

    await callback_query.edit_message_text(otp_text, reply_markup=keyboard)


# Balance Check
@app.on_callback_query(filters.regex("^balance$"))
async def balance_callback(client, callback_query: CallbackQuery):
    user_id = callback_query.from_user.id
    user = await db.get_user(user_id) or {}

    balance_text = f"""
**💰 Wallet Balance**

**Current Balance:** ₹{_safe_get(user, 'wallet_balance', 0)}
**Total Spent:** ₹{_safe_get(user, 'total_spent', 0)}
**Referral Earnings:** ₹{_safe_get(user, 'referral_count', 0) * 0.5}

**💸 Recharge Options:**
- Minimum: ₹{MIN_RECHARGE}
- Instant UPI Payment
- Automatic Verification
    """

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("💳 Recharge Wallet", callback_data="recharge")],
        [InlineKeyboardButton("🎁 Redeem Code", callback_data="redeem")],
        [InlineKeyboardButton("🔙 Back", callback_data="main_menu")]
    ])

    await callback_query.edit_message_text(balance_text, reply_markup=keyboard)


# Recharge Flow
@app.on_callback_query(filters.regex("^recharge$"))
async def recharge_callback(client, callback_query: CallbackQuery):
    recharge_text = f"""
**💳 Recharge Wallet**

**Minimum Recharge:** ₹{MIN_RECHARGE}

Please enter the amount you want to recharge:

**Example:** `50` or `100` or `500`

⚠️ **Note:** Enter only numbers without any symbols.
    """

    await callback_query.edit_message_text(recharge_text)

    # Store that we're waiting for recharge amount
    await db.db.users.update_one(
        {"user_id": callback_query.from_user.id},
        {"$set": {"waiting_for": "recharge_amount"}}
    )


# Handle recharge amount input
@app.on_message(filters.text & filters.private & ~filters.command())
async def handle_recharge_amount(client, message: Message):
    user_id = message.from_user.id
    user = await db.get_user(user_id) or {}

    if user.get('waiting_for') == 'recharge_amount':
        try:
            amount = int(message.text.strip())
        except ValueError:
            await message.reply_text("❌ Please enter a valid number only!")
            return

        if amount < MIN_RECHARGE:
            await message.reply_text(
                f"❌ Minimum recharge amount is ₹{MIN_RECHARGE}. "
                f"Please enter amount {MIN_RECHARGE} or more."
            )
            return

        # Create payment link via Razorpay wrapper (assumed async)
        try:
            payment_data = await razorpay.create_payment_link(amount, user_id)
        except Exception:
            logger.exception("Failed to create payment link")
            await message.reply_text("❌ Payment gateway error. Try again later.")
            return

        payment_text = f"""
**💰 Payment Details**

**Amount:** ₹{amount}
**Payment ID:** `{payment_data.get('id', 'N/A')}`

**Payment Methods:**
- GPay
- PhonePe
- Paytm
- BHIM UPI
- Any UPI App

**Steps:**
1. Scan QR code below or use payment link
2. Complete payment
3. Click 'Payment Done' button
4. Enter UTR/Transaction ID
        """

        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("📱 Payment Link", url=payment_data.get('short_url'))],
            [InlineKeyboardButton("✅ Payment Done", callback_data=f"payment_done_{payment_data.get('id')}")],
            [InlineKeyboardButton("📞 Support", url=SUPPORT_GROUP)]
        ])

        # Send QR code image
        try:
            qr = await generate_qr_code(payment_data.get('short_url', ''))
            await message.reply_photo(
                photo=qr,
                caption=payment_text,
                reply_markup=keyboard
            )
        except Exception:
            # fallback: send text with link
            await message.reply_text(payment_text + f"\n\n{payment_data.get('short_url')}", reply_markup=keyboard)


# Admin Commands
@app.on_message(filters.command("cs") & filters.private)
async def create_session_command(client, message: Message):
    # TODO: implement session creation logic
    await message.reply_text("Session creation command received. (Not yet implemented)")


@app.on_message(filters.command("readotp") & filters.private)
async def read_otp_command(client, message: Message):
    # TODO: implement admin OTP read flow
    await message.reply_text("Admin readotp command received. (Not yet implemented)")


@app.on_message(filters.command("addfile") & filters.private)
async def add_file_command(client, message: Message):
    user_id = message.from_user.id

    if not await db.is_admin(user_id):
        await message.reply_text("❌ Admin access required!")
        return

    await message.reply_text(
        "**📁 Add Number File**\n\n"
        "Please send the file in this format:\n"
        "`/addfile platform country price`\n\n"
        "**Example:**\n"
        "`/addfile telegram india 10`\n\n"
        "Then send the ZIP file."
    )


# Main menu callback
@app.on_callback_query(filters.regex("^main_menu$"))
async def main_menu_callback(client, callback_query: CallbackQuery):
    # forward to start command - supply message object
    await start_command(client, callback_query.message)


# Initialize bot
async def main():
    try:
        await db.init_db()
    except Exception:
        logger.exception("db.init_db failed")

    logger.info("Bot starting...")
    await app.start()
    logger.info("Bot started successfully!")
    await idle()
    await app.stop()


if __name__ == "__main__":
    asyncio.run(main())
