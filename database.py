from motor.motor_asyncio import AsyncIOMotorClient
from config import MONGO_DB_URI
from logging import Logger

logger = Logger(__name__)

class MongoDB:
    def __init__(self):
        self.client = None
        self.db = None
        
    async def init_db(self):
        try:
            self.client = AsyncIOMotorClient(MONGO_DB_URI)
            self.db = self.client.SessionBot
            logger.info("Connected to MongoDB successfully!")
        except Exception as e:
            logger.error(f"Failed to connect to MongoDB: {e}")
            exit()

    # User Management
    async def add_user(self, user_id, username, first_name):
        user_data = {
            "user_id": user_id,
            "username": username,
            "first_name": first_name,
            "wallet_balance": 0,
            "referral_code": f"REF{user_id}",
            "referred_by": None,
            "referral_count": 0,
            "banned": False,
            "joined_date": datetime.now(),
            "total_spent": 0
        }
        await self.db.users.update_one(
            {"user_id": user_id},
            {"$setOnInsert": user_data},
            upsert=True
        )

    async def get_user(self, user_id):
        return await self.db.users.find_one({"user_id": user_id})

    async def update_wallet(self, user_id, amount):
        await self.db.users.update_one(
            {"user_id": user_id},
            {"$inc": {"wallet_balance": amount}}
        )

    # Number Management
    async def add_number_file(self, platform, country, price, file_data):
        number_data = {
            "platform": platform,
            "country": country,
            "price": price,
            "file_data": file_data,
            "uploaded_at": datetime.now(),
            "used": False,
            "used_by": None,
            "used_at": None
        }
        return await self.db.numbers.insert_one(number_data)

    async def get_available_number(self, platform, country):
        return await self.db.numbers.find_one({
            "platform": platform,
            "country": country,
            "used": False
        })

    async def mark_number_used(self, number_id, user_id):
        await self.db.numbers.update_one(
            {"_id": number_id},
            {
                "$set": {
                    "used": True,
                    "used_by": user_id,
                    "used_at": datetime.now()
                }
            }
        )

    # Payment Management
    async def add_payment(self, user_id, amount, utr, status="pending"):
        payment_data = {
            "user_id": user_id,
            "amount": amount,
            "utr": utr,
            "status": status,
            "date": datetime.now()
        }
        return await self.db.payments.insert_one(payment_data)

    async def verify_payment(self, utr):
        await self.db.payments.update_one(
            {"utr": utr},
            {"$set": {"status": "verified"}}
        )

    # Admin Functions
    async def add_sudo(self, user_id):
        await self.db.admins.insert_one({"user_id": user_id, "role": "sudo"})

    async def is_sudo(self, user_id):
        return await self.db.admins.find_one({"user_id": user_id})

    async def is_admin(self, user_id):
        return user_id in ADMIN_IDS or await self.is_sudo(user_id)

# Global database instance
db = MongoDB()
