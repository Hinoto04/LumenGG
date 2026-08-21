import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from card.models import Character


class RulesetRelease(models.Model):
    """Immutable, published snapshot consumed by automatic simulator sessions."""

    RULEBOOK_SHA256 = '2A30590E2857C03FCE2FB5995029D4CEF3B5017493C8760FCFF8B92D39EC7D59'

    version = models.CharField(max_length=64, unique=True)
    schema_version = models.PositiveSmallIntegerField(default=1)
    source_manifest = models.JSONField(default=dict, blank=True)
    snapshot = models.JSONField(default=dict)
    content_hash = models.CharField(max_length=64, unique=True)
    is_active = models.BooleanField(default=False)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name='simulator_ruleset_releases',
        null=True,
        blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    published_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ['-published_at', '-id']
        permissions = [
            ('publish_ruleset', '자동 시뮬레이터 규칙 릴리스 게시'),
        ]

    def __str__(self):
        return f'{self.version} ({self.content_hash[:12]})'

    def save(self, *args, **kwargs):
        if self.pk:
            original = type(self).objects.filter(pk=self.pk).values(
                'version', 'schema_version', 'source_manifest', 'snapshot',
                'content_hash', 'created_by_id', 'published_at',
            ).first()
            if original:
                current = {
                    'version': self.version,
                    'schema_version': self.schema_version,
                    'source_manifest': self.source_manifest,
                    'snapshot': self.snapshot,
                    'content_hash': self.content_hash,
                    'created_by_id': self.created_by_id,
                    'published_at': self.published_at,
                }
                if current != original:
                    raise ValidationError('게시된 규칙 릴리스 내용은 변경할 수 없습니다.')
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError('감사와 기존 세션 재생을 위해 규칙 릴리스는 삭제할 수 없습니다.')


class SimulatorAIPolicy(models.Model):
    """Versioned policy artifact produced by deterministic self-play."""

    ALGORITHM_LINEAR_V1 = 'linear_v1'
    ALGORITHM_CHOICES = [(ALGORITHM_LINEAR_V1, 'Linear policy v1')]

    name = models.CharField(max_length=80, default='Lumen AI')
    version = models.CharField(max_length=64, unique=True)
    algorithm = models.CharField(
        max_length=32,
        choices=ALGORITHM_CHOICES,
        default=ALGORITHM_LINEAR_V1,
    )
    weights = models.JSONField(default=dict)
    metrics = models.JSONField(default=dict, blank=True)
    training_games = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    activated_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at', '-id']
        permissions = [('train_ai_policy', '시뮬레이터 AI 정책 훈련')]

    def __str__(self):
        return f'{self.name} {self.version}'

    def save(self, *args, **kwargs):
        if self.pk:
            original = type(self).objects.filter(pk=self.pk).values(
                'name', 'version', 'algorithm', 'weights', 'metrics', 'training_games',
            ).first()
            if original:
                current = {
                    'name': self.name,
                    'version': self.version,
                    'algorithm': self.algorithm,
                    'weights': self.weights,
                    'metrics': self.metrics,
                    'training_games': self.training_games,
                }
                if current != original:
                    raise ValidationError('게시된 AI 정책 내용은 변경할 수 없습니다.')
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError('세션 재현을 위해 게시된 AI 정책은 삭제할 수 없습니다.')


class BattleSession(models.Model):
    SESSION_STANDALONE = 'standalone'
    SESSION_TOURNAMENT = 'tournament'
    SESSION_TYPE_CHOICES = [
        (SESSION_STANDALONE, '일반 계산기'),
        (SESSION_TOURNAMENT, '대회 매치'),
    ]

    session_type = models.CharField(max_length=16, choices=SESSION_TYPE_CHOICES, default=SESSION_STANDALONE)
    view_token = models.CharField(max_length=64, unique=True)
    control_token = models.CharField(max_length=64, unique=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name='battle_sessions',
        null=True,
        blank=True,
    )
    tournament_match = models.OneToOneField(
        'tournament.TournamentMatch',
        on_delete=models.CASCADE,
        related_name='battle_session',
        null=True,
        blank=True,
    )
    player1_name = models.CharField(max_length=60, default='플레이어1')
    player2_name = models.CharField(max_length=60, default='플레이어2')
    player1_character = models.ForeignKey(
        Character,
        on_delete=models.SET_NULL,
        related_name='battle_sessions_as_player1',
        null=True,
        blank=True,
    )
    player2_character = models.ForeignKey(
        Character,
        on_delete=models.SET_NULL,
        related_name='battle_sessions_as_player2',
        null=True,
        blank=True,
    )
    player1_initial_hp = models.IntegerField(default=0)
    player2_initial_hp = models.IntegerField(default=0)
    player1_hp = models.IntegerField(default=0)
    player2_hp = models.IntegerField(default=0)
    player1_fp = models.IntegerField(default=0)
    player2_fp = models.IntegerField(default=0)
    player1_passive_state = models.JSONField(default=dict, blank=True)
    player2_passive_state = models.JSONField(default=dict, blank=True)
    timer_started_at = models.DateTimeField(null=True, blank=True)
    timer_duration_seconds = models.PositiveSmallIntegerField(default=10)
    sudden_death = models.BooleanField(default=False)
    sudden_death_turns_remaining = models.PositiveSmallIntegerField(default=0)
    round_extra_seconds = models.PositiveIntegerField(default=0)
    version = models.PositiveIntegerField(default=1)
    expires_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.get_session_type_display()} #{self.id}: {self.player1_name} vs {self.player2_name}'


