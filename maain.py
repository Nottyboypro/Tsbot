import os
import asyncio
import zipfile
import io
from pyrogram import Client, filters
from pyrogram.types import (
    Message, InlineKeyboardMarkup, 
    InlineKeyboardButton, CallbackQuery
)
from config import *
from database import db
from payment_gateway import RazorpayPayment

# Initialize bot
app = Client("session_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# Initialize payment gateway
razorpay = RazorpayPayment(RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET)

# Start Command
@app.on_message(filters.command("start"))
async def start_command(client, message: Message):
    user_id = message.from_user.id
    username = message.from_user.username
    first_name = message.from_user.first_name
    
    # Add user to database
    await db.add_user(user_id, username, first_name)
    
    # Welcome message with buttons
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("👤 Profile", callback_data="profile"),
         InlineKeyboardButton("🔢 Get Number", callback_data="get_number")],
        [InlineKeyboardButton("💰 Balance", callback_data="balance"),
         InlineKeyboardButton("📞 Support", url=SUPPORT_GROUP)],
        [InlineKeyboardButton("ℹ️ How to Use", callback_data="how_to_use")]
    ])
    
    await message.reply_photo(
        photo="https://telegra.ph/file/random.jpg",  # Replace with your image
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

# Profile Callback
@app.on_callback_query(filters.regex("^profile$"))
async def profile_callback(client, callback_query: CallbackQuery):
    user_id = callback_query.from_user.id
    user = await db.get_user(user_id)
    
    profile_text = f"""
**👤 User Profile**

**🆔 User ID:** `{user_id}`
**👤 Name:** {callback_query.from_user.first_name}
**💰 Wallet Balance:** ₹{user['wallet_balance']}
**📊 Total Spent:** ₹{user['total_spent']}
**👥 Referrals:** {user['referral_count']} users
**🔗 Referral Code:** `{user['referral_code']}`
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
    user = await db.get_user(user_id)
    
    # Check if user is banned
    if user.get('banned'):
        await callback_query.answer("❌ You are banned from using this bot!", show_alert=True)
        return
    
    # Get available platforms from database
    platforms = await db.db.numbers.distinct("platform", {"used": False})
    
    if not platforms:
        await callback_query.answer("❌ No numbers available currently!", show_alert=True)
        return
    
    keyboard_buttons = []
    for platform in platforms:
        keyboard_buttons.append([InlineKeyboardButton(
            f"📱 {platform.title()}", 
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
    platform = callback_query.data.split("_")[1]
    
    # Get available countries for this platform
    countries = await db.db.numbers.distinct("country", {
        "platform": platform,
        "used": False
    })
    
    if not countries:
        await callback_query.answer("❌ No numbers available for this platform!", show_alert=True)
        return
    
    keyboard_buttons = []
    for country in countries:
        # Get price for this platform-country combination
        number = await db.db.numbers.find_one({
            "platform": platform,
            "country": country,
            "used": False
        })
        
        keyboard_buttons.append([InlineKeyboardButton(
            f"🇺🇸 {country} - ₹{number['price']}", 
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
    data = callback_query.data.split("_")
    platform = data[1]
    country = data[2]
    user_id = callback_query.from_user.id
    
    user = await db.get_user(user_id)
    
    # Get available number
    number_data = await db.get_available_number(platform, country)
    
    if not number_data:
        await callback_query.answer("❌ No numbers available for this country!", show_alert=True)
        return
    
    # Check wallet balance
    if user['wallet_balance'] < number_data['price']:
        insufficient_text = f"""
**❌ Insufficient Balance!**

**Number Price:** ₹{number_data['price']}
**Your Balance:** ₹{user['wallet_balance']}

Please recharge your wallet to continue.
        """
        
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("💰 Recharge Wallet", callback_data="recharge")],
            [InlineKeyboardButton("🔙 Back", callback_data=f"platform_{platform}")]
        ])
        
        await callback_query.edit_message_text(
            insufficient_text,
            reply_markup=keyboard
        )
        return
    
    # Deduct balance and assign number
    await db.update_wallet(user_id, -number_data['price'])
    await db.mark_number_used(number_data['_id'], user_id)
    
    # Extract number from file (pseudo code - implement based on your file format)
    phone_number = await extract_number_from_zip(number_data['file_data'])
    
    success_text = f"""
**✅ Number Assigned Successfully!**

**📞 Your Number:** `{phone_number}`
**📱 Platform:** {platform}
**🌍 Country:** {country}
**💰 Deducted:** ₹{number_data['price']}
**💳 Remaining Balance:** ₹{user['wallet_balance'] - number_data['price']}

**📝 Instructions:**
1. Open original Telegram app (from Play Store)
2. Request OTP on this number
3. Click 'I Requested OTP' button below
4. Get your OTP code automatically

⚠️ **Note:** Use only official Telegram apps.
    """
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("📲 I Requested OTP", callback_data=f"read_otp_{number_data['_id']}")],
        [InlineKeyboardButton("🔄 Get Another Number", callback_data="get_number")]
    ])
    
    await callback_query.edit_message_text(
        success_text,
        reply_markup=keyboard
    )
    
    # Send log to channel
    await client.send_message(
        LOG_CHANNEL,
        f"**📊 Number Purchased**\n\n"
        f"**👤 User:** {callback_query.from_user.mention}\n"
        f"**🆔 ID:** `{user_id}`\n"
        f"**📞 Number:** `{phone_number}`\n"
        f"**📱 Platform:** {platform}\n"
        f"**💰 Price:** ₹{number_data['price']}\n"
        f"**💳 Balance Left:** ₹{user['wallet_balance'] - number_data['price']}"
    )

# Read OTP Functionality
@app.on_callback_query(filters.regex("^read_otp_"))
async def read_otp_callback(client, callback_query: CallbackQuery):
    number_id = callback_query.data.split("_")[2]
    
    # Get number data
    number_data = await db.db.numbers.find_one({"_id": number_id})
    
    if not number_data:
        await callback_query.answer("❌ Number data not found!", show_alert=True)
        return
    
    # Read OTP from file (implement your OTP reading logic here)
    otp_code = await read_otp_from_file(number_data['file_data'])
    
    if otp_code:
        otp_text = f"""
**✅ OTP Code Found!**

**📞 Number:** `{await extract_number_from_zip(number_data['file_data'])}`
**📱 Platform:** {number_data['platform']}
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
    
    await callback_query.edit_message_text(
        otp_text,
        reply_markup=keyboard
    )

# Balance Check
@app.on_callback_query(filters.regex("^balance$"))
async def balance_callback(client, callback_query: CallbackQuery):
    user_id = callback_query.from_user.id
    user = await db.get_user(user_id)
    
    balance_text = f"""
**💰 Wallet Balance**

**Current Balance:** ₹{user['wallet_balance']}
**Total Spent:** ₹{user['total_spent']}
**Referral Earnings:** ₹{user['referral_count'] * 0.5}

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
    
    await callback_query.edit_message_text(
        balance_text,
        reply_markup=keyboard
    )

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
@app.on_message(filters.text & filters.private & ~filters.command)
async def handle_recharge_amount(client, message: Message):
    user_id = message.from_user.id
    user = await db.get_user(user_id)
    
    if user.get('waiting_for') == 'recharge_amount':
        try:
            amount = int(message.text)
            
            if amount < MIN_RECHARGE:
                await message.reply_text(
                    f"❌ Minimum recharge amount is ₹{MIN_RECHARGE}. "
                    f"Please enter amount {MIN_RECHARGE} or more."
                )
                return
            
            # Generate payment link/QR
            payment_data = await razorpay.create_payment_link(amount, user_id)
            
            payment_text = f"""
**💰 Payment Details**

**Amount:** ₹{amount}
**Payment ID:** `{payment_data['id']}`

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
                [InlineKeyboardButton("📱 Payment Link", url=payment_data['short_url'])],
                [InlineKeyboardButton("✅ Payment Done", callback_data=f"payment_done_{payment_data['id']}")],
                [InlineKeyboardButton("📞 Support", url=SUPPORT_GROUP)]
            ])
            
            # Send QR code image (you need to generate QR from payment_data['short_url'])
            await message.reply_photo(
                photo=await generate_qr_code(payment_data['short_url']),
                caption=payment_text,
                reply_markup=keyboard
            )
            
        except ValueError:
            await message.reply_text("❌ Please enter a valid number only!")

# Admin Commands
@app.on_message(filters.command("cs") & filters.private)
async def create_session_command(client, message: Message):
    # Session creation logic here
    pass

@app.on_message(filters.command("readotp") & filters.private)
async def read_otp_command(client, message: Message):
    # OTP reading logic here
    pass

@app.on_message(filters.command("addfile") & filters.private)
async def add_file_command(client, message: Message):
    user_id = message.from_user.id
    
    if not await db.is_admin(user_id):
        await message.reply_text("❌ Admin access required!")
        return
    
    # File addition logic here
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
    await start_command(client, callback_query.message)

# Initialize bot
async def main():
    await db.init_db()
    print("Bot started successfully!")
    await app.start()
    await idle()
    await app.stop()

if __name__ == "__main__":
    asyncio.run(main())
