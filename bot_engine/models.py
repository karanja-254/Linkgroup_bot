from django.db import models

class TelegramUser(models.Model):
    telegram_id = models.BigIntegerField(unique=True)
    username = models.CharField(max_length=255, null=True, blank=True)
    first_name = models.CharField(max_length=255, null=True, blank=True)
    phone_number = models.CharField(max_length=15, null=True, blank=True)
    # Credits: How many paid posts they have available
    credits = models.IntegerField(default=0)
    joined_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.username} ({self.credits} credits)"

class Transaction(models.Model):
    user = models.ForeignKey(TelegramUser, on_delete=models.CASCADE)
    checkout_request_id = models.CharField(max_length=255, unique=True) # M-Pesa ID
    amount = models.IntegerField()
    mpesa_receipt_number = models.CharField(max_length=255, null=True, blank=True)
    phone_number = models.CharField(max_length=15)
    is_completed = models.BooleanField(default=False)
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.phone_number} - {self.amount} KES"

class PendingAd(models.Model):
    """Stores the ad content while waiting for payment"""
    user = models.ForeignKey(TelegramUser, on_delete=models.CASCADE)
    message_text = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    is_posted = models.BooleanField(default=False)

    def __str__(self):
        return f"Ad by {self.user.username}"