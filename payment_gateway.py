import razorpay
from config import RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET

class RazorpayPayment:
    def __init__(self, key_id, key_secret):
        self.client = razorpay.Client(auth=(key_id, key_secret))
    
    async def create_payment_link(self, amount, user_id):
        data = {
            "amount": amount * 100,  # Convert to paise
            "currency": "INR",
            "accept_partial": False,
            "reference_id": f"user_{user_id}",
            "description": f"Wallet recharge for user {user_id}",
            "customer": {
                "name": f"User_{user_id}",
                "email": f"user_{user_id}@sessionbot.com"
            },
            "notify": {"sms": False, "email": False},
            "reminder_enable": False,
            "callback_url": "https://yourdomain.com/payment_verify",
            "callback_method": "get"
        }
        
        payment_link = self.client.payment_link.create(data=data)
        return payment_link
    
    async def verify_payment(self, payment_id):
        payment = self.client.payment.fetch(payment_id)
        return payment['status'] == 'captured'
