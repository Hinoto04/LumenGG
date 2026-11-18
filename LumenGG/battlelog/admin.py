from django.contrib import admin, messages
from django.db import transaction
from django.shortcuts import redirect, render
from django.urls import path, reverse
from django.utils import timezone
from django import forms
from django.utils.html import format_html, format_html_join

from .game.catalog import RulesetPublicationError, publish_ruleset_release, validate_catalog
from .automatic_services import active_ai_policy, ai_policy_activation_issues
from .game.ai import DEFAULT_POLICY_WEIGHTS
from .game.ai_decisions import DEFAULT_EFFECT_RULES
from .game.ai_profile import CONDITION_KEYS, EFFECT_RULE_KEYS, STYLE_CHOICES, WEIGHT_DESCRIPTIONS, ProfileError
from .models import (
    AutomaticIssueComment,
    AutomaticIssueReport,
    BattleEvent,
    BattleSession,
    BattleSet,
    LumenSimulatorSession,
    PartyCard,
    RulesetRelease,
    SimulatorAIDeck,
    SimulatorAIPolicy,
)


@admin.register(PartyCard)
class PartyCardAdmin(admin.ModelAdmin):
    list_display = ['code', 'kind', 'name', 'effect_text', 'updated_at']
    list_filter = ['kind']
    search_fields = ['code', 'name', 'effect_text']
    readonly_fields = ['code', 'kind', 'key', 'effect_box', 'updated_at']

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(BattleSession)
class BattleSessionAdmin(admin.ModelAdmin):
    list_display = [
        'id',
        'session_type',
        'player1_name',
        'player2_name',
        'tournament_match',
        'expires_at',
        'updated_at',
    ]
    list_filter = ['session_type', 'sudden_death']
    search_fields = ['player1_name', 'player2_name', 'view_token', 'control_token']
    readonly_fields = ['view_token', 'control_token', 'created_at', 'updated_at']


@admin.register(BattleEvent)
class BattleEventAdmin(admin.ModelAdmin):
    list_display = ['id', 'session', 'event_type', 'target', 'amount', 'actor_label', 'created_at', 'undone']
    list_filter = ['event_type', 'target', 'undone']
    search_fields = ['session__player1_name', 'session__player2_name', 'actor_label', 'event_uid']
    readonly_fields = ['event_uid', 'created_at']


@admin.register(BattleSet)
class BattleSetAdmin(admin.ModelAdmin):
    list_display = ['id', 'session', 'set_number', 'status', 'winner_side', 'ended_at']
    list_filter = ['status', 'winner_side']
    search_fields = ['session__player1_name', 'session__player2_name']
    readonly_fields = ['started_at', 'ended_at']


@admin.register(LumenSimulatorSession)
class LumenSimulatorSessionAdmin(admin.ModelAdmin):
    list_display = ['id', 'player1_name', 'player2_name', 'mode', 'player2_controller', 'ruleset_release', 'ai_policy', 'version', 'expires_at', 'updated_at']
    list_filter = ['mode', 'player1_controller', 'player2_controller', 'ruleset_release', 'ai_policy']
    search_fields = ['player1_name', 'player2_name', 'view_token', 'player1_token', 'player2_token']
    readonly_fields = ['view_token', 'player1_token', 'player2_token', 'created_at', 'updated_at']


@admin.register(SimulatorAIPolicy)
class SimulatorAIPolicyAdmin(admin.ModelAdmin):
    list_display = ['name', 'version', 'algorithm', 'training_games', 'is_active', 'created_at']
    list_filter = ['algorithm', 'is_active']
    search_fields = ['name', 'version']
    readonly_fields = [
        'name', 'version', 'algorithm', 'weights', 'metrics', 'training_games',
        'is_active', 'created_at', 'activated_at',
    ]
    actions = ['activate_selected']

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return request.user.has_perm('battlelog.train_ai_policy')

    @admin.action(description='선택한 한 AI 정책을 활성화')
    def activate_selected(self, request, queryset):
        if queryset.count() != 1:
            self.message_user(request, '한 개의 AI 정책만 선택하세요.', level=messages.ERROR)
            return
        policy = queryset.first()
        activation_issues = ai_policy_activation_issues(policy)
        if activation_issues:
            self.message_user(
                request,
                'AI 정책을 활성화할 수 없습니다: ' + ' '.join(activation_issues),
                level=messages.ERROR,
            )
            return
        with transaction.atomic():
            list(SimulatorAIPolicy.objects.select_for_update().values_list('id', flat=True))
            SimulatorAIPolicy.objects.filter(is_active=True).exclude(pk=policy.pk).update(is_active=False)
            SimulatorAIPolicy.objects.filter(pk=policy.pk).update(is_active=True, activated_at=timezone.now())
        self.message_user(request, f'{policy.version} AI 정책을 활성화했습니다.', level=messages.SUCCESS)


class SimulatorAIDeckForm(forms.ModelForm):
    class Meta:
        model = SimulatorAIDeck
        fields = '__all__'
        widgets = {
            'profile_text': forms.Textarea(attrs={
                'rows': 36, 'cols': 100, 'spellcheck': 'false',
                'style': 'font-family: ui-monospace, Consolas, monospace; font-size: 13px;',
            }),
        }


