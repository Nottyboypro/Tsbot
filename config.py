import os

# Bot Configuration
API_ID = int(os.getenv("API_ID", "1234567"))
API_HASH = os.getenv("API_HASH", "your_api_hash_here")
BOT_TOKEN = os.getenv("BOT_TOKEN", "your_bot_token_here")

# MongoDB Configuration
MONGO_DB_URI = os.getenv("MONGO_DB_URI", "mongodb://localhost:27017")

# Payment Configuration
RAZORPAY_KEY_ID = os.getenv("RAZORPAY_KEY_ID", "your_razorpay_key")
RAZORPAY_KEY_SECRET = os.getenv("RAZORPAY_KEY_SECRET", "your_razorpay_secret")

# Admin Configuration
ADMIN_IDS = [123456789, 987654321]  # Replace with actual admin IDs
SUDO_IDS = []  # Will be populated dynamically

# Channel Configuration
LOG_CHANNEL = -1001234567890  # Your log channel ID
SUPPORT_GROUP = "your_support_group_link"

# Payment Settings
MIN_RECHARGE = 20
