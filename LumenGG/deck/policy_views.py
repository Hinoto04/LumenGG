from django import forms
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.shortcuts import render, redirect, get_object_or_404
from card.models import Card
from .models import Regulation, RegulationVersion
from .regulations import accessible_versions, DEFAULT_RULES


class PolicyForm(forms.Form):
    name = forms.CharField(label='규정 이름', max_length=120)
    version = forms.CharField(label='새 버전 이름', max_length=64)
    effective_date = forms.DateField(label='시행일', required=False, widget=forms.DateInput(attrs={'type': 'date'}))
    source = forms.URLField(label='규정 출처', required=False)
    bans = forms.ModelMultipleChoiceField(label='금지 카드', queryset=Card.objects.order_by('code'), required=False)
    combinations = forms.CharField(label='제한 조합', required=False, widget=forms.Textarea(attrs={'rows': 4}),
        help_text='한 줄에 한 조합을 입력하세요. 예: LMI-AT-001 + LMI-AT-002')
    scope = forms.ChoiceField(label='금지·제한 검사 범위', choices=[('registered', '전체 등록 구성'), ('active', '게임 사용 구성')])
    reserve_limit = forms.IntegerField(label='교체 덱 등록 한도', min_value=0, max_value=1000, initial=0)
    technique_swap_limit = forms.IntegerField(label='기술 카드 교체 한도', min_value=0, max_value=1000, initial=0)
    trait_swap_limit = forms.IntegerField(label='특성 교체 허용 횟수', min_value=0, max_value=1, initial=0)
    ultimate_swap_limit = forms.IntegerField(label='얼티밋 교체 허용 횟수', min_value=0, max_value=1, initial=0)
    reserve_public = forms.BooleanField(label='확정 후 교체 덱 공개', required=False)
    swaps_public = forms.BooleanField(label='확정 후 교체 내역 공개', required=False)

    def rules(self):
        data = self.cleaned_data
        combinations = []
        for line in data['combinations'].splitlines():
            codes = [s.strip() for s in line.split('+') if s.strip()]
            if not codes:
                continue
            mapping = dict(Card.objects.filter(code__in=codes).values_list('code', 'id'))
            if len(mapping) != len(codes):
                raise ValidationError('제한 조합의 카드 번호를 확인해주세요.')
            combinations.append({'card_ids': [mapping[c] for c in codes], 'scope': data['scope']})
        return {**{k: data[k] for k in DEFAULT_RULES if k not in ('bans', 'combinations')},
                'bans': [{'card_ids': [c.pk], 'scope': data['scope']} for c in data['bans']], 'combinations': combinations}


@login_required
def manage(request):
    source = get_object_or_404(accessible_versions(request.user), pk=request.GET['copy']) if request.GET.get('copy') else None
    initial = {'version': '', 'scope': 'registered', **DEFAULT_RULES}
    if source:
        initial.update(source.rules)
        initial.update(name=source.regulation.name, source=source.source, effective_date=source.effective_date,
                       bans=[pk for rule in source.rules.get('bans', []) for pk in rule['card_ids']])
        initial['combinations'] = '\n'.join(' + '.join(Card.objects.get(pk=pk).code or str(pk) for pk in rule['card_ids']) for rule in source.rules.get('combinations', []))
        scopes = {r['scope'] for key in ('bans', 'combinations') for r in source.rules.get(key, [])}
        if len(scopes) == 1:
            initial['scope'] = scopes.pop()
    form = PolicyForm(request.POST or None, initial=initial)
    if request.method == 'POST' and form.is_valid():
        try:
            with transaction.atomic():
                regulation = source.regulation if source and source.regulation.owner_id == request.user.pk else Regulation.objects.create(name=form.cleaned_data['name'], owner=request.user)
                published = RegulationVersion(regulation=regulation, version=form.cleaned_data['version'], rules=form.rules(),
                                              effective_date=form.cleaned_data['effective_date'], source=form.cleaned_data['source'])
                published.full_clean()
                published.save()
            return redirect('deck:manageRegulations')
        except ValidationError as exc:
            form.add_error(None, exc)
    return render(request, 'deck/regulations_v2.html', {'form': form, 'versions': accessible_versions(request.user), 'source_version': source})
