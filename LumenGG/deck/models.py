from django.db import models
from django.contrib.auth.models import User

from card.models import Character, Card

# Create your models here.
class Deck(models.Model):
    name = models.CharField(max_length=25, null=False)
    author = models.ForeignKey(User, on_delete=models.CASCADE)
    character = models.ForeignKey(Character, on_delete=models.CASCADE)
    card = models.ManyToManyField(Card, through="CardInDeck")
    version = models.CharField(max_length=5, default='LMI')
    keyword = models.CharField(max_length=255, default='', blank=True)
    description = models.TextField(blank=True, default="", null=False)
    private = models.BooleanField(default=False)
    deleted = models.BooleanField(default=False)
    tags = models.CharField(max_length=255, default='', blank=True)
    created = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.name} by {self.author.username}"

class CardInDeck(models.Model):
    card = models.ForeignKey(Card, on_delete=models.CASCADE)
    deck = models.ForeignKey(Deck, on_delete=models.CASCADE)
    count = models.SmallIntegerField(default=1)
    hand = models.SmallIntegerField(default=0)
    side = models.SmallIntegerField(default=0)
    
    def __str__(self):
        return f"{self.deck.name} : {self.card.name} × {self.count}"