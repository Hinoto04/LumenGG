"""Atomic persistence of v2 fields, also used by the web builder and imports."""
from django.core.exceptions import ValidationError
from .models import ReserveCardInDeck, Regulation, RegulationVersion
from .regulations import accessible_versions
from .traits import selected_trait


def apply_extensions(deck, data, user):
    if isinstance(data.get('schema_version', 1), bool) or data.get('schema_version', 1) not in (1, 2):
        raise ValidationError('지원하지 않는 덱 형식입니다.')
    modern = data.get('schema_version') == 2
    if not modern:
        if deck.pk and deck.schema_version >= 2:
            raise ValidationError('이 덱을 수정하려면 최신 앱 또는 덱 작성기를 사용해주세요.')
        if deck.trait_card_id and deck.trait_card.character_id != deck.character_id:
            deck.trait_card = selected_trait(deck.character_id)
            deck.save(update_fields=['trait_card'])
        return
    try:
        trait_id = data.get('trait_card_id')
        if trait_id is not None and (isinstance(trait_id, bool) or not isinstance(trait_id, int)):
            raise ValueError('특성 번호가 올바르지 않습니다.')
        trait = selected_trait(deck.character_id, trait_id)
    except (TypeError, ValueError) as exc:
        raise ValidationError(str(exc)) from exc
    version_id = data.get('regulation_version_id')
    if version_id is not None and (isinstance(version_id, bool) or not isinstance(version_id, int) or version_id < 1):
        raise ValidationError('규정 번호가 올바르지 않습니다.')
    version = accessible_versions(user).filter(pk=version_id).first() if version_id else None
    if not version and version_id and deck.regulation_version_id == version_id:
        # A copied public deck may retain its original owner's immutable policy.
        version = deck.regulation_version
    imported = data.get('imported_regulation')
    if imported is not None:
        if not isinstance(imported, dict):
            raise ValidationError('가져올 규정이 올바르지 않습니다.')
        from .regulations import normalize_regulation_rules
        imported_rules = normalize_regulation_rules(imported.get('rules', {}))
        if version and version.rules != imported_rules:
            version = None
        if not version:
            previous = deck.regulation_version
            if previous and previous.regulation.owner_id == user.pk and previous.rules == imported_rules:
                version = previous
            else:
                owned = Regulation.objects.create(name=str(imported.get('name') or '가져온 규정')[:120], owner=user)
                version = RegulationVersion.objects.create(regulation=owned, version=str(imported.get('version') or '1')[:64], rules=imported_rules, source=imported.get('source') or '', effective_date=imported.get('effective_date') or None)
    if version_id and not version:
        raise ValidationError('선택할 수 없는 규정입니다.')
    reserve = data.get('reserve_cards', [])
    if not isinstance(reserve, list) or len(reserve) > 1000:
        raise ValidationError('교체 덱 목록이 올바르지 않습니다.')
    from card.models import Card
    seen = set()
    for row in reserve:
        if not isinstance(row, dict):
            raise ValidationError('교체 카드 항목이 올바르지 않습니다.')
        pk, count = row.get('card_id'), row.get('count')
        if any(isinstance(n, bool) or not isinstance(n, int) or not 1 <= n <= 32767 for n in (pk, count)) or pk in seen:
            raise ValidationError('교체 카드 수량이나 번호가 올바르지 않습니다.')
        seen.add(pk)
    if Card.objects.filter(pk__in=seen).count() != len(seen):
        raise ValidationError('존재하지 않는 교체 카드가 있습니다.')
    deck.schema_version = 2
    deck.trait_card = trait
    deck.regulation_version = version
    deck.save()
    deck.reserve_entries.all().delete()
    ReserveCardInDeck.objects.bulk_create([ReserveCardInDeck(deck=deck, **row) for row in reserve])
    from .validation import snapshot_deck, validate
    report = validate(snapshot_deck(deck), stage='draft')
    if not report['is_valid']:
        raise ValidationError([i['message'] for i in report['issues'] if i['severity'] == 'error'])


def copy_extensions(source, target):
    target.trait_card_id = source.trait_card_id
    target.regulation_version_id = source.regulation_version_id
    target.schema_version = source.schema_version
    target.save(update_fields=['trait_card', 'regulation_version', 'schema_version'])
    ReserveCardInDeck.objects.bulk_create([ReserveCardInDeck(deck=target, card_id=e.card_id, count=e.count) for e in source.reserve_entries.all()])
