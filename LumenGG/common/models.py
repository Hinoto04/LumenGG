from django.db import models
from django.contrib.auth.models import User

from card.models import Character, Card

# Create your models here.
def getUsername(self):
    return self.username

User.add_to_class("__str__", getUsername)

class UserData(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='data')
    character = models.ForeignKey(Character, on_delete=models.SET_NULL, null=True, related_name="mosted")
    card1 = models.ForeignKey(Card, on_delete=models.SET_NULL, null=True, related_name="most1ed")
    card2 = models.ForeignKey(Card, on_delete=models.SET_NULL, null=True, related_name="most2ed")
    card3 = models.ForeignKey(Card, on_delete=models.SET_NULL, null=True, related_name="most3ed")
    
    def __str__(self):
        return self.user.username

class SiteSettings(models.Model):
    name = models.CharField(max_length=30)
    setting = models.JSONField()
    
    def __str__(self):
        return self.name