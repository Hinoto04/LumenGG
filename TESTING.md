# Isolated database tests

The normal database account intentionally cannot create `test_lumengg`. The
test settings never connect to that database account.

For a zero-dependency local regression run, use the in-memory SQLite profile:

```powershell
.\test.ps1
```

This runs the existing simulator suite, the automatic engine suite, and the
card/localization regression suites used by the full-project baseline.
Pass Django test labels when a narrower run is useful:

```powershell
.\test.ps1 -TestLabel battlelog.tests.LumenSimulatorServiceTests
```

Current 2026-08-21 SQLite baseline: 785 automatic-engine tests and 894 tests
across the full project, all passing. The latest production-catalog command was
run without `--apply`; its read-only result was 112 preserved plus 316
automatically reviewed definitions, or 428 of 453 cards, leaving 25 for
card-specific review. The completed UNC, AWL, and all 24 RFS definitions are
included in that observed count. This does not update the production database or
publish an automatic ruleset.

For production-database compatibility, start the disposable MariaDB service
and select the MariaDB profile:

```powershell
docker compose -f compose.test.yml up -d --wait
.\test.ps1 -Database mariadb
docker compose -f compose.test.yml down
```

To use an existing MySQL/MariaDB server, copy `test.local.ps1.example` to
`test.local.ps1`, fill in the test-only account, and run:

```powershell
Copy-Item test.local.ps1.example test.local.ps1
# Edit test.local.ps1 without committing it.
.\test.ps1 -Database mysql
```

The database stores data on `tmpfs`; stopping the service discards it. The
checked-in password is only exposed on loopback and is exclusively for this
disposable service. Connection values can be overridden with
`LUMENGG_TEST_DB_NAME`, `LUMENGG_TEST_DB_TEST_NAME`, `LUMENGG_TEST_DB_USER`,
`LUMENGG_TEST_DB_PASSWORD`, `LUMENGG_TEST_DB_HOST`, and
`LUMENGG_TEST_DB_PORT`.

## Automatic simulator release workflow

Install the project requirements before publishing because rulebook
verification opens the PDF and checks both its SHA-256 and page count:

```powershell
python -m pip install -r LumenGG\requirements.txt
```

After applying migrations, verify the pinned rulebook and inspect card effect
coverage. Automatic mode stays hidden until all 453 cards pass validation and
an immutable release is activated.

```powershell
Push-Location LumenGG
python manage.py migrate
python manage.py verify_automatic_rulebook
python manage.py seed_automatic_effect_drafts --dry-run
python manage.py seed_automatic_effect_drafts
python manage.py validate_automatic_ruleset
python manage.py publish_automatic_ruleset 2026.06.1
Pop-Location
```

Draft seeding never overwrites reviewed definitions. It splits numbered card
text into editor nodes, preserves related Q&A references, compiles supported
phrases into structured commands, and applies the registered exact card
overrides. Run the read-only catalog audit to confirm that every card text was
compiled and that no unresolved placeholder remains:

To regenerate a specific unreviewed draft without touching the rest of the
catalog, repeat `--card-code` for each exact target. Unknown codes fail before
any write, and reviewed definitions remain protected even with
`--overwrite-unreviewed`:

```powershell
python manage.py seed_automatic_effect_drafts --dry-run --overwrite-unreviewed --card-code CB03-AT-001
python manage.py seed_automatic_effect_drafts --overwrite-unreviewed --card-code CB03-AT-001
```

```powershell
python manage.py audit_automatic_effect_drafts
python manage.py smoke_automatic_catalog --games 4
```

`smoke_automatic_catalog` is read-only and selects only legacy card columns,
so it can run against the catalog before the automatic-rule migrations are
deployed. It builds two deterministic 20-card decks in memory and fails on an
engine exception, deadlock, or command-limit overrun.

Generated definitions still remain drafts. Staff must compare each definition
with the card text, detail/errata text, and linked Q&A in the visual editor,
then mark it reviewed and clear its draft flags. Publication rejects any draft
or unreviewed card even when the catalog audit reports complete compilation.
The seed records a SHA-256 digest of the card text, detail text, and complete
linked-Q&A contents. Publication also fails if that digest is stale or any
linked source is missing from `source_refs`; toggle review off and on after
rechecking a changed source to record a fresh approval digest.

For card-by-card review, open `Cards`, filter `자동 효과 검토` to `미검토`,
and open the first card. The change page shows a compact `자동 효과 검수 요약`
before the collapsed DSL editor: source text, mandatory/optional timing, engine
operations, current/declared Q&A IDs, and whether the approved source digest is
still current. Expand `자동 효과 정의 편집` only when a correction or approval
is needed, clear the draft flags, check `검토 완료`, and use
`저장 후 다음 미검수` to continue through the queue.

The normal card effect-review page also contains an isolated effect sandbox.
It runs the currently edited JSON without saving it, so an incomplete catalog
or unpublished ruleset does not block testing. Six `공통 테스트` scenarios
are always available even when the current card has no ability definition:
acquire exactly one Technique, acquire exactly two Techniques, break one
Technique followed by the normal optional side-deck replenishment, discard one
card from Hand, move one Side-deck card to Lumen, and make the opponent choose
one of their own Hand cards to discard. Select a
common scenario or one card ability and its trigger, choose
`각 영역에 공격·수비·특수 후보 추가`, and start the test. Mandatory
acquire/discard/break/move effects stop at a real `pending_decision`; choose the
cards and continue to inspect the before/after zones and the event timeline.
The compact `선택·영역 이동 검증` list records who made each decision,
the required selection range, the chosen card labels, every source/destination
zone pair, and any break/discard/prevention result before the raw event log.
An empty answer is rejected when at least one card is mandatory. Breaking a
normal attack/defense card also exposes the subsequent list-replenishment
decision, rather than silently completing the effect.
Choosing a Special Technique in the common acquire scenario also exercises the
core movement rule: it is sent to Break instead of Hand, and that actual
destination is shown in both the zone view and event timeline.
Selectors whose minimum is two or more render checkboxes and enforce the full
minimum/maximum range for either player. The `p1 · 여러 후보 중 선택` and
`p2 · 여러 후보 중 선택` presets make it possible to compare ownership and
hidden-information behavior without changing or publishing the card definition.
Choose `아무 후보도 추가하지 않음` to test the opposite boundary. The result
must be `필수 선택 후보 부족`, and the engine aborts the rest of that ability's
effect sequence. A later damage, FP, modifier, acquire, or break command cannot
resolve by itself after the required movement failed.
For an explicitly optional `0~1` selector, zero candidates do not create an
empty decision. Its nested move is skipped and independent commands after that
choice continue normally. If paying a card movement is itself required before
an optional ability may start, add an ability-level `availability_selector`;
the engine checks it at trigger collection and again after the player accepts.
This also hides the activation when every apparent candidate is currently
protected from the requested break or discard operation.

Combo proposals follow Q&A 580. Normal 2- and 3-combo cards are issued as one
simultaneous server action and each later card is checked again after the
previous card's effects. A card acquired by the proposed 2-combo card enters
the hand but cannot be added to that already-submitted proposal; a card acquired
by the 1-combo source before proposing is available. Effects that explicitly
permit a particular card immediately after their source are previewed only for
the proposal, then validated again after the real optional effect and costs
resolve. Four-combo extensions use the same contract with one ordered sequence.

