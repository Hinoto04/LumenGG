from django import forms
from django.contrib import admin, messages
from django.core.exceptions import ValidationError
from django.http import HttpResponseRedirect
from django.urls import reverse
from django.utils.html import format_html, format_html_join

from battlelog.game.schema import validate_effect_definition
from battlelog.game.catalog import effect_source_digest_values
from .models import Character, CharacterTranslation, Card, CardTranslation, CardComment, CharacterComment


EFFECT_MODE_LABELS = {
    'mandatory': '강제',
    'optional': '선택',
    'continuous': '상시',
    'replacement': '대체',
}
EFFECT_TIMING_LABELS = {
    'function': '기능',
    'replacement': '대체',
    'use': '사용 시',
    'before_judgment': '판정 전',
    'dodge': '회피 시',
    'opponent_dodge': '상대 회피 시',
    'guard': '방어 시',
    'opponent_guard': '상대 방어 시',
    'hit_counter': '히트·카운터 시',
    'opponent_hit_counter': '상대 히트·카운터 시',
    'clash': '상쇄 시',
    'opponent_clash': '상대 상쇄 시',
    'combo': '콤보 시',
    'result': '판정 결과',
    'after_judgment': '판정 후',
    'after_use': '사용 후',
    'catch': '캐치 시',
    'cleanup': '정리 시',
}
EFFECT_OPERATION_LABELS = {
    'deal_damage': '데미지 처리',
    'change_hp': 'HP 변경',
    'change_fp': 'FP 변경',
    'reset_fp': 'FP 초기화',
    'move_card': '카드 이동',
    'draw': '카드 획득',
    'discard': '카드 버리기',
    'reveal': '카드 공개',
    'hide': '카드 비공개',
    'break_card': '브레이크',
    'break_cards': '여러 카드 일괄 브레이크',
    'create_token': '토큰 생성',
    'delete_token': '토큰 제거',
    'gain_state': '상태 획득',
    'lose_state': '상태 제거',
    'change_counter': '카운터 변경',
    'set_counter': '카운터 설정',
    'gain_shield': '보호막 획득',
    'modify_stat': '수치 변경',
    'fix_speed': '속도 고정',
    'modify_damage': '데미지 변경',
    'modify_judgment': '판정 변경',
    'prevent': '행동·효과 금지',
    'negate': '효과 무효',
    'replace': '효과 대체',
    'skip_phase': '페이즈 스킵',
    'skip_get': 'Get 스킵',
    'repeat_phase': '페이즈 반복',
    'schedule': '지연 효과 예약',
    'random_select': '무작위 선택',
    'request_choice': '대상 선택 요청',
    'choose_effect': '효과 선택 요청',
    'start_combo': '콤보 시작',
    'end_combo': '콤보 종료',
    'grant_catch': '캐치 부여',
    'end_catch': '캐치 종료',
    'modify_combo': '콤보 규칙 변경',
    'set_usage_limit': '사용 제한 설정',
    'end_battle': '배틀 종료',
    'end_turn': '턴 종료',
    'win_game': '게임 승리',
    'conditional': '조건부 처리',
    'sequence': '순차 처리',
    'emit_event': '타이밍 발생',
    'log': '기록',
}


def effect_operation_labels(effects):
    """Return compact, ordered labels for every executable node in an ability."""
    labels = []

    def visit(value):
        if isinstance(value, list):
            for item in value:
                visit(item)
            return
        if not isinstance(value, dict):
            return
        operation = value.get('op')
        if operation == 'static_rule':
            return
        if operation in EFFECT_OPERATION_LABELS:
            label = EFFECT_OPERATION_LABELS[operation]
            if label not in labels:
                labels.append(label)
        for key in ('then', 'else', 'effects', 'commands', 'choices'):
            visit(value.get(key))

    visit(effects)
    return labels


class EffectDefinitionWidget(forms.Textarea):
    template_name = 'admin/card/effect_definition_widget.html'

    class Media:
        css = {'all': ('admin/card-effect-editor.css',)}
        js = ('admin/card-effect-editor.js',)


class CardAdminForm(forms.ModelForm):
    class Meta:
        model = Card
        fields = '__all__'
        widgets = {'effect_definition': EffectDefinitionWidget()}

    def clean_effect_definition(self):
        definition = self.cleaned_data.get('effect_definition')
        previous = (self.instance.effect_definition or {}) if self.instance and self.instance.pk else {}
        if definition.get('reviewed') is True and previous.get('reviewed') is not True:
            definition = dict(definition)
            qnas = list(self.instance.qna.all()) if self.instance and self.instance.pk else []
            definition['source_digest'] = effect_source_digest_values(
                code=self.cleaned_data.get('code'),
                text=self.cleaned_data.get('text'),
                detail_text=self.cleaned_data.get('detail_text'),
                qnas=qnas,
            )
        issues = validate_effect_definition(definition, card_has_text=bool((self.cleaned_data.get('text') or '').strip()))
        if issues:
            raise ValidationError([f'{issue.path}: {issue.message}' for issue in issues])
        return definition