class BattleEvent(models.Model):
    EVENT_HP = 'hp'
    EVENT_FP = 'fp'
    EVENT_UNDO = 'undo'
    EVENT_TIMER = 'timer'
    EVENT_SUDDEN_DEATH = 'sudden_death'
    EVENT_PASSIVE = 'passive'
    EVENT_CHARACTER = 'character'
    EVENT_SET_REPORT = 'set_report'
    EVENT_SET_START = 'set_start'
    EVENT_EXTRA_TIME = 'extra_time'
    EVENT_TYPE_CHOICES = [
        (EVENT_HP, '체력 변경'),
        (EVENT_FP, 'FP 변경'),
        (EVENT_UNDO, '되돌리기'),
        (EVENT_TIMER, '타이머'),
        (EVENT_SUDDEN_DEATH, '서든 데스'),
        (EVENT_PASSIVE, '패시브 기록'),
        (EVENT_CHARACTER, '캐릭터 선택'),
        (EVENT_SET_REPORT, '세트 결과 보고'),
        (EVENT_SET_START, '세트 시작'),
        (EVENT_EXTRA_TIME, '추가 시간'),
    ]

    TARGET_PLAYER1 = 'p1'
    TARGET_PLAYER2 = 'p2'
    TARGET_GLOBAL = 'global'
    TARGET_CHOICES = [
        (TARGET_PLAYER1, '플레이어1'),
        (TARGET_PLAYER2, '플레이어2'),
        (TARGET_GLOBAL, '공통'),
    ]

    session = models.ForeignKey(BattleSession, on_delete=models.CASCADE, related_name='events')
    event_uid = models.CharField(max_length=36, unique=True, null=True, blank=True)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name='battle_events',
        null=True,
        blank=True,
    )
    actor_label = models.CharField(max_length=80, blank=True, default='')
    event_type = models.CharField(max_length=24, choices=EVENT_TYPE_CHOICES)
    target = models.CharField(max_length=8, choices=TARGET_CHOICES, default=TARGET_GLOBAL)
    amount = models.IntegerField(null=True, blank=True)
    hp_before = models.IntegerField(null=True, blank=True)
    hp_after = models.IntegerField(null=True, blank=True)
    payload = models.JSONField(default=dict, blank=True)
    undone = models.BooleanField(default=False)
    undone_event = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        related_name='undo_events',
        null=True,
        blank=True,
    )
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ['-created_at', '-id']

    def __str__(self):
        return f'{self.session_id} {self.event_type} {self.target} {self.amount or ""}'


class BattleSet(models.Model):
    STATUS_RUNNING = 'running'
    STATUS_FINISHED = 'finished'
    STATUS_CHOICES = [
        (STATUS_RUNNING, '진행 중'),
        (STATUS_FINISHED, '종료'),
    ]

    WINNER_PLAYER1 = BattleEvent.TARGET_PLAYER1
    WINNER_PLAYER2 = BattleEvent.TARGET_PLAYER2
    WINNER_CHOICES = [
        (WINNER_PLAYER1, '플레이어1'),
        (WINNER_PLAYER2, '플레이어2'),
    ]

    session = models.ForeignKey(BattleSession, on_delete=models.CASCADE, related_name='sets')
    set_number = models.PositiveSmallIntegerField()
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=STATUS_RUNNING)
    winner_side = models.CharField(max_length=8, choices=WINNER_CHOICES, blank=True, default='')
    player1_confirmed_at = models.DateTimeField(null=True, blank=True)
    player2_confirmed_at = models.DateTimeField(null=True, blank=True)
    player1_confirmed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name='battle_sets_confirmed_as_player1',
        null=True,
        blank=True,
    )
    player2_confirmed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name='battle_sets_confirmed_as_player2',
        null=True,
        blank=True,
    )
    forced_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name='battle_sets_forced',
        null=True,
        blank=True,
    )
    player1_start_hp = models.IntegerField(default=0)
    player2_start_hp = models.IntegerField(default=0)
    player1_start_fp = models.IntegerField(default=0)
    player2_start_fp = models.IntegerField(default=0)
    player1_end_hp = models.IntegerField(null=True, blank=True)
    player2_end_hp = models.IntegerField(null=True, blank=True)
    player1_end_fp = models.IntegerField(null=True, blank=True)
    player2_end_fp = models.IntegerField(null=True, blank=True)
    started_at = models.DateTimeField(default=timezone.now)
    ended_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['set_number']
        constraints = [
            models.UniqueConstraint(fields=['session', 'set_number'], name='unique_battle_set_number'),
        ]

    def __str__(self):
        return f'{self.session_id} set {self.set_number}'


