from django.core.management.base import BaseCommand

from card.models import Card, CardTranslation, Character, CharacterTranslation


FIELDS = ('text', 'detail_text')
LANGUAGES = ('en', 'ja')


class Command(BaseCommand):
    help = 'Convert clear card/character name references to localization tokens.'

    def add_arguments(self, parser):
        parser.add_argument('--apply', action='store_true', help='Write clear replacements. Without this, only prints a dry-run report.')
        parser.add_argument('--samples', type=int, default=50)

    def handle(self, *args, **options):
        apply_changes = options['apply']
        sample_limit = options['samples']
        total = 0
        samples = []

        source_targets = self.source_targets()
        for card in Card.objects.order_by('id'):
            changed = self.convert_object_text(card, source_targets)
            if changed:
                total += len(changed)
                samples.extend([
                    (f'{card.code}.{field}', old, new)
                    for field, old, new in changed
                ])
                if apply_changes:
                    card.save(update_fields=[field for field, _old, _new in changed])

        for language in LANGUAGES:
            targets = self.translation_targets(language)
            for translation in CardTranslation.objects.filter(language=language).select_related('card').order_by('card_id'):
                changed = self.convert_object_text(translation, targets)
                if changed:
                    total += len(changed)
                    samples.extend([
                        (f'{translation.card.code}/{language}.{field}', old, new)
                        for field, old, new in changed
                    ])
                    if apply_changes:
                        translation.save(update_fields=[field for field, _old, _new in changed])

        label = 'Applied' if apply_changes else 'Dry-run'
        self.stdout.write(f'{label}: {total} field replacements')
        for item in samples[:sample_limit]:
            if len(item) == 3 and isinstance(item[0], str) and '.' in item[0]:
                owner, old, new = item
            else:
                owner, old, new = item
            self.stdout.write(f'  {owner}: {old[:80]} -> {new[:80]}')
        if not apply_changes:
            self.stdout.write('Run again with --apply to write these unambiguous replacements.')

    def convert_object_text(self, obj, targets):
        changed = []
        owner = getattr(getattr(obj, 'card', obj), 'code', str(obj.pk))
        for field in FIELDS:
            old = getattr(obj, field, '') or ''
            if not old or '[[' in old:
                continue
            new = self.replace_targets(old, targets, owner)
            if new != old:
                setattr(obj, field, new)
                changed.append((field, old, new))
        return changed

    def replace_targets(self, text, targets, owner):
        replaced = text
        for name, token, target_owner in targets:
            if target_owner == owner:
                continue
            replaced = replaced.replace(name, token)
        return replaced

    def source_targets(self):
        card_targets = [
            (card.name, f'[[card:{card.code}]]', card.code)
            for card in Card.objects.exclude(name='').exclude(code='')
        ]
        character_targets = [
            (character.name, f'[[character:{character.localization_key}]]', character.localization_key)
            for character in Character.objects.exclude(name='').exclude(localization_key='')
        ]
        return self.safe_targets(card_targets + character_targets)

    def translation_targets(self, language):
        card_names = {
            translation.card_id: translation.name
            for translation in CardTranslation.objects.filter(language=language).select_related('card')
            if translation.name
        }
        card_targets = [
            (name, f'[[card:{card.code}]]', card.code)
            for card in Card.objects.exclude(code='')
            for name in [card_names.get(card.id)]
            if name
        ]
        character_names = {
            translation.character_id: translation.name
            for translation in CharacterTranslation.objects.filter(language=language)
            if translation.name
        }
        character_targets = [
            (name, f'[[character:{character.localization_key}]]', character.localization_key)
            for character in Character.objects.exclude(localization_key='')
            for name in [character_names.get(character.id)]
            if name
        ]
        return self.safe_targets(card_targets + character_targets)

    def safe_targets(self, targets):
        names = [name for name, _token, _owner in targets if len(name) >= 3]
        unsafe = {
            name
            for name in names
            for other in names
            if name != other and name in other
        }
        safe = [
            (name, token, owner)
            for name, token, owner in targets
            if len(name) >= 3 and name not in unsafe
        ]
        return sorted(safe, key=lambda item: len(item[0]), reverse=True)
