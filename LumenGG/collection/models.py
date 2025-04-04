from django.db import models
from card.models import Card
from django.contrib.auth.models import User
from django.utils import timezone
import datetime

# Create your models here.
class Pack(models.Model):
    name = models.CharField(max_length=100, default='')
    code = models.CharField(max_length=20, default='')
    released = models.DateField(null=True, blank=True, default=datetime.date(2024,2,20))
    
    def __str__(self):
        return self.code + ' - ' + self.name

class CollectionCard(models.Model):
    card = models.ForeignKey(Card, null=True, on_delete=models.DO_NOTHING, related_name='collection_card')
    rare = models.CharField(max_length=10, default='')
    code = models.CharField(max_length=20, default='')
    image = models.URLField(blank=True)
    name = models.CharField(max_length=50, default='', blank=True)
    pack = models.ForeignKey(Pack, null=True, on_delete=models.DO_NOTHING, related_name='collection_card')
    
    def __str__(self):
        return self.code + ' - ' + self.card.name + ' - ' + self.rare

class Collected(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='collection')
    card = models.ForeignKey(CollectionCard, on_delete=models.CASCADE, related_name='collected')
    amount = models.SmallIntegerField(default=0)

    def __str__(self):
        return self.user.username + ' <- ' + self.card.card.name + '-' + self.card.rare