class LumenSimulatorSession(models.Model):
    MODE_MANUAL = 'manual'
    MODE_AUTOMATIC = 'automatic'
    MODE_CHOICES = [
        (MODE_MANUAL, '수동'),
        (MODE_AUTOMATIC, '자동'),
    ]
    CONTROLLER_HUMAN = 'human'
    CONTROLLER_AI = 'ai'
    CONTROLLER_CHOICES = [
        (CONTROLLER_HUMAN, '사람'),
        (CONTROLLER_AI, 'AI'),
    ]

    view_token = models.CharField(max_length=64, unique=True)
    player1_token = models.CharField(max_length=64, unique=True)
    player2_token = models.CharField(max_length=64, unique=True)
    player1_name = models.CharField(max_length=60, default='플레이어1')
    player2_name = models.CharField(max_length=60, default='플레이어2')
    player1_controller = models.CharField(max_length=12, choices=CONTROLLER_CHOICES, default=CONTROLLER_HUMAN)
    player2_controller = models.CharField(max_length=12, choices=CONTROLLER_CHOICES, default=CONTROLLER_HUMAN)
    mode = models.CharField(max_length=16, choices=MODE_CHOICES, default=MODE_MANUAL)
    ruleset_release = models.ForeignKey(
        RulesetRelease,
        on_delete=models.PROTECT,
        related_name='simulator_sessions',
        null=True,
        blank=True,
    )
    automation_failure = models.JSONField(default=dict, blank=True)
    ai_policy = models.ForeignKey(
        SimulatorAIPolicy,
        on_delete=models.SET_NULL,
        related_name='sessions',
        null=True,
        blank=True,
    )
    document = models.JSONField(default=dict, blank=True)
    version = models.PositiveIntegerField(default=1)
    expires_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'시뮬레이터 #{self.id}: {self.player1_name} vs {self.player2_name}'


class AutomaticIssueReport(models.Model):
    STATUS_OPEN = 'open'
    STATUS_RESOLVED = 'resolved'
    STATUS_CHOICES = [(STATUS_OPEN, '미해결'), (STATUS_RESOLVED, '해결')]
    ORIGIN_ENGINE = 'engine'
    ORIGIN_CLIENT = 'client'
    ORIGIN_USER = 'user'
    ORIGIN_CHOICES = [
        (ORIGIN_ENGINE, '엔진 자동 감지'),
        (ORIGIN_CLIENT, '브라우저 자동 감지'),
        (ORIGIN_USER, '사용자 제보'),
    ]

    public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    session = models.ForeignKey(
        LumenSimulatorSession,
        on_delete=models.SET_NULL,
        related_name='issue_reports',
        null=True,
        blank=True,
    )
    ruleset_release = models.ForeignKey(
        RulesetRelease,
        on_delete=models.PROTECT,
        related_name='issue_reports',
        null=True,
        blank=True,
    )
    origin = models.CharField(max_length=12, choices=ORIGIN_CHOICES)
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default=STATUS_OPEN)
    error_type = models.CharField(max_length=120, blank=True)
    summary = models.CharField(max_length=500)
    diagnostic = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at', '-id']

    def __str__(self):
        return f'{self.public_id}: {self.summary[:60]}'


class AutomaticIssueComment(models.Model):
    report = models.ForeignKey(AutomaticIssueReport, on_delete=models.CASCADE, related_name='comments')
    reporter = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name='automatic_issue_comments',
        null=True,
        blank=True,
    )
    role = models.CharField(max_length=12, blank=True)
    body = models.TextField(max_length=4000)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at', 'id']


class RealtimePresence(models.Model):
    SCOPE_BATTLE = 'battle'
    SCOPE_SIMULATOR = 'simulator'
    SCOPE_CHOICES = [
        (SCOPE_BATTLE, '계산기'),
        (SCOPE_SIMULATOR, '시뮬레이터'),
    ]

    scope = models.CharField(max_length=16, choices=SCOPE_CHOICES)
    view_token = models.CharField(max_length=64, db_index=True)
    role = models.CharField(max_length=16)
    channel_name = models.CharField(max_length=255, unique=True)
    connected_at = models.DateTimeField(auto_now_add=True)
    last_seen_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=['scope', 'view_token', 'role'], name='battlelog_r_scope_9af048_idx'),
            models.Index(fields=['last_seen_at'], name='battlelog_r_last_se_f30c9f_idx'),
        ]

    def __str__(self):
        return f'{self.scope}:{self.view_token}:{self.role}'