The automatic reviewer executes only effects whose interpretation can be
proved conservatively in at least three deterministic situations: owner as
player 1, owner as player 2, and a wrong trigger that must not resolve.
Unrecognized conditions, Q&A rulings, unrecognized follow-up clauses,
unbounded calculations, quoted-name filters, custom handlers, and unsupported
card-level rules remain pending for human review.
An exact `[[state:key]]` gate is additionally tested with the state enabled for
both owners, disabled, and on a wrong trigger. A single-sentence dodge/clash
speed, damage, hit-judgment, or body restriction is tested at its boundary for
both owners and outside the restriction. A two-sided speed or damage range
tests both endpoints and both sides outside the range. Printed card, character,
and token tags must also
match the generated selector filters before any scenario can approve a card.
Exact HP/FP boundary conditions add a false-boundary scenario. Simple card-use
conditions are checked through the engine's actual legality function for both
owners and once while unsatisfied. Continuous guard/dodge/clash prohibitions
are refreshed in the live rules layer and checked for both owners plus an
unrelated action. A printed grab-negation clause must map to the dedicated
`grab_negated` event, and printed hand-discard text must have a matching DSL
discard command. Printed replacement wording such as `대신` remains pending
unless a dedicated replacement scenario proves the branch semantics.
Exact combo range rules are checked at their first legal combo number for both
owners and once immediately before it; counter-gated speed options additionally
test the missing-counter case and combo-penalty boundary. Exact fixed catch
speeds are checked through the engine's real catch-card legality list for both
owners and against a limit one point below the fixed speed.
An effect-granted catch is checked through the same public legal-action list
used by the browser and AI. Zone, code, speed, owner, and condition filters are
asserted independently. If three cards are eligible, all three
`play_catch_card` actions must be visible to the choosing player and none to the
opponent. Random selection is replayed with the recorded seed; its selected
card must move through the normal discard path before a following Get skip can
resolve.
Direct damage/speed and judgment changes must match the printed target, field,
value, and sign. Their evidence records the actual before/after value, while a
state-gated continuous modifier is refreshed for both owners and verified once
more with the state inactive. Exact `[[token:key]]` counter-presence conditions
also add an inactive scenario. A simple defense restriction may be combined
with other independently proven abilities; its generated continuous prevention
command must match the same boundary rule before the card can pass.
For the bounded damage-history choice form, the reviewer exercises both
branches at their printed maxima (currently 4 cards when undamaged and 1 card
when damaged), verifies the resulting zone moves, and adds a wrong-trigger
case. Direct shield gains likewise record the shield total before and after.
Exact opponent battle-card conditions replace the sandbox opponent with both a
matching and a deliberately mismatching type/position/body fixture. Optional
hand-discard damage bonuses select the printed maximum at both hit and counter,
then compare the discarded count with the resolved per-card bonus. A delayed
named-card catch bonus is tested for the owning player, a wrong same-owner catch
that must not consume it, the matching catch, and turn expiry. Combined catch
speed/judgment text runs three catch-legality boundaries plus three judgment
trigger scenarios. Exact lumen-token minimum and hand-size maximum conditions
run at the printed boundary and one card outside it. An optional list-card
break followed by healing or a source-card damage bonus selects exactly one
eligible list card for each owner, verifies the real break event and follow-up
value, and checks that an unrelated trigger performs neither operation.
Printed counter minimums and combo-number conditions likewise run once at the
legal boundary and once immediately outside it. A numeric FP gain printed for
the recovery phase must remain unchanged at the originating trigger, create a
turn-scoped scheduled effect, and change FP only when recovery starts. Multi-
trigger text is exercised at both ends of its declared trigger set. Character,
card, and token tags in list-acquire text must remain on the generated selector.
State-dependent numeric expressions use the DSL `if` value operator. The
bounded card-count damage form is tested below its cap, above its normal cap,
above its state-expanded cap, and on an unrelated trigger; each individual
damage event and the final HP total must agree with the printed repeat count.
Card-specific Q&A reviewers remain opt-in by exact card code and exact Q&A ID
set. `CRS-AT-003` verifies its own Ember gain, the additional `CRS-PS-001`
gain, the non-Rin boundary, both owners, and a wrong trigger for Q&A 224.
`ST5-003` keeps its two 100-damage occurrences separate: it checks per-hit
damage reduction, zero-damage Howling suppression, one Howling gain per actual
hit, and confirms that 100 + 100 + 500 is not a single 600-or-more damage event
for Q&A 173/221/483/615. Any source ID, amount, repeat count, or trigger drift
returns these cards to manual review.
`ST1-011` and `ST1-012` additionally execute owner-direct break prevention,
opponent-effect breaking, and the defense-over cleanup bypass. Their self-
damage is checked with damage reduction and an opposing Howling passive.
`ST1-012` covers the 0/9 FP bounds, own-dodge-before-opponent-dodge ordering,
the zero-FP requirement for an FP catch, and defensive upper-dodge interaction
with Down Stance. `ST1-013` checks all four sides of its upper/middle dodge
speed boundaries, delays its granted catch until the catch window, and proves
that only an eligible hand card—not a same-speed list card—can be caught.
`RFS-AT-025` requires an eligible Pinp hand card before its two separate
100-damage events, including decline and no-candidate cases. `CB03-AT-004`
checks both hand and foot body judgments rather than collapsing the printed
OR condition. `ST1-006` checks the opponent-special condition, speed locking
against FP and later speed changes, both prohibited judgments, and battle
expiry. `AWL-AT-052` checks its self-only catch prohibition and turn expiry.
For Q&A 242, `AWL-AT-055` proves that a mandatory selected hand discard moves
to the list and that no candidate aborts the effect atomically.
`CB02-AT-009` tests the 500-damage clash boundary and its 8-speed hand catch.
`RFS-AT-012` proves that its +300 applies to the future caught lumen card—not
the source card—and verifies the final catch damage. `DFR-AT-038` exposes all
three qualifying lumen cards as player choices only at its printed threshold.
`ST4-008` tests both ends of the 9–10 Speed clash range against live
effect-modified pre-FP Speed. Its deterministic private random selection uses
only cards that can currently be discarded, records the selected instance,
and changes the opposing Hit to +1. Get is skipped only when the selected card
really leaves Hand. Empty/protected Hand, full-List redirection to Break,
Special-Technique discard to Break, numbered negation, and inactive source are
covered by 19 deterministic scenarios.
`ST4-009` keeps its three numbered Hand-size tiers cumulative and live. The
4-card damage tier is Battle-only, turns on/off as Hand changes, and is
projected after the source leaves Hand. The 3-card pre-judgment Speed -6 tier
is optional. The 2-card Combo tier ignores the normal damage penalty and counts
every jointly proposed Combo card as already outside Hand; this implements Q&A
105/106 for both seats. Numbered negation removes every tier while preserving
the descriptive numberless function. These behaviors and mutation rejection
are covered by 23 deterministic scenarios.
`ST4-010` applies its numberless all-position Dodge only to effect-modified
pre-FP Speed 8 or less (Q&A 496). A successful Dodge gains 7 FP and schedules
one owner-only Catch obligation for the turn. At that Catch the owner must
choose one currently discardable physical Hand card; normal Techniques move to
List (Q&A 242), while Special Techniques follow the core redirect to Break.
Protected cards are omitted, an empty Hand safely consumes the impossible
obligation, an opposing Catch does not consume it, and turn expiry removes it.
Its second effect resolves only After Use against an opposing Defense, grants
that opponent 6 FP, resets Defense Over (Q&A 68), and correctly misses timing
when Dash restarts Ready after judgment (Q&A 276/573). The three rule groups
are covered by 27 deterministic and mutation-rejection scenarios.
`UNC-AT-013` checks
both printed position/speed boundaries and breaks only after actual received
damage. `CRS-AT-040` implements Q&A 503 explicitly: Harmony's live Combo hit
allows the clash, while losing Harmony before judgment restores the original
hit and rejects it. `CB03-AT-005` checks all three High Tension dodge positions,
the 5-speed boundary, disabled state, and compound `상·중·하단` parsing.
`CB02-AT-008` applies its dodge/clash prohibition only when the opposing
judgment is special. `CB02-AT-010` covers optional acceptance and decline,
breaking its source, the ordinary break-replenishment pause, and the following
list-card catch. `CB03-AT-003` verifies its state gate and exposes every exact
speed/character catch candidate from both hand and list. `PMP-AT-005` covers
both printed triggers, optional decline, insufficient HP, the HP payment, and
the opponent FP loss. `CB03-AT-030` stops at a mandatory hand-card decision,
discards the selected card before dealing its two separate damage events, and
aborts both damage events when there is no legal hand card. Its second effect
checks the combo-number boundary and lets the player choose the acquired list
card instead of selecting one automatically.
`CB01-AT-024` likewise stops after grab negation until its owner selects one
hand card. The selected card is discarded first and only then is the source
card moved from battle to list; no hand candidate leaves both cards in place
and aborts the remaining sequence.
`ST4-004` applies its two-card hand discard cost only when played as a combo
from the list. The legal action is absent with fewer than two cards, payment is
a mandatory `play_cost` decision, and a normal hand combo neither pays that
cost nor skips Get. The discarded pair is a real player choice and reaches the
list before resolution continues (Q&A 242). Numbered-effect negation removes
the list permission and its cost while preserving ordinary hand combos. Its
numberless dodge limit is scoped to the battle copy only and uses pre-FP Speed.
Grab no longer bypasses a matching Guard or paid defense judgment (Q&A 460).
`ST4-005` scopes its numberless 9-Speed dodge limit to the battle copy and
checks both dodges before either dodge effect can change Harmony (Q&A 555).
Its optional Counter grant adds exactly one list-only Combo slot, is consumed
by only one list card, breaks that card after use, and cannot be assigned to
two simultaneously proposed cards. The relative extension stacks after
Madness's fourth-Combo grant so the list card is legal as the fifth Combo while
an ordinary Hand card is not (Q&A 665).
`ST4-006` scopes its numberless 8–11 Speed middle-Dodge limit to the battle
copy and evaluates that boundary against effect-modified, pre-FP Speed. Advance
Notice removes only the Speed range before judgment, retains the middle
position requirement, and adds the opposing Technique's live damage at the
moment the effect resolves. This preserves priority ordering when the opponent
also changes damage. Q&A 399/557 prove Dodge resolves before Clash or FP Speed
comparison, while Q&A 419 proves both priority orders produce the same Clash,
300 damage difference, and the Crescent owner's Combo. Both owners, numbered
negation, inactive-zone isolation, wrong position, and mutation rejection are
covered by 17 deterministic scenarios.
`ST4-007` treats its fixed 7-Speed Catch as a numbered rule, so numbered-effect
negation removes that shortcut while the printed Speed-11 card remains usable
in an 11-Speed Catch window. On Hit, the optional effect is offered only when
at least one Hand card can actually be broken; after acceptance the player
must choose one or two cards. Damage is calculated from the Attack cards that
really reached Break, not merely the submitted choices. Initial and late Break
protection, Attack/Defense mixtures, decline, empty Hand, inactive source,
numbered negation, and normal Break replenishment/resumption are covered by 17
deterministic scenarios.
`PMP-AT-050` verifies side-to-lumen setup, optional decline,
one-of-many hand selection, special-card break without list replenishment, and
Q&A 632's exact third-combo timing; a fourth combo cannot trigger it.
`PMP-AT-009` exposes every matching Spider token and requires the player to
choose exactly four before the card can be used; three tokens remove the card's
legal action and unrelated tokens are never candidates. Q&A 627 is tested with
less than 400 HP to prove the mandatory payment still occurs and can lose the
game. Its combo-end healing is multiplied by the actual number of combo cards
and does not trigger for the opponent's combo.
`DFR-AT-042` offers the controller only the opponent's technique cards in the
battle and lumen zones, then moves the selected instance to that opponent's
list; a missing `LEG` condition or an opponent with no legal technique creates
no forced movement. `PMP-AT-042` exposes only Lita techniques in the owner's
list, and the opponent's Get skip is nested after the successful acquisition so
an empty candidate set cannot skip Get by itself. `RFS-AT-023` first asks
whether to use the optional effect, then exposes only `ARM`-named lumen
techniques; the selected card moves to side before both judgments become Combo
and the source gains 200 damage. Each card runs as both owners, includes a
missing-candidate or disabled-condition boundary, and includes a wrong-trigger
case. These scenario records are also shown in the card effect review page and
can be replayed without creating a simulator session.
Break, discard, and move commands may store their actually successful card IDs
in `result_key`. Follow-up commands that say "그 경우" can compare that result
count instead of assuming every selected card moved. A selector may explicitly
keep break-protected cards visible with `include_operation_blocked`; this is
used only where a ruling says the card may be designated even though the break
fails. `CB01-AT-023` exercises that distinction for Q&A 197 and offers the
Dagger placement choice only after a real break. `LMI-AT-038` applies its 100
damage and ends the combo only after a real list-card break, including the
Q&A 446 prevented-break case. `LMI-AT-050` now grants 2 FP per successfully
broken card rather than a flat 2 FP, but remains pending because Q&A 547 still
requires a dedicated simultaneous-timing interpretation. `DFR-AT-041` collects
one independent choice in Hand, List, and Battle before moving any of them,
excludes every Linear Buster and non-Technique card, and awards +100 only for
each card that actually reaches Break. Its eight scenarios cover three, two,
zero, initial protection, protection introduced after choice, decline,
numbered-effect negation, and a wrong trigger.
`UNC-AT-048` derives exactly one candidate from `combo_previous`, checks both
the second- and third-combo boundaries, and leaves the +200 unapplied when
Q&A 593 makes that predecessor unbreakable. `CB02-AT-030` requires the player
to choose exactly two of all eligible Dagger tokens and then records a second
decision between changing its own two judgments or only the opponent's hit
judgment. `CB02-AT-029` likewise exposes only currently affordable branches:
the Dagger branch records two separate 100-damage events, while the AWL branch
lets the player choose an exact `AWL-AT-009` from hand or list before moving it
to side and dealing 500 damage. Both branch cards include decline, insufficient
resource, wrong-trigger, both-owner, and multi-candidate scenarios.
`CRS-AT-045` chains two mandatory two-card decisions. The second selector is
rebuilt after the first move, excludes special Techniques, publicly reveals the
chosen cards for Q&A 605, and awards Yin/Yang only after both cards reach hand.
Its successful-effect scenario also proves Q&A 68 resets the defense-over
counter even though no HP or FP changed. `PMP-AT-045` records the actual hand
break before granting its catch, processes the normal break-replenishment
decision, and exposes only Rin cards at speed 8 or lower from the break zone.
Q&A 622 is covered by making the just-broken cost card itself a legal catch;
Q&A 623 verifies that the selected side card reaches the list before the catch
grant is consumed.
`CB01-AT-034` exercises the complete hidden-hand decision chain: accept the
optional effect, select an opponent hand card, declare odd/even, and on a wrong
guess select exactly one own hand card to discard. Correct guesses add two
Foresight counters, record the deterministic random result, reveal it, and
force that card to ready first. Q&A 678 is enforced by excluding already
face-up hand cards from the random reveal candidates. Q&A 666 is covered by
proving that this Special Ultimate reaches the break zone without opening a
normal attack/defense replenishment decision. HP above 2000, an empty opponent
hand, decline, and a wrong trigger leave the Ultimate untouched.
`DFR-AT-021` records whether its own Ultimate actually reached the break zone
before applying any text introduced by "그 경우". A successful break exposes
every `LMI-AT-041` in side as an optional one-card placement, while unrelated
cards are excluded. Placement decline or no matching card still resets both FP,
skips both players' next Lumen phase, enables Dark Night through the next turn,
and requests the current turn to end. A prevented break performs none of those
follow-ups. Nine deterministic scenarios cover both owners, multiple/zero
candidates, decline, HP and phase boundaries, wrong timing, and delayed state
expiry.
`CRS-AT-004` makes both printed breaks mandatory player decisions. The hit
effect lists every breakable Technique in list; the counter effect does the
same for hand and grants one Ember only after the selected card actually
breaks. Q&A 610's empty-hand case aborts before the counter gain. Tokens,
face-down non-Techniques, and operation-blocked cards are not offered. Normal
attack/defense breaks still pause for the optional side-to-list replenishment
before any dependent command resumes. Five scenarios per ability cover both
owners, multiple candidates, replenishment, missing/blocked candidates, and a
wrong trigger.
`ST1-014` (Jump) is reviewed with three defense-boundary situations, four
speed-based FP situations, and five paired-break situations. The exact review
includes Q&A 655's 8-speed → 6FP calculation, Q&A 656's atomic cancellation
when the opposing Grab cannot be broken, and Q&A 69's real Grab-negation path,
which returns both battle cards to hand without opening Jump's after-use timing.
`ST1-015` (Dash) uses eight deterministic situations covering both owners,
priority order, zero and nonzero received damage, mutual Dash, and a preceding
opponent after-judgment effect. Q&A 404/454/626 verify that restarting Ready
does not end the battle scope, preserves turn Get skips, clears pending Catch
opportunities, resets Defense Over, and makes later effects miss their timing.
`ST1-016` (Cutting) fixes result effects into rulebook sub-timings: Dodge is
resolved before Opponent Dodge (Q&A 574), and Counter before Opponent Counter
(Q&A 577), regardless of priority. Four deterministic situations per ability
cover both owners, the paired timing, and a wrong trigger.
`ST3-017` (Counter Rat) tests the optional Catch decision from list against
printed speeds 4/5/6, a speed-5 card in hand, and Q&A 223's printed-5 card that
is fixed to speed 8 while catching. Five deterministic situations cover both
owners, decline, wrong timing, damage, and breaking both the caught card and
Counter Rat only after a Catch was actually used.
`ST1-017` (Down Slash) uses five situations for its Defense condition, hit
judgment replacement, and fixed speed. The fixed speed remains 8 despite FP or
a later speed modifier, and Q&A 655 is replayed with Jump gaining exactly 6FP.
`ST1-018` (Setsumei Kick) uses six situations proving that Dodge, Guard,
Counter loss, and Combo still reach After Use and break the card. Q&A 339 uses
the real Grab-negation restart path, where After Use is skipped and the Kick
returns to hand instead. A broken Kick is absent from a reopened Combo action
list (Q&A 511).
`ST1-019` (Catch Drop) fixes the draft to trigger its -4FP only on the
`grab_negated` event, not Dodge or another invalidation (Q&A 260/675). Its
fourth-Combo rule now ends Combo after use and schedules +1FP exactly once at
the next Recovery. Static candidate `min_combo` rules may extend the normal
three-Combo proposal depth up to the engine's bounded maximum, which also
unblocks the other catalog cards printed for fourth or fifth Combo.
`ST1-020` (Desperate Tackle) separately verifies its Combo-only prohibition,
self-damage on Opponent Guard, FP loss on Opponent Dodge, and Clash damage
reduction. Q&A 477/540 is replayed as 900 versus the reduced 500 damage and
deals the expected 400 Clash difference.
`AWL-AT-046` (Backstep) checks the printed 6-speed Dodge boundary for both
owners, rejects speed 7, and preserves Q&A 146's Down Stance transition.
Its FP formula uses the opponent's effect-adjusted speed before FP; Q&A 435 is
replayed as Backstep gaining 0FP before the opposing Dodge effect grants 9FP.
`AWL-AT-050` (Rending Dagger) permits Clash only against Hand-judgment cards.
Its 100 effect damage is tested for both owners, triggers Reve's Dark Night as
effect damage under Q&A 190, and immediately ends a lethal game before base
Clash damage or Sudden Death under Q&A 575.
`UNC-AT-050` (Rolling Spinner) stores its Catch behavior as a card rule:
printed speed 12 is fixed to 9 for Catch legality, Hit adds 100 damage, and the
card breaks only after Catch Hit, 600 damage, and After Use have completed.
Three deterministic situations per ability cover both owners, the speed-8
rejection boundary, event order, and absence of a false Catch interruption.
`UNC-AT-049` (May Slide) verifies that an Attack card's special Dodge still
uses the printed 7-speed boundary, cannot enter Combo, and gives the opponent
1FP only on its own Dodge. `UNC-AT-051` (Setsumei Rolling) uses a negated
whole-judgment predicate: Q&A 396 is replayed for both Attack special judgments
and every Defense position, so the bonus applies only when no Dodge exists.
`UNC-AT-052` (Air Slash Kick) checks both ends of its 7~9-speed Dodge range,
makes its fifth-Combo candidate reachable but rejects fourth Combo, and applies
its +300 damage at the Combo event for either owner.
`LMI-AT-049` (Flexible Dodge) filters its mandatory list acquisition to actual
Techniques and exposes every legal candidate to the owning player. Tests cover
one of multiple candidates, the other owner, no candidates, 499 damage, and
Q&A 441's later Combo/Catch damage missing the already-finished After Use
window. Its Dodge FP and turn-scoped Catch prohibition are tested separately.
`LMI-AT-050` (Zero-Sum) tests selecting one or two list Techniques, each
normal-card replenishment pause, decline, and empty candidates. Q&A 444 reaches
8FP after two breaks: 4FP from Zero-Sum and 4FP from Rubiette. The definition
records general Q&A 597 as the newer ruling over linked Q&A 547; equal current
values retain the existing priority player, whose optional effect is offered
first.
`UNC-AT-053` (Fighting Spirit) now has separate executable effects for its
private Recovery deployment, optional Lumen-phase state, Ready-card +100
damage/+1 speed modifier, Battle-end state loss, and one-turn cooldown. Q&A 71
is covered with two Lumen copies stacking their modifiers; Q&A 404 preserves
the state when an effect restarts Ready without ending Battle; Q&A 658 proves
that a fixed speed ignores the slowing modifier. Simultaneous effects now open
a mandatory owner-only ordering decision, alternate by priority, and use a
stable first option on timeout in accordance with general Q&A 597. Each of the
four abilities has at least four deterministic scenarios, including both
owners, invalid timing/state cases, actual Battle-end cleanup, and the
following-turn re-enable. The scheduler removes a due item before resolving it
so a state-loss effect can safely create a new next-turn schedule.
`ST1-001` (Lap Cats) now has two mutually exclusive After-use effects and 12
deterministic scenarios. Outside Over Limit, the owner must choose one actual
Technique from every legal List candidate and move it to the Lumen Zone. In
Over Limit, the owner instead chooses one face-up Technique in the Lumen Zone
and moves it to the List; face-down Secret Time cards and tokens are never
offered (Q&A 544). Both branches still trigger after Dodge, Guard, Clash, or
Counter because the card was used (Q&A 328), while an empty legal candidate set
opens no impossible dialog. Eligibility is captured when the After-use timing
starts, so moving the fourth Lumen Technique and entering Over Limit cannot
replay the second branch in that same timing (Q&A 650). The production-data
dry run also classifies linked Q&A 597 as a general ruling for Fighting Spirit
instead of duplicating it in both source lists.
`ST1-002` (Cats Muffins) now has two reviewed rule groups and 12 deterministic
scenarios. Over Limit continuously changes this card's 400 damage to 100 even
while it is a Combo candidate; after the ordinary 100 Combo penalty, final
damage 0 is rejected, while an external +100 damage modifier restores legality
(Q&A 322). Its mandatory Before Judgment effect checks an opponent Attack's
effect-adjusted, pre-FP Speed and Hand judgment. Both owners and the Speed-7
boundary are covered, as are an 8-Speed card changed to 7, fixed Speed, Foot
Attacks, Hand Defense cards, and a card whose FP alone makes its final Speed 5.
The gained 2FP is present before the immediately following FP correction and
therefore makes Cats Muffins two Speed faster in the captured battle result
(Q&A 235).
`ST1-003` (Rai! Bounce!) now has three reviewed rule groups and 15
deterministic scenarios. Because the catalog's printed Special field is `X`,
its continuous text explicitly grants High Clash and then restricts that
judgment to opposing Hand Techniques; High Foot and Middle Hand cards do not
Clash. Its mandatory Clash effect changes Hit 3 to Combo, and the result
pipeline now discovers that newly created Combo timing after Clash effects but
before judgment FP and damage. The Combo trigger and Combo Time each open once.
The card can follow a Speed-14 `Lefi!` Technique at its unchanged printed Speed
7 (Q&A 318), but the card after it must again be at least Speed 8 (Q&A 20).
Server-issued actions also include the simultaneously proposed Speed-12 Lefi!
Technique → Speed-7 Rai! Bounce! pair required by Q&A 532.
`ST1-005` (Rai! Chop!) now has three reviewed rule groups and 19
deterministic scenarios. Its printed Middle Clash is restricted to opposing
Foot Techniques, so Middle Hand and High Foot cards are not offered that
judgment. It can follow a `Lefi!` Technique at its printed Speed 9 regardless
of the preceding Speed and can be proposed in the same two-card action after a
Speed-12 Lefi! Technique (Q&A 20/532). In Over Limit, the owner must first
choose one face-up, legally breakable Technique in their Lumen Zone. Face-down
Secret Time cards, tokens, and break-protected Techniques are excluded from
the decision (Q&A 85/351/530). After a successful normal-Technique break, the
optional Side Deck replenishment decision resolves before a second mandatory
choice is built from the updated List, and the chosen Technique then moves to
Hand (Q&A 84/296). If replenishment is declined and the List is empty, no
impossible acquisition dialog opens. A List card that would only be acquired
by the proposed 2-Combo card cannot be retroactively added as its 3-Combo
partner (Q&A 580).
`ST1-007` (Rai! Lefi! Bomber!) now has two reviewed rule groups and eight
deterministic scenarios. The card is a legal Combo candidate in either Hand
or List, but its self-damage is mandatory only after it was actually used from
the List. The Combo pipeline preserves that origin zone and counts the live
Lumen Zone at this card's own Combo timing: two cards deal 400 self-damage,
three deal 600, and using it from Hand deals none (Q&A 90/323). In Over Limit,
both the 100-point 2-Combo penalty and the 200-point 3-Combo penalty are
ignored, so the printed 600 damage is dealt in either position; outside that
state the same scenarios deal 500 and 400.
`ST1-008` (Lefi! Fire!) now has two reviewed rule groups and 11 deterministic
scenarios. In Over Limit its mandatory Before-Judgment effect adds 5FP before
the engine captures FP-adjusted battle Speed, changing printed Speed 12 to 6
from an initial 1FP and to 7 from 0FP (Q&A 235). The effect does not run
without the state or at Use timing. Its Combo rule permits printed Speed 12
after a Speed-14 `Rai!` Technique without changing the card's actual Speed;
the following card must return to the ordinary ascending rule and therefore
needs at least Speed 13 (Q&A 20). Server actions also prove a simultaneous
Speed-14 Rai! → Speed-12 Lefi! Fire! proposal for both owners (Q&A 532).
`ST1-009` (Rai! Lefi! Rocket!) now has four reviewed rule groups and 21
deterministic scenarios. Its continuous rule prevents only the opponent's
Guard and Clash while leaving Dodge and unrelated actions available. Counter
effects resolve before opponent-Counter effects (Q&A 577), after which the
opponent gains the card's mandatory 4FP. The card is illegal at 2- and
3-Combo; at 4-Combo its printed 1200 damage becomes 500 after the ordinary
300-point Combo penalty and its own 400-point reduction. Ignoring the ordinary
Combo penalty still leaves the card's reduction, for 800 damage (Q&A 524). In
Over Limit it breaks at After-use even when dodged (Q&A 61). The Q&A 581
integration scenario exercises the real player-decision sequence: choose the
same-owner effect order, choose a Side Deck replenishment after the break,
then choose that replenished List card for the passive's Lumen movement. A
state first gained by another After-use effect does not retroactively collect
the Rocket break effect (Q&A 75).
`ST1-010` (Nyaaaang) now has three reviewed rule groups and 16 deterministic
scenarios. Its Guard and no-damage After-Judgment grants share one battle-wide
use key, so the first resolved grant suppresses the other; merely gaining the
Catch permission also resets Defense Over even if it is declined (Q&A 68).
The generated actions contain only face-up NYA Attack Techniques in the Lumen
Zone at the appropriate printed-speed boundary (9 after Guard, 8 after taking
no damage), while Hand cards, other characters, and slower cards are excluded.
An actual Catch declaration resets both players' FP (Q&A 493), deals the Catch
card's damage, and moves that card to the List at cleanup (Q&A 91). Concurrent
effect-granted Catches are offered in priority order: playing the first makes
the later grant miss timing, while declining passes the opportunity onward
(Q&A 406/641). Zero printed damage satisfies the second condition (Q&A 59),
all After-use effects finish before Catch opens (Q&A 648), a Catch whose Hit
judgment opens Combo triggers the opposing Paki Defense effect (Q&A 542), and
Ready restart or an effect ending Battle clears the pending grant before Catch
time (Q&A 67/690).
`AWL-AT-013` (Lefi! Screw!) now has two reviewed rule groups and 13
deterministic scenarios. Its first-Combo effect is mandatory, breaks the card,
offers the normal Side-to-List replenishment choice, and caps an externally
extended Combo at three cards. Q&A 387 verifies that replenishment completes
before an Over Limit After-use choice can move the replenished card to Lumen.
The Speed-8 card may follow a Speed-14 Rai Technique, but ordinary ascending
Speed applies again to the following card; Q&A 532 also checks a simultaneous
Rai-to-Screw proposal.
`AWL-AT-015` (Rai! Lefi! Cannon!) excludes itself when counting the six
Lumen-zone Attack/Defense Techniques required to play it. Face-down Secret
Time cards do not count as Techniques (Q&A 350), and legality is recomputed
after a preceding effect adds the sixth card (Q&A 566). On Hit or Counter, all
face-up normal neutral Techniques return to the List, Special Techniques break,
and hidden or character Techniques remain in place. Two reviewed groups cover
13 deterministic scenarios.
`AWL-AT-016` (Help Catcher) now requires printed Speed 10 or less for Defense.
When the Speed difference is exactly two, both pre-FP Speeds are fixed for the
battle and ignore FP and later modifiers. On Counter, its controller must pick
one actual opposing Technique from Battle or Lumen to move to the List;
Special Techniques break, Secret Time's hidden card remains under the broken
host, and tokens or hidden cards are excluded (Q&A 97/353/376/543). Three
reviewed groups cover 14 deterministic scenarios.
`AWL-AT-017` (Nya Boosting) opens real mandatory owner decisions at Catch and,
while Over Limit, After Use. Only face-up Techniques in the owner's Lumen Zone
are offered. Catch moves the selected card to the List, applying the core
Special-Technique break rule, while After Use moves the selected card directly
to the Side Deck without a break-replenishment pause (Q&A 233/349). Two
reviewed groups cover 11 deterministic scenarios.
`UNC-AT-011` (Rai! Lefi! Catch!) splits effect 1 into explicit Grab-negated and
Opponent-Dodge triggers. Either event gives the opponent 2FP, while an unrelated
card-effect invalidation does nothing (Q&A 675). Guard and Clash are forbidden,
but only a Special-judgment Dodge is forbidden. The card is legal only from
fourth Combo onward and may ignore Speed after a Rai or Lefi Technique,
including a simultaneous proposal under Q&A 532. In Over Limit, the real Combo
pipeline finishes this card, suppresses an already-proposed fifth card, and
schedules +1FP exactly once for the next Recovery. Six reviewed rule groups
cover 23 deterministic scenarios.
`UNC-AT-012` (Lefi! Drill!) counts only actual face-up Techniques in Lumen for
its Before-Judgment damage bonus and caps that bonus at +500; zero Techniques
therefore adds zero (Q&A 539). It ignores Combo Speed only immediately after a
Rai-named Technique and still rejects a card whose final Combo damage is zero.
While Over Limit, an opposing Guard deals effect damage from the owner's broken
Techniques, including Special Techniques but excluding tokens, capped at 300.
Three reviewed rule groups cover 17 deterministic scenarios.
`UNC-AT-013` (Sorryyyyy!) now treats its printed High Speed-10 and Middle
Speed-8 Dodge limits as continuous defense rules. Its own Dodge gives +2FP,
and taking positive damage schedules the card's mandatory After-Judgment
break. That normal Technique break opens the real Side-to-List replenishment
choice when candidates exist and completes safely when none exist. Three
reviewed rule groups cover 12 deterministic scenarios.
`UNC-AT-016` (Powerful Sweep) records a successful Dodge and performs the
printed break at After Use, so all intervening result effects still resolve
(Q&A 360/388/485). A face-up All-In Charge in Lumen adds +100 damage at Use;
the two independent After-Use effects prohibit Catch and skip the owner's Get.
When the delayed normal-Technique break has eligible Side cards, its owner
chooses the replenishment before the remaining ordered After-Use effects
continue. Five reviewed rule groups cover 19 deterministic scenarios.
`UNC-AT-017` (Instant Smash) fixes its Speed to 7 under Charge, then applies
-100 damage and changes Hit to +3. An earlier same-timing fixed Speed retains
priority while later Speed changes and FP cannot alter the result (Q&A
470/657/691). Clash opens a mandatory owner choice over every card in that
player's Hand; the selected card breaks, while an empty Hand skips cleanly
(Q&A 583). Its Combo modifier grants +100 damage only to the immediately next
Technique whose text contains a Charge effect, never a later card. Three
reviewed rule groups cover 12 deterministic scenarios.
`UNC-AT-018` (Gear Change) checks every opposing battle judgment field: an
Attack's Special judgment and a Defense card's High/Middle/Low judgment can
all satisfy its Dodge condition, while Clash and Guard do not. Q&A 669 is
modeled in both priority orders: a Dodge gained after Gear Change resolves
does not retroactively change its position, while an already gained Dodge
changes Gear Change from High to Middle. Its reviewed rule group covers six
deterministic scenarios.
`LMI-AT-016` (Stormbringer) can be used only while a face-up All-In Charge is
in the owner's Lumen Zone, including when another effect grants a Catch
(Q&A 586); missing, hidden, or wrong-zone copies fail the same play condition
and an illegal Ready becomes No Response under the core rule (Q&A 588). Charge
blocks Guard, Dodge, and Clash only while Stormbringer is in Battle. At Use it
fixes Speed 14 and adds Low Clash; FP and later changes are ignored while an
earlier fixed Speed retains priority (Q&A 691). Three reviewed groups cover 13
deterministic scenarios.
`ST5-001` (Wolf Cutter) now has separate conditional Combo rules for its
Intimidation Speed exception and original-damage bonus. It may descend after a
Middle Technique while Intimidation is active; a preceding printed Damage of
500 or less grants +200 even when that card's effective damage was increased.
The following Technique must again ascend from Wolf Cutter's printed Speed 5
(Q&A 20). Its reviewed rule group covers five deterministic scenarios.
`ST5-002` (Hunting Head) blocks Guard only while it is in Battle and splits
Grab-negated from Opponent-Dodge events, so unrelated card invalidation cannot
grant the opponent 5FP (Q&A 260/675). A reusable `damage_bonus_speed` Combo
rule now exposes both printed Speed 6 and optional Speed 10 during Intimidation,
but applies +200 only when Speed 10 is selected; the following card must then
be Speed 11 or higher. Four reviewed groups cover 12 deterministic scenarios.
`ST5-004` (Fenrir Styx) dodges only an exact 500-damage Technique after
effect modifiers, with both adjacent boundaries rejected. Its Catch effect applies
-200 damage, changes Hit to Combo, and breaks the card at Catch timing while
the already-started Catch still deals 500 and opens Combo. Its second effect
likewise breaks Fenrir Styx both when its own Counter starts 1-Combo and when
it is used as a later Combo part (Q&A 184/269/284). A validated
`break_card.continue_resolution` flag and pipeline judgment synchronization
make this explicit without weakening ordinary external-break interruption.
Three reviewed groups cover ten deterministic scenarios.

