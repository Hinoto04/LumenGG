"""Get phase: which List card to take, what to throw back, and when to pass.

The AI values its whole hand against the opponent's visible cards (known
hand, weight 1, and List, weight ``LIST_WEIGHT`` since they can fetch it):

* coverage — for each opponent card, the best predicted battle any hand card
  gets against it (``ai_preview.battle_value``, about -2..+2), so the hand
  keeps an answer to each threat;
* depth — the mean matchup of the ``keep`` best hand cards, so it holds a few
  cards that do well against the opponent overall, not one answer each.

A get is worth the gain in hand value. With a full hand the engine makes the
player discard after the get (back to the List), so the gain is that of the
best swap; when no swap gains ``swap_margin`` the AI passes instead of
taking a card only to throw it (or another card) back. The discard after a
get uses the same value, so it keeps the hand the get was planned for.

Base stats only (like the rest of ``ai_preview``): card effects are not
simulated. Cards that cannot be readied (no attack/defense) are never thrown
back by this value and add nothing to it.
"""

from .ai_preview import _players, _zone, battle_value, fp_values, is_ready_candidate, rival_hand_view

LIST_WEIGHT = 0.5


def rival_cards(observation, role):
    """``[(card, weight)]`` of visible opponent cards to judge the hand against."""
    _own, rival = _players(observation, role)
    known, _unknown = rival_hand_view(observation, role)
    cards = [(card, 1.0) for card in known if is_ready_candidate(card)]
    cards += [(card, LIST_WEIGHT) for card in _zone(rival, 'list') if is_ready_candidate(card)]
    return cards


class HandValue:
    """Hand value against fixed opponent cards and FP, with cached matchups."""

    def __init__(self, observation, role, *, keep=3):
        self.threats = rival_cards(observation, role)
        self.total = sum(weight for _card, weight in self.threats)
        self.my_fp, self.their_fp = fp_values(observation, role)
        self.keep = max(1, int(keep))
        self._rows = {}

    @property
    def known(self):
        return bool(self.total)

    def row(self, card):
        key = card.get('instance_id') or id(card)
        if key not in self._rows:
            self._rows[key] = [
                battle_value(card, threat, my_fp=self.my_fp, their_fp=self.their_fp)
                for threat, _weight in self.threats
            ]
        return self._rows[key]

    def matchup(self, card):
        """Weighted mean battle value of one card against the opponent's cards."""
        if not self.known or not is_ready_candidate(card):
            return 0.0
        return sum(value * weight for value, (_t, weight) in zip(self.row(card), self.threats)) / self.total

    def value(self, cards):
        if not self.known:
            return 0.0
        ready = [card for card in cards if is_ready_candidate(card)]
        if not ready:
            return -2.0
        rows = [self.row(card) for card in ready]
        coverage = sum(
            weight * max(row[index] for row in rows)
            for index, (_threat, weight) in enumerate(self.threats)
        ) / self.total
        best = sorted((self.matchup(card) for card in ready), reverse=True)[:self.keep]
        depth = sum(best) / self.keep
        return coverage + depth

    def best_discard(self, cards, count=1):
        """Cards to throw back so the rest keeps the highest value."""
        cards = list(cards)
        dropped = []
        for _ in range(max(0, count)):
            options = [card for card in cards if is_ready_candidate(card)] or cards
            if not options:
                break
            worst = max(options, key=lambda card: (
                self.value([other for other in cards if other is not card]),
                -self.matchup(card),
                str(card.get('instance_id')),
            ))
            dropped.append(worst)
            cards = [card for card in cards if card is not worst]
        return dropped

    def get_gain(self, hand, card, *, full):
        """Value gained by taking ``card`` (and, with a full hand, the best discard)."""
        before = self.value(hand)
        after = [*hand, card]
        if full:
            dropped = self.best_discard(after)
            after = [other for other in after if all(other is not item for item in dropped)]
        return self.value(after) - before


def hand_cards(observation, role):
    own, _rival = _players(observation, role)
    return [card for card in _zone(own, 'hand') if isinstance(card, dict)]