class EffectReviewFilter(admin.SimpleListFilter):
    title = '자동 효과 검토'
    parameter_name = 'effect_review'

    def lookups(self, request, model_admin):
        return (
            ('reviewed', '검토 완료'),
            ('unreviewed', '미검토'),
            ('abilities', '능력 정의 있음'),
            ('no_effect', '효과 없음'),
        )

    def queryset(self, request, queryset):
        if self.value() == 'reviewed':
            return queryset.filter(effect_definition__reviewed=True)
        if self.value() == 'unreviewed':
            return queryset.exclude(effect_definition__reviewed=True)
        if self.value() == 'abilities':
            return queryset.exclude(effect_definition__abilities=[])
        if self.value() == 'no_effect':
            return queryset.filter(effect_definition__no_effect=True)
        return queryset

class CharacterTranslationInline(admin.StackedInline):
    model = CharacterTranslation
    extra = 0

class CharacterAdmin(admin.ModelAdmin):
    list_display = ('name', 'description', 'group')
    list_filter = ('group',)
    search_fields = ('name',)
    inlines = [CharacterTranslationInline]

class CardTranslationInline(admin.StackedInline):
    model = CardTranslation
    extra = 0

class CardAdmin(admin.ModelAdmin):
    form = CardAdminForm
    change_form_template = 'admin/card/card/change_form.html'
    list_display = ('name', 'code', 'character', 'type', 'effect_review_status', 'effect_revision', 'effect_updated_at')
    list_filter = (EffectReviewFilter, 'character', 'type')
    search_fields = ('name', 'pos', 'special', 'frame', 'code', 'detail_text', 'translations__name', 'translations__text')
    inlines = [CardTranslationInline]
    readonly_fields = ('effect_revision', 'effect_updated_at', 'related_qna_summary', 'effect_review_summary')
    fieldsets = (
        (None, {'fields': ('name', 'ruby', 'code', 'character', 'type', 'ultimate')}),
        ('기본 수치', {'fields': ('frame', 'damage', 'pos', 'body', 'special', 'hit', 'guard', 'counter', 'g_top', 'g_mid', 'g_bot')}),
        ('카드 원문과 재정', {'fields': ('text', 'detail_text', 'related_qna_summary')}),
        ('자동 효과 검수 요약', {'fields': ('effect_review_summary',)}),
        ('자동 효과 정의 편집', {'classes': ('collapse',), 'fields': ('effect_definition', 'effect_revision', 'effect_updated_at')}),
        ('이미지와 검색', {'classes': ('collapse',), 'fields': ('img', 'img_mid', 'img_sm', 'hiddenKeyword', 'keyword', 'search')}),
    )

    def _next_unreviewed_card(self, current_pk):
        queryset = self.model._default_manager.exclude(
            effect_definition__reviewed=True,
        ).exclude(pk=current_pk).order_by('pk')
        return queryset.filter(pk__gt=current_pk).first() or queryset.first()

    def changeform_view(self, request, object_id=None, form_url='', extra_context=None):
        context = dict(extra_context or {})
        if object_id:
            next_card = self._next_unreviewed_card(object_id)
            if next_card:
                context['next_unreviewed_url'] = reverse(
                    'admin:card_card_change', args=(next_card.pk,),
                )
                context['next_unreviewed_label'] = f'{next_card.code} · {next_card.name}'
            context['unreviewed_card_count'] = self.model._default_manager.exclude(
                effect_definition__reviewed=True,
            ).count()
        return super().changeform_view(request, object_id, form_url, context)

    def response_change(self, request, obj):
        if '_saveandnextunreviewed' in request.POST:
            next_card = self._next_unreviewed_card(obj.pk)
            if next_card:
                self.message_user(
                    request,
                    f'{obj} 저장 완료. 다음 미검수 카드로 이동했습니다.',
                    messages.SUCCESS,
                )
                return HttpResponseRedirect(reverse(
                    'admin:card_card_change', args=(next_card.pk,),
                ))
            self.message_user(request, '저장 완료. 남은 미검수 카드가 없습니다.', messages.SUCCESS)
            return HttpResponseRedirect(reverse('admin:card_card_changelist'))
        return super().response_change(request, obj)

    @admin.display(description='자동 효과')
    def effect_review_status(self, obj):
        definition = obj.effect_definition or {}
        if definition.get('draft') is True:
            abilities = definition.get('abilities') or []
            compiled = sum(1 for ability in abilities if ability.get('draft_compiled'))
            return f'초안 · 명령 후보 {compiled}/{len(abilities)}개'
        if definition.get('reviewed') is not True:
            return '미검토'
        if definition.get('no_effect'):
            return '검토 완료 · 효과 없음'
        return f'검토 완료 · 능력 {len(definition.get("abilities") or [])}개'

    @admin.display(description='관련 Q&A')
    def related_qna_summary(self, obj):
        if not obj or not obj.pk:
            return '-'
        rows = obj.qna.all().order_by('-created_at', '-id')
        if not rows:
            return '-'
        return format_html_join('', '<details><summary><a href="{}">#{} {}</a></summary><p><b>Q.</b> {}</p><p><b>A.</b> {}</p></details>', (
            (
                reverse('admin:qna_qna_change', args=(item.pk,)),
                item.id,
                item.title,
                item.question,
                item.answer,
            )
            for item in rows
        ))

    @admin.display(description='원문 대비 자동 해석')
    def effect_review_summary(self, obj):
        if not obj or not obj.pk:
            return '카드를 먼저 저장하면 검수 요약이 표시됩니다.'
        definition = obj.effect_definition or {}
        qnas = list(obj.qna.all().order_by('id'))
        current_qna_ids = {item.id for item in qnas}
        referenced_qna_ids = set((definition.get('source_refs') or {}).get('qna_ids') or [])
        for ability in definition.get('abilities') or []:
            referenced_qna_ids.update((ability.get('source_refs') or {}).get('qna_ids') or [])

        reviewed = definition.get('reviewed') is True
        current_digest = effect_source_digest_values(
            code=obj.code,
            text=obj.text,
            detail_text=obj.detail_text,
            qnas=qnas,
        )
        approved_digest = definition.get('source_digest')
        if not reviewed:
            source_status = '미검수 · 원문과 아래 자동 해석을 비교하세요.'
            source_class = 'is-pending'
        elif not approved_digest:
            source_status = '재검수 필요 · 승인된 출처 해시가 없습니다.'
            source_class = 'is-error'
        elif approved_digest != current_digest:
            source_status = '재검수 필요 · 검수 후 카드 원문·보충 설명·Q&A가 변경되었습니다.'
            source_class = 'is-error'
        else:
            source_status = '검수 완료 · 현재 원문과 Q&A가 승인 시점과 일치합니다.'
            source_class = 'is-ok'

        source_difference = ''
        if current_qna_ids != referenced_qna_ids:
            missing = sorted(current_qna_ids - referenced_qna_ids)
            stale = sorted(referenced_qna_ids - current_qna_ids)
            pieces = []
            if missing:
                pieces.append(f'정의에 빠진 현재 Q&A: {missing}')
            if stale:
                pieces.append(f'더 이상 연결되지 않은 Q&A 참조: {stale}')
            source_difference = ' · '.join(pieces)

        ability_rows = []
        for index, ability in enumerate(definition.get('abilities') or [], start=1):
            source_text = ability.get('draft_text') or ability.get('label') or '(표시 문구 없음)'
            mode = EFFECT_MODE_LABELS.get(ability.get('mode'), ability.get('mode') or '-')
            timing = EFFECT_TIMING_LABELS.get(ability.get('timing'), ability.get('timing') or '-')
            operations = effect_operation_labels(ability.get('effects') or [])
            ability_rows.append((
                index,
                source_text,
                f'{mode} · {timing}',
                ', '.join(operations) if operations else '관련 실행 명령 없음(상시·구성 규칙)',
                '초안' if ability.get('draft') else '검수 대상',
            ))

        if ability_rows:
            abilities_html = format_html_join(
                '',
                '<li><div class="effect-review-source"><b>{}. {}</b><span>{}</span></div>'
                '<div class="effect-review-result">자동 해석: {} <em>{}</em></div></li>',
                ability_rows,
            )
        elif definition.get('no_effect'):
            abilities_html = format_html('<p class="effect-review-empty">효과 없음으로 정의된 카드입니다.</p>')
        else:
            abilities_html = format_html('<p class="effect-review-empty">능력 정의가 없습니다.</p>')

        return format_html(
            '<div class="effect-review-overview">'
            '<p class="effect-review-status {}"><b>{}</b></p>'
            '{}'
            '<p class="effect-review-qna">현재 관련 Q&A: {} · 정의가 참조하는 Q&A: {}</p>'
            '<ol class="effect-review-abilities">{}</ol>'
            '<p class="help">원문과 자동 해석이 같으면 아래 “자동 효과 정의 편집”을 펼쳐 초안 표시를 해제하고 검토 완료를 선택한 뒤 저장하세요.</p>'
            '</div>',
            source_class,
            source_status,
            format_html('<p class="effect-review-warning">{}</p>', source_difference) if source_difference else '',
            ', '.join(map(str, sorted(current_qna_ids))) or '없음',
            ', '.join(map(str, sorted(referenced_qna_ids))) or '없음',
            abilities_html,
        )

class CharCommentAdmin(admin.ModelAdmin):
    list_display = ('author', 'character', 'power', 'combo', 'reversal', 'safety', 'tempo')
    list_filter = ('character',)
    search_fields = ('author__username',)

class CardCommentAdmin(admin.ModelAdmin):
    list_display = ('author', 'card', 'score')
    search_fields = ('card__name', 'author__username')

# Register your models here.
admin.site.register(Character, CharacterAdmin)
admin.site.register(Card, CardAdmin)
admin.site.register(CharacterTranslation)
admin.site.register(CardTranslation)
admin.site.register(CardComment, CardCommentAdmin)
admin.site.register(CharacterComment, CharCommentAdmin)
