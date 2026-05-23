from django.db import models
from card.models import Card, Character
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

class PackTranslation(models.Model):
    LANGUAGE_CHOICES = [
        ('en', 'English'),
        ('ja', '日本語'),
    ]

    pack = models.ForeignKey(Pack, on_delete=models.CASCADE, related_name='translations')
    language = models.CharField(max_length=5, choices=LANGUAGE_CHOICES)
    name = models.CharField(max_length=100, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['pack', 'language'], name='unique_pack_translation_language'),
        ]

    def __str__(self):
        return f'{self.pack.code} / {self.language}'

class CollectionCard(models.Model):
    ITEM_TYPE_CARD = 'card'
    ITEM_TYPE_SKIN = 'skin'
    ITEM_TYPE_TOKEN = 'token'
    ITEM_TYPE_OTHER = 'other'
    ITEM_TYPE_CHOICES = [
        (ITEM_TYPE_CARD, '카드'),
        (ITEM_TYPE_SKIN, '스킨'),
        (ITEM_TYPE_TOKEN, '토큰'),
        (ITEM_TYPE_OTHER, '기타'),
    ]

    card = models.ForeignKey(Card, null=True, on_delete=models.DO_NOTHING, related_name='collection_card')
    character = models.ForeignKey(
        Character,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='collection_cards',
    )
    item_type = models.CharField(max_length=12, choices=ITEM_TYPE_CHOICES, default=ITEM_TYPE_CARD)
    rare = models.CharField(max_length=10, default='')
    code = models.CharField(max_length=20, default='')
    image = models.URLField(blank=True)
    img_sm = models.URLField(blank=True, default='')
    name = models.CharField(max_length=50, default='', blank=True)
    pack = models.ForeignKey(Pack, null=True, on_delete=models.DO_NOTHING, related_name='collection_card')
    
    def __str__(self):
        return self.code + ' - ' + self.name + ' - ' + self.rare
    
    @property
    def isReleased(self):
        if timezone.now().date() >= self.pack.released:
            return True
        return False

class Collected(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='collection')
    card = models.ForeignKey(CollectionCard, on_delete=models.CASCADE, related_name='collected')
    amount = models.SmallIntegerField(default=0)

    def __str__(self):
        return self.user.username + ' <- ' + self.card.name + '-' + self.card.rare
