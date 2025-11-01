import os

# Bot Configuration
API_ID = int(os.getenv("API_ID", "24168862"))
API_HASH = os.getenv("API_HASH", "916a9424dd1e58ab7955001ccc0172b3")
BOT_TOKEN = os.getenv("BOT_TOKEN", "8321137468:AAGdNvdqm6Z7xflnjwyokaGc-WKSO9dxurI")

# MongoDB Configuration
MONGO_DB_URI = os.getenv("MONGO_DB_URI", "mongodb+srv://jaydipmore74:xCpTm5OPAfRKYnif@cluster0.5jo18.mongodb.net/?retryWrites=true&w=majority")

# Payment Configuration
RAZORPAY_KEY_ID = os.getenv("RAZORPAY_KEY_ID", "rzp_test_RZgDQF4C4AZQen")
RAZORPAY_KEY_SECRET = os.getenv("RAZORPAY_KEY_SECRET", "dyG6Kpj1jP936iG3l96w9VDL")

# Admin Configuration
ADMIN_IDS = [6421770811, 987654321]  # Replace with actual admin IDs
SUDO_IDS = []  # Will be populated dynamically

# Channel Configuration
LOG_CHANNEL = -1002023049910  # Your log channel ID
SUPPORT_GROUP = "https://t.me/ZeeMusicSupport"

# Payment Settings
MIN_RECHARGE = 20
