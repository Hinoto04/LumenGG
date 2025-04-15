from django.db import models
from deck.models import Deck

# Create your models here.
class Championship(models.Model):
    name = models.CharField(max_length=50)
    description = models.TextField()
    datetime = models.DateField(auto_created=True)
    decks = models.ManyToManyField(Deck, through="CSDeck")
    
    def __str__(self):
        return self.name

class CSDeck(models.Model):
    cs = models.ForeignKey(Championship, on_delete=models.CASCADE)
    deck = models.ForeignKey(Deck, on_delete=models.CASCADE, related_name='csdecks')
    place = models.CharField(max_length=10, blank=True)
    user = models.CharField(max_length=30, default='', blank=True)
    
    def __str__(self):
        return self.cs.name + ' - ' + self.place + ' - ' + self.deck.name