@admin.register(SimulatorAIDeck)
class SimulatorAIDeckAdmin(admin.ModelAdmin):
    form = SimulatorAIDeckForm
    list_display = ['name', 'deck', 'profile_style', 'is_active', 'sort_order', 'updated_at']
    list_editable = ['is_active', 'sort_order']
    list_filter = ['is_active']
    search_fields = ['name', 'deck__name', 'deck__character__name']
    autocomplete_fields = ['deck']
    readonly_fields = ['profile_summary', 'deck_cards', 'weight_table', 'condition_table', 'effect_table', 'created_at', 'updated_at']
    fieldsets = [
        (None, {'fields': ['name', 'description', 'deck', 'is_active', 'sort_order']}),
        ('AI 설정', {
            'fields': ['profile_text', 'profile_summary', 'deck_cards'],
            'description': '양식 설명: docs/AI_DECK_PROFILE.md. 저장할 때 문법과 카드 코드를 검사합니다.',
        }),
        ('참고표', {'fields': ['weight_table', 'condition_table', 'effect_table'], 'classes': ['collapse']}),
        ('기록', {'fields': ['created_at', 'updated_at']}),
    ]

    @admin.display(description='성향')
    def profile_style(self, obj):
        try:
            style = obj.profile()['style']
        except ProfileError:
            return '설정 오류'
        return dict(STYLE_CHOICES).get(style, style)

    @admin.display(description='해석 결과')
    def profile_summary(self, obj):
        if not obj or not obj.pk:
            return '저장하면 해석 결과가 표시됩니다.'
        try:
            profile = obj.profile(check_codes=True)
        except ProfileError as exc:
            return format_html('<pre style="color:#c00">{}</pre>', str(exc))
        lines = [
            f"성향: {dict(STYLE_CHOICES).get(profile['style'])}",
            f"가중치 덮어쓰기: {profile['weights'] or '없음'}",
            f"항상 선호: {profile['prefer'] or '없음'}",
        ]
        lines += [f"상황 「{item['name']}」 when={item['when']} prefer={item['prefer']} weights={item['weights']}" for item in profile['situations']]
        lines += [f"콤보 「{item['name']}」 {' → '.join(item['cards'])} (+{item['bonus']:g}) when={item['when'] or '항상'}" for item in profile['combos']]
        counter = profile['counter']
        lines.append(f"상대 대처: {'켜짐' if counter['enabled'] else '꺼짐'} (+{counter['bonus']:g}, {counter['scope']})")
        lines.append(f"패배 확정 카드 피하기: {'켜짐' if profile['safety']['avoid_certain_loss'] else '꺼짐'}")
        for rule in profile['effects']:
            target = ', '.join(rule['ability'] + rule['card'] + rule['decision'])
            parts = [f"{key}={rule[key]}" for key in ('use', 'choose', 'pick', 'avoid', 'count', 'amount') if key in rule]
            lines.append(f"효과 \u300c{rule['name']}\u300d [{target}] when={rule['when'] or '항상'} {' '.join(parts)}")
        lines.append(f"규칙 없는 선택형 효과: {'발동' if profile['effect_settings']['default_use'] else '발동하지 않음'}")
        return format_html('<pre>{}</pre>', '\n'.join(lines))

    @admin.display(description='덱 카드 코드')
    def deck_cards(self, obj):
        if not obj or not obj.deck_id:
            return '덱을 저장하면 카드 코드 목록이 표시됩니다.'
        cards = {}
        for entry in obj.deck.cids.select_related('card'):
            cards[entry.card.code] = entry.card
        for entry in obj.deck.reserve_entries.select_related('card'):
            cards.setdefault(entry.card.code, entry.card)
        if obj.deck.trait_card_id:
            cards.setdefault(obj.deck.trait_card.code, obj.deck.trait_card)
        rows = sorted((code, card) for code, card in cards.items() if code)
        def starter(card):
            # 히트·카운터 판정이 '콤보'인 카드로 이겨야 콤보가 시작된다.
            kinds = [label for label, value in (('히트', card.hit), ('카운터', card.counter)) if str(value or '') == '콤보']
            return f" · 콤보 시작({'/'.join(kinds)})" if kinds else ''

        return format_html_join(
            '', '<div><code>{}</code> {} <small>({}, 속도 {}, 데미지 {}, 히트 {}, 카운터 {}){}</small></div>',
            (
                (code, card.name, card.type, card.frame or '-', card.damage or '-',
                 card.hit or '-', card.counter or '-', starter(card))
                for code, card in rows
            ),
        )

    @admin.display(description='가중치 표')
    def weight_table(self, obj):
        policy = active_ai_policy()
        current = (policy.weights if policy else None) or DEFAULT_POLICY_WEIGHTS
        return format_html(
            '<table><tr><th>키</th><th>현재 정책 값</th><th>뜻</th></tr>{}</table>',
            format_html_join('', '<tr><td><code>{}</code></td><td>{}</td><td>{}</td></tr>', (
                (key, round(float(current.get(key, 0) or 0), 3), text)
                for key, text in WEIGHT_DESCRIPTIONS.items()
            )),
        )

    @admin.display(description='[[effect]] 항목과 기본 패시브 규칙')
    def effect_table(self, obj):
        keys = format_html_join('', '<tr><td><code>{}</code></td><td>{}</td></tr>', EFFECT_RULE_KEYS.items())
        defaults = format_html_join('', '<tr><td>{}</td><td><code>{}</code></td><td>{}</td><td>{}</td></tr>', (
            (
                rule['name'], ', '.join(rule['ability'] + rule['card']), rule['when'] or '항상',
                ' '.join(f"{key}={rule[key]}" for key in ('use', 'choose', 'pick', 'avoid', 'count', 'amount') if key in rule),
            )
            for rule in DEFAULT_EFFECT_RULES
        ))
        return format_html(
            '<table><tr><th>항목</th><th>뜻</th></tr>{}</table>'
            '<p>기본 패시브 규칙(덱 규칙이 없을 때 위에서부터 적용, ai_effect_defaults.toml)</p>'
            '<table><tr><th>이름</th><th>능력</th><th>조건</th><th>결정</th></tr>{}</table>',
            keys, defaults,
        )

    @admin.display(description='when 조건 표')
    def condition_table(self, obj):
        return format_html(
            '<table><tr><th>키</th><th>뜻</th></tr>{}</table>',
            format_html_join('', '<tr><td><code>{}</code></td><td>{}</td></tr>', (
                (key, text) for key, (_kind, text) in CONDITION_KEYS.items()
            )),
        )


