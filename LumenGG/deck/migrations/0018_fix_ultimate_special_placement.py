from django.db import migrations
from django.db.models import F, Q


def fix_fixed_placements(apps, schema_editor):
    """예전 덱 빌더가 저장한 고정 위치를 규칙에 맞게 정리한다(룰북 p20).

    - 얼티밋은 패·사이드가 아닌 얼티밋 영역에 둔다.
    - 특수 기술은 전부 사이드 덱에 둔다.
    """
    CardInDeck = apps.get_model('deck', 'CardInDeck')
    CardInDeck.objects.filter(card__ultimate=True).exclude(hand=0, side=0).update(hand=0, side=0)
    (
        CardInDeck.objects
        .filter(card__type__contains='특수', card__ultimate=False)
        .exclude(card__type='특성').exclude(card__code__icontains='PS')
        .filter(Q(hand__gt=0) | ~Q(side=F('count')))
        .update(hand=0, side=F('count'))
    )


class Migration(migrations.Migration):
    dependencies = [('deck', '0017_unrestrict_basic_regulation_decks')]

    operations = [
        migrations.RunPython(fix_fixed_placements, migrations.RunPython.noop),
    ]