`ST5-005` (Thunder Arctic) clashes only with Techniques whose effective
damage after pre-judgment modifiers is 500 or less. Its Q&A fixtures verify
the 500/501 boundary, reject a printed 500 Technique increased to 600, and
resolve Belgian Kick's Dodge before Thunder Arctic's simultaneous Clash
(Q&A 270/358). While Intimidation is active it may follow an Upper Technique
without the normal increasing-speed requirement; later Combo cards still use
Thunder Arctic's printed speed. Two reviewed groups cover eight deterministic
scenarios.
`ST5-007` (Street Wolf) ignores the normal 2-/3-Combo damage penalties and
uses a fixed Speed 7 when chosen for Catch. Once that Catch is declared, its
200 effect damage and the owner's Get skip are mandatory; the effect damage
and printed 400 Technique damage remain two separate damage events for Q&A
615 interactions. Two reviewed groups cover six deterministic scenarios.
`ST5-008` (Demise End) prevents Dodge only while it is in Battle. A Hit now
schedules Ready after the current Battle finishes instead of aborting damage
resolution immediately; during Intimidation the source moves to the list
first while the already-started resolution continues. Its Lower-following
speed exception is exposed as a distinct server-issued Combo action, applies
-100 only when that exception is selected, and still makes the next card
follow printed Speed 12 (Q&A 20/186). Three reviewed groups cover ten
deterministic scenarios. The shared Combo contract now carries validated
`optional_ignore_speed` choices, and `repeat_phase.after_current` distinguishes
deferred phase repetition from immediate Ready restarts such as Dash.
`ST5-009` (Chasing Fang) limits its Dodge to effective damage 500 or less.
Before judgment it inspects the opponent Attack's effect-adjusted Speed
without FP; Speed 8 or slower changes it to Middle and fixes it at Speed 7.
The fixtures cover priority-driven threshold changes, prior slow/fix effects,
FP immunity, mutual Dodge after the position change, and the current fixed
speed rules (Q&A 188/215/358/601/611/644/657/691). When used at 2- or
3-Combo it breaks but its already-started 800/700 damage resolves; a granted
4-Combo does not break it. Three reviewed groups cover 13 deterministic
scenarios.
`ST5-010` (Tabula) preserves its mixed defense grid: Upper Dodge and Middle
Clash work only against effect-adjusted Speed 9 or faster, while the empty
Lower entry remains empty under defense-judgment replacement (Q&A 341). Dodge
deals separate 300 effect damage, grants 5FP, and blocks only its controller's
Catch for the turn. Clash reduces the opposing Technique by 400, deals a
separate 200, and adjusts that opponent to exactly +1FP; lethal effect damage
wins before later Clash damage can create Sudden Death (Q&A 575). The shared
Combo-end pipeline now resets both FP after both players' Combo-end effects,
as required by Q&A 171. Three reviewed groups cover 12 deterministic
scenarios.
`AWL-AT-036` (Dicetied) prevents only the opponent's Clash while it is in
Battle and deals a separate 100 when the Technique is guarded. Its Q&A 576
fixture executes the real Guard/ Opponent-Guard timing sequence: Force
Parrying's Guard effect wins first at 500/100 HP, so Dicetied's later effect
does not resolve and Sudden Death is not entered. Two reviewed groups cover
seven deterministic scenarios.
`AWL-AT-037` (Absolute) gains +100 Technique damage only on Counter. During
Intimidation, printed Speed 9 and optional Speed 10 are separate Combo
actions; only Speed 10 deals two distinct 100 effect-damage events and skips
the controller's next Lumen phase. The normal Combo hit remains a third,
separate 300 event, preserving the per-damage-event Intimidation accounting
in Q&A 241. Two reviewed groups cover seven deterministic scenarios.
`AWL-AT-038` (Jet Rising) adds 200 on Clash only when the opponent's
effect-adjusted, pre-FP Speed is 8 or slower. Q&A 185 verifies that equal
final Speed produces mutual Hit before Clash is considered, while Q&A 477
verifies the final 900-versus-500 Clash difference. Its “after 3-Combo” text
now uses `extend_combo_to: 4`: ordinary 2-/3-Combo remains legal and the card
also becomes legal at 4-Combo, dealing 600/500/400 respectively. Two reviewed
groups cover eight deterministic scenarios.
`AWL-AT-039` (Cutdown) clashes only with effective Speed 7 or faster,
gains +400 on Clash, and ignores the normal Combo damage penalty. Its three
reviewed groups cover the 7/8 boundary, both owners, wrong timing, and 2-/
3-Combo damage in nine deterministic scenarios.
`UNC-AT-031` (Static Territory) now gains exactly three Howling after a
zero-damage judgment and stops at an explicit owner decision to place itself
in Lumen or remain in Battle. Either resolved branch resets Defense Over, while
actual received damage and a wrong timing do neither. From Lumen, five Howling
offers the optional break; only a successful break schedules +200 damage for
the next Attack readied that turn. Readying a Defense does not consume that
schedule. Q&A 59/67/68/570 are covered by two reviewed groups and eight
deterministic scenarios.
`UNC-AT-032` (Deadly Spark) stops on Hit until its owner selects exactly one
Attack or Defense Technique from List to break; non-Technique tokens are never
offered, and an empty legal set safely skips the break (Q&A 183/365/583). Its
Combo effect applies speed ignoring only to the immediately following Wolf
Middle Technique, excludes Lulu (Q&A 671), and restores ordinary ascending
speed from that linked card for any later Combo slot (Q&A 20). Two reviewed
groups cover eight deterministic scenarios.
`UNC-AT-033` (Brutal Surge) deals a separate 200 effect damage on Counter,
adds +100 Combo damage only when the immediately previous Technique has a Hand
judgment, and exposes printed Speed 8 plus optional Speed 11 while Intimidation
is active. Only the selected Speed 11 receives the second +100. Three reviewed
groups cover ten deterministic scenarios, including both owners, Foot
predecessors, printed-speed use, missing Intimidation, and wrong timing.
`LMI-AT-027` (Lightning Wrath) now uses a dedicated post-reveal/pre-Use timing
for its five-Howling requirement (Q&A 434/480). Intimidation satisfies the use
condition without payment; otherwise five counters are removed after both
Techniques are revealed, and numbered-effect negation does not refund that
numberless cost. The card remains unavailable for Combo and Catch (Q&A 437),
blocks only special-judgment Dodge normally, blocks every Dodge and changes
Hit to +7 during Intimidation, and grants exactly 9FP after a normal zero-FP
Defense Dodge (Q&A 435). Five reviewed groups cover 21 deterministic
scenarios, including both owners, wrong timing, inactive zones, and numbered
effect negation.
`LMI-AT-028` (Rai Vajra) resolves only on the opponent's Guard: it deals a
separate 200 effect damage, moves itself from Battle to List, and installs a
source-specific Get prohibition for the rest of that turn. The real Get
action projection hides Rai Vajra while leaving other List Techniques
selectable, then offers it again after turn-scoped rules expire. One reviewed
group covers four deterministic scenarios across both owners and wrong result
timings.
`ST6-PS1` (Matude) gains one Grace after each Combo card used at exactly two
Speed slower than its predecessor, at After-use timing and capped at three
(Q&A 121-123/127/139). Joint Combo proposals now preview a deterministic
earlier Grace gain so a later card whose use condition becomes legal can be
presented and is still rechecked during resolution (Q&A 625). With three Grace,
only a Viola Technique in Hand receives the optional declared-Speed action;
the counters are paid before that card's own use condition (Q&A 124), a
2-Combo declaration requires a legal 3-Combo follow-up (Q&A 125), and a
two-Speed declaration can earn one Grace back at After-use (Q&A 445). Three
reviewed groups cover 15 deterministic scenarios.
`ST6-001` (Shadow Cut) applies its numberless -200 damage continuously only
while its owner has no Grace counter, then adds +200 at Counter timing.  The
two modifiers compose to 500 damage with no Grace on Counter and 700 with at
least one Grace, while Hit and Clash do not receive the numbered bonus.  Q&A
477's no-Grace Clash value of 300 is covered explicitly.  Two reviewed groups
cover eight deterministic scenarios across both owners and wrong timings.
`ST6-002` (Spear Jeté) grants its Low Dodge only before judgment while the
opponent is ahead in FP, and the generated defense rule enforces both the Low
position and the Speed-8 minimum. The FP comparison is made once in the
Before-judgment window; it is deliberately absent from the generated defense
rule because both players' FP have already been reset before judgment. The
Speed boundary uses the effect-adjusted, pre-FP reference Speed, so an external
9-to-7 change rejects Dodge while a 7-to-9 change allows it, and FP reducing
final Speed below 8 does not reject it. One reviewed group covers 12
deterministic scenarios across both owners, FP boundaries, Low/non-Low
positions, Speed modification, wrong timing/zone, numbered-effect negation,
and the actual battle order. Mutation tests reject the earlier FP-rechecking
shape and altered card statistics.
`ST6-003` (Plié Shade) keeps printed Speed 7 plus the optional Combo Speed 8,
but only the declared Speed-8 path resolves after Use.  It deals the reduced
Combo damage first, then breaks itself, waits for the normal Side-to-List
replenishment, and finally requires the owner to select exactly one Technique
from the resulting List for acquisition.  An empty candidate set is the only
safe skip.  This covers Q&A 307's ordering and Q&A 580's rule that newly
acquired cards cannot be added to the already-submitted joint Combo proposal.
One reviewed group covers five deterministic scenarios across both owners,
replenishment, no candidates, printed Speed 7, and an early timing.
`ST6-004` (Black Dart) checks the pre-judgment FP threshold, forcibly resets
its owner's FP to zero before Speed is applied, and blocks both ordinary and
special Guard/Dodge for the battle.  Q&A 306 is exercised as an actual
8-versus-5 judgment after the reset, and Q&A 485's broad Dodge prohibition is
checked directly.  One reviewed group covers five deterministic scenarios
across both owners, the FP threshold, expiry, wrong timing, and final Speed.
`ST6-005` (Bad Catcher) requires at least one Grace at card-use validation.
As the battle's 1-Combo it spends one Grace, then requires an owner choice
from only odd-Speed Attack Techniques in List; even Attacks and odd Defenses
are excluded.  The acquired card reaches Hand before the later Combo proposal
(Q&A 580), while the After-use spend is rechecked and therefore does not apply
when the first effect used the owner's only Grace (Q&A 128).  Three reviewed
groups cover 12 deterministic scenarios, including both owners, empty legal
candidates, later-Combo use, and the general illegal-use rule in Q&A 588.
`ST6-006` (Fouetté en Lumen) adds Mid Clash and changes Hit to Combo at
three FP before judgment without consuming that FP.  The FP-unapplied Speed
comparison is exercised against a Middle attack, while its Combo metadata now
preserves both declared Speed 7 and 9 in addition to printed Speed 10 and
filters each by normal ascending-speed legality.  Two reviewed groups cover
ten deterministic scenarios, including Q&A 642's declared-Speed context.
`ST6-007` (Arena Battement) exposes Speed 10 and 12 only while the shared
Viola `hidden_bond`/Grace counter exists, and ignores the accumulated Combo
damage penalty only when it is used as 6-Combo or later.  One reviewed group
covers five deterministic scenarios across both owners, a missing counter,
and the 5-/6-Combo penalty boundary.  Matude, Shadow Cut, and Bad Catcher were
also migrated from a private `grace` key to this existing shared counter key
so all Viola cards now interoperate.
`ST6-008` (Leg Doll) keeps printed Speed 12 Catch and its paid Speed 9 Catch as
separate server-issued actions.  The optional action is shown only when one
`hidden_bond` counter can be paid, consumes exactly one counter when selected,
and disappears when the numbered effect is negated.  Its numberless function
blocks both ordinary Defense Dodge and broad Special Dodge while the card is
in Battle without blocking Guard.  Two reviewed groups cover nine
deterministic scenarios across both owners, missing cost, numbered-effect
negation, source-zone expiry, and Q&A 367/485 behavior.
`ST6-009` (Pain Prison) rechecks its shared `hidden_bond` use condition for
Ready, Catch, and each Combo card.  Its Before-judgment branches are mutually
exclusive at the current FP comparison: an advantage adds 300 damage, while a
tie or disadvantage changes printed Speed 13 to Speed 5.  Effect-modified
Speed 5 is visible to Dodge restrictions, but printed Damage 600 still fails a
500-damage Dodge limit.  Same-window Speed-change/Speed-fix conflicts now keep
the first-applied mandatory effect, so priority produces both Q&A 500 outcomes
against Charging Smash.  Three reviewed groups cover 18 deterministic
scenarios, including both owners, negative FP, wrong timing, Combo rechecks,
and Q&A 133/134/286/459/496/500/511/588/611/625.
`ST6-010` (Chassé Preparation) now treats its Clash result changes as
mandatory and the following Combo Time as a separate optional decision.  Its
After-use move sends the card to the List and correctly clears Defense Over
without breaking the opposing card.  Two reviewed groups cover eight
deterministic scenarios across both owners, non-Combo Hit, wrong timing, and
Q&A 251/341/468/570.
`AWL-AT-042` (Needle Spike) cannot be used for Catch.  Its Before-judgment
Guard prohibition is active only at exactly 2 FP, not at 3 or more FP, and it
does not prohibit Clash.  Two reviewed groups cover nine deterministic
scenarios across both owners, legal Ready/Combo use, timing boundaries, and
Q&A 590.
`AWL-AT-043` (Fortissimo) cannot be used for Catch and exposes both printed
Speed 8 and effect Speed 9 during Combo.  When another effect has already
extended the normal Combo maximum, using it at Speed 9 as 4-Combo or later
breaks it after use and opens the ordinary mandatory replenishment selection;
printed Speed 8 and 3-Combo Speed 9 do not break it.  Two reviewed groups
cover nine deterministic scenarios across both owners and Q&A 642.
`AWL-AT-044` (Grand Crescendo) now requires at least one `hidden_bond`
counter in every use context.  Its Combo effect first spends one counter,
then offers a separate optional extra spend only when both another counter
and an eligible List Technique exist.  Accepting opens a real mandatory card
choice containing only Techniques whose text spends `hidden_bond`; unrelated
cards and marker-bearing tokens are excluded.  A selected ordinary Technique
moves to Hand while a selected Special Technique follows the core movement
rule and moves to Break.  Two reviewed groups cover 11 deterministic
scenarios across both owners, decline/no-candidate paths, wrong timing, and
Q&A 129/580/588.
`AWL-AT-047` (Mei Shoot), `AWL-AT-049` (Throw Kick), `AWL-AT-051`
(Split Cutter), `AWL-AT-053` (Fry End), and `AWL-AT-054` (Hook Breaker) are
now pinned to the shared DSL reviewer.  Every ability has at least three
deterministic engine situations covering both owners and an outside-boundary
or wrong-trigger case.  These scenarios verify the Speed-7/6 Dodge limits,
Foot-only Clash, Guard prohibition plus self-Break on Hit, and Clash damage
increase respectively.
`AWL-AT-048` (Low Kick) is explicitly pinned as a reviewed empty DSL
definition. Its three no-effect scenarios verify both owners and the absence
of any generated command; it was already included among the catalog's
explicit no-effect cards.
`UNC-AT-036` (Scene Nocturne) now restricts Dodge to an opposing Technique
whose Hit or Counter judgment contains Combo. On Dodge, its optional cost
opens a real owner choice containing only Combo-judgment Techniques in Hand
or List; unrelated cards and tokens are excluded. A successful Break installs
the turn-scoped 3-Combo cap and one-`hidden_bond` gain limit before granting
the special Combo. The core special-Combo path now requires the 1- and
2-Combo cards to be presented together, applies damage penalties 0 then 100,
rejects a one-card command, returns the Defense source to Hand, and skips the
Combo Time without consuming a pending Catch when no legal pair exists.
Three reviewed groups cover 11 deterministic scenarios across both owners and
Q&A 455/468/595.
`UNC-AT-037` (Nightmare Jeté) now requires at least one `hidden_bond`
counter to be used and can Dodge only Speed-10-or-lower Techniques. On Hit or
Counter it grants a List-only Catch containing only actual Techniques whose
text spends `hidden_bond`; unrelated cards and marker-bearing tokens are
excluded. The Catch action is issued in normal and source-Break variants. The
source-Break variant uses the real Break and replenishment flow, then waives
both a selected Catch-speed counter cost and every negative `hidden_bond`
change from that caught card's Use/Catch/Hit/After-use effects. If the source
cannot be broken, those variants are not issued. Combo Time still clears the
earlier effect Catch before it can be used. Two reviewed groups cover 11
deterministic scenarios across both owners and Q&A 131/367/384/406/588/641.
`UNC-AT-038` (Quick Accent) now exposes only Speed 6 through 9 while it is
used in a Combo. Its numbered Catch rule fixes the card at Speed 8, gains one
`hidden_bond`, adds 100 damage, and breaks the used Technique only after Catch
damage and After-use timing finish. The full Catch action is submitted through
the engine rather than testing isolated DSL nodes. Two reviewed groups cover
eight deterministic situations across both owners, both Combo speed
boundaries, a Catch Speed-7 rejection, an existing counter, and numbered-effect
negation. The ordering assertion requires the 500-damage event to precede the
card's Break event.
`LMI-AT-032` (Blanc Adagio) now has two reviewed judgment-change effects and
11 deterministic situations. Its first numbered effect changes the printed
Guard result from -6 to -3 only when its owner has at least one `hidden_bond`;
additional counters do not apply the replacement repeatedly. On Clash, its
second effect changes its Hit result to Combo only when the opponent's current
Hit result is exactly Combo. A non-Combo result and a composite text such as
`+2 Combo` both leave the printed Hit result unchanged. Both groups cover both
owners, false conditions, wrong timing, and numbered-effect negation.
`LMI-AT-033` (Thorn Allegro) now has two reviewed Counter-timing effects and
nine deterministic situations. A Counter adds exactly 100 to the Technique's
battle damage. Its separate FP effect grants exactly 1FP only when the owner
has at least one `hidden_bond`; multiple counters do not multiply that gain.
Both effects cover both owners, wrong timing, and numbered-effect negation,
while the FP effect additionally covers the zero-counter boundary.
`AWL-PS-001` (Veiled Blade) now has two reviewed rule groups and 11
deterministic situations. Damage dealt by its owner during Clash, including
separate effect damage (Q&A 190/615), deals one additional 100 damage and
enters Dark Night through the end of the next Battle phase. The generic state
duration scheduler advances only at an actual matching phase end, so a Ready
restart does not shorten the duration (Q&A 404). While active, the opponent's
Technique special judgments are removed in Battle, Hand, List, Side Deck,
Break, Lumen, and Ultimate zones; later replacement or newly gained special
judgments are removed again (Q&A 193/370/552). Grab negation now searches both
Hand and List and uses these effective judgments. A Technique-granted Dark
Night state survives Charm while the negated Trait's removal rule stops
(Q&A 220). Limited abilities reserve their use before nested domain commands,
preventing the additional damage from recursively triggering itself.
`AWL-AT-001` (Quick Allez) now has two reviewed rule groups and twelve
deterministic situations. A Hit removes exactly 1FP from the opponent and an
opponent Dodge grants that opponent exactly 3FP. Both groups cover both
owners, unrelated judgment events, numbered-effect negation, and the same
event emitted by the opponent's card. Source-only collection prevents either
effect from reacting to the opponent card's result. The Hit group also
verifies the rulebook's negative-FP boundary: an opponent at 0FP goes to -1FP
rather than being clamped, preserving the subsequent negative-FP Catch
condition.
`AWL-AT-002` (Sadistic Heel) now has one reviewed rule group and seven
deterministic situations. Its printed Speed 6 becomes fixed Speed 2 for Catch
only when its owner used a Low-judgment Technique in the current turn. The
usage history accepts both normal Ready use and an earlier Catch (Q&A 194),
but rejects a previous-turn use and a current-turn Middle use. Numbered-effect
negation removes the speed rule, and a copy already in the Battle zone is not
offered again as a Catch card (Q&A 466). A legal Hand copy is submitted through
the real Catch action and verified in the Battle zone at fixed Speed 2.
`AWL-AT-004` (Épée Corbeau) now has two reviewed rule groups and 11
deterministic situations. Its Clash trigger reduces only the opposing
Technique's damage by 200 and is collected once from its own result rather
than again from the opponent's simultaneous Clash. A full Battle pipeline
reduces a 200-damage opponent to zero while still applying that opponent's Hit
FP before resolving the 500 damage difference (Q&A 250). In Dark Night, its
printed High Clash remains the only special judgment until the Before
Judgment window, when Mid Clash is appended. This timing is verified before
and after the event for Q&A 448, including both owners, a false state, an
earlier Use event, and numbered-effect negation.
`AWL-AT-005` (Crescent) now has three reviewed rule groups and 19
deterministic situations. Before Judgment it replaces a Special judgment only
on an opposing Attack Technique with Mid Clash; a Defense card with a Special
judgment and an Attack without one are excluded. Against Defense, its printed
Combo Hit becomes -4 before Clash. A Paki Defense fixture reads that live -4,
applies its later Clash adjustment to -5, and the judgment FP becomes -5
(Q&A 195/236). The Rabbit Stamp integration runs the complete battle with
either priority order: Rabbit's +300 damage and Crescent's Special replacement
both resolve, the cards Clash, Crescent takes the 300-damage difference, and
its still-printed Combo starts Combo Time (Q&A 419). The independent Catch
group changes damage from 700 to 500 only at Catch timing. All groups include
both owners, false conditions or timings, and numbered-effect negation.
`AWL-AT-006` (Marnomery) now has two reviewed rule groups and 11 deterministic
situations. Its Combo rule ignores the 100/200 damage penalties at 2-Combo and
3-Combo, while numbered-effect negation restores the normal penalty. Dark
Night continuously raises only that card's damage from 400 to 600 and stops
when the state is absent or its numbered effects are negated. The Q&A 407
integration starts with a real Clash, gains Dark Night from the resulting
damage, opens Combo Time in the same Battle phase, and then resolves
Marnomery for 600 damage with both effects active. The complete sequence is
run for both owners. Root `combo_rules` can now mark `numbered_effect: true`,
so static Combo permissions and exceptions follow the same negation rule as
their visible numbered ability.
`AWL-AT-007` (Floraison) now has three reviewed rule groups and 18
deterministic situations. On Clash, only List Techniques whose text contains
the Dark Night state marker are offered, and the owner must choose the exact
card to acquire; unrelated cards, empty candidate sets, wrong timing, and
numbered-effect negation are covered. In Dark Night it is illegal at 2-Combo
and 3-Combo, extends the normal limit to 4-Combo, and deals its full printed
500 damage without the 300 scaling penalty (Q&A 600). A Dark Night state
gained after Combo Time opened is re-read immediately in the same Battle and
enables that 4-Combo permission (Q&A 407). Numbered-effect
negation now also prevents a root Combo rule from extending the Combo maximum.
After use, the card schedules Dark Night for that turn's Recovery entry and
expires it at the end of the next Battle phase. The granted state records a
Technique origin and therefore survives active Trait negation (Q&A 220).
The core engine now computes the live character hand limit after every move
to Hand. If the limit is exceeded, it opens a mandatory owner decision for
exactly the excess cards and discards the chosen cards to the List. The Q&A
438 scenario acquires at six cards without trimming, returns Floraison after
Battle to reach seven, exposes all seven legal discard choices, and finishes
at the six-card limit.
`AWL-AT-008` (Refuse) now has two reviewed rule groups and 18 deterministic
situations. Its unnumbered function checks the opponent's effect-adjusted,
pre-FP speed and permits Dodge only at speed 8 or 9 (Q&A 487), even while
numbered effects are negated. Before judgment against a Defense Technique,
`modify_defense_judgments` changes only existing positional judgments to
Clash, preserving blank fields (Q&A 341/380). A battle-scoped schedule with
`effect_controller: event` models the effect granted to the opposing Defense
Technique: when that card actually Clashes, it lowers Refuse's damage by 300.
Full-pipeline cases cover ordinary Guard conversion, blank-field Hit,
Charging Barrier accept/decline and its existing -500 stacking (Q&A 492),
normal Guard after numbered-effect negation (Q&A 393), and zero actual damage
under Light Lumen while Refuse still gains its Clash judgment FP without
granting Dark Night (Q&A 250/525).
`AWL-AT-009` (Silent Dagger) now has two reviewed rule groups and 13
deterministic situations. The numbered Combo rule exposes speeds 8, 9, and 10
alongside the printed speed 12, rechecks the normal increasing-speed rule, and
breaks the Technique only after damage, judgment FP, and After-use processing
when one of the three alternate speeds was selected. A successful ordinary
Attack break exposes every legal Side-deck Attack/Defense replacement to the
owner rather than choosing one automatically. Its numbered Dark Night rule
blocks self-break and all external break attempts while leaving the card a
legal target. Failed breaks produce neither a copied damage bonus nor a Dagger
token (Q&A 197). Both rules disappear under numbered-effect negation, and Dark
Night gained after Combo Time has already opened is read from live state and
immediately prevents the pending self-break (Q&A 407).
`AWL-AT-010` (Et Vous Prêt) now has one reviewed rule group and nine
deterministic situations. At Before-judgment it first requires an opposing
special judgment, replaces that judgment with Upper Clash, and only then makes
itself six speed faster. Empty special judgments, wrong timing, and numbered
effect negation leave both cards unchanged. Full battle scenarios reproduce
Q&A 348 in both priority orders: Panning Stun acting first creates Upper Dodge,
which Et Vous Prêt subsequently converts before becoming speed 7 and reaching
Clash; Et Vous Prêt acting first finds no special judgment, misses the whole
effect, and Panning Stun later retains Upper Dodge against the printed speed
13 Technique. The review asserts effect-resolution order as well as the final
judgment, speed, and battle result.
`AWL-AT-011` (Nevermore) now has two reviewed rule groups and 11 deterministic
situations. Its unnumbered play condition is checked for Ready, Combo, and
Catch and permits use only while the owner's FP is strictly lower. Before
judgment it performs generic invalidation rather than Grab negation, returns
the opposing Technique to Hand, breaks itself, resets both FP values, and
restarts Ready without ending the Battle. The turn-scoped use prohibition is
matched by card instance and therefore blocks every Technique already used in
Ready, Combo, or Catch while leaving unused cards and a Grab spent only as a
negation cost available (Q&A 343/551/685). Existing use costs, usage history,
Dark Night, and battle-scoped schedules survive the restart (Q&A 404/480/645),
and generic invalidation emits no Grab-negated trigger (Q&A 675). Three CMYK
attachments move to the List with their `attached_to` relation intact when the
host returns to Hand (Q&A 696). The self-break scenario also pauses on the
normal optional Side-deck replenishment choice before completing the FP reset
and Ready restart.
`AWL-AT-019` (Badman Punish) now has two reviewed rule groups and 12
deterministic situations. Its numbered Charge clause is represented as a
continuous effect rather than a numberless function, so numbered-effect
negation suppresses it correctly. While Charge is active the source-specific
damage modifier follows the card from Hand into Combo resolution; full Combo
scenarios apply the +200 before the normal 2-Combo -100 damage adjustment,
including both owners as required by Q&A 529. Full battle-pipeline scenarios
then verify that the Counter-only +100 resolves after judgment but before
damage, stacks with Charge to 700, misses an equal-Speed Hit, and disappears
together with the Charge clause under numbered-effect negation.
`AWL-AT-021` (Wingstar) now has two reviewed rule groups and 15 deterministic
situations. Its numberless Mid-Clash rule accepts the Speed-9 boundary and
rejects Speed 8. The numbered reaction copies an opposing lock only while
Wingstar is in the Battle zone, then installs a battle-scoped, one-use damage
prevention. A generic replacement `max_uses` field makes the first damage zero,
allows later damage through, and expires an unused prevention at Battle end.
Speed-lock events created inside one ability are now dispatched only after all
commands of that ability finish, reproducing Charging Smash's two locks before
Wingstar reacts regardless of priority (Q&A 680/681). Full battle scenarios
also prove that Charging Smash can gain 5FP while its Counter damage becomes
zero, and that zero damage does not erase either Combo judgment: both players'
Ready cards remain their sole 1-Combo and mutual Combo time ends immediately
(Q&A 682). Q&A 683 is retained as the source for applying the current errata
text to older printings.
`AWL-AT-023` (Dominate) now has two reviewed rule groups and 14 deterministic
situations. Full judgment scenarios accept both ends of its Speed 8–9 Dodge
range and reject Speed 7 and 10. Its Dodge trigger grants a Catch from Hand
only; List cards, Special Techniques, unmarked Techniques, and cards that only
mention Charge later in their text are excluded. A new `text_effect_prefix`
card predicate distinguishes a Technique whose effect actually begins with
`[[state:charge]]:` from a mere Charge reference. Catch candidates still pass
the normal play-condition checker, so Stormbringer is unavailable without a
face-up All In Charge in Lumen and becomes playable when that requirement is
met (Q&A 586). The scenarios execute both an ordinary Charge Catch and a
Stormbringer Catch through Use, Catch, Hit, damage, and After-use timing, and
confirm that an unspecified Catch location never includes the List (Q&A 667).
`AWL-SP-001` (All In Charge) now has three reviewed rule groups and 24
deterministic situations. Its private Recovery trigger offers the source from
Side at the exact 1000-HP boundary, preserves decline, and is absent above the
boundary, in another phase, or outside Side. When Fighting Spirit is offered
at the same timing, the owner receives the normal `effect_order` choice and
can deploy either card first (Q&A 378). While the source is in Lumen and its
owner has Charge, only that owner's Route Attack gains +100 damage at Use;
other characters, Defense cards, the opponent's card, another phase, and an
inactive source are excluded. Losing Charge applies one 500-damage instance
and then installs a game-scoped `state_gain` prohibition whose source filter
blocks only `ST2-PS1` Charge-trait re-entry. A different Technique may still
grant Charge. Root Astra refreshing an existing Charge replaces its expiration
without first losing the state, so the first Recovery end causes no damage and
the extended expiration causes exactly one later penalty (Q&A 509). The
remaining linked Q&A sources retain Charge-duration, adjusted-speed, and Lumen
Special-Technique movement rulings (Q&A 162/164/376).
`UNC-AT-041` (Lenore Knock) now has two reviewed rule groups and 14
deterministic situations. Both numbered Clash effects are explicitly active
only while the source is in Battle. The first deals a separate 100 effect
damage for either owner, ignores the wrong timing, and activates the damaged
Reve player's Dark Night listener (Q&A 190). If that effect damage reduces the
opponent to zero, the engine records an immediate normal HP-zero win without
starting Sudden Death or applying the later Clash damage (Q&A 575). The Dark
Night clause reduces only the opposing Battle Technique's damage by 100,
stacks after existing damage modifiers, and is absent without Dark Night,
outside Battle, at another trigger, or while numbered effects are negated.
When both clauses trigger, `effect_order` exposes both ability IDs and the
owner may resolve either one first while preserving the same final damage.
`UNC-AT-042` (Midnight) now has three card-effect groups plus one linked-ruling
group and 23 deterministic situations. At Clash it changes its own Hit judgment
to +7 and reduces the opposing Technique's damage by 200; Dark Night also
changes the opposing Hit judgment to +0. All three clauses are limited to the
source in Battle, respect numbered-effect negation, and expose `effect_order`
when two or three clauses trigger together. Full battle-pipeline scenarios
reduce a 200-damage opposing attack to zero while still applying that attack's
Hit-3 FP and Midnight's changed Hit-7 FP (Q&A 250). Separate Catch-window
scenarios prove that an effect-granted Catch is offered before Midnight's FP
Catch, that playing it resets the pending FP, and that declining it allows the
FP Catch to proceed (Q&A 406).
`UNC-AT-043` (La Nuit Blanche) now has four reviewed rule groups and 27
deterministic situations. Its static Clash rule accepts only Techniques whose
pre-FP speed is at least 8, so a printed/effect speed of 8 remains eligible
even when 5FP changes the battle speed to 3, while speed 7 is rejected
(Q&A 359). At Clash, ability 1 checks the opponent's current Hit judgment: an
opposing optional effect that changes Hit to Combo first enables La Nuit
Blanche to replace that Hit with +0 and its own Hit with Combo; declining the
optional change leaves ability 1 untriggered (Q&A 237). Dark Night reduces the
opposing Technique's damage by 200 and shares the normal owner-selected
`effect_order` window with ability 1. The Combo clause is absent at 1-combo
and reduces this Technique from 700 to 500 damage at both 2- and 3-combo.
Every numbered clause is also checked for the wrong timing, an inactive source
zone, numbered-effect negation, and both player ownerships.
`LMI-AT-036` (Noir) now has three reviewed rule groups and 21 deterministic
situations. At Use, the engine issues a mandatory owner decision for exactly
one Technique from Hand, or exactly two while Dark Night is active. Only cards
that actually reach Break contribute to the fixed damage sum and inherited
positional Clash judgments; a Dark Night-protected Silent Dagger remains a
legal choice but contributes neither value (Q&A 197). Defense or missing
damage counts as zero (Q&A 59), multiple current Clash positions are retained
(Q&A 450), a Clash gained only at Before-judgment is not copied at Use
(Q&A 448/461), and the source card's speed restriction is never copied with
the judgment (Q&A 449). A reusable `selected_cards_field_sum` value operation
and `copy_clash_judgments` command provide these semantics without a database
mutation or card-specific Python handler. The Combo rule ignores the normal
damage penalty only during Dark Night at the exact opposing 1000-HP boundary,
and numbered-effect negation restores the penalty. After-use checks the live
Dark Night state, including a state gained earlier in the same Battle
(Q&A 407), then breaks Noir or sends it to Side while allowing a Combo
resolution to continue after the source leaves Battle.
`LMI-AT-039` (Night Talon) now has one reviewed rule group and 11 deterministic
situations. Its Before-judgment effect adds 100 damage only when the opposing
card is an Attack Technique whose currently effective special judgment is
empty. The scenarios cover both owners, a printed Grab, a Defense Technique,
the wrong timing, an inactive source zone, and numbered-effect negation. They
also integrate the actual Dark Night continuous rule from `AWL-PS-001`: a
printed Grab is cleared before Night Talon's condition is evaluated, including
when Dark Night was gained during the preceding Use window (Q&A 584). Battle
timing and result dispatch now scope Battle-zone abilities to the Technique
whose timing slot is being resolved, while global Passive/Lumen/Ultimate
reactions remain active; this prevents the opposing Battle card from resolving
the same effect a second time. The generic draft compiler also recognizes
Attack/Defense type plus absent-special conditions for other cards using the
same wording.
`LMI-AT-040` (Wicked Shadow) has one reviewed rule group and 10 deterministic
situations. Hit or Counter grants Dark Night through the end of the next
Battle, moves Wicked Shadow to List without interrupting the current Catch or
Combo resolution, and blocks every attempt to move it to Hand until turn end.
The scenarios cover both owners, state expiry, Get-phase acquisition
prevention, turn-end release, numbered-effect negation, inactive source and
wrong timing. The granted state is a Technique effect rather than a trait, so
trait negation does not remove it (Q&A 220), and a blocked Get still advances
to Recovery (Q&A 652).
`LMI-AT-041` (Black Feather) has three reviewed rule groups covering 20
deterministic situations. Its private once-per-turn Side trigger asks the
owner which physical Black Feather card to place in Lumen and shares one
usage key across two copies (Q&A 501/597). A Feather already in Lumen reduces
the opposing Technique by 100 and moves one physical Dagger token from Side to
Lumen; multiple Feathers stack, but the global Dagger count stops at six
(Q&A 202). A Feather placed during that Clash misses the current public
effect window (Q&A 451/634), and Dagger remains a non-Technique token
(Q&A 543). During Combo, Dark Night may delete every Dagger for one damage
event of 200 per three tokens; the reviewer verifies zero-damage deletion,
single reduction of a six-token 400 hit (Q&A 525), a third Dagger created by
an earlier same-timing effect (Q&A 639), repeated optional windows (Q&A 663),
and deletion without a Break-zone card or replenishment (Q&A 452).
`LMI-AT-043` (Butterfly) has three reviewed rule groups and 13 deterministic
situations. Breaking the physical card grants 1 FP at the actual break timing
(Q&A 227). It can ignore Combo Speed only after a TAO Low Technique. Harmony
requires at least 3-Combo, removes the damage penalty, ends Combo after use,
and schedules +2 FP exactly once for the current turn's Recovery (Q&A 489).
`LMI-AT-044` (Wave Cannon Embrace) has three reviewed rule groups and 13
deterministic situations. Use removes whichever of Yin and Yang actually
exists without making either counter a play condition (Q&A 212/428). Hit opens
one mandatory branch choice for two Yin or two Yang and never offers a split
choice (Q&A 429). Harmony's +100 damage applies only to this physical card.
`LMI-AT-045` (Dodge Roll) has three reviewed rule groups and 14 deterministic
situations. Its Speed-9 Dodge limit uses the effect-adjusted pre-FP Speed
(Q&A 215). Dodge remains valid at zero Yang, but counter removal and every
"then" effect stop there (Q&A 558). With Yang, only a Speed-7-or-lower TAO
Technique in Hand is offered for Catch. The engine now exposes the shared
`catch_opportunity_resolved` timing after Catch use/decline and before a Catch
card's Combo: Harmony then opens a mandatory List-card choice. The caught card
is already in Battle and cannot be acquired (Q&A 447), while the chosen List
card cannot be used for that Catch but can be used in its following Combo
(Q&A 490).
`UNC-AT-006` and its `LMI-AT-046` reprint (Wolf Pack Rush) each have four
reviewed rule groups and 21 deterministic situations. The Hit/Counter choice
selects an exact Yin amount, increases only the Technique damage, and gains
Yang only after at least one Yin was actually removed (Q&A 382). The current
Counter window does not retroactively collect a Bagua effect from the newly
gained Yang (Q&A 653), while existing Yang does. Its 2-to-3 Combo restriction,
Harmony effect damage, and turn-scoped Catch prohibition are tested for both
owners, numbered-effect negation, wrong timing, expiry, and effect damage not
receiving Technique-damage bonuses (Q&A 618).
`UNC-AT-003` and its `LMI-AT-047` reprint (Ground Sweeper Dragon) each have
five reviewed rule groups and 23 deterministic situations. Its unnumbered
Speed-6 Dodge limit survives numbered-effect negation, while the Harmony
Speed-7 extension and Hit-to-Combo replacement do not. The scenarios use the
effect-adjusted pre-FP reference Speed, cover both owners and condition
boundaries, and verify that Use-time Yang removal can end Harmony before
judgment so the Hit judgment returns from Combo to its printed value
(Q&A 503). Dodge-time Yin and Use-time Yang removal also cover zero counters,
wrong triggers, and numbered-effect negation.
Eight physical marker cards (`UNC-AT-058/059`, `LMI-AT-056/057/058/059`,
`PMP-AT-053`, and `PMP-CS-009`) each have one reviewed rule group and four
deterministic situations. Released `token_key` and `token_usage` metadata is
now applied both to pre-existing zone cards and to tokens created from only a
catalogue code. The scenarios cover both owners, Lumen token deletion,
passive counter-marker preservation, runtime token creation, and deterministic
replay.
`DFR-TK-001` (New Single) has two reviewed rule groups and 11 deterministic
situations. A New Single in Hand, including one created from its catalogue
code, becomes a legal Speed-1 CMYK Attack; outside Hand it retains its printed
Token form, while a played card keeps the form needed for resolution. When it
is set under a CMYK Technique, that host's Use breaks the exact attached token
before offering its owner only CMYK List candidates to acquire. The scenarios
cover both owners, explicit selection among two candidates, no candidates,
an unattached token, a non-CMYK host, numbered-effect negation, and a prevented
break. A failed break stops the subsequent acquisition, and breaking this
temporary Attack-form token never opens ordinary Technique replenishment.
`DFR-AT-001` (Climax!) has three reviewed rule groups and 16 deterministic
situations. The review covers the HP 2500 use boundary and confirms that its
unnumbered Dodge prohibition applies only while the card is in Battle, then
continues even if HP rises or numbered effects are negated. Hit/Counter opens
an optional effect first and, when accepted, a mandatory player choice that
contains only normal CMYK Attack/Defense Techniques in Hand. A failed move
does not attach the card or grant the Combo Speed exception. Its After-use
bonus affects only CMYK Technique damage during the current Combo, expires
before the next Combo/Catch flow, and schedules Climax! to break at Combo end.
The scenarios also verify ordinary break replenishment and the protected-break
case, which proceeds through normal Battle cleanup to List.
`DFR-AT-002` (Intro Drum), `DFR-AT-003` (Walking Bass), and `DFR-AT-004`
(Backing Guitar) each have two reviewed rule groups and 12 deterministic
situations. Their attached Drum/Bass/Guitar effects activate only for the
matching CMYK host and identical set keywords are deduplicated per timing
window; both owners, unattached cards, a non-CMYK host, numbered-effect
negation, and Vocal's doubled numeric value are covered. Intro Drum's granted
Catch lists only attached CMYK Techniques whose effect-adjusted pre-FP Speed is
6 or lower, including a card that remained attached after moving to List as
specified by Q&A 697. Walking Bass's Catch Speed 5 and Backing Guitar's chosen
Combo Speed are now explicitly marked as numbered top-level rules, so effect
negation correctly restores printed Speed 6 or the ordinary Combo speed
options instead of leaving the rule active.
`CB03-AT-032` (Slap&Crash) and `CB03-AT-033` (Drum Phalanx) complete the
remaining CMYK card-specific review with five ability groups and 42
deterministic situations. Slap&Crash reuses the non-stacking Bass rule, gains
Speed 2 exactly once when at least one attached Drum is present, and offers
real owner choices for the Battle host, the CMYK Technique moved from Hand or
List, and zero to two New Single tokens. Initially move-immune candidates are
not offered; immunity added after selection leaves the Technique in its old
zone and prevents both attachment and the New Single follow-up. Successful
sets remain successful even with no tokens, while token movement immunity
leaves selected tokens in List. Drum Phalanx reuses the non-stacking Drum
rule, takes 200 effect damage on Guard, and grants Catch only to cards still
attached to it with effect-adjusted pre-FP Speed 8 or lower. Q&A 697's
List-preserved attachment is covered, and actually playing the attached card
clears its set state. Both owners, wrong timing/zone, empty candidates,
declines, numerical boundaries, Vocal doubling, and numbered-effect negation
are included.
`CB03-PS-001` (High Tension), `CB03-AT-001` (Moon Authority), and
`CB03-AT-002` (You, I Took Your Picture) add eight reviewed ability groups and
47 deterministic situations. High Tension now expires at Recovery end and
blocks only Special-judgment Dodge for the opponent during that turn; its
Guard recoil is limited to the owner whose opponent actually guarded. Moon
Authority enforces the HP 2000 boundary, exposes a real Attack choice for its
High-Tension invalidation, filters movement-immune targets, opens only the
fourth Combo slot from Hand, and breaks itself before applying the turn Catch
lock. The photographed Technique moves to the opponent's Lumen zone while
retaining its printed owner; damage to that zone's holder deals the additional
200 first and then returns the card to its original owner's List. Self-produced
effect damage cannot recurse, while unrelated effect damage still triggers.
Both owners, decline, wrong timing/zone/player, numbered-effect negation, turn
expiry, and post-return repeated damage are covered.
`CB03-AT-006` (Moonlight Arrow), `CB03-AT-007` (Nemesis), and
`CB03-AT-008` (Moonlight Armbar) add six reviewed ability groups and 43
deterministic situations. Moonlight Arrow now exposes a mandatory, real player
choice containing only movable Techniques in List; non-Technique tokens and
initially move-immune cards are excluded, while immunity gained after selection
keeps the card in List. Its optional fixed-Speed 5 Catch is distinct from the
printed Speed 7 option and applies the 400 damage reduction only when selected.
Nemesis applies its High-Tension Guard/Clash lock and +200 damage only through
Battle end, and fixes both effect-modified pre-FP reference Speeds so later
Speed changes and FP cannot alter them. Moonlight Armbar's numberless Dodge
limit uses effect-modified pre-FP Speed 6, creates no duplicate replacement,
and survives numbered-effect negation; its numbered Combo rule ends after the
card is used, leaving a jointly proposed follow-up in Hand unless that numbered
effect is negated.
`CB03-AT-019` (Blazing Rakshasa Kick), `CB03-AT-024` (Spiderling Brood),
and `CB03-AT-029` (Doppelschwerter Zwei) add seven reviewed ability groups and
57 deterministic situations. The Kick now distinguishes Dodge from unrelated
Special judgments, fixes Speed 6 through FP and prior Speed changes, and uses
the actual Ember count with Guard-loss 8 and Counter-gain 9 caps. Spiderling
Brood moves released Spider tokens from Side to the opponent's List instead of
creating substitutes, enforces the four-token limit, and heals 400 only when
the required pair cannot be placed. Its explicit special-destination override
does not weaken the ordinary rule that Special Techniques sent to Hand/List
break. Zwei requires two actual ARM-named Techniques, offers a real choice of
movable Pinp Techniques in List, and breaks itself only after the selected card
successfully reaches Hand. Automatic multi-card selectors now also refuse a
partial result when fewer than their declared minimum remain legal.
`CB03-AT-011` (Moon Step) and `CB03-AT-020` (Rakshasa Guren Wave) add three
reviewed ability groups and 26 deterministic situations. Moon Step requires an
actual `[[state:high_tension]]:` effect prefix on the immediately preceding
Technique instead of accepting a marker mentioned elsewhere, ignores Speed
only while High Tension is active, and ignores the damage penalty beginning
with 4-combo. Rakshasa Guren Wave exposes printed Speed 11 and optional fixed
Speed 4 as distinct Catch actions; only the fixed-Speed action gains one Ember
and returns the card to Hand, and Catch damage continues after that move. Its
Combo effect requires exactly three `CRS-AT-002` cards in Break and presents a
real mandatory choice of movable Rakshasa-named Techniques across List and
Break, excluding non-Techniques and movement-immune candidates.
`DFR-AT-005` (Heavenly Doubling) has two reviewed rule groups and 15
deterministic situations. Its attached Guitar effect shares the same
non-stacking CMYK-host rules and Vocal numeric doubling as Backing Guitar. Its
own Before-judgment bonus requires at least one actually attached card carrying
a Vocal marker; an unattached Vocal card and a non-Vocal set card do not count.
One or multiple attached Vocal cards add exactly 200 damage once, alternate
legacy Vocal marker text is recognized, and wrong timing or numbered-effect
negation leaves the printed 500 damage unchanged.
`DFR-AT-006` (Accent Kick) has three reviewed rule groups and 22 deterministic
situations. Its Drum attachment uses the shared non-stacking and Vocal
multiplier rules. At Combo end the optional effect first exposes the exact
breakable New Single candidates in Hand/List, records which selected token was
actually broken, and only then opens a second optional player choice containing
Battle Techniques. Declining either step, having no candidate, initial break
immunity, a break that becomes prohibited after activation, non-Technique
distractors, and numbered-effect negation are covered. If Q&A 697's Battle-long
Hand movement prohibition applies, the selected Technique remains in Battle.
The third effect changes Guard from -6 to -8 only with exactly three attached
cards; two, four, wrong timing, and numbered-effect negation do not qualify.
`DFR-AT-007` (C Dominant) has two reviewed rule groups and 13 deterministic
situations. Its unnumbered Bass attachment remains active through numbered-
effect negation while retaining the shared CMYK-host and non-stacking rules.
Hit/Counter schedules +100 damage for the owner's next Catch card only: an
opponent Catch neither receives nor consumes it, the first owner Catch consumes
it, a second Catch receives no bonus, and an unused schedule expires at turn
end. Wrong timing and negation of numbered effect ② do not create the schedule.
`DFR-AT-008` (Volume Up!!) has three reviewed rule groups and 17 deterministic
situations. Vocal doubles numeric effects from attached CMYK cards only; an
attached non-CMYK effect remains unchanged, multiple CMYK effects are each
doubled, and numbered-effect negation disables the multiplier. Three or more
attached CMYK cards block the opponent's Dodge, while two CMYK plus one other
character card do not. Its Combo rule ignores only the normal Combo damage
penalty, preserves independent damage bonuses, and is now marked as numbered
so negation restores the 100/200-point penalty correctly.
`DFR-AT-009` (Rising Tension) has two reviewed rule groups and 12
deterministic situations. Its Vocal multiplier uses the same CMYK-only,
numbered-effect behavior as Volume Up. With three or more attached CMYK cards,
Before-judgment simultaneously blocks the opponent's Guard and fixes the card
at Speed 12. The fixed speed overrides prior modifiers, later modifiers, and
FP; two CMYK cards or a non-CMYK third attachment do not satisfy the condition,
and wrong timing or numbered-effect negation leaves ordinary modifiers and FP
active.
`LMI-AT-048` (Impact Trigger) is split into use-time speed 6 fixing, its
turn-scoped Catch prohibition, opponent-Dodge +7FP, After-use Lumen movement,
and the optional once-per-game HP 2500 Lumen-to-list return. Q&A 657/658/691
prove that FP and earlier/later speed modifiers cannot change its fixed speed;
Q&A 680 emits the fixed-speed event at Use timing for Wingstar. Q&A 465 proves
that neither movement performs normal break replenishment or a side/list
exchange, while Q&A 59 treats its missing printed damage as zero and Q&A 493
resets both players' FP when the opponent declares Catch. Its Lumen immunity is
limited to another card effect moving it specifically to the list: another
destination remains legal and its own return effect bypasses the immunity.
The two mandatory After-use effects also require an owner-selected order and
both remain resolved afterward. Six reviewed rule groups contain at least
three deterministic situations each.
`ST1-PS1` (Over Limit) now restricts both After-use and Recovery payments to
actual Technique cards, so tokens and face-down non-Technique cards never
appear in the mandatory choice. Its five reviewed rule groups cover the
Rai/Lefi After-use move, the NYA Attack damage modifier, four-card state entry,
the mandatory Recovery branch, and the eight-card Lumen release in at least
three deterministic situations each. The scenarios also cover no-candidate
failure without blocking card use (Q&A 76/290), persistent state below four
(Q&A 77), face-down exclusion (Q&A 354), and Exceed removing the protected
break branch (Q&A 530).
`ST2-PS1` (Charge) now has five reviewed rule groups for Lumen-phase state
entry, Attack-only Ready restriction, Ready-card speed/damage modification,
next-owner-Lumen skipping after state loss, and trait-negation state origin.
The scenarios cover Charge/Intimidation priority exclusion (Q&A 163), no legal
Attack becoming No Response (Q&A 589), Ready restarts preserving Charge
(Q&A 404), fixed-speed interactions (Q&A 169/658), and an externally granted
Charge surviving trait negation while its trait-owned modifier stops
(Q&A 220). Every group has at least three deterministic situations.
`ST3-PS1` (Down Stance) now has reviewed rule groups for live-judgment
state entry, unmarked-Technique speed slowing, and state loss. The scenarios
distinguish High Dodge on Attack/Defense from a Defense card's Low Clash
(Q&A 145-148), use the actual judgment after Before-Judgment changes so a
Deldmil changed from upper to middle Dodge does not enter the state
(Q&A 156), apply state changes between individual Combo cards (Q&A 149), slow
cards whose text only says they are unaffected (Q&A 152), and preserve the
state for No Response or virtual no-response cards (Q&A 280). Every group has
at least three deterministic situations.
`ST4-PS1` (Advance Notice) now has five reviewed rule groups and 35
deterministic scenarios for its Calling Card deck supplement, Lumen-phase
placement, global one-card Lumen limit, derived Advance Notice state, and
Calling Card Break penalty. The deck allocator permits two Calling Cards in
the ordinary 20 cards plus three extra slots (Q&A 484), while subtracting only
the allocated extra copies from the character-card minimum (Q&A 537). The
placement is a real mandatory Side-deck choice, reveals only a successfully
moved card, and remembers the previous physical card so it cannot be chosen
on the next application (Q&A 98/282). Any Calling Card in Lumen grants the
public derived state; Trait/numbered-effect negation removes the grant without
moving the card (Q&A 383). A Calling Card broken directly or by an invalid
Special-to-List move loses 2FP and requires one legal Side Technique to be
chosen and broken (Q&A 376); breaking a normal Attack/Defense from Side does
not create List replenishment. The observation API projects the derived state
to both human and AI roles without persisting duplicate passive state.
`ST4-001` (Appearance Blade) now has two reviewed rule groups and 15
deterministic scenarios. Its Speed exception is active only at 4-combo or
later, extends the ordinary proposal depth to 4, and does not leak to a card
played after Appearance Blade (Q&A 20/102). Normal Combo now seeds its first
speed comparison from the effective Speed of the already-used 1-combo card.
The damage rule counts Hand after excluding every card in the simultaneous
Combo proposal, including a future 3-combo card when Appearance Blade is the
2-combo (Q&A 578). It removes only the ordinary Combo penalty, preserves
external damage bonuses, and both rules stop under numbered-effect negation.
`ST4-002` (Belgian Kick) now has two reviewed rule groups and 18 deterministic
scenarios. Its continuous Dodge rule uses the effect-adjusted, pre-FP Speed
and accepts only 9 or higher; Dodge wins over a simultaneous Low Clash
(Q&A 270). A successful Dodge still grants the optional Catch when Belgian
Kick is itself dodged (Q&A 103/388). The Catch offers only effective-Speed-6-
or-lower Attacks from List, ignores both players' FP when opening, clears both
FP on declaration, then applies the catching card's Hit FP and breaks that
card after its After-use timing (Q&A 398). Decline, wrong timing/zone,
numbered-effect negation, and effect-modified Catch Speed are also covered.
`ST5-PS1` (Intimidation) now has four reviewed rule groups for gaining Howling
from each actual damage instance, optional state entry and duration, both
players' Ready restrictions, and the state-loss FP reward. The scenarios cover
zero or fully absorbed damage (Q&A 174/483), Defense-card effect damage
(Q&A 175), the five-counter cap and optional activation (Q&A 178),
Charge exclusion (Q&A 163), Ready restart and No Response behavior
(Q&A 404/589), Catch remaining legal (Q&A 335), and Charm removing the trait
state without granting FP while preserving and externally changing Howling
(Q&A 139/439). Every group has at least three deterministic situations.
`UNC-PS-001` (Bagua Engine) now has eight reviewed rule groups for Yin/Yang
counter gain, state reconciliation, Yin hit FP, Yang counter damage, both
Harmony choices, trait negation, and cross-timing integration. A new
`limit.per_effect_resolution` DSL flag distinguishes separate normal/additional
damage from repeated damage commands in one effect resolution. The scenarios
cover one counter per Combo Technique (Q&A 377), additional effect damage
(Q&A 395/475), printed rather than modified Speed parity (Q&A 596), equal
counters and repeated Harmony choices (Q&A 204/206), hit/counter timing before
damage-created states (Q&A 207/210/653), Technique damage versus effect damage
(Q&A 618), and Charm counter preservation/restoration (Q&A 139). Every group
has at least three deterministic situations.
`AWL-SP-003` (Charm) now has four reviewed rule groups for exact-three-counter
deployment, mutual Trait negation, Recovery upkeep, and related-card
integration. The scenarios distinguish Trait-origin states from states granted
by Techniques (Q&A 140/220), preserve and externally change counters
(Q&A 139/225), end Trait state-loss rewards without granting them (Q&A 439),
break Charm when another effect sends the Special Technique to the List
(Q&A 376), and immediately end Third Eye's temporary hand reveal and Ready
order while retaining its activation history (Q&A 564). Every group has at
least three deterministic situations.
`LMI-AT-001` (Light Lumen) now has six reviewed rule groups for its private
Side Deck deployment, continuous damage and Saintess modifiers, all three
Legion blessings, and opponent-effect immunity. Paladin acquisition is a
mandatory one-card player choice when the List has a legal candidate, does not
open without one, and is limited to once per turn. Scenarios cover public
triggers preceding the hidden deployment (Q&A 597), per-instance damage
reduction (Q&A 221/525), Charm retaining only Light Lumen's explicitly granted
blessings (Q&A 220), non-stacking Legion effects (Q&A 413), and Special
Technique movement to Break (Q&A 72).
`LMI-PS-001` (Legion) now has six reviewed rule groups for permanent Saintess,
the three-way blessing choice, current-turn duration, next-turn selection
cooldown, all three blessing effects, and cross-card timing. The compiler now
uses counter-backed cooldown history so Charm cannot erase the previous
selection, requires the Legion owner to be the guard/counter/combo actor, and
deduplicates the same blessing supplied by Light Lumen. Scenarios cover
Saintess persistence (Q&A 412), Ready restart persistence (Q&A 404),
state-gated card effects (Q&A 458), and missing a Paladin Combo trigger when
the state is gained after that trigger was collected (Q&A 673).
`CRS-PS-002` (Third Eye) now has four reviewed rule groups and 20 deterministic
scenarios for its starting counters, optional random hand reveal, additional
counter amount, turn-end concealment, forced Ready order, and once-per-game HP
threshold. Already revealed cards are excluded from random reveal candidates
and cap the additional amount (Q&A 678); a forced player receives an immediate
10-second Ready clock and may Ready the revealed card (Q&A 228/229); simultaneous
Third Eyes retain the priority player's first-applied instruction so the
non-priority player Readies first (Q&A 602). Charm immediately ends the reveal
and Ready-order effect without consuming the later HP-threshold opportunity
(Q&A 564).
Legacy states that contain this PS card outside the Passive Zone are repaired
before either effect is evaluated, so its review also covers Break-to-Passive
recovery instead of treating an impossible wrong zone as inactive.
`AWL-AT-033` (Kissing You) now has two reviewed rule groups for its Advance
Notice play condition and mandatory two-step Calling Card selection. The two
chosen cards use one atomic `exchange_cards` command, so Advance Notice is not
lost between moves (Q&A 119), the outgoing card retains its next-announcement
restriction (Q&A 120), and the incoming card is active before Kissing You is
broken (Q&A 116). Scenarios also verify FP preservation (Q&A 118/645), battle
state preservation on Ready restart (Q&A 404), opponent use history retention
(Q&A 679), non-Grab invalidation (Q&A 675), Defense Over reset (Q&A 68), missing
candidate suppression, and explicit selection among multiple legal cards.
`PMP-AT-034` (Occam Knife) now has two reviewed rule groups and 14 deterministic
scenarios. Dark Night changes its Catch speed to a fixed 2 and the linked
-200 damage is mandatory once that Catch is chosen; without Dark Night it uses
its printed speed and damage. Its second effect first exposes every legally
breakable Dagger token, records the token actually broken, and only then offers
the optional acquisition of a Reve Technique from the List. Break-protected
tokens suppress the activation entirely, unrelated character cards never
appear, an empty Reve candidate set creates no empty choice dialog, and a
Special Technique selected for acquisition follows the core rule and goes to
Break instead of Hand. The generic `availability_selector` field is checked
both when an ability is collected and again when it resolves, so a mandatory
movement cost cannot proceed after its last legal candidate becomes protected.
Optional zero-to-one selectors also skip their dialog when no candidates exist
while continuing any following independent commands.
`PMP-AT-038` (Waterflow Cannon) now has four reviewed rule groups and 19
deterministic scenarios. Its base Dodge limit is Speed 5, Harmony extends that
limit to 10 and changes both Hit and Counter judgments to Combo, and a Dodge
opens a mandatory player choice containing only Speed-7-or-lower TAO Techniques
from Hand. Entering Combo timing caps the current turn at 3-Combo and removes
two Yin and two Yang counters. Natural Combo judgment now emits the card's
Combo trigger before judgment FP and damage are applied, while opening Combo
time clears any earlier Catch grant. The scenarios verify that spending the
counters can end Harmony before Waterflow Cannon deals damage (Q&A 636), that
its Dodge Catch cannot be used after its Combo time (Q&A 637), that Yang gained
at Combo timing is too late for the preceding Counter trigger (Q&A 638), and
that an unspecified Catch zone means Hand only (Q&A 667). The DSL's
`modify_combo.max_combo_cap` field keeps this restriction distinct from effects
that extend the normal Combo maximum.
`DFR-AT-010` (Red Line) now has two reviewed rule groups and 15 deterministic
scenarios. Its unnumbered Defense rule only permits Clash against a Technique
whose current Hit judgment is Combo, including while numbered effects are
negated. Before Judgment it records the Set cards that actually reached Hand;
only exactly three successful moves schedule its optional New Single branch.
The scheduled choice exposes every legally breakable matching token to the
player, excludes unrelated tokens, and records the token actually broken before
changing the opponent's Hit to +0, reducing its damage by 500, and granting a
four-card Combo time. Declining the choice, a move immunity, a newly protected
token, a missing token, the wrong trigger, and the opponent's Clash timing all
leave the dependent effects unapplied.
`DFR-AT-011` (Trouble Maker) now has two reviewed rule groups and 17
deterministic scenarios. At Game Start it moves itself from Side to Lumen and
creates exactly ten face-up New Single tokens for either seat. While in Lumen,
move, break, and stat-changing effects from other cards are ignored, while core
movement and effects outside Lumen remain legal. Its numbered Lumen-phase
effect opens an explicit optional choice for zero, one, or two New Single
tokens; unrelated tokens and cards that cannot currently move to Hand are not
shown. An empty candidate set creates no activation prompt, and a movement
restriction introduced after selection still prevents the actual acquisition.
The reusable selector schema now supports `as_operation: move_card` together
with `to_zone`, so future acquisition and forced-movement choices can expose
only candidates that pass effect immunity, temporary Hand restrictions, and
destination limits.
`DFR-AT-012` (Second Law of Thermodynamics) now has one reviewed rule group and
21 deterministic scenarios. The optional Ultimate activation is limited to the
Lumen phase, HP 2000 or lower, and a currently breakable source. Availability
is rechecked after acceptance; if the source becomes protected, the activation
is cancelled before its 600 damage. Successful activation records the source
actually broken, counts only Techniques—not tokens—for FP, protects Over Limit
until Battle ends, and schedules both later branches. The Ready bonus uses live
HP and only consumes on the owner's Attack Technique. Turn-end cleanup selects
only Techniques, records successful move operations, and deals 200 damage per
sent card; movement immunity reduces that count, while cards sent into a full
14-card List are broken by the core overflow rule but still count as sent.
`DFR-AT-015` (Stormslayer) now has three reviewed rule groups and 24
deterministic scenarios. HP 2500 is accepted while HP 2501 is rejected, Combo
use is always forbidden, and only frame increases from other card effects are
ignored; speed-up effects and FP still apply. On Use, the owner must choose a
currently breakable `LMI-AT-016` (Stormbringer) from Hand or List. The +500
damage and opponent Guard/Clash prevention are installed only after that exact
card is actually broken, including when normal Break replenishment temporarily
interrupts resolution. After Use, Stormslayer first breaks itself, completes
any replenishment choice, and then offers an explicit optional zero-or-one
Stormbringer recovery from Break. Missing, initially protected, and newly
protected targets cannot incorrectly unlock dependent effects or move zones.
`DFR-AT-018` (Lucky Days) now has two reviewed rule groups and 25 deterministic
scenarios. Its once-per-game Lumen activation checks live HP at the 2000
boundary, requires enough currently movable Calling Cards to fill Lumen to
exactly three, and asks the owner to select those physical tokens. With five or
more cards in Hand it next asks for the exact number of currently discardable
cards needed to reach four; insufficient legal discard candidates abort before
the tokens move. Successful token movement is recorded before the dependent
discard, so protection introduced after either choice cannot silently unlock or
complete the other operation. While the numbered Ultimate effect is active, a
live player-scoped zone limit rejects only a fourth Calling Card. It does not
affect unrelated tokens or the opponent, disappears immediately when the
Ultimate leaves its zone or is negated, and handles exchanges by allowing a
Calling-Card-for-Calling-Card replacement while rejecting a net fourth card.
`DFR-AT-019` (Night of Execution) now has two reviewed rule groups and 14
deterministic scenarios. Its optional Lumen activation requires the opposing
HP to be at most 2500, a currently breakable Ultimate source, and either the
Intimidation state or five Howling counters. Intimidation preserves Howling;
otherwise exactly five counters are spent after the source is successfully
broken. The resulting turn-duration schedule listens only to positive damage
dealt by its owner to the opponent. A hit that leaves more than 500 HP, damage
from the opponent, and self-damage do not consume the schedule; a later owner
hit at the exact 500 boundary declares the card-effect victory. Turn expiry,
decline, numbered-effect negation, wrong phase/zone, and break protection leave
no special victory behind. The shared DSL now supports conditional scheduled
event matching and a deterministic `win_game` domain command.
`DFR-AT-020` (Endless Ballare) now has three reviewed rule groups and 18
deterministic scenarios. HP 3000 is accepted while 3001 blocks every use
context, and its numberless Combo rule keeps the printed 100 damage legal at
both the second- and third-Combo penalties. On Use it schedules one Recovery-
end batch Break for every exact-name copy then in Hand, List, or Side; the batch
prevalidates and moves all targets before offering normal Break replenishments,
so those choices never contain a stale copy that the same effect already
broke. Protected copies and similarly prefixed names remain in place. At Combo
end, the owner explicitly selects zero to three legal Hand destinations from
List/Battle, then the opponent independently selects zero or one from their
List. Special Techniques and move-immune cards are not offered, a restriction
introduced after selection is rechecked by the real move, and Ready restarts
after both choices even when both decline. The shared `break_cards` command now
accepts selectors/selection keys for atomic multi-card effects, and move-choice
projection excludes Special Techniques whose requested destination would
immediately Break them.
`DFR-AT-023` (Yin-Yang Awakening) now has seven reviewed rule groups and 52
deterministic scenarios. Its numberless immunity applies in every zone against
opposing Technique effects while allowing its own effects and core movement.
At the Lumen phase start, Harmony moves the Ultimate source to Lumen, grants
the same-turn Harmony FP exactly once, and offers an explicit zero-or-one
choice of `UNC-AT-010` from Hand or List; initially or newly move-immune cards
cannot be selected or moved. While the numbered Lumen effect remains active,
both Bagua Harmony benefits apply together: Tao Technique damage +100 and one
FP per turn at the Lumen phase. An actual Ready Technique with a Combo judgment
deals 700 effect damage after use and suppresses that specific not-yet-opened
Combo Time, without affecting later battles, opposing Combos, or 2+ Combo
cards. Recovery opens a mandatory choice between each currently present Yin
or Yang counter, and losing Harmony breaks the source. Wrong phases and zones,
numbered-effect negation, both player roles, absent candidates, choice decline,
and post-choice immunity changes are covered. The shared battle event context
now exposes the Ready use context and actual one-Combo judgment, and `end_combo`
can target the event card before the Combo object exists.
`DFR-AT-026` (Sacred Circle) now has two reviewed rule groups and 19
deterministic scenarios. On Hit, every card in Hand is publicly revealed, two
FP is gained for each Technique whose text contains Paladin or Saintess up to
eight FP, and only cards which were originally hidden are hidden again; an
already-public card stays public. Q&A 643 narrows the Paladin After Use grant
to Combo only: after Sacred Circle is the 2-Combo, one matching Attack in List
can be used as the 3-Combo. It never creates a Catch permission, ignores
unrelated and Defense cards, consumes one source-scoped usage shared by every
duplicate grant, and expires with the turn. The shared `grant_flexible_use`
command now accepts an explicit `contexts` subset while preserving the former
Combo-and-Catch default for other cards.
`DFR-AT-027` (Child of Starlight) now has three reviewed rule groups and 30
deterministic scenarios. Its optional once-per-turn effect reacts only to its
owner's Counter, Clash, Catch, or Combo and exposes only Side-deck Techniques
whose text contains Saintess; declining does not spend the use, while a
successful choice sets the card face-up on the Ultimate source. At 2500 HP or
less, the Lumen phase offers every currently movable `LMI-AT-001` in Side and
moves the selected physical card to Lumen, with both initial and post-choice
movement immunity checked. At turn end, a present `LMI-AT-001` makes the owner
choose one Set card to send to List; the core Special-Technique destination
rule still redirects a selected Special card to Break. If no Set card exists,
the owner chooses one of any multiple `LMI-AT-001` instances and the engine
prevalidates then breaks it together with the Ultimate source as one batch.
Wrong owners, phases, zones, events, empty candidates, numbered-effect
negation, late move protection, and late Break protection are covered.
`DFR-AT-030` (Incessant Inferno) now has two reviewed rule groups and 14
deterministic scenarios. The numberless HP gate accepts exactly 2500 and blocks
2501. During the Lumen phase, while the source remains in Ultimate, the
optional numbered effect is offered only with at least four Ember counters and
at least one currently movable Rin Technique in Break. Accepting removes
exactly four counters, then makes the player choose the physical Rin card to
send to List; declining preserves both counters and cards. Other-character
cards, Special Techniques whose List destination would immediately redirect
to Break, Passive cards, and initially move-immune cards are never offered.
Movement immunity introduced after selection is rechecked by the actual move,
so the cost remains paid but the protected card stays in Break.
`DFR-AT-031` (Order: Minotaur) now has one reviewed rule group and 15
deterministic scenarios. In Disaster One, Use first exposes the opponent's
hidden Hand only as anonymous choices, then lets the controller declare odd or
even before recording the selected card's code, name, type, and printed Speed
in a public inspection event. A correct declaration changes both Hit and
Counter to Combo and adds 200 battle damage. A wrong declaration randomly
selects exactly one currently discardable own Hand card with a private,
seed-recorded outcome, then schedules an opponent-controlled choice of the
Technique the owner must Get from List. Initially discard-immune cards are not
random candidates, an empty own Hand does not prevent the Get penalty, and
Special Techniques are not legal designated Get choices. The designation is
stored with its originating turn, removed after a successful or candidate-less
Get, and expires at turn end if that Get was skipped, so it cannot leak into a
later turn.
`DFR-AT-032` (Lady Cassandra) now has three reviewed rule groups and 17
deterministic scenarios. Its printed two-copy deck limit and one- or two-copy
Game Start movement from Side to Lumen are pinned independently. On the
owner's Yohann Technique Use, the owner may resolve Cassandra first, Break the
physical Lumen source, and replace that Technique's odd/even hand-guess
categories with Attack/Defense for the current Battle. The replacement is
installed only after a successful Break, matches the exact event Technique,
works for both player roles, treats Attack/Defense independently of printed
Speed parity, and expires at Battle end. Declining, Break protection,
non-Yohann or opposing Yohann uses, a source outside Lumen, numbered-effect
negation, and wrong timing all preserve the original odd/even choices. The
shared DSL now includes `modify_hand_guess_categories`, and `guess_hand_parity`
accepts the generic `attack` category.
`DFR-AT-033` (N.A.B.I) now has three reviewed rule groups and 20 deterministic
scenarios. Its Ready eligibility accepts 2000 HP and rejects 2001. In Disaster
One, Hit or Counter selects only a face-down opposing Hand card and declares
odd-Speed Attack, even-Speed Attack, or Defense. Correct guesses deal 400 to
the opponent and wrong guesses deal 200 to the controller. Each inspected card
is revealed, a real repeat decision is offered after every attempt, and the
sequence is capped at five; declining stops immediately. Every revealed card
is hidden at this Technique's After Use, when the source also Breaks. Both
player roles, all three categories, a five-card maximum sequence, no state,
wrong timing, no hidden candidate, numbered-effect negation, and Break
protection are covered.
`DFR-AT-34` (Punishment Thorn; the production card code intentionally lacks
the second zero) now has two reviewed rule groups and 12 deterministic
scenarios. At Before Judgment an FP lead of exactly five is sufficient to
prevent only the current opponent Battle card from dodging this source, and
the prevention expires with the Battle. On Hit or Counter, either an Attack's
Special dodge judgment or a Defense card's positional dodge judgment adds 100
Battle damage. A four-FP lead, unrelated cards, wrong timing, absent dodge
judgments, numbered-effect negation, and Battle expiration are covered.
`DFR-AT-035` (Impaler Venom) now has two reviewed rule groups and 17
deterministic scenarios. At Battle end from Ultimate, an FP lead and at least
300 HP offer the optional payment. Accepting pays 300 HP, then makes the owner
select the opponent's physical Attack in Battle and moves it to that
opponent's List. The selected card cannot move to Hand before turn end and is
released afterward. Initially immovable cards are omitted; movement immunity
introduced after selection leaves the paid cost in place but prevents the
move. Decline, equal FP, insufficient HP, wrong zone/event, Defense targets,
numbered-effect negation, the Recovery 3000 HP Break boundary, and Break
protection are covered.
`DFR-AT-036` (Blue Lotus) now has one reviewed rule group and nine
deterministic scenarios. Catch gains 300 damage only when the same owner used
a Defense Technique to Guard or Dodge an opposing Attack during the previous
turn. Same-turn history, opposing ownership, a non-Attack opponent, and other
results do not qualify. A successful Catch tries to return its source to Hand
and continues to deal the resulting 500 damage; movement protection can keep
the source in Battle without interrupting that damage pipeline.
`DFR-AT-043` (Assembly Add) now has three reviewed rule groups and 20
deterministic scenarios. Its three-copy deck limit is independent from its
mandatory Game Start movement, which moves every physical Side-deck copy to
Lumen. At Recovery the owner may Break one live Lumen copy. Only a successful
Break continues: the owner independently chooses zero or one Parts token from
Lumen to Side and zero or one from Side to Lumen, then loses 3 FP. Both choices
use real pending decisions, initially protected candidates are omitted, and a
new movement restriction after selection is rechecked by the actual command.
All copies share the printed once-per-turn-by-name limit, while declining the
source Break consumes neither the limit nor FP.
`DFR-AT-044` (LEG: Hover Booster) now has two reviewed rule groups and 23
deterministic scenarios. Its root and live continuous limits jointly prevent a
second exact-name-fragment `LEG` Technique in the same owner's Lumen Zone while
leaving ordinary Techniques and the opponent's Lumen Zone independent. At the
Lumen phase, activation is offered only when a currently discardable Defense
Technique exists in Hand. The owner selects the physical Defense card; only a
successful discard schedules both the current-turn modifier and the next-turn
cooldown. The next normal Ready Attack's Use appends `9속도 이하 하단 회피`
to any existing Special judgment. Defense, Combo, Catch, and opposing uses do
not consume the schedule, while turn expiry removes it. The next turn is
blocked and the following turn is available again. Scheduled effects now have
an explicit `preserve_source` option, so immunity and audit events attribute
the delayed judgment change to Hover Booster rather than incorrectly treating
it as the target Attack's own effect.
`DFR-AT-045` (L ARM: Protector Shield) now has two reviewed rule groups and 20
deterministic scenarios. Its root and live continuous limits enforce one
`L ARM` Technique in each owner's Lumen Zone without restricting unrelated
cards or the opponent. At the Lumen phase the owner selects one currently
discardable physical Hand card. The 200 turn-duration Shield and next-turn
cooldown are created only after that card is actually discarded; an initially
or newly protected choice cannot unlock either dependent effect. The scenarios
verify partial absorption, damage exceeding the Shield, stacking with an
existing Shield, turn expiration, same-turn reactivation prevention, and the
one-turn cooldown followed by normal availability. The generic Shield compiler
test now uses a neutral draft code so it remains independent from this exact
card override.
The previously approved `DFR-AT-041` (Linear Buster) definition has been
corrected without writing to the production database. It now asks for the
Hand, List, and Battle choices before breaking any card, records a separate
result key for each actual Break, and derives its damage bonus from those
successful results rather than the requested selections. The Break selector
also predicts movement immunity to the Break Zone, matching the command that
eventually executes. Eight deterministic scenarios cover both owners, all
three, two, and zero successful Break outcomes, initial and late protection,
decline, numbered-effect negation, non-Technique/name exclusions, and a wrong
event.
The previously approved `DFR-AT-042` (Grind Press) definition now requires the
owner's Lumen `LEG`-named card to be an actual Technique. Its mandatory target
decision exposes only opposing Battle/Lumen Techniques that can really enter
List, so Traits, Special Techniques, initially protected cards, and cards
blocked by destination rules are omitted. The move command still rechecks
state after selection; newly gained immunity leaves the selected card in its
original zone. Ten deterministic scenarios cover both owners, Hit/Counter,
missing and non-Technique LEG conditions, no target, initial and late
protection, Special Techniques, numbered-effect negation, and a wrong event.
`DFR-AT-047` (Full Blocking) now has four reviewed rule groups and 20
deterministic scenarios. The root game-scope limit blocks a second copy for the
same owner while leaving the opponent and unrelated cards independent. On Use,
the owner chooses an actually movable Defense Technique from Hand, reveals it,
moves it face-down to Lumen, and only a successful move blocks Grab negation
for the turn. Initially protected and non-Technique cards are omitted; immunity
introduced after choice leaves the card hidden in Hand and prevents the
dependent restriction. After Judgment, only an opposing Defense gains 4 FP.
After Use, the source Break and the owner's turn Catch restriction are
independent, so Break prevention does not remove the Catch restriction. Every
turn restriction is also tested for expiry.
`DFR-AT-048` (Swift Flip) now has three reviewed rule groups and 17
deterministic scenarios. A Defense rule can carry a mandatory card cost that
is offered after all Before Judgment effects and before FP is applied. Swift
Flip therefore exposes only Hand Techniques whose Speed is at least the
opponent's effect-modified reference Speed, lets the player choose the actual
discard, and dodges only after that discard succeeds. The cost is not charged
for a middle attack, an attack above the printed 10-Speed boundary, Grab, or an
otherwise prohibited dodge. Its Dodge effect gains opponent reference Speed
minus 1 FP, and its optional After Use effect grants three-card Combo reach for
the turn. The scenarios cover both owners, exact boundaries, unavailable and
non-Technique costs, FP exclusion, numbered-effect negation, decline, wrong
timings, and turn expiration.
`DFR-AT-049` (Offense Break) now has one reviewed rule group and seven
deterministic scenarios. On Guard, an opposing reference Speed of 7 or less
blocks only the controller's Catch for the rest of the turn, while Speed 8 or
more deals exactly 300 effect damage to the controller. The scenarios cover
both owners, the 7/8 boundary, low and high values, numbered-effect negation,
a wrong timing, opponent isolation, and expiration of the turn restriction.
`DFR-AT-040` (Spin Drill) now has one reviewed rule group and seven
deterministic scenarios. Its previous draft incorrectly required two ARM-named
cards before the effect could run and still dealt only two packets. It now
always deals two separate 100-damage packets on Hit/Counter/Combo and replaces
that count with three only when the owner's Lumen Zone contains at least two
actual ARM-named Techniques. ARM-named tokens do not satisfy the count. Both
owners, all three timings, the 0/1/2/3-card boundary, numbered-effect negation,
and a wrong timing are covered.
`ST3-001` (Short Clutch) now has one reviewed rule group and seven deterministic
scenarios. Its Down Stance function applies only while that copy is in Battle:
Speed 5 becomes 4 and Counter 3 becomes Combo. The Hand keeps the printed
values as required by Q&A 651, while Combo use keeps Speed 4 as confirmed by
Q&A 314. Both owners, inactive and lost state, Hand isolation, Combo use, and
numbered-effect negation are covered.
`ST3-002` (Straight Kick) now has four reviewed rule groups and 21 deterministic
scenarios. Its numberless rule prohibits only this card from Catch; Down Stance
and a live numbered effect allow the Catch and schedule this card's Break after
its After Use window. Q&A 278 is implemented independently: the +200 damage is
continuous in Battle for Ready, Combo, and Catch rather than being limited to
Catch. Opponent Dodge grants exactly 3 FP. The engine now projects a candidate's
Battle-only source modifiers while enumerating Combo/Catch, then applies source
judgment changes to the actual Combo/Catch pipeline card instead of the earlier
Ready card. Full Combo resolves for 700 after its 100 penalty, and full Catch
resolves for 800 before the card is broken.
`ST3-003` (Down Toss) now has two reviewed rule groups and 13 deterministic
scenarios. The numberless function blocks an opponent's special Dodge only
while Down Toss is in Battle, while numbered-effect negation does not remove
that function. Its own upper Dodge is limited to opposing reference Speed 7 or
less; effect Speed changes count, FP does not, and negating the numbered effect
removes the limit. Q&A 148 is tied to the printed upper-Dodge special judgment.
Both owners, Speed 1/7/8 boundaries, wrong position, Hand isolation, special
Dodge blocking, actual battle results, and mutation rejection are covered.
`ST3-004` (Rock Armbar) now has three reviewed rule groups and 24 deterministic
scenarios. Its numberless Guard/Clash prohibition is active only while the card
is in Battle. Its numbered Combo rule rejects 2- and 3-Combo use, extends the
normal limit so the card can be used from 4-Combo onward, applies the ordinary
300-point penalty at 4-Combo for 400 damage, and ends Combo after this card even
when another card was submitted behind it. An independent extension can reach
5-Combo. Down Stance blocks Ready, Combo, and Catch use, while numbered-effect
negation removes both numbered restrictions. Q&A 551 is exercised through the
actual decision path: the down-stanced card still appears as a Hand Grab that
can be broken for Grab negation because this is not card use. List Grabs are no
longer exposed as core Grab-negation candidates. Q&A 422 also proves the card's
printed Down Stance marker matches follow-up filters such as Sky Smashing.
`ST3-005` (Power Low Kick) now has three reviewed rule groups and 21
deterministic scenarios. Counter changes this card's Battle damage from 400 to
700 only for that Battle and numbered-effect negation suppresses the bonus.
Combo use ignores the normal 100/200/300 damage penalties at 2/3/4-Combo, while
negating numbered effects restores the appropriate penalty. Q&A 582 is checked
through a full Combo after the preceding Technique counters: Power Low Kick
still deals 400 rather than incorrectly inheriting its own Counter +300. In
Down Stance the player may choose either Speed 8 or the printed Speed 9, but
Speed 8 must still be at least one faster than the preceding Combo card. Both
owners, inactive state, negation, actual damage, Battle expiry, and mutation
rejection are covered.
`ST3-006` (Revenge Upper) now has two reviewed rule groups and 17 deterministic
scenarios. Before Judgment, an opposing Defense Technique mandatorily changes
this card's Battle position from upper to middle as required by Q&A 462; an
actual middle Dodge therefore changes the resulting judgment. In Down Stance,
Catch offers both the printed Speed 10 and an optional fixed Speed 8. The
mandatory 200 damage penalty is bound to the selected Speed-8 variant rather
than the state itself, so printed Speed 10 still deals 600 while Speed 8 deals
400. Losing Down Stance after declaring the legal Speed-8 Catch does not remove
that consequent penalty. Both owners, wrong timing/type/zone, Speed-9 Catch
windows, numbered-effect negation, actual damage, and mutation rejection are
covered.
`ST3-007` (Deldmil) now has two reviewed rule groups and 21 deterministic
scenarios. Its numberless Dodge restriction uses the opponent's
effect-modified reference Speed and permits Speed 8 or less; FP never changes
that boundary. Before Judgment, only an opposing Attack at reference Speed 6
or less mandatorily replaces the printed upper Dodge with middle Dodge. Q&A
291 is exercised through actual battles: an upper Speed-5/6 Attack is no longer
dodged and counters Deldmil, while a middle Attack is dodged. Q&A 156 is also
integrated with the corrected Down Stance trait: the replaced middle Dodge
does not enter Down Stance, while an unchanged upper Dodge does. Both owners,
Defense exclusion, wrong timing/zone, effect Speed changes, FP exclusion,
numbered-effect negation, and mutation rejection are covered.
`ST3-008` (Raging Punch) now has two reviewed rule groups and 19 deterministic
scenarios. On Clash with an opposing Hand-judgment Technique, the owner makes
a real mandatory choice among currently breakable Hand cards; protected cards
are omitted, a normal Technique Break can open the ordinary replenishment
decision, and an empty or wholly protected Hand does not invalidate the Clash
(Q&A 288/583). When Raging Punch is the 1-Combo, it installs a one-use optional
penalty waiver without opening an early accept/decline decision. The waiver can
be assigned to any one later submitted Combo card, including a later card in a
joint special-Combo proposal as required by Q&A 650. Get is skipped only when
the waiver is actually consumed; declining it keeps all normal penalties and
does not skip Get. Source-scoped limited usage and Combo-duration expiration,
both owners, numbered-effect negation, wrong events/zones, protected choices,
normal versus special Combo numbering, and mutation rejection are covered.
`ST3-009` (Sky Smashing) now has two reviewed rule groups and 21 deterministic
scenarios. Its numberless lower-Dodge restriction uses the opponent's
effect-modified reference Speed and permits only Speed 9 or higher; positive
and negative FP do not move that boundary, and numbered-effect negation leaves
the function intact. Its Combo effect grants an immediate-next-card Speed
exception only to a Technique with a real effect line prefixed by
`[[state:down_stance]]:`. A mere state mention does not qualify (Q&A 152), and
the owner need not currently be in Down Stance (Q&A 158). Ready-source,
ordinary joint 2/3-Combo, and special 1/2-Combo proposals are supported. After
the exempt card, normal ascending Speed applies again (Q&A 20). Rock Armbar is
recognized as a Down Stance-effect card but still must satisfy its own use
condition and 4-Combo rule (Q&A 422). Both owners, Speed/FP boundaries,
inactive zones, numbered-effect negation, proposal preview, Combo expiration,
actual damage, and mutation rejection are covered.
`ST3-010` (Paki Defense) now has two reviewed rule groups and 25 deterministic
scenarios. Its Clash effect reads the opposing Attack's live Hit and Counter
judgments after earlier effects: either judgment containing Combo suppresses
the effect, while a Combo judgment removed before Clash permits it (Q&A
236/255/389/469). A successful trigger reduces damage by 500, replaces any
earlier Hit value with -5, and prevents the owner from Catching until turn end
(Q&A 195). Both numbered effects are active from Battle or List, covering the
List-source ruling and Catch-created Combo path (Q&A 542/592). During each
opposing Combo, the opponent may waive the ordinary damage penalty for at most
one submitted card, including a later 4-Combo card (Q&A 334/650). The waiver
does not suppress a card's own -400 effect, so the review Rocket deals 800 as
required by Q&A 524. The permission now expires at Combo end and is recreated
for a later Combo instead of being incorrectly limited to once per Battle.
Both owners, live judgment gain/loss, wrong timing/type/zone/controller,
numbered-effect negation, turn/Combo expiration, decline, one/two/three-card
proposals, actual damage, and mutation rejection are covered.
All printed card codes containing `PS` are now authoritative Trait identifiers.
Manual and automatic setup create one public copy in the owner's Passive Zone
regardless of a stale database `type` value or an accidental deck entry.
Existing documents repair PS cards found in Hand, List, Battle, Side, Lumen,
Ultimate, or Break; normal movement, Break, exchange, Ready, Combo, and Catch
cannot remove or use them. Imported PS cards also enter Passive rather than
Lumen. Their definitions remain active there through the normal Trait-negation
rules.
`DFR-PS-001` (Jam Day) now has three reviewed rule groups and 27 deterministic
scenarios. The optional Lumen effect selects up to three CMYK Techniques from
Hand, records only successful moves, keeps them face-down in Battle, and sets
them on the owner's Ready Technique in stable order. Set cards follow a moved
host until Battle cleanup and then return to Hand (Q&A 696). A current effective
Speed of at least 8 with three Set cards changes Hit and Counter to Combo and
permits only those Set cards from Battle or List. Opponent Dodge, Guard, Hit,
or Counter moves every Set card to List while preserving Set identity and
blocks movement to Hand until Battle ends; separate Combo/Catch use clears the
identity as required by Q&A 697.

