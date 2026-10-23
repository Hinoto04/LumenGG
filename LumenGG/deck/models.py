from django.db import models
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
import uuid

from card.models import Character, Card


class Regulation(models.Model):
    name = models.CharField(max_length=120)
    owner = models.ForeignKey(User, null=True, blank=True, on_delete=models.PROTECT, related_name='regulations')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class RegulationVersion(models.Model):
    regulation = models.ForeignKey(Regulation, on_delete=models.PROTECT, related_name='versions')
    version = models.CharField(max_length=64)
    effective_date = models.DateField(null=True, blank=True)
    source = models.URLField(blank=True)
    rules = models.JSONField(default=dict)
    published_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['regulation', 'version'], name='unique_regulation_version')]

    def __str__(self):
        return f'{self.regulation.name} / {self.version}'

    def save(self, *args, **kwargs):
        from .regulations import normalize_regulation_rules
        self.rules = normalize_regulation_rules(self.rules)
        self.full_clean()
        ids = {pk for key in ('bans', 'combinations') for row in self.rules[key] for pk in row['card_ids']}
        if ids and Card.objects.filter(pk__in=ids).count() != len(ids):
            raise ValidationError('존재하지 않는 금지·제한 카드가 있습니다.')
        if self.pk:
            original = type(self).objects.get(pk=self.pk)
            fields = ('regulation_id', 'version', 'effective_date', 'source', 'rules')
            if any(getattr(original, key) != getattr(self, key) for key in fields):
                raise ValidationError('게시된 규정은 변경할 수 없습니다. 새 버전을 게시해주세요.')
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError('사용 기록 보존을 위해 게시된 규정은 삭제할 수 없습니다.')

# Create your models here.
def is_forced_side_card(card):
    return bool(card and not card.ultimate and '특수' in (card.type or ''))


class Deck(models.Model):
    VISIBILITY_PUBLIC = 'public'
    VISIBILITY_UNLISTED = 'unlisted'
    VISIBILITY_PRIVATE = 'private'
    VISIBILITY_CHOICES = [
        (VISIBILITY_PUBLIC, '공개'),
        (VISIBILITY_UNLISTED, '일부 공개'),
        (VISIBILITY_PRIVATE, '비공개'),
    ]

    name = models.CharField(max_length=255, null=False)
    mobile_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    author = models.ForeignKey(User, on_delete=models.CASCADE, related_name='decks')
    character = models.ForeignKey(Character, on_delete=models.CASCADE, related_name='decks')
    trait_card = models.ForeignKey(Card, null=True, blank=True, on_delete=models.PROTECT, related_name='trait_decks')
    regulation_version = models.ForeignKey(RegulationVersion, null=True, blank=True, on_delete=models.PROTECT, related_name='decks')
    schema_version = models.PositiveSmallIntegerField(default=1)
    card = models.ManyToManyField(Card, through="CardInDeck")
    version = models.CharField(max_length=20, default='LMI')
    keyword = models.CharField(max_length=255, default='', blank=True)
    description = models.TextField(blank=True, default="", null=False)
    private = models.BooleanField(default=False)
    visibility = models.CharField(max_length=12, choices=VISIBILITY_CHOICES, default=VISIBILITY_PUBLIC)
    locked = models.BooleanField(default=False)
    deleted = models.BooleanField(default=False)
    tags = models.CharField(max_length=255, default='', blank=True)
    created = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.name} by {self.author.username}"

    def save(self, *args, **kwargs):
        self.private = self.visibility == self.VISIBILITY_PRIVATE
        update_fields = kwargs.get('update_fields')
        if update_fields is not None and 'visibility' in update_fields:
            kwargs['update_fields'] = set(update_fields) | {'private'}
        super().save(*args, **kwargs)
    
    def add_card(self, card:Card):
        card_in_deck, created = CardInDeck.objects.get_or_create(
            deck=self,
            card=card,
        )
        if not created:
            # If the card already exists, increment the count
            card_in_deck.count += 1
        if is_forced_side_card(card):
            card_in_deck.hand = 0
            card_in_deck.side = card_in_deck.count
        card_in_deck.save()
        return card_in_deck

class CardInDeck(models.Model):
    card = models.ForeignKey(Card, on_delete=models.CASCADE, related_name='cids')
    deck = models.ForeignKey(Deck, on_delete=models.CASCADE, related_name='cids')
    count = models.SmallIntegerField(default=1)
    hand = models.SmallIntegerField(default=0)
    side = models.SmallIntegerField(default=0)
    
    def __str__(self):
        return f"{self.deck.name} : {self.card.name} × {self.count}"


class ReserveCardInDeck(models.Model):
    deck = models.ForeignKey(Deck, on_delete=models.CASCADE, related_name='reserve_entries')
    card = models.ForeignKey(Card, on_delete=models.PROTECT)
    count = models.PositiveSmallIntegerField(default=1)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['deck', 'card'], name='unique_deck_reserve_card'),
            models.CheckConstraint(condition=models.Q(count__gt=0), name='positive_deck_reserve_count'),
        ]

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
