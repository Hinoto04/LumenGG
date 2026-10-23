"""Versioned tournament policy, independent from card-effect releases."""
import copy
from django.core.exceptions import ValidationError

DEFAULT_RULES = {
    'bans': [], 'combinations': [], 'reserve_limit': 0,
    'technique_swap_limit': 0, 'trait_swap_limit': 0, 'ultimate_swap_limit': 0,
    'reserve_public': False, 'swaps_public': False,
}


def normalize_regulation_rules(value):
    if not isinstance(value, dict) or set(value) - set(DEFAULT_RULES):
        raise ValidationError('규정 항목이 올바르지 않습니다.')
    result = {**copy.deepcopy(DEFAULT_RULES), **copy.deepcopy(value)}
    for key in ('reserve_limit', 'technique_swap_limit', 'trait_swap_limit', 'ultimate_swap_limit'):
        n = result[key]
        if isinstance(n, bool) or not isinstance(n, int) or not 0 <= n <= (1 if key in ('trait_swap_limit', 'ultimate_swap_limit') else 1000):
            raise ValidationError(f'{key}: 한도가 올바르지 않습니다.')
    if result['reserve_limit'] and not all(key in value for key in ('technique_swap_limit', 'trait_swap_limit', 'ultimate_swap_limit')):
        raise ValidationError('교체를 허용하려면 유형별 한도를 모두 지정해주세요.')
    for key in ('reserve_public', 'swaps_public'):
        if not isinstance(result[key], bool):
            raise ValidationError('공개 여부가 올바르지 않습니다.')
    for key in ('bans', 'combinations'):
        if not isinstance(result[key], list) or len(result[key]) > 1000:
            raise ValidationError('금지·제한 목록이 올바르지 않습니다.')
        for rule in result[key]:
            if not isinstance(rule, dict) or set(rule) - {'card_ids', 'scope'}:
                raise ValidationError('금지·제한 항목이 올바르지 않습니다.')
            rule.setdefault('scope', 'registered')
            ids = rule.get('card_ids')
            if rule['scope'] not in ('registered', 'active') or not isinstance(ids, list) or not ids or any(isinstance(n, bool) or not isinstance(n, int) or n <= 0 for n in ids):
                raise ValidationError('카드와 검사 범위를 지정해주세요.')
            if len(ids) != len(set(ids)) or (key == 'combinations' and len(ids) < 2):
                raise ValidationError('제한 조합에는 서로 다른 카드가 2종 이상 필요합니다.')
    return result


def accessible_versions(user):
    from django.db.models import Q
    from .models import RegulationVersion
    q = Q(regulation__owner__isnull=True)
    if user and user.is_authenticated:
        q |= Q(regulation__owner=user)
    return RegulationVersion.objects.filter(q).select_related('regulation').order_by('-published_at')


def version_payload(version):
    return {'id': version.pk, 'regulation_id': version.regulation_id,
            'name': version.regulation.name, 'version': version.version,
            'owner_id': version.regulation.owner_id, 'rules': version.rules,
            'effective_date': version.effective_date.isoformat() if version.effective_date else None,
            'source': version.source}
