import secrets
import string
from datetime import timedelta

from django.contrib.auth.models import User
from django.db import models
from django.utils import timezone

from deck.models import Deck


class Tournament(models.Model):
    FORMAT_SWISS = 'swiss'
    FORMAT_ELIMINATION = 'elimination'
    FORMAT_HYBRID = 'hybrid'
    FORMAT_CHOICES = [
        (FORMAT_SWISS, '스위스'),
        (FORMAT_ELIMINATION, '토너먼트'),
        (FORMAT_HYBRID, '스위스 + 토너먼트'),
    ]

    STATUS_REGISTRATION = 'registration'
    STATUS_RUNNING = 'running'
    STATUS_FINISHED = 'finished'
    STATUS_CHOICES = [
        (STATUS_REGISTRATION, '참가 접수'),
        (STATUS_RUNNING, '진행 중'),
        (STATUS_FINISHED, '종료'),
    ]

    VISIBILITY_PUBLIC = 'public'
    VISIBILITY_UNLISTED = 'unlisted'
    VISIBILITY_CHOICES = [
        (VISIBILITY_PUBLIC, '공개'),
        (VISIBILITY_UNLISTED, '일부 공개'),
    ]

    TIEBREAKER_BUCHHOLZ = 'buchholz'
    TIEBREAKER_OWM = 'owm'
    TIEBREAKER_CHOICES = [
        (TIEBREAKER_BUCHHOLZ, 'Buchholz'),
        (TIEBREAKER_OWM, 'OWM%'),
    ]

    ELIMINATION_SINGLE = 'single'
    ELIMINATION_DOUBLE = 'double'
    ELIMINATION_CHOICES = [
        (ELIMINATION_SINGLE, '싱글 엘리미네이션'),
        (ELIMINATION_DOUBLE, '더블 엘리미네이션'),
    ]

    name = models.CharField(max_length=80)
    organizer = models.ForeignKey(User, on_delete=models.CASCADE, related_name='organized_tournaments')
    description = models.TextField(blank=True, default='')
    venue = models.CharField(max_length=120, blank=True, default='')
    event_date = models.DateTimeField(default=timezone.now)
    format = models.CharField(max_length=16, choices=FORMAT_CHOICES, default=FORMAT_SWISS)
    elimination_mode = models.CharField(max_length=16, choices=ELIMINATION_CHOICES, default=ELIMINATION_SINGLE)
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=STATUS_REGISTRATION)
    visibility = models.CharField(max_length=16, choices=VISIBILITY_CHOICES, default=VISIBILITY_PUBLIC)
    join_code = models.CharField(max_length=24, blank=True, default='')
    tags = models.CharField(max_length=255, blank=True, default='')
    decklist_required_count = models.PositiveSmallIntegerField(default=1)
    round_duration_minutes = models.PositiveSmallIntegerField(default=50)
    round_set_count = models.PositiveSmallIntegerField(default=1)
    swiss_round_count = models.PositiveSmallIntegerField(default=0)
    top_cut_count = models.PositiveSmallIntegerField(default=0)
    tiebreaker = models.CharField(max_length=16, choices=TIEBREAKER_CHOICES, default=TIEBREAKER_BUCHHOLZ)
    win_points = models.PositiveSmallIntegerField(default=3)
    draw_points = models.PositiveSmallIntegerField(default=1)
    loss_points = models.PositiveSmallIntegerField(default=0)
    max_players = models.PositiveSmallIntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-event_date', '-created_at']

    def __str__(self):
        return self.name

    @property
    def tag_list(self):
        return [
            tag.strip().lstrip('#')
            for tag in self.tags.split('/')
            if tag.strip().lstrip('#')
        ]

    def save(self, *args, **kwargs):
        join_code_changed = False
        if self.visibility == self.VISIBILITY_UNLISTED and not self.join_code:
            alphabet = string.ascii_uppercase + string.digits
            self.join_code = ''.join(secrets.choice(alphabet) for _ in range(8))
            join_code_changed = True
        elif self.visibility == self.VISIBILITY_PUBLIC:
            join_code_changed = bool(self.join_code)
            self.join_code = ''
        if join_code_changed and kwargs.get('update_fields') is not None:
            kwargs['update_fields'] = set(kwargs['update_fields']) | {'join_code'}
        super().save(*args, **kwargs)

    @property
    def can_join(self):
        if self.status != self.STATUS_REGISTRATION:
            return False
        if self.max_players and self.participants.filter(dropped=False).count() >= self.max_players:
            return False
        return True

    @property
    def require_decklist(self):
        return self.decklist_required_count > 0


