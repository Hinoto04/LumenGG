from django.db import models
from django.contrib.auth.models import User

from card.models import Character, Card

# Create your models here.
class Deck(models.Model):
    name = models.CharField(max_length=50, null=False)
    author = models.ForeignKey(User, on_delete=models.CASCADE, related_name='decks')
    character = models.ForeignKey(Character, on_delete=models.CASCADE, related_name='decks')
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
    card = models.ForeignKey(Card, on_delete=models.CASCADE, related_name='cids')
    deck = models.ForeignKey(Deck, on_delete=models.CASCADE, related_name='cids')
    count = models.SmallIntegerField(default=1)
    hand = models.SmallIntegerField(default=0)
    side = models.SmallIntegerField(default=0)
    
    def __str__(self):
        return f"{self.deck.name} : {self.card.name} × {self.count}"

class DeckLike(models.Model):
    deck = models.ForeignKey(Deck, on_delete=models.CASCADE, related_name='deck_like')
    author = models.ForeignKey(User, on_delete=models.CASCADE, related_name='deck_like')
    like = models.BooleanField(default=False)
    bookmark = models.BooleanField(default=False)
    
    def __str__(self):
        return f"{self.deck.name} : {self.author.username} - \
            {'L' if self.like else ''}{'B' if self.bookmark else ''}"

class DeckComment(models.Model):
    deck = models.ForeignKey(Deck, on_delete=models.CASCADE, related_name='deck_comment')
    author = models.ForeignKey(User, on_delete=models.CASCADE, related_name='deck_comment')
    content = models.TextField()
    created = models.DateTimeField(auto_now_add=True)
    comment = models.ForeignKey('self', on_delete=models.DO_NOTHING, null=True, blank=True, related_name='replies')
    deleted = models.BooleanField(default=False)
    
    def __str__(self):
        return f"{self.deck.name} : {self.author.username} : {self.content}"