from django.contrib import admin
from .models import Deck, CardInDeck

# Register your models here.
admin.site.register(Deck)
admin.site.register(CardInDeck)