class TournamentParticipant(models.Model):
    tournament = models.ForeignKey(Tournament, on_delete=models.CASCADE, related_name='participants')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='tournament_entries')
    display_name = models.CharField(max_length=40, blank=True, default='')
    deck = models.ForeignKey(Deck, on_delete=models.SET_NULL, related_name='tournament_entries', null=True, blank=True)
    seed = models.PositiveSmallIntegerField(null=True, blank=True)
    dropped = models.BooleanField(default=False)
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['joined_at']
        constraints = [
            models.UniqueConstraint(fields=['tournament', 'user'], name='unique_tournament_user'),
        ]

    def __str__(self):
        return f'{self.tournament.name} - {self.name}'

    @property
    def name(self):
        return self.display_name or self.user.username


class TournamentDeckSubmission(models.Model):
    participant = models.ForeignKey(TournamentParticipant, on_delete=models.CASCADE, related_name='deck_submissions')
    deck = models.ForeignKey(Deck, on_delete=models.CASCADE, related_name='tournament_submissions')
    slot = models.PositiveSmallIntegerField(default=1)
    submitted_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['slot']
        constraints = [
            models.UniqueConstraint(fields=['participant', 'slot'], name='unique_tournament_deck_submission_slot'),
            models.UniqueConstraint(fields=['participant', 'deck'], name='unique_tournament_deck_submission_deck'),
        ]

    def __str__(self):
        return f'{self.participant.name} #{self.slot} - {self.deck.name}'


class TournamentRound(models.Model):
    STAGE_SWISS = 'swiss'
    STAGE_ELIMINATION = 'elimination'
    STAGE_CHOICES = [
        (STAGE_SWISS, '스위스'),
        (STAGE_ELIMINATION, '토너먼트'),
    ]

    STATUS_RUNNING = 'running'
    STATUS_FINISHED = 'finished'
    STATUS_CHOICES = [
        (STATUS_RUNNING, '진행 중'),
        (STATUS_FINISHED, '종료'),
    ]

    tournament = models.ForeignKey(Tournament, on_delete=models.CASCADE, related_name='rounds')
    number = models.PositiveSmallIntegerField()
    stage = models.CharField(max_length=16, choices=STAGE_CHOICES, default=STAGE_SWISS)
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=STATUS_RUNNING)
    started_at = models.DateTimeField(default=timezone.now)
    ended_at = models.DateTimeField(null=True, blank=True)
    duration_minutes = models.PositiveSmallIntegerField(default=50)
    set_count = models.PositiveSmallIntegerField(default=3)
    win_points = models.PositiveSmallIntegerField(default=3)
    draw_points = models.PositiveSmallIntegerField(default=1)
    loss_points = models.PositiveSmallIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['number']
        constraints = [
            models.UniqueConstraint(fields=['tournament', 'number'], name='unique_tournament_round_number'),
        ]

    def __str__(self):
        return f'{self.tournament.name} R{self.number}'

    @property
    def ends_at(self):
        return self.started_at + timedelta(minutes=self.duration_minutes)


class TournamentMatch(models.Model):
    STATUS_PENDING = 'pending'
    STATUS_REPORTED = 'reported'
    STATUS_CHOICES = [
        (STATUS_PENDING, '결과 대기'),
        (STATUS_REPORTED, '결과 입력'),
    ]

    round = models.ForeignKey(TournamentRound, on_delete=models.CASCADE, related_name='matches')
    table_no = models.PositiveSmallIntegerField()
    player1 = models.ForeignKey(TournamentParticipant, on_delete=models.CASCADE, related_name='matches_as_player1')
    player2 = models.ForeignKey(
        TournamentParticipant,
        on_delete=models.CASCADE,
        related_name='matches_as_player2',
        null=True,
        blank=True,
    )
    winner = models.ForeignKey(
        TournamentParticipant,
        on_delete=models.SET_NULL,
        related_name='won_matches',
        null=True,
        blank=True,
    )
    is_draw = models.BooleanField(default=False)
    player1_score = models.PositiveSmallIntegerField(default=0)
    player2_score = models.PositiveSmallIntegerField(default=0)
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=STATUS_PENDING)
    reported_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['round__number', 'table_no']

    def __str__(self):
        player2_name = self.player2.name if self.player2 else 'BYE'
        return f'{self.round} T{self.table_no}: {self.player1.name} vs {player2_name}'

    @property
    def is_bye(self):
        return self.player2_id is None
