from django import forms
from django.utils import timezone

from deck.models import Deck

from .models import Tournament, TournamentParticipant, TournamentRound


EVENT_DATE_INPUT_FORMAT = '%Y-%m-%dT%H:%M'


def _format_local_event_date(value):
    if not value or isinstance(value, str):
        return value
    if timezone.is_aware(value):
        value = timezone.localtime(value)
    return value.strftime(EVENT_DATE_INPUT_FORMAT)


class TournamentForm(forms.ModelForm):
    event_date = forms.DateTimeField(
        label='대회 일시',
        input_formats=['%Y-%m-%dT%H:%M', '%Y-%m-%d %H:%M:%S', '%Y-%m-%d %H:%M'],
        widget=forms.DateTimeInput(attrs={'type': 'datetime-local'}, format=EVENT_DATE_INPUT_FORMAT),
    )

    class Meta:
        model = Tournament
        fields = [
            'name',
            'event_date',
            'venue',
            'format',
            'elimination_mode',
            'visibility',
            'join_code',
            'tags',
            'decklist_required_count',
            'round_duration_minutes',
            'round_set_count',
            'swiss_round_count',
            'top_cut_count',
            'tiebreaker',
            'win_points',
            'draw_points',
            'loss_points',
            'max_players',
            'description',
        ]
        labels = {
            'name': '대회명',
            'venue': '장소',
            'format': '운영 방식',
            'elimination_mode': '토너먼트 방식',
            'visibility': '공개 범위',
            'join_code': '참가 코드',
            'tags': '대회 태그',
            'decklist_required_count': '요구 덱 리스트 수',
            'round_duration_minutes': '라운드 시간',
            'round_set_count': '라운드 세트 수',
            'swiss_round_count': '스위스 라운드 수',
            'top_cut_count': '토너먼트 진출자 수',
            'tiebreaker': '동률 처리 기준',
            'win_points': '승리 점수',
            'draw_points': '무승부 점수',
            'loss_points': '패배 점수',
            'max_players': '최대 참가자',
            'description': '설명',
        }
        widgets = {
            'join_code': forms.TextInput(attrs={'placeholder': '비워두면 자동 생성'}),
            'tags': forms.TextInput(attrs={'placeholder': '예: 공식/시즌1/입문'}),
            'decklist_required_count': forms.NumberInput(attrs={'min': 0, 'max': 10}),
            'round_duration_minutes': forms.NumberInput(attrs={'min': 1, 'max': 240}),
            'round_set_count': forms.NumberInput(attrs={'min': 1, 'max': 15}),
            'swiss_round_count': forms.NumberInput(attrs={'min': 0, 'max': 20, 'placeholder': '0이면 제한 없음'}),
            'top_cut_count': forms.NumberInput(attrs={'min': 0, 'max': 256, 'placeholder': '하이브리드 대회에서 사용'}),
            'win_points': forms.NumberInput(attrs={'min': 0, 'max': 99}),
            'draw_points': forms.NumberInput(attrs={'min': 0, 'max': 99}),
            'loss_points': forms.NumberInput(attrs={'min': 0, 'max': 99}),
            'description': forms.Textarea(attrs={'rows': 5}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.is_bound:
            event_date = self.initial.get('event_date') or getattr(self.instance, 'event_date', None)
            if event_date:
                self.initial['event_date'] = _format_local_event_date(event_date)
        for field_name, field in self.fields.items():
            field.widget.attrs.setdefault('class', 'v2-tournament-input')
            if field_name in ['join_code', 'swiss_round_count', 'top_cut_count', 'max_players']:
                field.required = False

    def clean_decklist_required_count(self):
        value = self.cleaned_data['decklist_required_count']
        if value > 10:
            raise forms.ValidationError('요구 덱 리스트 수는 10개 이하로 설정해주세요.')
        return value

    def clean_join_code(self):
        code = (self.cleaned_data.get('join_code') or '').strip().upper()
        visibility = self.cleaned_data.get('visibility')
        if visibility == Tournament.VISIBILITY_PUBLIC:
            return ''
        return code

    def clean_tags(self):
        raw_tags = (self.cleaned_data.get('tags') or '').replace(',', '/')
        tags = []
        seen = set()
        for tag in raw_tags.split('/'):
            normalized = tag.strip().lstrip('#')
            if normalized and normalized not in seen:
                tags.append(normalized)
                seen.add(normalized)
        return '/'.join(tags)

    def clean_swiss_round_count(self):
        return self.cleaned_data.get('swiss_round_count') or 0

    def clean_top_cut_count(self):
        return self.cleaned_data.get('top_cut_count') or 0

    def clean(self):
        cleaned_data = super().clean()
        tournament_format = cleaned_data.get('format')
        top_cut_count = cleaned_data.get('top_cut_count') or 0
        if tournament_format == Tournament.FORMAT_HYBRID and top_cut_count < 2:
            self.add_error('top_cut_count', forms.ValidationError('스위스 + 토너먼트 대회는 토너먼트 진출자 수를 2명 이상으로 지정해주세요.'))
        return cleaned_data


class TournamentJoinForm(forms.ModelForm):
    class Meta:
        model = TournamentParticipant
        fields = ['display_name']
        labels = {
            'display_name': '표시 이름',
        }
        widgets = {
            'display_name': forms.TextInput(attrs={'placeholder': '비워두면 계정 이름 사용'}),
        }

    def __init__(self, *args, user=None, tournament=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user
        self.tournament = tournament
        self.selected_decks_by_slot = {}
        self.needs_join_code = (
            tournament
            and tournament.visibility == Tournament.VISIBILITY_UNLISTED
            and not (self.instance and self.instance.pk)
        )

        if self.needs_join_code:
            self.fields['join_code'] = forms.CharField(
                label='참가 코드',
                required=True,
                widget=forms.TextInput(attrs={'placeholder': '대회 참가 코드를 입력'}),
            )

        submitted_by_slot = {}
        if self.instance and self.instance.pk:
            submitted_by_slot = {
                submission.slot: submission.deck
                for submission in self.instance.deck_submissions.all()
            }

        deck_count = tournament.decklist_required_count if tournament else 0
        for slot in range(1, deck_count + 1):
            field_name = f'deck_{slot}'
            selected_deck = submitted_by_slot.get(slot)
            self.fields[field_name] = forms.IntegerField(
                label=f'제출 덱 {slot}',
                required=True,
                widget=forms.HiddenInput(attrs={'data-deck-slot': slot}),
            )
            if selected_deck:
                self.fields[field_name].initial = selected_deck.id
                self.selected_decks_by_slot[slot] = selected_deck

        for field in self.fields.values():
            field.widget.attrs.setdefault('class', 'v2-tournament-input')

    def _can_submit_deck(self, deck):
        if not self.user or not self.user.is_authenticated:
            return False
        if deck.author_id == self.user.id:
            return True
        return deck.visibility in [Deck.VISIBILITY_PUBLIC, Deck.VISIBILITY_UNLISTED]

    def _get_submittable_deck(self, deck_id):
        try:
            deck = Deck.objects.select_related('author', 'character').get(id=deck_id, deleted=False)
        except Deck.DoesNotExist:
            raise forms.ValidationError('존재하지 않는 덱입니다.')

        if not self._can_submit_deck(deck):
            raise forms.ValidationError('제출할 수 없는 덱입니다.')
        return deck

    def clean(self):
        cleaned_data = super().clean()
        if self.needs_join_code:
            input_code = (cleaned_data.get('join_code') or '').strip().upper()
            if input_code != (self.tournament.join_code or '').upper():
                self.add_error('join_code', forms.ValidationError('참가 코드가 올바르지 않습니다.'))

        if not self.tournament or self.tournament.decklist_required_count == 0:
            return cleaned_data

        decks = []
        for slot in range(1, self.tournament.decklist_required_count + 1):
            field_name = f'deck_{slot}'
            deck_id = cleaned_data.get(field_name)
            if deck_id:
                try:
                    deck = self._get_submittable_deck(deck_id)
                except forms.ValidationError as exc:
                    self.add_error(field_name, exc)
                    continue
                cleaned_data[field_name] = deck
                self.selected_decks_by_slot[slot] = deck
                decks.append(deck)

        if len(decks) != self.tournament.decklist_required_count:
            raise forms.ValidationError('요구된 수만큼 덱 리스트를 제출해야 합니다.')
        deck_ids = [deck.id for deck in decks]
        if len(deck_ids) != len(set(deck_ids)):
            raise forms.ValidationError('같은 덱을 중복 제출할 수 없습니다.')
        return cleaned_data

    def submitted_decks(self):
        if not self.tournament:
            return []
        return [
            self.cleaned_data[f'deck_{slot}']
            for slot in range(1, self.tournament.decklist_required_count + 1)
        ]


class RoundStartForm(forms.Form):
    stage = forms.ChoiceField(
        label='매칭 방식',
        choices=TournamentRound.STAGE_CHOICES,
        initial=TournamentRound.STAGE_SWISS,
    )
    duration_minutes = forms.IntegerField(
        label='라운드 시간',
        min_value=1,
        max_value=240,
        required=False,
    )
    set_count = forms.IntegerField(
        label='세트 수',
        min_value=1,
        max_value=15,
        required=False,
    )
    win_points = forms.IntegerField(
        label='승리 점수',
        min_value=0,
        max_value=99,
        required=False,
    )
    draw_points = forms.IntegerField(
        label='무승부 점수',
        min_value=0,
        max_value=99,
        required=False,
    )
    loss_points = forms.IntegerField(
        label='패배 점수',
        min_value=0,
        max_value=99,
        required=False,
    )

    def __init__(self, *args, tournament=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.tournament = tournament
        if tournament:
            self.fields['duration_minutes'].initial = tournament.round_duration_minutes
            self.fields['set_count'].initial = tournament.round_set_count
            self.fields['win_points'].initial = tournament.win_points
            self.fields['draw_points'].initial = tournament.draw_points
            self.fields['loss_points'].initial = tournament.loss_points
            if tournament.format == Tournament.FORMAT_SWISS:
                self.fields['stage'].choices = [(TournamentRound.STAGE_SWISS, '스위스')]
            elif tournament.format == Tournament.FORMAT_ELIMINATION:
                self.fields['stage'].choices = [(TournamentRound.STAGE_ELIMINATION, '토너먼트')]
            elif tournament.format == Tournament.FORMAT_HYBRID and tournament.swiss_round_count:
                finished_swiss_rounds = tournament.rounds.filter(
                    stage=TournamentRound.STAGE_SWISS,
                    status=TournamentRound.STATUS_FINISHED,
                ).count()
                if finished_swiss_rounds >= tournament.swiss_round_count:
                    self.fields['stage'].initial = TournamentRound.STAGE_ELIMINATION
        for field in self.fields.values():
            field.widget.attrs.setdefault('class', 'v2-tournament-input')
