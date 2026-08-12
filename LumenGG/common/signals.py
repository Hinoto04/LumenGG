from django.db.models.signals import post_save
from django.dispatch import receiver

from card.models import Card, CardTranslation, Character, CharacterTranslation
from common.localization import (
    sync_card_source,
    sync_card_translation,
    sync_character_source,
    sync_character_translation,
    sync_term_translation,
)
from common.models import TermTranslation


@receiver(post_save, sender=Card)
def sync_card_source_on_save(sender, instance, **kwargs):
    sync_card_source(instance)


@receiver(post_save, sender=CardTranslation)
def sync_card_translation_on_save(sender, instance, **kwargs):
    sync_card_translation(instance)


@receiver(post_save, sender=Character)
def sync_character_source_on_save(sender, instance, **kwargs):
    sync_character_source(instance)


@receiver(post_save, sender=CharacterTranslation)
def sync_character_translation_on_save(sender, instance, **kwargs):
    sync_character_translation(instance)


@receiver(post_save, sender=TermTranslation)
def sync_term_translation_on_save(sender, instance, **kwargs):
    sync_term_translation(instance)
