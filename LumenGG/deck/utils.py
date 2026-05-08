from django.utils import timezone

from collection.models import Pack


def get_latest_booster_version():
    latest_pack = Pack.objects.filter(
        released__lte=timezone.now().date()
    ).exclude(
        code__contains='-'
    ).exclude(
        code__startswith='ST'
    ).order_by('-released', '-id').first()

    return latest_pack.code if latest_pack else 'N/A'


def normalize_deck_version(version):
    if not version or version == 'N/A':
        return get_latest_booster_version()
    return version