`LMI-AT-011` (Protocol: Exceed) now has five reviewed rule groups and 39
deterministic scenarios. Its numberless immunity applies in every zone and
blocks only other Technique effects, while its own placement effect and core
rule movement still work. The first Over Limit state schedules one optional
Side-to-Lumen placement at Battle end. While it remains in Lumen, the numbered
effect raises the release threshold to 11, prevents only its controller from
breaking their own Nya Techniques in Lumen, and permits one Nya Technique from
Lumen in each Combo before breaking that used card. Q&A 88's source-excluded
Lumen count is checked at five/six other Techniques. Its optional Get happens
after normal Gets, is suppressed when that player's Get is skipped, offers
only currently movable normal Nya Techniques, and rechecks movement immunity
after the choice. Losing Over Limit deals 500 effect damage; numbered-effect
negation disables the Lumen rules, Get, and damage without disabling the
numberless immunity.

`LMI-AT-012` (Rai! Lefi! Rush!) now has four reviewed rule groups and 38
deterministic scenarios. Its numberless rule prevents owner, opponent, and
direct Break attempts while the card is in Lumen and remains active when
numbered effects are negated. On use, the owner may make a real one-card choice
from Hand or List; unavailable candidates are omitted and movement protection
is checked again after selection. Normal and Special Techniques may move to
Lumen. While Over Limit is active, its live damage is 300 plus 100 for each
complete group of three Techniques in Lumen. Before Judgment it gains 2 FP for
each complete group of three regardless of Over Limit; Q&A 235 verifies that
the gained FP applies in the following speed step. Q&A 431 verifies that the
card's own use-time move can cross the three-card boundary, while a Passive
move at After Use occurs too late for that Judgment.

