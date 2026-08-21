import copy

from django import forms
from django.core.exceptions import ValidationError

from battlelog.game.catalog import effect_source_digest_values, effect_source_qnas
from battlelog.game.sandbox import describe_ability_choices
from battlelog.game.schema import validate_effect_definition

from .models import Card


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


class EffectDefinitionReviewWidget(forms.Textarea):
    template_name = 'admin/card/effect_definition_widget.html'

    class Media:
        css = {'all': ('admin/card-effect-editor.css',)}
        js = ('admin/card-effect-editor.js',)


class CardEffectReviewForm(forms.ModelForm):
    class Meta:
        model = Card
        fields = ('effect_definition',)
        widgets = {'effect_definition': EffectDefinitionReviewWidget()}

    def clean_effect_definition(self):
        definition = copy.deepcopy(self.cleaned_data.get('effect_definition'))
        if isinstance(definition, dict) and definition.get('reviewed') is True:
            definition['draft'] = False
            for ability in definition.get('abilities') or []:
                if isinstance(ability, dict):
                    ability['draft'] = False
            linked_qnas = list(self.instance.qna.all()) if self.instance and self.instance.pk else []
            qnas = effect_source_qnas(
                self.instance, definition=definition, linked_qnas=linked_qnas,
            ) if self.instance and self.instance.pk else []
            definition['source_digest'] = effect_source_digest_values(
                code=self.instance.code,
                text=self.instance.text,
                detail_text=self.instance.detail_text,
                qnas=qnas,
            )
        issues = validate_effect_definition(
            definition,
            card_has_text=bool((self.instance.text or '').strip()),
        )
        if issues:
            raise ValidationError([
                f'{issue.path}: {issue.message}' for issue in issues
            ])
        return definition


def card_effect_review_context(card):
    stored_definition = card.effect_definition
    definition = stored_definition if isinstance(stored_definition, dict) else {}
    qnas = list(card.qna.all().order_by('id'))
    current_qna_ids = {item.id for item in qnas}
    referenced_qna_ids = set(
        (definition.get('source_refs') or {}).get('qna_ids') or []
    )
    general_qna_ids = set(
        (definition.get('source_refs') or {}).get('general_qna_ids') or []
    )
    for ability in definition.get('abilities') or []:
        referenced_qna_ids.update(
            (ability.get('source_refs') or {}).get('qna_ids') or []
        )
        general_qna_ids.update(
            (ability.get('source_refs') or {}).get('general_qna_ids') or []
        )
    all_source_qnas = effect_source_qnas(
        card, definition=definition, linked_qnas=qnas,
    )
    general_qnas = [
        item for item in all_source_qnas if item.id not in current_qna_ids
    ]

    current_digest = effect_source_digest_values(
        code=card.code,
        text=card.text,
        detail_text=card.detail_text,
        qnas=all_source_qnas,
    )
    reviewed = definition.get('reviewed') is True
    approved_digest = definition.get('source_digest')
    validation_issues = validate_effect_definition(
        stored_definition,
        card_has_text=bool((card.text or '').strip()),
    )
    if validation_issues:
        status = 'error'
        status_label = f'정의 오류 {len(validation_issues)}건'
        status_message = '저장 전에 아래 오류와 카드 원문을 함께 확인해 주세요.'
    elif reviewed and approved_digest == current_digest:
        status = 'ok'
        status_label = '검수 완료'
        status_message = '승인 시점의 카드 원문·보충 설명·Q&A와 현재 출처가 일치합니다.'
    elif reviewed:
        status = 'error'
        status_label = '재검수 필요'
        status_message = '승인 후 카드 원문·보충 설명 또는 관련 Q&A가 변경되었습니다.'
    else:
        status = 'pending'
        status_label = '미검수'
        evidence = definition.get('review_evidence') or {}
        status_message = (
            evidence.get('reason')
            or '카드 원문과 자동 해석을 비교한 뒤 검토 완료를 선택해 저장하세요.'
        )

    ability_rows = []
    for index, ability in enumerate(definition.get('abilities') or [], start=1):
        choice_description = describe_ability_choices(ability)
        ability_rows.append({
            'index': index,
            'id': ability.get('id') or '-',
            'source_text': (
                ability.get('draft_text') or ability.get('label')
                or '(표시 문구 없음)'
            ),
            'mode': EFFECT_MODE_LABELS.get(
                ability.get('mode'), ability.get('mode') or '-',
            ),
            'timing': EFFECT_TIMING_LABELS.get(
                ability.get('timing'), ability.get('timing') or '-',
            ),
            'operations': effect_operation_labels(ability.get('effects') or []),
            'is_draft': ability.get('draft') is True,
            'is_compiled': ability.get('draft_compiled') is True,
            'choice_steps': choice_description['steps'],
            'automatic_steps': choice_description['automatic_steps'],
            'choice_warnings': choice_description['warnings'],
        })

    review_evidence = definition.get('review_evidence') or {}
    review_scenarios = []
    for evidence_ability in review_evidence.get('abilities') or []:
        for scenario in evidence_ability.get('scenarios') or []:
            review_scenarios.append({
                **scenario,
                'label': (
                    f'{evidence_ability.get("ability_id") or "효과"} · '
                    f'{scenario.get("name") or "상황"}'
                ),
            })

    return {
        'definition': definition,
        'status': status,
        'status_label': status_label,
        'status_message': status_message,
        'review_evidence': review_evidence,
        'review_scenarios': review_scenarios,
        'ability_rows': ability_rows,
        'validation_issues': validation_issues,
        'qnas': qnas,
        'general_qnas': general_qnas,
        'current_qna_ids': sorted(current_qna_ids),
        'referenced_qna_ids': sorted(referenced_qna_ids),
        'general_qna_ids': sorted(general_qna_ids),
        'missing_qna_ids': sorted(current_qna_ids - referenced_qna_ids),
        'stale_qna_ids': sorted(referenced_qna_ids - current_qna_ids),
    }