class AutomaticIssueCommentInline(admin.TabularInline):
    model = AutomaticIssueComment
    extra = 0
    readonly_fields = ['reporter', 'role', 'body', 'created_at']


@admin.register(AutomaticIssueReport)
class AutomaticIssueReportAdmin(admin.ModelAdmin):
    list_display = ['public_id', 'origin', 'status', 'error_type', 'session', 'ruleset_release', 'created_at']
    list_filter = ['origin', 'status', 'error_type', 'ruleset_release']
    search_fields = ['public_id', 'summary', 'error_type']
    readonly_fields = ['public_id', 'session', 'ruleset_release', 'origin', 'error_type', 'summary', 'diagnostic', 'created_at', 'updated_at']
    inlines = [AutomaticIssueCommentInline]


@admin.register(RulesetRelease)
class RulesetReleaseAdmin(admin.ModelAdmin):
    change_list_template = 'admin/battlelog/rulesetrelease/change_list.html'
    list_display = ['version', 'content_hash_short', 'schema_version', 'is_active', 'published_at', 'created_by']
    list_filter = ['is_active', 'schema_version']
    readonly_fields = [
        'version', 'schema_version', 'source_manifest', 'snapshot', 'content_hash',
        'is_active', 'created_by', 'created_at', 'published_at',
    ]
    actions = ['activate_selected']

    @admin.display(description='내용 해시')
    def content_hash_short(self, obj):
        return obj.content_hash[:16]

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return request.user.has_perm('battlelog.publish_ruleset')

    def get_urls(self):
        return [
            path('publish/', self.admin_site.admin_view(self.publish_view), name='battlelog_rulesetrelease_publish'),
        ] + super().get_urls()

    def publish_view(self, request):
        if not request.user.has_perm('battlelog.publish_ruleset'):
            from django.core.exceptions import PermissionDenied
            raise PermissionDenied()
        report = validate_catalog(require_coverage=True)
        if request.method == 'POST' and report.is_valid:
            version = str(request.POST.get('version') or '').strip()
            if not version:
                messages.error(request, '릴리스 버전이 필요합니다.')
            else:
                try:
                    release, _report = publish_ruleset_release(version, user=request.user, activate=True)
                except (ValueError, RulesetPublicationError) as exc:
                    messages.error(request, str(exc))
                else:
                    messages.success(request, f'{release.version} 규칙 릴리스를 게시하고 활성화했습니다.')
                    return redirect(reverse('admin:battlelog_rulesetrelease_changelist'))
        context = {
            **self.admin_site.each_context(request),
            'title': '자동 규칙 릴리스 게시',
            'opts': self.model._meta,
            'report': report.as_dict(),
        }
        return render(request, 'admin/battlelog/rulesetrelease/publish.html', context)

    @admin.action(description='선택한 한 릴리스를 활성화')
    def activate_selected(self, request, queryset):
        if queryset.count() != 1:
            self.message_user(request, '한 개의 릴리스만 선택하세요.', level=messages.ERROR)
            return
        release = queryset.first()
        with transaction.atomic():
            list(RulesetRelease.objects.select_for_update().values_list('id', flat=True))
            RulesetRelease.objects.filter(is_active=True).exclude(pk=release.pk).update(is_active=False)
            RulesetRelease.objects.filter(pk=release.pk).update(is_active=True)
        self.message_user(request, f'{release.version} 릴리스를 활성화했습니다.', level=messages.SUCCESS)