`LMI-AT-019` (Club Kick) now has two reviewed rule groups and 21 deterministic
scenarios. In Down Stance, Before Judgment gains 1 FP only against an upper
Attack, and the gained FP participates in the immediately following speed
step. If its owner used a middle Attack earlier in the current turn, Catch
offers both the printed Speed 7 and an optional fixed Speed 3. A middle
Defense, the opponent's use, an upper Attack, or a prior-turn use does not
unlock that variant. Selecting Speed 3 mandatorily applies damage -200 for 200
Catch damage, while printed Speed 7 keeps 400. The consequence remains bound
to the selected Catch rule even if use history changes after declaration;
numbered-effect negation removes both numbered effects.

`LMI-AT-020` (Street Rule) now has three reviewed rule groups and 23
deterministic scenarios. Its continuous Clash restriction uses effect-modified
Speed and Damage before FP and accepts only Speed 8 or lower and Damage 500 or
lower. On Clash, effect ① changes the opposing Attack's Hit judgment to -5
without reducing its Clash damage (Q&A 540). The effect still completes when
the judgment was already -5, so Down Stance can grant the effect Catch as well
as leaving an independent FP Catch available (Q&A 416). The granted Catch
selects an actual Speed-7-or-lower Delphi Hand Technique and replaces all of
that card's original abilities for the one Catch: Use changes Hit to +0, Hit
deals five separate 100-damage instances, and After Use Breaks the card. A
normal Attack/Defense Break then opens the existing player-controlled Side-to-
List replenishment choice. The shared Catch grant DSL now carries a validated
temporary `effect_replacement` without mutating the live card permanently.

