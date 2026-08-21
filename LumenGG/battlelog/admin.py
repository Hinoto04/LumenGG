from django.contrib import admin, messages
from django.db import transaction
from django.shortcuts import redirect, render
from django.urls import path, reverse
from django.utils import timezone

from .game.catalog import RulesetPublicationError, publish_ruleset_release, validate_catalog
from .automatic_services import ai_policy_activation_issues
from .models import (
    AutomaticIssueComment,
    AutomaticIssueReport,
    BattleEvent,
    BattleSession,
    BattleSet,
    LumenSimulatorSession,
    RulesetRelease,
    SimulatorAIPolicy,
)


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
