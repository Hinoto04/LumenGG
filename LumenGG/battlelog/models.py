from django.conf import settings
from django.db import models
from django.utils import timezone

from card.models import Character


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