`LMI-AT-023` (Steel Swing) now has two reviewed rule groups and 22
deterministic scenarios. Advance Notice Combo may be offered with Steel Swing
alone when the opponent has a legal printed-Speed-10-or-lower List Technique;
accepting the effect then requires exactly one such follow-up, while a joint
proposal remains legal. The borrowed card is evaluated against the Kiss
player's state, keeps numberless functions, has numbered effects and numbered
Combo rules negated, cannot grant another numbered follow-up, and returns to
the opponent's List at Combo end (Q&A 20/423/643). A numberless prohibition
still excludes the candidate, and ordinary ascending-Speed legality resumes
after the borrowed card. If the owner has at most two cards in Hand, effect ②
opens a real mandatory choice among already completed Kiss Combo predecessors,
excluding Steel Swing and jointly proposed future cards; it rechecks movement
legality before acquiring the selected card and rejects Special Techniques
(Q&A 421). Source-only accept/decline, joint proposals, both owners, Combo
positions 2–4, effect/function negation boundaries, Speed boundaries, protected
targets, and actual return/acquisition movement are covered.

`LMI-AT-024` (West Wind Zephyr) now has three reviewed rule groups and 30
deterministic scenarios. A controller's effect-modified, pre-FP Speed-8 Kiss
Technique Hit opens a mandatory real Hand discard choice. Only a successful
discard changes that live Technique's Hit judgment to Combo and schedules
Zephyr to return from Lumen to Side after the resulting Combo Time. Initially
unmovable discards are omitted and a target protected after selection aborts
both later steps. Clash now exposes each attacking Technique's Hit window
before the Clash window, so Zephyr changes the judgment before Paki Defense
rechecks it even when Paki's owner has priority (Q&A 236/432/469). Recovery
effect ② compares Hand count to the live HP-tier limit including Lumen bonuses,
not a hard-coded five. Effect ③ Breaks Zephyr after the opponent's Combo Time.
Mutual Combo now resolves both owners' Combo-end effects before either
opponent-Combo-end window, so a paid Zephyr returns to Side instead of being
prematurely Broken; without the paid residual it is Broken normally (Q&A 433).

`LMI-AT-004` (Blade of Sanctus) now has two reviewed rule groups and 19
deterministic scenarios. Effect ① is no longer treated as a candidate-card
rule on Blade itself: only when Blade is the actual 1-Combo does it grant the
card used at 3-Combo a normal damage-penalty waiver. A jointly presented
2/3-Combo therefore deals 500 then 600 with the review fixtures, while Blade
used at 2-Combo and numbered-effect negation retain the ordinary penalties.
Effect ② is optional, requires the live Paladin state, and offers only Hand
Techniques whose text carries the Saintess effect marker. A successful real
discard changes Blade's live Hit judgment to Combo and creates a turn-scoped
Get prohibition for exactly the card that reached List. Other List cards stay
legal, a movement failure aborts both follow-ups, and turn expiry restores the
discarded card. Clash scenarios confirm that declining leaves the printed Hit
and creates no late Combo window, while accepting creates the live Combo
window before later Clash effects (Q&A 237/242). The reusable `prevent`
command can now bind its card filter to a successful prior `selection_key`.

`LMI-AT-005` (Heretic Execution) now has four reviewed rule groups and 24
deterministic scenarios. Its numberless Assassin use requirement is enforced
for Ready and Combo while its opponent-Dodge prohibition remains active in
Battle even when numbered effects are negated (Q&A 588). With Assassin, the
live Damage bonus applies at the exact opponent-HP boundary of 1500 and is
removed above that boundary, outside Battle, or by numbered-effect negation.
The optional any-Speed Combo path now opens a mandatory server-side choice for
exactly three discardable Hand cards. The source and every card in a jointly
presented Combo proposal are excluded, initially protected cards are omitted,
and protection introduced after selection cancels the entire cost without a
partial discard or free Speed exception. The damage-penalty waiver is an
independent per-use choice: accepting it removes the normal Combo penalty and
Breaks Heretic Execution only after its damage and After-use processing;
declining it keeps both the penalty and the card. The shared Combo DSL now
validates `optional_speed_cost`, selectors support
`exclude_combo_proposed`, and `break_on_optional_ignore_damage_penalty` binds
the post-use Break to the actual waiver choice.

`LMI-AT-006` (Starlight) now has three reviewed rule groups and 24 deterministic
scenarios. On Hit while Saintess is active, its owner makes a real mandatory
choice among Lita Techniques in List and acquires the selected card. The
Q&A 438 ordering is enforced by deferring an over-limit Hand adjustment until
all Battle cards have returned, so the returning Starlight participates in the
final Hand-size choice. Before Judgment, the owner may decline or select an
actual Saintess-marked Hand Technique to discard; 3 FP is granted only after
that move succeeds. Catch skips this Before-Judgment effect but still runs the
Hit acquisition (Q&A 473). In Combo, an own `LMI-AT-001` in Lumen adds 200 to
Starlight's live damage after the normal Combo penalty; an opponent's copy does
not qualify. Initial and late movement protection, numbered-effect negation,
both owners, actual Catch flow, source references, and schema mutations are
covered.

`LMI-AT-007` (Unwavering Loyalty) now has two reviewed rule groups and 21
deterministic scenarios. While Guardian is active, Clash offers a mandatory
real choice among List Techniques whose text carries the Saintess marker;
marker-bearing Passive cards and ordinary Techniques are excluded. The
acquired card moves to Hand, with initial and late movement protection checked,
and Q&A 438 Hand-size adjustment remains deferred until both Battle cards have
returned. Its second Clash effect may discard an actual Guardian-marked Hand
Technique to List (Q&A 242), and adds 300 to the source Technique's live damage
only after that move succeeds. Against a 400-damage attack, declining or a
blocked move leaves the Clash difference at 100, while a successful payment
raises it to 400. When both numbered effects trigger together, the player can
resolve either one first. Choice continuations now preserve the current
ability's remaining commands across nested card-move events, preventing the
damage command from being stranded behind its sibling effect. Both effect
orders, both owners, wrong timing/zone, negation, candidate filtering, source
metadata, and schema mutations are covered.

`LMI-AT-008` (For the Promised Victory) now has two reviewed rule groups and 25
deterministic scenarios. Before Judgment, a Paladin owner may first select and
discard an actual Guardian-marked Hand Technique to List (Q&A 242), gaining
damage +200 and a turn-scoped Get prohibition for that exact card. Only after
that payment succeeds may the owner additionally discard one Assassin-marked
Hand Technique; success prevents the opponent from dodging, grants 2 FP, and
locks that exact card out of Get for the turn (Q&A 442). Initial and late move
protection, decline paths, turn expiry, FP-adjusted speed, both owners, and
plain/Passive marker filtering are covered. Its optional Paladin Combo effect
permits exactly the immediate next Saintess-marked Technique from List and
reopens the Combo window when a legal follow-up exists, but does not ignore the
normal speed requirement: after this card is used mid-Combo, speed 13 is legal
and speed 12 is not (Q&A 536). Definition, source-value, condition, selector,
operation, result-gate, timing, and permission mutations are rejected.

`LMI-AT-009` (Steel Faith) now has three reviewed rule groups and 26
deterministic scenarios. Guardian Before Judgment appends an 8-or-higher Speed
Middle Clash without replacing the printed Lower Clash. The granted judgment
uses effect-modified reference Speed but ignores FP: Speed 8 remains legal with
5 FP, Speed 7 fails, and a +1 Speed effect moves printed 7 onto the boundary.
In Clash, Guardian changes the opposing Technique's exact Combo Hit judgment to
+4, while the independent second effect changes numeric +6 or higher to +4.
The scenarios distinguish Combo, +5, +6, +12, and -6, then verify that the
changed judgment supplies the actual +4 judgment FP. Both owners, wrong timing
and zone, numbered-effect negation, state absence, printed-judgment preservation,
definition mutations, and every published base value are covered.

`LMI-AT-010` pays its mandatory two-card discard only after both Ready cards are
revealed (Q&A 222/526), using a real player choice among eligible Guardian,
Assassin, or Paladin Techniques. An unpaid or newly protected cost invalidates
the Technique without firing its Use effect; a successful payment precedes the
Get skip and later Grab invalidation (Q&A 588/645). Its Saintess Guard effect
rechecks Saintess state and `LMI-AT-001` in Lumen, offers only effect-modified
Speed 10 or lower Saintess Techniques from List, adds 200 Catch damage, and
returns the original Ready Technique to hand. Three ability groups cover 28
deterministic scenarios, including both owners, boundaries, failed payment,
numbered negation, Ready restart, repeated Get skip, and Battle-end cleanup.

`UNC-AT-001` (Buung Fist), `UNC-AT-002` (Falling Dragon Kick), `UNC-AT-004`
(Bodyguard Palm), and `UNC-AT-005` (Immortal Dragon Kick) now cover 11 ability
groups with 70 deterministic scenarios. The review checks Yin/Yang removal and
the Bagua four-counter cap, Harmony branches and effect order, damage and
Attack-position gates, effect-modified judgment Speed without FP, continuous
fixed Speed precedence and its explicit Combo override, real optional-cost
accept/decline decisions, Q&A 558's fully-resolved "then" gate, and Q&A 555's
opposing special-Dodge prevention. Numbered-effect negation, source zones,
zero/boundary counters, Combo-not-Hit, and definition mutations are included.

`UNC-AT-007/008/009/010/021/022/023` add 20 reviewed ability groups and 145
deterministic scenarios. Their card-specific definitions use real decisions for
unspecified Break and movement targets and only continue success-linked effects
after the domain operation succeeds. The scenarios cover Yin/Yang/Harmony state,
atomic three-card Break costs, fixed Speed 14 precedence, optional Speed-1 Catch
with After-Use return to Hand, Combo/Catch variants, break replenishment ordering,
late movement immunity, Get prevention scoped to the exact successfully moved
card, turn expiry, both owners, wrong timing/zone, and numbered-effect negation.
The remaining UNC focus is `UNC-AT-026/027/028`.

The AWL review worktree's six card commits (`AWL-AT-026/027/030/031/032` and
`AWL-SP-002`) are now integrated as card-specific blocks. `AWL-AT-025` had no
commit or ruling blocker, so it was completed in the integration tree from its
printed text, detail text, and Q&A 152/155. Its numberless Combo prohibition
survives numbered-effect negation; only a Lower Attack used by the same player
in the current turn enables the optional fixed-Speed-3 Catch, and selecting that
variant reduces Catch damage by 500. Lower Defense, Upper Attack, prior-turn
history, and numbered negation do not enable that variant, while Down Stance
does not disable it. The card has two reviewed ability groups and 13
deterministic scenarios. All seven AWL card tests pass on the integration tree.

The four cards that remained after the RFS review branch are now completed in
the integration tree. `RFS-AT-026` verifies the Zero Suit play condition,
numbered source-specific immunity to the `RFS-PS-002` damage decrease, and the
opponent's 5 FP on opponent Dodge. `RFS-AT-027` moves every eligible Parts card,
keeps its `RFS-PS-002` damage-decrease immunity through the following turn,
offers a real `RFS-AT-028` Side-to-Hand choice, always gains 5 FP after use, and
restarts Ready only when no damage was received. `RFS-AT-041` applies exactly
Guardian/Assassin/Paladin aliases only while a Lita effect discards it, then
offers the Saintess-only fixed-Speed-5 Catch and real List acquisition choice.
`RFS-PS-001` covers the five-card Guisum deck supplement, optional game-start
placement, the HP-2500 Blue Flame boundary, successful-move-gated Get
replacement, and optional Recovery placement of up to two Guisum. Together
these cards add 13 reviewed ability groups and 69 deterministic scenarios,
including both owners, inactive zones/timings, numbered-effect negation,
declines, empty candidates, and movement immunity after selection.

`CB03-AT-027` and `CB03-AT-028` add three reviewed ability groups and 25
deterministic scenarios. Ghost Fire pays exactly 200 HP at the boundary, adds
Middle Dodge only for effect-modified pre-FP Speed 7 or higher, and schedules
Recovery FP from the live number of `RFS-AT-002` cards with a maximum of three.
Ghost Dance installs two repeating same-turn schedules so every matching
`RFS-AT-002` Use receives Damage +100 and Hit `<+1>`, ignores the opponent and
other card codes, and keeps Blue Flame through the following turn's Recovery
end. Battle-scoped judgment changes on Combo/Catch cards are now restored to
their printed values when the battle expires; `UNC-AT-022` also verifies its
temporary Catch Hit `<+0>` before returning to printed Hit `1` in Hand.

`CB03-AT-013`, `CB03-AT-022`, and `CB03-AT-031` add seven reviewed ability
groups and 50 deterministic scenarios. Taunting returns both normal Battle
cards to their owners' Hands after a no-damage judgment, redirects a Special
opponent through the core Break rule, restarts Ready, restricts only the
opponent's Defense cards, and copies the next opponent Technique's live Damage.
Aegis inspects a real opponent Hand choice without leaving it face-up, copies
all Defense judgments only from a Defense Technique, resolves both correct and
incorrect parity branches, hides a correctly revealed card at turn end, and
restarts Ready only after this same Aegis resolved its second ability. Revolver
Launcher asks for a real Hand discard before recording the next Lumen skip and
the current-turn state. Its bonus reacts once to each positive Damage event
from a Pinp Technique, including another Technique effect, but preserves the
causing ability ID so its own 100 Damage cannot recurse. The state expires at
the current Recovery end.

`CB03-AT-009`, `CB03-AT-010`, and `CB03-AT-012` add seven reviewed ability
groups and 40 deterministic scenarios. Kong Kong Rush changes to Middle only
against a Defense Technique and exposes printed Speed 10 and optional fixed
Speed 8 as distinct Catch actions; only the selected Speed-8 variant changes
Hit to Combo. Dropkick applies its Dodge limit to effect-modified, pre-FP
Speed, keeps the numberless rule under numbered-effect negation, adds 200
Damage only on Counter, and gains 5 FP on Opponent Dodge only during High
Tension. Moonlight Radiance prevents a real Middle Dodge while in Battle and
schedules exactly one 5-FP gain at the current turn's Recovery after Hit,
Counter, or Combo during High Tension.

The remaining `CB03-AT-003/004/005/030` block adds five reviewed ability
groups and 37 deterministic scenarios. Moonlight Punch exposes only real
Hand/List Minyeongi Techniques at exactly Speed 5 for its High-Tension Catch;
Moonlight Kick checks both Hand and Foot while excluding bodyless Techniques;
and Triple Barrage covers all three positions, the Speed-5 boundary, inactive
zones, and numbered-effect negation. Tech Blaster offers a real mandatory Hand
choice, gates both 100-Damage events on a successful discard, and offers only
movable Techniques from List after the third Combo. Late movement immunity is
rechecked after both selections. Together with the earlier blocks, all 25
`CB03-*` cards now have card-specific review evidence: 51 ability groups and
367 deterministic scenarios.

`CB02-AT-003`, `CB02-AT-005`, and `CB02-AT-026` add four reviewed ability
groups and 29 deterministic scenarios. Hand Blade exposes every legal declared
Combo Speed while still enforcing the increasing-Speed order. Low Kick exposes
printed Speed 7 and optional fixed Speed 4 as separate Catch actions and changes
Hit to `+0` only for the selected Speed-4 branch. Tempo de Dou can reuse its
Battle-zone copy only after another Viola Technique, only with Hidden Bond, and
only once per turn; its second use ignores the Combo Damage penalty even when
the first use was negated (Q&A 679), while Nevermore's turn use lock still wins
(Q&A 685).

`CB02-AT-040` and `CB02-AT-041` add four reviewed ability groups and 34
deterministic scenarios. Order: Karkinos moves from Side to Lumen at game
start, reacts independently to every Yohann parity result during Disaster I
(Q&A 693), and Breaks at Recovery when either player is at 2000 HP or less.
Order: Troia Hippos makes the initial guess optional, hides every opposing Hand
card after each correct result, adds 200 Damage per correct result, fixes Damage
back to 400 after a wrong result, and stops at five correct guesses/+1000
(Q&A 694).

`CB02-AT-006`, `CB02-AT-042`, and `CB02-AT-043` add five reviewed ability
groups and 41 deterministic scenarios. Taeseon Bigyeok changes Hit to Combo at
Catch but keeps the physical card in Battle until that controller's actual
Combo end. Order: Philiada exposes a real opposing Hand-card choice, preserves
negative Guard judgments when adjusting FP, and applies its -200 Damage branch
only on a wrong declaration. Atelier of Pain moves Side to Lumen at game start,
checks the exact four-FP advantage and payment boundary, reads actual current-
turn Ezebel use history, and counts only Spider tokens for its Recovery heal and
Break.

`CB02-AT-036` and `CB02-AT-038` add four reviewed ability groups and 34
deterministic scenarios. Overwhelming Discipline continuously prevents Dodge
only while Guardian is active, then exposes the real Saintess-Technique discard
choice after use; skipping Get and preventing Catch occur only after that card
actually moves. Rakshasa Crushing Chain Fist derives its pre-judgment Speed
bonus from capped Rin-Technique counts in Break, exposes up to two eligible
Speed-8-or-less Rin Techniques from Break as real Combo actions, and Breaks all
Technique cards in both Battle zones at that controller's Combo end. The Combo
review also verifies that a jointly proposed pair consumes the two-use grant
without allowing a third card.

The remaining Chimera block, `CB02-AT-001/002/012/035` and `CB02-PS-001`, adds
13 reviewed ability groups and 85 deterministic scenarios. Yanar Tash counts
printed character marks even after Chimera treatment, excludes neutral marks,
and ends Battle after its exact third-Combo exception. Providence's Track
enforces its included-card special-Technique deck restriction, Lumen immunity,
setup movement, hand-limit bonus, and a real List acquisition choice outside
Combo Time. Friends Shield chooses as many real Hand cards as possible up to
two, changes an opposing Combo Hit to +6, and blocks its List copy from entering
Hand through the end of the next turn. Shooting Star implements the unrevealed
Hand requirement from Q&A 678, effect-Catch grant, repeatable skipped-Get choice
from Q&A 677, and the turn-long Saintess-only use restriction. Hayot Ha Kodesh
keeps the trait in Passive, validates the 30-card/import limits, preserves each
imported Technique's printed character mark, negates its effects, and Breaks it
after use.

The first CRS Rin block, `CRS-PS-001`, `CRS-AT-002`, and `CRS-AT-005`, adds
eight reviewed ability groups and 46 deterministic scenarios. Rakshasa
Princess reacts only to the owner's Rin Technique Breaks, stops under trait
negation, and stacks independently with Prison Flame's own Break reward as
required by Q&A 224. Prison Flame enforces its three-copy limit and fixed
eight-Speed Catch, converts the exact removed Ember count into Damage, and
Breaks itself before gaining its own Ember. Great Wheel Kick checks the
opposing attack's pre-FP Speed boundary and always gains Ember on Counter while
offering a real, optional Hand-card Break choice whose protected candidates
are excluded.

The next CRS Rin block, `CRS-AT-009`, `CRS-AT-010`, and `CRS-AT-011`, adds
eight reviewed ability groups and 46 deterministic scenarios. Rakshasa Great
Flame limits its printed Dodge to pre-FP Speed 10 or less, gains two Ember on
Counter, and grants the Speed exception only to the immediately following Rin
Technique whose name contains Rakshasa; Q&A 20 restores normal ascending Speed
after that card. Rakshasa Prison Flame counts current Rin Techniques in Break
in pairs, preserves the controller's same-timing effect order, and continues
Combo Hit and Damage after breaking itself. Gentlemanly Response prevents only
Guard, loses one FP after its negated Grab returns it to Hand, and applies its
-100 Damage/+0 Hit branch only against an opposing Defense Technique.

The Yohann parity block, `CRS-AT-012`, `CRS-AT-013`, and `CRS-AT-014`, adds
three reviewed ability groups and 32 deterministic scenarios. Each effect uses
the real opponent-Hand card choice and parity declaration decisions before the
selected card is mutually inspected. Order: Harpe applies its two FP only after
the successful pre-FP reference-Speed check (Q&A 235), Agent Hustle adds Lower
Dodge only against an opposing Lower Attack, and Order: Triaina preserves its
printed Combo judgment on success or decline while a failed guess replaces it
with +1 (Q&A 236).

The following Yohann block, `CRS-AT-015`, `CRS-AT-016`, and `CRS-AT-017`,
adds four reviewed ability groups and 36 deterministic scenarios. Order:
Cerberus performs the Disaster parity check mandatorily and blocks only Dodge
on success. Order: Arges optionally blocks only Guard and gains 300 Damage, or
replaces its Guard judgment with -8 on failure. Order: Stymphalos ignores its
Combo Damage penalty under Disaster and pays a real player-selected List-card
movement cost before its fixed eight-Speed Catch; the cost moves to Side
without replenishment (Q&A 233), then the Catch changes Hit to Combo.

The next Yohann block, `CRS-AT-018`, `CRS-AT-019`, and `CRS-AT-020`, adds
seven reviewed ability groups and 51 deterministic scenarios. Order: Gigas
uses a real opponent-Hand parity choice and changes both Hit and Counter to
Combo only on success. Dramatic Exit is legal only as the third Combo card,
adds 200 Damage, applies Disaster penalty immunity, and ends the Combo before
an already proposed follow-up can resolve. Pandora Box ignores opposing card
effects in every zone, can move from Side to Lumen only after the current-turn
Foresight ability resolved, and uses real card/type/discard decisions for its
Lumen attack-or-defense guess, including already revealed Hand cards (Q&A
517) and the no-repeat boundary after Disaster is gained (Q&A 554).

The next CRS block, `CRS-AT-029`, `CRS-AT-037`, and `CRS-AT-041`, adds six
reviewed ability groups and 37 deterministic scenarios. Tricky Step pays a
real selected Hand discard before offering a real optional List acquisition;
its Advance Notice exchange selects both physical cards, swaps them atomically,
and records both public reveals before restoring hidden state (Q&A 550).
Divertissement requires three Hidden Bond counters for List Combo use and can
spend one counter to reuse only a prior Hand/Foot-judgment Combo card, ignoring
Speed, ending Combo, and returning that card to Hand (Q&A 511/643/685).
Walking Reaper enforces its numberless Dark Night play condition and, on Dodge,
caps reflected printed Damage at 500 and numeric Hit FP at 5; a Combo Hit gives
no FP while still reflecting Damage (Q&A 588/606).

The next CRS block, `CRS-AT-043`, `CRS-AT-046`, and `CRS-AT-047`, adds eight
reviewed ability groups and 50 deterministic scenarios. Beginner Overlord Roar
requires both Harmony and `UNC-AT-010` in Lumen, pays real Yin/Yang counters for
its optional Guard response, and marks the 300 effect Damage so neither Bagua
nor Howling can gain a counter from it. Celestial Word enforces its three-copy
deck limit, caps its 400 recovery at initial HP, lets the player select an
actual Saintess card from Hand to discard or skips Get, gains 4 FP only after
zero received Damage, and breaks itself after use. Vanity Suppression likewise
uses an actual Saintess Hand-card discard and applies its +6 Counter judgment
and Get skip only after the discard succeeds.

The following `CRS-AT-048`, `CRS-AT-049`, and `CRS-AT-050` block adds seven
reviewed ability groups and 44 deterministic scenarios. Trial Slash makes the
player select the actual Saintess card acquired from List and, during a
Paladin Combo, the actual Saintess card discarded from Hand; its Damage bonus
is applied only after that discard succeeds. A Q&A 438 boundary also confirms
that an acquired seventh Hand card remains until Battle-end adjustment. Nebula Strike observes the
effect-modified 500/501 Damage Clash boundary, blocks only the opponent's
Clash, and changes Guard only after a selected Lita Technique is successfully
discarded. Chasing Fan checks its Dodge limit against Speed before FP, keeps
its numberless opponent-Clash prohibition under numbered-effect negation, and
blocks the opponent's Dodge only when its controller has strictly less FP.

The following `CRS-AT-051`, `CRS-AT-052`, and `CRS-AT-053` block adds five
reviewed ability groups and 27 deterministic scenarios. Coiling Serpent moves
the opposing Defense card to its owner's List exactly once on Hit, and Q&A 592
confirms that the moved card may still resolve a List-active effect. Combat
Sense enforces its three-copy deck limit and Ready-phase use prohibition, then
gains 1 FP only when that exact card instance is broken, including the Q&A
227/523 timing boundary. Rapid Dodge gains FP from the opposing reference
Speed on Dodge and installs a mandatory turn-duration three-Combo cap that
overrides a larger Combo extension until it expires.

`CRS-AT-054` (Drift Conversion) adds two reviewed ability groups and 13
deterministic scenarios. It enforces the three-copy deck limit, breaks the
actual source card from Side without replenishing List as required by Q&A 594,
then permits exactly the next third Combo card from Hand while ignoring Speed.
The permission is granted only after a successful Break, and using the third
card ends Combo Time.

`DFR-AT-017` (Garage Style) adds two reviewed ability groups and 19
deterministic scenarios. Game setup creates three physical Garage tokens in
Lumen. While the card is in Ultimate, its optional After Use effect requires
the player to select and remove an actual token. It can release Down Stance,
offers a separate real Hand discard choice for an upper Dodge or lower Attack,
restores Down only after that discard succeeds, and installs the owner-only
turn Catch lock at the correct immediate or next-Catch boundary.

The next unreserved PMP block, `PMP-AT-002`, `PMP-PS-001`, and
`PMP-AT-029`, adds four reviewed ability groups and 35 deterministic
scenarios. Strange Birth follows Q&A 627 by making its mandatory 200 HP
payment even when that reaches zero. Blood Resonance receives explicit
ability-cost provenance, moves a player-selected physical Spider from Side to
Lumen after the owner's HP payment, and only deals its optional 200 Damage
after a selected Lumen Spider was actually removed. Its once-per-Technique
limit distinguishes Battle/Clash/Combo/Catch damage from effect Damage.
Marchen Arabesque applies only one branch against an opposing Attack: Hand
reduces Speed by two, Foot adds 200 Damage, and a fixed Speed still ignores the
later change.

`PMP-AT-012`, `PMP-AT-033`, and `PMP-AT-051` add six reviewed ability
groups and 42 deterministic scenarios. Horrible Kindred applies the mandatory
200 HP cost even when it defeats its owner, then offers the optional 100 HP
payment only after taking no battle damage and grants a real Hand-only Ezebel
Catch at Speed 8 or less. Un Jour keeps its numberless Dodge prohibition under
numbered-effect negation and asks the owner to choose up to two physical Dagger
tokens from Side without exceeding six in Lumen. Counter Slash reads Combo from
either opposing Attack judgment only while that card remains in Battle, changes
its own Hit to Combo, and adds 200 Damage only on Counter. The three read-only
card dry runs, 774 automatic-engine tests, and 883 full SQLite tests pass.

The parallel-review integration adds `CRS-AT-021/024`, `CB01-AT-008/010`, and
`PMP-AT-013/019/022`: 20 reviewed ability groups and 104 deterministic
scenarios. It covers a shared once-per-turn choice/combo limit, Charge refresh
and next-Ready lock, exact-three real card moves, Guard/Clash prohibitions,
Grab-negation FP, fourth-Combo correction, Lumen thresholds, named-technique
Combo, conditional Dodge/fixed Speed, Counter replacement, forced Battle-to-List
movement, and deterministic random Hand movement with Q&A 607 recovery return.
All eight focused integration tests, 781 automatic-engine tests, and 890 full
SQLite tests pass.

`PMP-AT-032`, `PMP-AT-036`, and `PMP-AT-044` add nine reviewed ability
groups and 73 deterministic scenarios. Vengeance covers use-time Feather
ordering, a real Side-to-Lumen Feather choice, exact-three physical Dagger
deletion, Dark Night expiry, and Q&A 609/634/639 interactions. Negative Spiral
Fist enforces four Yin to play, blocks Dodge, applies turn/game Yin/Yang gain
locks, and verifies fixed-Speed precedence and Q&A 644/647. Rising Dragon asks
the player to select one or two real List techniques, grants Ember only for two
successfully broken Rin techniques, and supports the Q&A 646 Break-zone Catch at
fixed Speed 8. Their read-only dry run, 782 automatic-engine tests, and 891 full
SQLite tests pass.

`PMP-AT-006`, `PMP-AT-007`, and `PMP-AT-008` add six reviewed ability
groups and 54 deterministic scenarios. Scarlet Guillotine offers only the HP
payment counts the owner can afford and applies the matching Battle Damage
bonus; Blood Maiden stops its follow-up Damage or Side move when Q&A 628's HP
payment immediately loses the game; Arachnophobia dynamically counts physical
Spider tokens and verifies Q&A 657 fixed-Speed precedence. Their card-specific
read-only dry run, 783 automatic-engine tests, and 892 full SQLite tests pass.

`CB01-AT-013`, `CB01-AT-014`, and `CB01-AT-015` add eleven reviewed ability
groups and 76 deterministic scenarios. Impossible Exit uses real three-card
Hand placement and arbitrary face-down Lumen recovery choices, applies the full
Hand-count Speed difference, and verifies Ultimate Attack replenishment. Catch
the Moon requires the Advance Notice player to choose the physical Calling Card
sent to Side. Madness forces its first-Combo discard, combines with Thief
Gimmick for the Q&A 665 fifth Combo, asks for three physical List techniques,
and excludes Battle cards under Q&A 672. Their read-only dry run, 784
automatic-engine tests, and 893 full SQLite tests pass.

`CB01-AT-026`, `CB01-AT-027`, and `CB01-AT-030` add eight reviewed ability
groups and 52 deterministic scenarios. Falling Blossom keeps its numberless
Guard/Clash prohibition and Grab-negation FP loss while its numbered Battle-only
break immunity can be negated; Q&A 656 verifies Jump's atomic two-card break is
cancelled. Storm Kick offers a real Yin/Yang branch, schedules Yin FP for
Recovery, and applies Yang Damage immediately. Shadow Attack uses fixed Speed 9
only while its numbered Catch effect is active and applies the Assassin gain
instead of the normal Grab-negation FP loss. Their read-only dry run, 785
automatic-engine tests, and 894 full SQLite tests pass.

`CB01-AT-001` and `CB01-AT-028` add eight reviewed ability groups and 58
deterministic scenarios. True Kick verifies the 2500-HP use boundary,
Recovery-scheduled FP, the FP-disadvantage 12-Speed Mid dodge boundary, and
Ultimate Attack replenishment. Star Judgment keeps its numberless Dodge/Clash
prohibition independent from its 1500-HP play condition, moves a player-chosen
physical `LMI-AT-001` from Side to Lumen, verifies Q&A 673 does not
retroactively trigger an effect in the same Combo timing, applies its Combo
Damage reduction, and replenishes after its mandatory break. Both card-specific
read-only dry runs, 791 automatic-engine tests, and 900 full SQLite tests pass.

`CB01-AT-011`, `CB01-AT-012`, and `PMP-AT-037` add nine reviewed ability
groups and 56 deterministic scenarios. Platinum Impact preserves earlier
Speed changes when it locks both current Speeds while still ignoring FP and
later changes, without weakening the Q&A 500 first-effect conflict rule.
Technical Dodger enforces Down Stance, blocks Guard, and grants the opponent
5 FP after Grab negation. Polar Meteor requires and removes four Yang, emits
twelve separate 100-Damage events without a Combo penalty, clears Yin, and
prevents Yin gain for the rest of the game. Their read-only dry run, 793
automatic-engine tests, and 902 full SQLite tests pass.

Automatic sessions also report browser-side command/state/event/WebSocket parse
failures through the same issue endpoint. Diagnostics redact all simulator
tokens, merge the same fingerprint for five minutes, cap distinct reports per
window, and allow a player's note to attach to the automatic report ID.

Publication validation now requires every defined ability to have a matching
review-evidence ID with at least three passed deterministic scenarios. The
plain review command also stops counting an already-reviewed definition when
that stored evidence is missing or stale. The production DB read-only audit
found two legacy evidence-ID mismatches, `ST1-011` and `ST1-012`; both pass the
current reviewer without writes. Apply only those refreshed evidence records
before publication:

```powershell
python manage.py review_automatic_effect_drafts --recheck-reviewed `
  --card-code ST1-011 --card-code ST1-012 --verbose
python manage.py review_automatic_effect_drafts --apply --recheck-reviewed `
  --card-code ST1-011 --card-code ST1-012
```

The integrated UNC Kiss block, `UNC-AT-026`, `UNC-AT-027`, and
`UNC-AT-028`, adds eight reviewed ability groups and 49 deterministic
scenarios. It covers the three-card Hand boundary and Advance Notice Combo
speeds, Secret Time's real reveal/opponent-selection/speed-guess flow and
three-damage game cap, and Switch!'s real Hand discard, Advance Notice
replacement, successful-break-dependent damage, and both-player FP reset.
The three card-specific read-only production dry runs, 752 automatic-engine
tests, and 861 full SQLite tests pass.

The integrated LIN/CB01 block, `CB01-AT-031`, `CB01-AT-032`, and
`CB01-AT-033`, adds seven reviewed ability groups and 37 deterministic
scenarios. It covers the 2500-HP play boundary and all-Ember cleanup, actual
prior-Combo and List-card break selections, success-gated Damage-penalty
immunity and Speed changes, Combo termination, and break-success-gated FP or
Ember gains. The three card-specific read-only production dry runs, 755
automatic-engine tests, and 864 full SQLite tests pass.

The latest strict production-DB read-only dry run reports 110 evidence-valid
preserved definitions plus 321 automatically reviewed definitions, or 431 of
453 cards, leaving 22 for card review or evidence refresh. After the two
read-only-verified ST1 evidence records above are applied, the implementation
count becomes 433 of 453 cards with 20 card-specific reviews remaining. This
replaces the earlier observed 313-card snapshot and
does not activate or publish an automatic ruleset. The complete
ST4 block and corrected `ST6-002`, `LMI-AT-011`, `LMI-AT-012`, and
`LMI-AT-004`/`LMI-AT-005`/`LMI-AT-006`/`LMI-AT-007`/`LMI-AT-008`/`LMI-AT-009`/
`LMI-AT-019`/`LMI-AT-020`/
`LMI-AT-010`/`LMI-AT-023`/`LMI-AT-024` and `ST4-SS1`/`ST4-SS2`/`ST4-SS3`
definitions, the four-card UNC Tao opening block, seven subsequent UNC cards,
seven AWL cards, and all 24 RFS cards are included in this dry-run count.
The previously reviewed CMYK groups through `CB03-AT-029`, including
`CB03-AT-011/020`, together with `CB03-AT-032/033`, and the newly completed
the complete `CB02-*` block is included in that observed snapshot. This plain dry run
did not use `--rebuild-reviewed` or `--recheck-reviewed`; corrected local
definitions for cards already preserved as reviewed were therefore not written
or republished.
Use a dry run first; repeat `--card-code` to apply only inspected candidates:

```powershell
python manage.py review_automatic_effect_drafts
python manage.py review_automatic_effect_drafts --apply `
  --card-code CB02-AT-039 --card-code RFS-AT-004
```

The command records scenario evidence and clears both definition-level and
ability-level draft flags only when all situations pass. Unknown card codes
fail before any write.

When the compiler or scenario rules change, re-run already approved definitions
before publishing. Use an exact card list with `--apply`: a definition that no
longer passes is returned to draft state instead of retaining stale approval.

```powershell
python manage.py review_automatic_effect_drafts --recheck-reviewed `
  --card-code CB02-AT-004
python manage.py review_automatic_effect_drafts --apply --recheck-reviewed `
  --card-code CB02-AT-004
```

If the stored definition itself must be replaced by a corrected card-specific
compiler result, use `--rebuild-reviewed` instead. Always dry-run first and
keep the card list exact; it cannot be combined with `--recheck-reviewed`.

```powershell
python manage.py review_automatic_effect_drafts --rebuild-reviewed `
  --card-code DFR-AT-041 --verbose
python manage.py review_automatic_effect_drafts --apply --rebuild-reviewed `
  --card-code DFR-AT-041
```

Related Q&A titles on the card page link directly to the Q&A admin editor.
Card relations are editable inline there; removing a relation changes the
approved source set, so reopen the card, compare the summary, and approve it
again to record a fresh source digest.

The same coverage report is available to staff in Django admin under
`Ruleset releases > 검증 및 게시`; every card error links to its visual effect
editor.

Run AI-vs-AI training against two valid decks only after a ruleset is active.
The trainer uses paired deterministic seeds, alternates both seats, and refuses
`--activate` unless the evolved candidate beats the active baseline with no
incomplete games.

```powershell
Push-Location LumenGG
python manage.py train_simulator_ai 12 34 `
  --policy-version linear-selfplay-v1.5.0 `
  --generations 8 --candidates 4 `
  --games-per-candidate 8 --evaluation-games 40 --activate
Pop-Location
```

## CRS Ember and Funky Junky review batch (2026-08-21)

`CRS-AT-006`, `CRS-AT-007`, `CRS-AT-008`, and `CRS-AT-026` now add eleven
reviewed ability groups and 70 deterministic scenarios. The scenarios cover a
real mandatory Hand-card Break choice, Combat Sense's immediate Q&A 523 FP
trigger, the Q&A 669 priority ordering with Gear Change, FP-excluded Dodge
speed boundaries, dynamic Inferno Break-zone Dodge prevention, and effect
Catches that precede FP Catches, miss their timing when Combo Time opens, can
reuse the original card from the List, end the Battle, and skip the owner's Get
phase.

Catch declarations now record the Catch card instance for Battle cleanup. This
keeps an original ready card in the List when Q&A 619 first moves it there and
the same physical card is then used for Catch. An effect-requested Battle end
also clears later Catch opportunities before entering cleanup.

The exact four-card production read-only dry run passes with nine ability
groups and 70 scenarios. The automatic-engine SQLite suite passes 795 tests and
the full project SQLite suite passes 904 tests. The strict production read-only
catalog dry run reports 110 preserved plus 325 automatically reviewed
definitions, or 435/453 cards. `ST1-011/012` account for two stale evidence
records; the remaining card-specific implementation list contains 16 cards.

## Final PMP/CB01 parallel integration (2026-08-21)

The PMP batch (`PMP-AT-010/011/043/046/047/049`) contributes 13 reviewed
ability groups and 88 deterministic scenarios. The integrated CB01 batch
(`CB01-PS-001`, `CB01-AT-020/021/029/035/036`) contributes 15 reviewed
ability groups and 93 deterministic scenarios. Its exact six-card
`--rebuild-reviewed` production read-only dry run passes 6/6.

The integration also removes an earlier `return definition` that left newly
appended card-specific compiler blocks unreachable. There is now one final
normalization and return after all card-specific blocks. The automatic review
dispatcher discovers three-argument card-specific reviewers in module order,
while generic direct-break, defense, play-condition, Combo, and Catch
reviewers remain explicit ordered fallbacks.

The automatic-engine SQLite suite passes 802 tests and the full project suite
passes 911 tests. A production read-only plain catalog dry run reports 110
preserved plus 337 automatically reviewed definitions, or 447/453 cards.
`ST1-011/012` are the two stale stored-evidence records. A read-only
`--rebuild-reviewed` run verifies both and reaches 449/453 without writing.
The four remaining card implementations are:

```text
CB01-AT-006 CB01-AT-009 CB01-AT-022 CB01-AT-025
```

## Final CB01 ultimate completion (2026-08-21)

`CB01-AT-006/009/022/025` now contribute ten reviewed ability groups and 54
deterministic scenarios. The implementation covers the Side-deck Nya Combo
grant and break-after-use, Over Limit release damage reduction, Charge speed
increase immunity without suppressing its damage bonus, the mandatory All-in
Charge-or-break branch, Blackout's public random Get replacement including a
blocked-card return, and Mujin's Q&A 676 activation and desired Bagua counter
choice.

The exact four-card production `--rebuild-reviewed` dry run passes 4/4 without
writing. The automatic-engine SQLite suite passes 803 tests and the full
project suite passes 912 tests. A plain production read-only catalog run
accepts 110 stored reviews plus 341 automatic reviews, or 451/453 cards; only
the stale stored evidence for `ST1-011/012` is excluded. A full read-only
`--rebuild-reviewed` run accepts 112 rebuilt stored reviews plus 341 automatic
reviews, reaching 453/453 with no pending definitions.

`validate_automatic_ruleset` still checks the definitions currently stored in
the production database, not the successful dry-run rebuilds. Before applying
the rebuilt definitions it reports 112 reviewed cards, 341 remaining cards,
and 1,832 publication errors. This is the expected pre-apply state. Do not
publish until an authorized operator runs the all-card reviewed rebuild with
`--apply`, then reruns validation.

## Automatic-mode completion audit (2026-08-21)

The final requirement audit verified the optional manual/automatic start
selector, release and trained-policy gates, role-filtered legal actions and
choices, HTTP and WebSocket commands, automatic engine/client issue reports,
user comments on an existing report, permanent manual fallback, AI-seat access
control, and deterministic self-play. Manual controls are now also hidden by a
mode-level CSS selector, so controls rendered after initial page setup cannot
briefly reappear in an automatic session; removing the mode class after a
fallback restores the unchanged manual UI.

A read-only production-catalog smoke run completed eight AI-vs-AI games using
all 453 catalog records and 1,017 in-memory abilities. Every game ended by
`hp_zero` in 76–149 commands with no deadlock, exception, or command-limit
overrun. The complete SQLite suite passes 912 tests. On the isolated MySQL
profile, the nine automatic-persistence tests and all ten simulator AI/HTTP
tests pass; the WebSocket and publication tests also passed in the combined DB
run. MySQL test DB creation and destruction on the configured server takes
several minutes even when the test body takes only seconds.

These checks are read-only with respect to the production catalog. The stored
production definitions are still at the pre-apply state described above, so
automatic mode remains intentionally unavailable until an authorized operator
applies the all-card rebuild, validates it, and publishes the immutable
release.

The final production preflight found one migration added after the earlier
production migration run: `battlelog.0029_client_issue_reports`. `migrate
--plan` shows it as the only pending operation; it updates the issue-report
origin field choices to include browser-detected errors. The exact authorized
release sequence is therefore:

```powershell
python manage.py migrate
python manage.py review_automatic_effect_drafts --apply --rebuild-reviewed
python manage.py validate_automatic_ruleset
python manage.py publish_automatic_ruleset 2026.06.1
```

Immediately before that sequence, the read-only preflight verified the pinned
rulebook SHA-256 and 54-page count, rebuilt 112 stored reviews plus 341
automatic reviews with zero pending cards, observed 112/453 definitions still
stored as reviewed, no active automatic ruleset release, and the verified
`linear-selfplay-v1.4.0` AI policy active.

## Production automatic release (2026-08-21)

The authorized production workflow completed. All 453 definitions were rebuilt
and stored, then publication validation reported 453 reviewed cards, 1,017
abilities, four explicit no-effect cards, and zero remaining cards, errors, or
warnings. Release `2026.06.1` is active with content hash
`df1ff01c586b829d50dad58726659c9c05ca8679dcacfe25976114e28cee9ba3`.

The first strict validation correctly stopped publication on four evidence
contract mismatches. `UNC-AT-053` referenced linked general Q&A 597;
`ST4-009`, `AWL-AT-033`, and `RFS-PS-002` had deterministic scenarios but a
helper-rule ID or jointly tested state-clear ability was absent from the stored
per-ability evidence list. The catalog now counts a linked Q&A in either source
bucket, all three real DSL ability IDs have at least three deterministic
scenarios, and the review command refuses to store a nominally passed result
when its evidence omits any real ability ID. The four corrected definitions
were reapplied before publication.

Post-publication verification resolves the active release and the verified
`linear-selfplay-v1.4.0` policy, confirms all 453 snapshot cards, and receives
HTTP 200 from the simulator start page with manual, automatic, and AI opponent
options all present. The final isolated SQLite suite passes 913 tests.

The HTTP 200 option check above uses the current application worktree against
the production database. A direct live check of
`https://lumen.hinoto.kr/battlelog/simulator/` immediately after publication
still returned the pre-feature HTML without the mode or AI selectors. The
database release is complete, but the current worktree must still be deployed
and the production application/static processes reloaded before the public
site exposes it.

## Post-effect multi-deck AI training (2026-08-21)

The self-play trainer now accepts repeated `--training-pair P1:P2` options and
rotates one deterministic seat-paired evaluation across a non-empty corpus of
initial states. Policy metrics retain both the legacy first `training_decks`
pair and the complete `training_deck_pairs` corpus. Headless policy games now
quarantine an initialization or effect-resolution exception as an incomplete
`engine_error` sample instead of aborting the entire training run.

An actual-card preflight exposed an integration bug in `LMI-PS-001`: the
nested turn-end schedule that clears a Legion blessing cooldown was being
expired on the same turn-end that created it. The inner schedule now uses the
`next_turn` duration, the schema accepts that schedule lifetime, and the card's
review lifecycle includes real turn-duration expiration. The exact card was
rebuilt and reviewed, the full 453-card catalog validated with zero errors or
warnings, and immutable release `2026.06.2` was published and activated with
content hash
`df8dd700cd3eb5be28415f55765595be4eb6bf3264647e1eb55d97ebbe914dfc`.

Policy `linear-selfplay-v1.5.0` trained on nine matchups covering all 18
currently valid characters. Five generations evaluated 450 games and a
separate 90-game promotion evaluation finished 58W/32L/0D against active
baseline `linear-selfplay-v1.4.0`, with zero incomplete games and an average
164.822 commands. The evolved policy was activated after 540 total training
games. A different-seed 36-game holdout then finished 23W/13L/0D with zero
incomplete games and an average 162.333 commands.

The final isolated SQLite regression suite passes all 916 tests. Single-state
training evaluation also preserves the historical seed format, so existing
deterministic policy replay benchmarks remain reproducible while multi-state
evaluations add an explicit state index to their paired seeds.
