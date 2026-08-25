---
title: "Lumen Condenser Comprehensive Rules"
short_title: "Comprehensive Rules"
slug: "/rules/comprehensive"
version: "0.2-web"
updated: "2026-08-24"
language: "en"
source_locale: "ko"
translation_status: "machine-draft"
translation_updated: "2026-08-25"
searchable: true
---

# Lumen Condenser Comprehensive Rules

> **Document Status:** This is a web edit v0.2 that rechecks the review draft v0.1 with the original rulebook dated 6, year 2026. We've consolidated the existing Master Rulebook and the answers to 65 official decision questions, but some details still need to be officially finalized.

## How to use this document

- Players learning the game for the first time are recommended to read [First time play guide](./lumen-beginner-guide.md) first.
- This document is a standard for searching and citing situations requiring a ruling by **Rule Number**.
- The rule number is given in the `Chapter, Section, Paragraph` structure so that it can be maintained even if the page changes.
- It is recommended that exception decisions and errata for each card are managed in a separate card decision book by citing the rule number in this document.
- `[Confirmation required]` is an item that the production team needs to confirm once more.
- Visuals of the original page and web usage can be found at [visual index](./VISUAL_ASSET_INDEX.md).

> [! WARNING]
> Before the official publication of this document, please check the latest official rulings for each card and announcements from the production team.

## table of contents

- [0. General provisions and document usage](#chapter-0)
- [1. Basic concepts and card grammar](#chapter-1)
- [2. Zone and Public Information](#chapter-2)
- [3.cards and decks](#chapter-3)
- [4. Game Ready](#chapter-4)
- [5.turns and phases](#chapter-5)
- [6. Effects and Priority](#chapter-6)
- [7.battle](#chapter-7)
- [8.combo](#chapter-8)
- [9. Catch](#chapter-9)
- [10. Zone movement and Break](#chapter-10)
- [11. Special Technique and Ultimate Technique](#chapter-11)
- [12. Game End and Special Situations](#chapter-12)
- [Appendix A. Glossary](#appendix-a)
- [Appendix B. Quick Reference Table](#appendix-b)
- [Appendix C. Edit Checklist](#appendix-c)
- [Appendix T. Draft Competition/Operating Regulations](#appendix-t)

---

<a id="chapter-0"></a>
# 0. General provisions and document usage

This chapter defines the basic purpose of Lumen Condenser and the processing unit/state checking principles used in this document.

## 0.1 Game Overview

<a id="rule-0-1-1"></a>
**0.1.1** Lumen Condenser is a competitive card game where you reduce your opponent's HP with Attack Technique and block the opponent's attacks with Defense Technique.

## 0.2 Status and priority of documents

<a id="rule-0-2-1"></a>
**0.2.1** This document is a review draft incorporating the existing Master Rulebook and Official Decision Response. Before official publication, check the latest official judgments for each card and announcements from the production team.`[Review Draft]`

<a id="rule-0-2-2"></a>
**0.2.2** The priorities between documents and the standard languages for the Korean, English, and Japanese versions have not yet been officially confirmed. In this draft, it is interpreted in the following order for editing convenience.`[Confirmation required]`

1. Latest errata and official card rulings
2. card text
3. comprehensive rules
4. introductory guide
5. example

> [! WARNING]
> The above order is not a rule confirmed by an official answer, but a temporary priority for editing the document. Before formal publication, the legal status of examples and the reference language in case of conflicting translations must be confirmed.

## 0.3 Check processing units and status

<a id="rule-0-3-1"></a>
**0.3.1** “Processing Unit” means one of the following:`[edit definition]`

- The scope of processing one effect, identified by one number, from beginning to end.
- A set of numerical treatments set to be applied simultaneously, such as both FP or both damage.

<a id="rule-0-3-2"></a>
**0.3.2** After each processing unit, check the status of HP 0, Hand Limit excess, etc. After performing all necessary status processing, proceed to the next effect or next step.

<a id="rule-0-3-3"></a>
**0.3.3** The effect currently being processed will not be interrupted due to a normal trigger effect. Only actions explicitly classified as “intervening” in the card text or official decision may enter between the current effects.

> [! EXAMPLE]
> If an effect reduces both HP by 500, check both HP after finishing the entire effect. If both sides are below 0, they are considered to have reached 0 HP at the same time in the same processing unit.

---

<a id="chapter-1"></a>
# 1. Basic concepts and card grammar

This chapter defines win conditions and common rules for reading card text.

## 1.1 Wins and Game States

<a id="rule-1-1-1"></a>
**1.1.1** Each player starts with the HP indicated on the far left of Character Card. After the processing unit ends, if it is confirmed that the opponent's HP is less than 0 and the player's HP is more than 1, that player wins.

## 1.2 Basics of Public Information

<a id="rule-1-2-1"></a>
**1.2.1** Before the game begins, both players check each other's initial hands. During the game, the list is kept face-to-face. Disclosure of other information is subject to the regulations of each zone.

## 1.3 Function/Effect/Omission Grammar

<a id="rule-1-3-1"></a>
**1.3.1** In the card description, a description without a number before the sentence is a **function**. The function is always applied without any separate activation, and applies regardless of which zone the card is in.

<a id="rule-1-3-2"></a>
**1.3.2** In the card description, the description with a number before the sentence is the **effect**.

<a id="rule-1-3-3"></a>
**1.3.3** If the target or subject of the effect is omitted, it is interpreted as follows.

- The subject of the action is considered to be the player **himself**, the owner of the card.
- Expressions indicating the status, value, or movement of a card are regarded as **this card**.

> [! EXAMPLE]
> - “Clash poetry” is interpreted as “your own Clash poetry.”
> - “Lumen Zone’s card” is interpreted as “your Lumen Zone’s card”.

---

<a id="chapter-2"></a>
# 2. Zone and Public Information

The place where the cards are placed is called the **zone**. Depending on the zone, the cards allowed, front and back, public range, and movement results vary.



## Zone Attribute Summary

| Zone | basic card | default display | Content disclosure | Owner confirmation/order |
| --- | --- | --- | --- | --- |
| Character Zone | character | front | public | no order |
| Trait Zone | characteristics | front | public | no order |
| loss | Attack/Defense/Ultimate Attack/Defense, etc. | private | Mutual confirmation of initial cards | Only check for owner |
| list | available Technique | front | public | No sense in order |
| Side Deck | Initial unselected Technique·Special Technique | back side | Private to the other party | Owner can order and confirm |
| Battle Zone | Ready Technique | Back side during Ready, front side after release | public after public | 1 each |
| Lumen Zone | Cards placed by effect | first draft front | Open as draft | Depending on card effect |
| Ultimate Zone | Ultimate | Front side is default, exceptions possible with effects | public | Chapters 0~1 |
| Break Zone | Card with Break | first draft front | Open as draft | Generally not reusable |

> [! WARNING]
> The official answer only confirmed that the range of Public Information must be individually specified for each zone. In the table above, the values ​​marked “in draft” and some detailed disclosure scopes must be confirmed before formal issuance.

## 2.1 definition of Zone

<a id="rule-2-1-1"></a>
**2.1.1** The list is a public zone where the player's Technique Card is placed, and can contain up to 14. If a card tries to move to the list while the list is 14, the card to be moved is Break instead.

<a id="rule-2-1-2"></a>
**2.1.2** Side Deck is the backside zone where the initial hand and cards not included in the list are placed. Owners can decide the order of cards before the game starts and check their Side Deck contents during the game.

<a id="rule-2-1-3"></a>
**2.1.3** Cards that are Break are placed in Break Zone and generally cannot be used again in that game.

<a id="rule-2-1-4"></a>
**2.1.4** Place the player's Character Card on Character Zone.

<a id="rule-2-1-5"></a>
**2.1.5** Place the character's Trait Card in Trait Zone.

<a id="rule-2-1-6"></a>
**2.1.6** Battle Zone is a zone where the selected Technique Card is placed in Ready Phase.

<a id="rule-2-1-7"></a>
**2.1.7** Place the card that is the target of the “effect placed on Lumen Zone” on Lumen Zone.

<a id="rule-2-1-8"></a>
**2.1.8** The FP area is used to display your own or your opponent's FP.

<a id="rule-2-1-9"></a>
**2.1.9** In Ultimate Zone, Ultimate Technique Card is placed face up by default. It may be face down if the card effect specifies it.

## 2.2 Public properties by zone

<a id="rule-2-2-1"></a>
**2.2.1** The number of cards in Zone is treated as Public Information, which is necessary for comparison and legitimacy confirmation of Priority. Disclosure of card contents and order is subject to zone regulations.`[Need to check details]`

---

<a id="chapter-3"></a>
# 3. cards and decks

## 3.1 meaning of deck

<a id="rule-3-1-1"></a>
**3.1.1** A deck refers to a pile of cards needed for play. The starter deck can be used immediately upon opening, and the deck you build yourself must adhere to the deck composition restrictions of 3.5.

## 3.2 Character Card and

<a id="rule-3-2-1"></a>
**3.2.1** Character Card represents the player and displays the player's remaining HP.

<a id="rule-3-2-2"></a>
**3.2.2** The value displayed in the current HP section of Character Card is that player's Hand Limit. If the HP changes, the upper limit is recalculated at the end of the processing unit.

<a id="rule-3-2-3"></a>
**3.2.3** If the hand exceeds the current Hand Limit after the end of the processing unit, the owner immediately gains discard by the amount that the upper limit has been exceeded. This processing is performed before processing the next effect.

<a id="rule-3-2-4"></a>
**3.2.4** You can only include Techniques with the same mark as your Character Emblem or Neutral Emblem in your deck.

> [! EXAMPLE]
> Even if you add multiple cards to your hand while processing the effect and exceed the limit, the effect will be processed until the end. Immediately after the effect ends, check the hand limit for the current HP range and discard any excess.

## 3.3 Trait Card

<a id="rule-3-3-1"></a>
**3.3.1** Trait Card is a card with a character's unique effect and is placed on Trait Zone next to Character Card at the start of the game.

<a id="rule-3-3-2"></a>
**3.3.2** Trait Card applies functions and effects immediately after starting the game.

## 3.4 Attack·Defense Technique

<a id="rule-3-4-1"></a>
**3.4.1** Attack Technique Card is Technique Card which can be used on Battle Zone to inflict damage to the opponent.

<a id="rule-3-4-2"></a>
**3.4.2** Defense Technique Card is used in Battle Zone to suppress the opponent's actions Technique Card.

## 3.5 Deck Construction

<a id="rule-3-5-1"></a>
**3.5.1** The basic deck consists of a total of 22 or 23 cards, and the card composition is as follows. If a character's characteristics change the number of deck compositions, the card text follows.

- Chapter Character Card 1
- Chapter Trait Card 1
- Offense, Defense, Special Technique Card Total 20 pieces
- 0 or 1 Ultimate Cards

<a id="rule-3-5-2"></a>
**3.5.2** If a character trait changes deck building restrictions, it only changes the items specified in the card text. Unspecified restrictions on the number of decks, card types, marks, and names of the same name still apply.

<a id="rule-3-5-3"></a>
**3.5.3** Basically, you cannot have more than 2 cards with the same name in one deck. Even if the card number, illustration, and edition are different, if the card name is the same, it is considered a card with the same name.

<a id="rule-3-5-4"></a>
**3.5.4** The deck's Technique Card must be either Neutral Emblem or the same as your Character Emblem.

<a id="rule-3-5-5"></a>
**3.5.5** At least 10 of the Technique Card in the deck must be the same as your Character Emblem.

<a id="rule-3-5-6"></a>
**3.5.6** Character Emblem of Trait Card must be the same as its Character Card mark.

---

<a id="chapter-4"></a>
# 4. Game Ready



## 4.1 Game Preparation Procedure

<a id="rule-4-1-1"></a>
**4.1.1** Before the game begins, each player places Character Card, Trait Card, and the selected Ultimate Card face up.

<a id="rule-4-1-2"></a>
**4.1.2** At the start of the game, the initial Priority holder is determined by an agreed upon method such as dice, rock, paper, scissors, or coin toss.

<a id="rule-4-1-3"></a>
**4.1.3** Each player selects Technique Card 5 rather than Special Technique as the initial hand, and 9 as the initial list. Therefore, a legal deck must contain at least Technique Card, not Special Technique, at least 14.

<a id="rule-4-1-4"></a>
**4.1.4** Technique Card and Special Technique Card not selected in the initial hand or list are placed face down on Side Deck.

<a id="rule-4-1-5"></a>
**4.1.5** The initial list 9 is first placed on the back, and after both sides are ready, it is revealed on the front.

<a id="rule-4-1-6"></a>
**4.1.6** Both players exchange the initial cards 5, check them, and then return them to their owners.

---

<a id="chapter-5"></a>
# 5. turns and phases

One turn progresses through five phases: **Lumen → Ready → Battle → Get → Recovery**.

```mermaid
flowchart LR
    A[Lumen Phase] --> B[Ready Phase]
    B --> C[Battle Phase]
    C --> D[Get Phase]
    D --> E[Recovery Phase]
    E --> A
```

## 5.1 turns and phases

<a id="rule-5-1-1"></a>
**5.1.1** A turn includes five phases, from Lumen Phase to Recovery Phase.

<a id="rule-5-1-2"></a>
**5.1.2** One turn proceeds in the following order: Lumen Phase, Ready Phase, Battle Phase, Get Phase, Recovery Phase.

## 5.2 Lumen Phase

<a id="rule-5-2-1"></a>
**5.2.1** In Lumen Phase, card effects that are described as being processed “in Lumen Phase” are processed starting from the holder of Priority.

## 5.3 Ready Phase

<a id="rule-5-3-1"></a>
**5.3.1** At Ready Phase, each player selects the Technique Card 1 card to use, places it face down on Battle Zone, and declares ready. After declaring Ready, you cannot change the card or cancel the declaration.

> [! IMPORTANT]
> Once you declare Ready, you cannot change the card even if your opponent has not yet done so. The non-response time of 10 seconds in the competition and operation regulations is also calculated from the moment the opponent clearly declares ready.

## 5.4 Battle Phase

<a id="rule-5-4-1"></a>
**5.4.1** In Battle Phase, both ready cards are revealed face up at the same time and the attack and defense results are judged.

<a id="rule-5-4-2"></a>
**5.4.2** Battle Phase At the end, bring the ready card to your hand. If there are separate movement rules such as combo·Catch·Break, those rules take priority. Both ready cards are treated as if they were used starting from the card of the Priority holder.

## 5.5 Get Phase

<a id="rule-5-5-1"></a>
**5.5.1** After processing all effects that occur when entering Get Phase, decide on Priority again. The order determined at this time is not recalculated until Get Phase is completed.

<a id="rule-5-5-2"></a>
**5.5.2** In Get Phase, show 1 cards from the list starting from the Priority holder decided at the time of entry to the opponent and then place them in your hand.

<a id="rule-5-5-3"></a>
**5.5.3** A player whose hand reaches Hand Limit may not take the Get action. Even if one player skips, the other player's get will not be skipped.

<a id="rule-5-5-4"></a>
**5.5.4** Instead of taking list card 1 to Get Phase, you can add Ultimate Zone's Ultimate Attack·Defense Technique 1 to your hand.

<a id="rule-5-5-5"></a>
**5.5.5** If there is no list card in Get Phase, you cannot retrieve a card from the list, but Get Phase itself will proceed. Even in this case, you can take the action of adding Ultimate Zone's ultimate attack·Defense Technique to your hand.

## 5.6 Recovery Phase

<a id="rule-5-6-1"></a>
**5.6.1** In Recovery Phase, the trigger effect “at the end of the turn” is processed first. Afterwards, the continuous effect for that turn and the “until the end of the turn” effect ends and the turn ends.

---

<a id="chapter-6"></a>
# 6. Effects and Priority

## 6.1 Priority

<a id="rule-6-1-1"></a>
**6.1.1** Priority is the authority to act first when you must act at the same timing.

<a id="rule-6-1-2"></a>
**6.1.2** Priority is compared in the following order.

1. Player with high FP
2. If FP is the same, the player with higher HP
3. If the HP is the same, the player with the most cards

<a id="rule-6-1-3"></a>
**6.1.3** When deciding on Priority again, if FP, HP, and hand are all the same, the previous Priority holder keeps Priority. This rule applies to all Priority re-determinations, not just Get Phase.

## 6.2 Effects to be processed simultaneously

<a id="rule-6-2-1"></a>
**6.2.1** If there are multiple effects to be processed by both sides at one time, the Priority holder takes turns processing one effect at a time. When it's your turn, the player chooses one of the effects he or she can deal with. If the opponent has no effects to process, the same player selects the next effect after the current effect is finished processing.

> [! EXAMPLE]
> If A has Priority and A has 2 atmospheric effects, and B has 3 atmospheric effects, they are processed in `A → B → A → B → B` order. Each turn a player chooses one of their atmospheric effects.

<a id="rule-6-2-2"></a>
**6.2.2** Effects that activate on face-up cards are treated as **Public Trigger**, and effects that activate on face-down cards such as Hidden Information** are treated as **Hidden Trigger**.

<a id="rule-6-2-3"></a>
**6.2.3** If both Public Trigger and Hidden Trigger can be processed at the same timing, the Public Trigger group is processed first. Within each group, it is processed according to Priority and effect selection rules.

## 6.3 Forced and Random Effects

<a id="rule-6-3-1"></a>
**6.3.1** “~” is a forced effect and “may” is a random effect. If a player skips his effect processing turn without using a random effect, he cannot use that effect again during the same timing.

## 6.4 text conflict

<a id="rule-6-4-1"></a>
**6.4.1** When coercive text conflicts, negatives that disable an action, such as “can’t”, take precedence.

<a id="rule-6-4-2"></a>
**6.4.2** If forced text other than the negative form collides, the effect of the Priority holder is applied first. Subsequent effects that conflict with the effect applied first are not applied to the extent of the conflict.

## 6.5 Interruption and waiting effects

<a id="rule-6-5-1"></a>
**6.5.1** An “interruption effect” is an effect designated as an intervention in the card text or official decision. Other triggering effects are processed as waiting effects after the current processing unit ends.`[Need to check notation method]`

> [! WARNING]
> It has not yet been decided what text or icon will identify the interrupt effect in existing cards. Your card review book should provide a classification for each card or add a common notation.

---

<a id="chapter-7"></a>
# 7. battle

The entire flow of the battle, attack, defense, Both Hit / Simultaneous Hit, Clash, Grab are integrated into one procedure.



## Battle processing order

1. Ready card released simultaneously
2. Effect when used
3. Effect before judgment
4. FP applied/consumes all
5. Evasion check
6. Defense check
7. Speed win/loss check
8. Clash OK
9. Grab Special processing such as invalidity
10. Judgment effect: Evasion → Defense → Hit/Counter → Clash → Combo
11. Apply both FP simultaneously
12. Apply damage to both sides simultaneously
13. Check status
14. Effect after judgment
15. Effects after use
16. combo
17. Catch
18. card organization

## speed terminology

| terminology | definition | Mainly used |
| --- | --- | --- |
| print speed | Original speed printed on card | basic information |
| Reference Speed | Speed that reflects the increase/decrease/fixation of card effects and does not reflect FP | Evasion·Defense·Clash conditions, combo connection |
| Final Speed | Final speed reflecting FP in Reference Speed | Attack vs attack speed comparison |

> [! NOTE]
> “Reference Speed” and “Final Speed” are editing terms to clearly distinguish the speed before and after applying FP of the existing rulebook.

## 7.1 Full sequence of battle

<a id="rule-7-1-1"></a>
**7.1.1** The battle is decided as a win, loss, or draw by comparing both techniques.

<a id="rule-7-1-2"></a>
**7.1.2** The battle proceeds in the following order: effect upon use/before judgment, FP speed correction, battle judgment, effect upon judgment, judgment result FP and damage, effect after judgment/after use, combo, Catch.

<a id="rule-7-1-3"></a>
**7.1.3** When used, the effect is processed starting from the Priority holder, and the pre-judgment effect is processed starting from the Priority holder.

<a id="rule-7-1-4"></a>
**7.1.4** Battle decisions are made in the following order: evasion confirmation, defense confirmation, decision win/loss decision, and Clash confirmation. If evasion is established for an attack, no further defense, speed win/loss, or Clash checks are made for that attack.

<a id="rule-7-1-5"></a>
**7.1.5** Grab Special processing that invalidates a decision result, such as invalidation, is declared and processed immediately after confirming a hit or counter decision, but before processing the effect of that decision.

<a id="rule-7-1-6"></a>
**7.1.6** Effects based on combat judgment are applied in the order of evasion, defense, hit/counter, Clash, and combo.

<a id="rule-7-1-7"></a>
**7.1.7** Effects that are activated “when the opponent makes the relevant decision” are processed after the effect of the relevant decision.

<a id="rule-7-1-8"></a>
**7.1.8** Calculate all FP changes according to both judgment results and apply them simultaneously, then calculate both damage and apply them simultaneously.

<a id="rule-7-1-9"></a>
**7.1.9** After the decision, the effect is processed starting from the Priority holder, and after use, the effect is processed starting from the Priority holder.

## 7.2 Speed and FP

<a id="rule-7-2-1"></a>
**7.2.1** The speed of Attack Technique is faster as the number is lower.

<a id="rule-7-2-2"></a>
**7.2.2** When comparing the speed of Attack Technique in battle, all of the player's current FP are applied. It becomes faster by a positive number FP and slower by the absolute value of a negative number FP.

<a id="rule-7-2-3"></a>
**7.2.3** Regardless of whether the ready card is attack or defense, or has a fixed speed, consume all FP you have in battle and set both FPs to 0. Fixed Speed Only speed changes due to FP are not applied to the Technique.

<a id="rule-7-2-4"></a>
**7.2.4** Techniques with fixed speed are not affected by FP and other speed changes that occur after the speed is fixed. If a speed change is applied first and then fixed, the change already applied will not be canceled.

<a id="rule-7-2-5"></a>
**7.2.5** “Fixed at X speed” changes the Technique speed to X and applies the fixed state.

<a id="rule-7-2-6"></a>
**7.2.6** Decrease the speed value for “faster” and increase the speed value for “slower.”If the Technique is not fixed, it will receive FP correction afterwards.

<a id="rule-7-2-7"></a>
**7.2.7** When referring to Technique speed in evasion, defense, Clash conditions, use Reference Speed, which does not apply FP.

<a id="rule-7-2-8"></a>
**7.2.8** The rate may vary above 13 or below 5. If the calculation result is less than 0, the actual speed is treated as 1.

<a id="rule-7-2-9"></a>
**7.2.9** If different Fixed Speed effects conflict, the fixation applied first is maintained in the effect processing order, and subsequent fixations are not applied to the extent of conflict.

> [! EXAMPLE]
> When using a speed 8 attack with +3FP, Final Speed becomes 5. At -4FP, Final Speed becomes 12. Techniques with fixed speed also consume all FP, but this is not reflected in speed.

## 7.3 attack vs attack

<a id="rule-7-3-1"></a>
**7.3.1** If the opponent's Technique does not have an effective defense or evasion that blocks your Attack Level, your attack will hit.

<a id="rule-7-3-2"></a>
**7.3.2** Hit attacks apply hit judgment and related effects and deal damage. If the hit judgment is a combo, proceed with Combo Time.

<a id="rule-7-3-3"></a>
**7.3.3** When comparing Attack Technique, if the opponent's attack's Final Speed is slower or the opponent's attack is avoided with Special Judgment, your attack will be countered.

<a id="rule-7-3-4"></a>
**7.3.4** Counter attacks apply counter judgments and related effects and deal damage. If the counter decision is a combo, proceed with Combo Time.

<a id="rule-7-3-5"></a>
**7.3.5** If the opponent's attack is Final Speed faster than your attack, or if your attack is evaded by the opponent's Special Judgment, your attack will be countered.

<a id="rule-7-3-6"></a>
Attacks that are evaded and countered with **7.3.6** Special Judgment apply the “when evading the opponent” effect and do not cause damage.

<a id="rule-7-3-7"></a>
**7.3.7** Countered techniques are treated as decision losses.

<a id="rule-7-3-8"></a>
**7.3.8** “Functions conditioned on invalidation” that do not activate when countered only refer to phrases that explicitly state invalidity as a condition, such as “if this card has not been invalidated.”

<a id="rule-7-3-9"></a>
**7.3.9** Avoid the opponent's attack with your own attack Special Judgment, and if the attack is successful, a counter judgment is applied rather than a hit.

## 7.4 Offense vs. Defense

<a id="rule-7-4-1"></a>
**7.4.1** Defense Technique's defense or evasion position decision must match the opponent's attack position decision for the decision to be valid.

<a id="rule-7-4-2"></a>
**7.4.2** If the defense position of the defense card matches the opponent's Attack Level, it defends. The effect is applied when defending and does not apply opponent attack damage.

<a id="rule-7-4-3"></a>
**7.4.3** If the defense card's evasion position matches the opponent's Attack Level, evade. When evading, the effect is applied and the opponent's attack damage is not applied.

<a id="rule-7-4-4"></a>
**7.4.4** If the defense position of the opponent's card matches your Attack Level, your attack is blocked. The “when the opponent defends” effect is applied, no damage is inflicted, and the guard decision is applied to FP.

<a id="rule-7-4-5"></a>
**7.4.5** If the evasion position of the opponent's card matches your Attack Level, your attack will be evaded. The effect “when evading the opponent” is applied and no damage is inflicted.

<a id="rule-7-4-6"></a>
**7.4.6** If there is no valid defense decision that matches the opponent's Attack Level, the defense card is hit and no defense or evasion effects are applied.

## 7.5 Draw and Clash

<a id="rule-7-5-1"></a>
**7.5.1** After FP correction between Attack Technique, if Final Speed is the same, it becomes Both Hit / Simultaneous Hit.

<a id="rule-7-5-2"></a>
**7.5.2** In Both Hit / Simultaneous Hit, the hit-related effects of both attacks are processed in the order of Priority. After that, both FP changes are applied simultaneously, and then both damage is applied simultaneously.

<a id="rule-7-5-3"></a>
**7.5.3** If the attack or Clash judgment of Defense Technique meets the conditions, the battle is processed as Clash.

<a id="rule-7-5-4"></a>
**7.5.4** An attack Clash occurs when the position of Clash of Attack Technique is the same as the opponent's Attack Level and your attack speed is slower than the opponent's attack.

<a id="rule-7-5-5"></a>
**7.5.5** If the Clash position of Defense Technique is the same as the opponent's Attack Level, defense Clash occurs.

<a id="rule-7-5-6"></a>
**7.5.6** The restriction “If the speed of a Technique with Clash judgment is the same or faster than the opponent’s Technique, it will not be activated” only applies to Clash of Attack Technique. Speed ​​comparison is not applied to Clash of Defense Technique.

<a id="rule-7-5-7"></a>
**7.5.7** When Clash, the hit effect of both attacks is processed, and then when Clash, the effect is processed. Next, the FP of the judgment result is applied simultaneously, and the HP of the side with lower damage is reduced by the difference between the attack damage of both sides.

<a id="rule-7-5-8"></a>
**7.5.8** The damage of Defense Technique is calculated as 0, and Defense Technique is treated as if there is no hit judgment.

<a id="rule-7-5-9"></a>
**7.5.9** If both sides use Defense Technique, the effect is not applied when hitting, countering, defending, or evading. When used, only effects that satisfy the conditions are processed, regardless of the judgment result, such as before, after, or after judgment.

<a id="rule-7-5-10"></a>
**7.5.10** If both attacks evade each other, the battle is a draw, and the trigger effect from evasion is processed and the damage from the evaded attack is not applied.

<a id="rule-7-5-11"></a>
**7.5.11** “Defending each other” only means when both players have used Defense Technique Card. This battle is a draw and the effect does not activate when defending.

## 7.6 Judgment result FP

<a id="rule-7-6-1"></a>
**7.6.1** Attack Technique shows the increase/decrease value of FP according to the hit, blocked, and counter results, respectively.

## 7.7 damage

<a id="rule-7-7-1"></a>
**7.7.1** When Attack Technique hits or counters, the opponent's HP is reduced by the amount of damage indicated on the card.

<a id="rule-7-7-2"></a>
**7.7.2** The Guard Damage inflicted upon a successful defense is the damage caused by that Defense Technique Card, and is treated as damage inflicted on the owner of the card. Therefore, the condition “when you suffer damage” is satisfied, but the condition “when the opponent inflicts damage” is not satisfied.

## 7.8 Summary of used cards

<a id="rule-7-8-1"></a>
**7.8.1** Techniques used in battle are returned to the hand in the order in which they were used. Both ready cards are treated as if the Priority holder's card was used first. Combo·Catch cards are sent to the list, and cards with Break effects are sent to Break Zone.

## 7.9 Special Judgment and Grab

<a id="rule-7-9-1"></a>
**7.9.1** Special Judgment is a special judgment of the card and has keywords such as avoidance, Clash, and Grab.

<a id="rule-7-9-2"></a>
**7.9.2** When applying the hit/counter judgment of the opponent's Grab technique, you can nullify Grab by Break the Grab technique 1 in your hand.

<a id="rule-7-9-3"></a>
**7.9.3** If Grab is invalidated, return both Ready cards to the hand without processing the remainder, and proceed with Ready Phase again in the same turn. Effects and FP changes that have already been processed upon use will not be reversed.

> [! IMPORTANT]
> Grab Invalidation does not rewind the entire battle. The use effect and FP that have already been processed are maintained, and only judgment effects and damage that have not yet been processed are stopped.

---

<a id="chapter-8"></a>
# 8. combo

A combo is a continuous attack sequence that begins with a hit or counter combo roll or card effect.



## Combo Correction Table

| combo number | Connection conditions | Damage Correction |
| --- | --- | ---: |
| 1Combo | The first card specified by the attack or effect that caused the combo | 0 |
| 2Combo | Random legal attacks in basic combos | -100 |
| 3Combo | The speed value is exactly 1 greater than the 2 combo. | -200 |
| 4combo or more | The speed value is exactly 1 higher than the previous card. | Add every time the combo number increases to 1 -100 |

## 8.1 Combo entry and legality

<a id="rule-8-1-1"></a>
**8.1.1** If an attack that is a combo judgment hits or is countered, the attack becomes a 1 combo and starts Combo Time.

<a id="rule-8-1-2"></a>
**8.1.2** Cards presented in a combo must actually be usable after the previous cards have been processed. If an illegal declaration is made, the card is treated as unused and returned to the hand, and another legal card can be presented again during the same combo phase.

<a id="rule-8-1-3"></a>
**8.1.3** Cards not used due to illegal combo declarations are returned to Hidden Information in the hand, but the information that has already been revealed does not disappear.`[Edit Codification]`

## 8.2 Combo common processing

<a id="rule-8-2-1"></a>
**8.2.1** Combo cards are processed in the order of use, combo, damage processing, and post-use effects.

<a id="rule-8-2-2"></a>
**8.2.2** Cards used in combos are not subject to hit/counter judgments.

<a id="rule-8-2-3"></a>
**8.2.3** The 2 combo reduces card damage by 100, the 3 combo reduces card damage by 200, and each time the number of combos increases by one, the card damage decreases by 100.

<a id="rule-8-2-4"></a>
**8.2.4** After processing the effect during a combo, if the damage is less than 0 as a result of damage compensation, the technique cannot be used in the combo.

<a id="rule-8-2-5"></a>
**8.2.5** All cards used in the combo, including the 1 combo, are sent to the list at the end of the combo.

<a id="rule-8-2-6"></a>
**8.2.6** Once Combo Time starts, that Battle Phase's Catch opportunity is gone. When Combo Time is terminated, Battle Phase is terminated immediately.

<a id="rule-8-2-7"></a>
**8.2.7** Cancellation of use of cards whose damage has become 0 or less after processing the effect during a combo, reversal of already processed effects, and reselection range require additional official decisions. Until then, only the conclusion that the card cannot be used is applied.`[Confirmation required]`

> [! WARNING]
> 0 It has not yet been confirmed whether the effect of a card whose damage has become less than that will be reversed, whether the card will be returned to the hand, or whether another card can be played again.

## 8.3 Basic combo connection

<a id="rule-8-3-1"></a>
**8.3.1** After the 1 combo, the player can either end Combo Time, or present a random attack card from their hand and an attack card with a speed value exactly 1 greater than that card in order. If you present two cards, they become 2 combo and 3 combo, respectively.

<a id="rule-8-3-2"></a>
**8.3.2** If you cannot present both the 2 combo and the 3 combo that can be used legally, Combo Time will end.

<a id="rule-8-3-3"></a>
**8.3.3** After the 3 combo, you can continue to use one attack card with a speed value 1 higher than the previous combo card.

## 8.4 Combo special handling

<a id="rule-8-4-1"></a>
**8.4.1** Even if there are no cards to use in the 2·3 combo, Combo Time starts, and the 1 combo card is sent to the list at the end.

<a id="rule-8-4-2"></a>
**8.4.2** When Combo Time ends, both FPs are set to 0.

<a id="rule-8-4-3"></a>
**8.4.3** When you enter Combo Time with an effect other than a hit/counter, you can present two attack cards that meet the conditions in order and use them as a 1 combo and 2 combo, respectively. If you cannot present both cards, end Combo Time without using any cards.

<a id="rule-8-4-4"></a>
**8.4.4** If a card is used in a combo by handling it at a certain speed, the next card must be a card with a value 1 greater than that handling speed.

<a id="rule-8-4-5"></a>
**8.4.5** If the speed of Attack Technique changes due to a card effect during a combo, the next combo is connected based on the changed speed.

<a id="rule-8-4-6"></a>
**8.4.6** If Break occurs during combo processing, the combo is paused and the combo is resumed after completing Break and immediate replenishment processing. However, the pair of 2 combo and 3 combo must be a combination in which both cards can be used legally.

<a id="rule-8-4-7"></a>
**8.4.7** 2 combo and 3 combo are presented together, but used in order. Even after applying the processing results of the 2combo, the 3combo must be legally usable, and otherwise, combinations cannot be presented from the beginning.

<a id="rule-8-4-8"></a>
**8.4.8** When a new effect is triggered during a combo, if the effect is classified as “interrupting” by card or official judgment, it will stop current processing and be processed immediately. Normal trigger effects are processed after the current effect's processing unit ends.

<a id="rule-8-4-9"></a>
**8.4.9** When presenting the 2 combo and the 3 combo together, the mandatory effect of the 2 combo must be applied and then the 3 combo must be combined to satisfy both usage conditions and connection speed.

> [! WARNING]
> If a legally declared 2·3 combo becomes illegal due to an unexpected intervention effect, additional decisions may be made for each card to determine which cards are returned.

## 8.5 Both Hit / Simultaneous Hit·Clash combo

<a id="rule-8-5-1"></a>
**8.5.1** If both Both Hit / Simultaneous Hit attacks are considered combos, each player's 1 combo is considered to have already been confirmed. Effects are processed in Priority order, damage is applied simultaneously, and one side's HP is treated as if it reached 0 first, so the other side's 1 combo is not interrupted. Each side only processes the 1 combo and ends Combo Time.

<a id="rule-8-5-2"></a>
**8.5.2** If both Clash attacks are considered combos, each player only processes the 1 combo and ends Combo Time.

---

<a id="chapter-9"></a>
# 9. Catch

Catch is an automatic hit attack that occurs at the end of the battle due to the FP status or card effect.



## Catch Type

| type | condition | card to use |
| --- | --- | --- |
| Positive number FP Catch | self FP > 0, opponent FP = 0 | An attack whose speed value is less than FP |
| Negative FP Catch | self FP = 0, opponent FP < 0 | An attack whose speed value is less than the absolute value of FP lost by the opponent. |
| Effect Catch | Card effect indicates Catch | Attack under the conditions determined by the effect |

## 9.1 Catch Condition

<a id="rule-9-1-1"></a>
**9.1.1** Catch can be progressed by satisfying the conditions before the end of Battle Phase after all Techniques in the battle have processed their effects after use.

<a id="rule-9-1-2"></a>
**9.1.2** If your FP is greater than 0 and your opponent's FP is 0, you can use Attack Technique with a speed value less than FP in your hand to Catch.

<a id="rule-9-1-3"></a>
**9.1.3** If your FP is 0 and the opponent's FP is less than 0, you can use Attack Technique in your hand with a speed value less than the absolute value of the opponent's lost FP to Catch.

<a id="rule-9-1-4"></a>
**9.1.4** When a card effect tells you to “Catch,” use Attack Technique that satisfies the conditions specified by the effect to Catch.

## 9.2 Catch Processing

<a id="rule-9-2-1"></a>
**9.2.1** If Catch is performed, both FPs are set to 0.

<a id="rule-9-2-2"></a>
**9.2.2** The attack used in Catch automatically hits and the hit judgment and related effects are applied. Catch attacks cannot be blocked by defense, evasion, or Clash other than Grab nullification. If the hit judgment is a combo, it enters Combo Time.

<a id="rule-9-2-3"></a>
**9.2.3** Catch cards are processed in the order of use, Catch, hit, damage processing, and post-use effect, and the effect before the decision is not applied.

<a id="rule-9-2-4"></a>
**9.2.4** Attack cards used in Catch are sent to the list at the end of Battle Phase.

## 9.3 Continuation Catch and special situations

<a id="rule-9-3-1"></a>
**9.3.1** When a player starts Catch, only that player has Catch rights during that Catch time. Even after Catch ends, if the conditions are met again, the same player can continue Catch.

<a id="rule-9-3-2"></a>
**9.3.2** Even if you use a Catch Grab attack, your opponent can nullify the attack by Break a Grab card in his hand.

<a id="rule-9-3-3"></a>
**9.3.3** If Grab used with Catch is invalidated, the original battle damage, FP, and card movement results are maintained. Return only the invalidated Catch card to your hand and proceed with Ready Phase again in the same turn.

<a id="rule-9-3-4"></a>
**9.3.4** Catch due to the effect is processed first regardless of FP. After that, Catch by FP can be additionally declared if possible.

<a id="rule-9-3-5"></a>
**9.3.5** If both can Catch, then the Priority holder does Catch first. When that player starts Catch, the opponent's Catch rights are lost until the Catch time runs out. If Grab is invalidated, etc., and you proceed with Ready Phase again, this limitation will disappear.

---

<a id="chapter-10"></a>
# 10. Zone movement and Break

## 10.1 Zone movement and discard

<a id="rule-10-1-1"></a>
**10.1.1** Break cards are sent to Break Zone.

<a id="rule-10-1-2"></a>
**10.1.2** “discard” means placing a card from your hand face up on the list, and is different from Break.

## 10.2 Supplementary with Break

<a id="rule-10-2-1"></a>
**10.2.1** If an attack or Defense Technique is Break in the hand, list, Lumen Zone, Battle Zone, supplementary processing is inserted immediately thereafter. The owner of that card can place Side Deck's attack or Defense Technique 1 card face up on the list. If there is no suitable card or the move is not possible, it is not replenished.

<a id="rule-10-2-2"></a>
**10.2.2** Break Techniques are generally no longer available in that game.



<a id="rule-10-2-4"></a>
**10.2.4** When the ultimate attack·Defense Technique becomes Break, it can be replenished from the list from Side Deck in the same way as the normal attack·Defense Technique.

> [! EXAMPLE]
> If the list already has 14 cards, the moment the card you were trying to replenish is about to be moved to the list, that card will be Break instead. This card has been Break from Side Deck, so no further replenishment will occur.

## 10.3 Illegal movement of Special Technique

<a id="rule-10-3-1"></a>
**10.3.1** If Special Technique Card attempts to move to the hand or list, that move is replaced with a move to Break Zone.

<a id="rule-10-3-2"></a>
**10.3.2** Even if Special Technique Card becomes Break, cards are not replenished from Side Deck to the list.

<a id="rule-10-3-3"></a>
**10.3.3** Ultimate Special Technique can only exist in Side Deck, Lumen Zone, Ultimate Zone, and Break Zone. If you try to move to another zone, it is replaced with Break Zone movement.

---

<a id="chapter-11"></a>
# 11. Special Technique and Ultimate Technique

## 11.1 Special Technique

<a id="rule-11-1-1"></a>
**11.1.1** To use Special Technique, proceed in the following order: check conditions, reveal card, place Lumen Zone, and process effect. Special Technique that does not meet the conditions cannot be released or deployed.

<a id="rule-11-1-2"></a>
**11.1.2** Special Technique Card can only exist in Side Deck, Lumen Zone, Ultimate Zone, and Break Zone and cannot be added to the hand.

## 11.2 Ultimate Technique

<a id="rule-11-2-1"></a>
**11.2.1** Ultimate Technique Card can adopt 0 or 1 cards in the deck, and reveal them face up at Ultimate Zone at the start of the game. The protector uses the same thing as the other Technique Card.

<a id="rule-11-2-2"></a>
**11.2.2** The Ultimate Attack·Defense Technique is added to the hand and then processed according to the same rules as the Normal Attack·Defense Technique. Even after use, the actual movement results, such as cards, lists, Break Zone, are maintained and do not automatically return to Ultimate Zone.

<a id="rule-11-2-3"></a>
**11.2.3** When the conditions are met, Ultimate Special Technique is placed on Lumen Zone, etc. according to the procedure indicated on the card, and cannot be added to the hand.

<a id="rule-11-2-4"></a>
**11.2.4** When the ultimate attack·Defense Technique is sent to the list, it remains in the list the same as the normal attack·Defense Technique.

<a id="rule-11-2-5"></a>
**11.2.5** If Ultimate Special Technique is sent to Side Deck, it is placed in Side Deck.

---

<a id="chapter-12"></a>
# 12. Game End and Special Situations

## 12.1 Defense Over

<a id="rule-12-1-1"></a>
**12.1.1** If all of the following four items are missing in three consecutive Battle Phase, Defense Over occurs.

- Use Attack Technique
- Damage occurs
- FP Variation
- Effect activated

If any of the four items occurs, the continuation count is initialized to 0. Even if the effect did not change the actual state, if there was an “effect activation”, it is reset.

<a id="rule-12-1-2"></a>
**12.1.2** If Defense Over occurs, both Battle Zone techniques are Break performed. The general Break supplementary rules also apply to this Break. If the same stagnation continues after the fourth time, it will be processed again for each battle.

## 12.2 Sudden Death

<a id="rule-12-2-1"></a>
**12.2.1** If both players' HP is below 0 at the end of the same effect or same judgment result processing unit, it is assumed that both players' HP has reached 0 at the same time and proceed with Sudden Death.

<a id="rule-12-2-2"></a>
**12.2.2** When Sudden Death is reached, reconfigure the hand, list, and Side Deck using the same procedure as normal new game preparation. However, the starting HP of both sides is 1000, and the starting hand is made up of the same number of HP 1000 as Hand Limit.

<a id="rule-12-2-3"></a>
**12.2.3** Sudden Death's initial cards and lists also follow the general preparation procedure of mutual confirmation and disclosure. Only the initial number of cards is changed from 5 to Hand Limit in HP 1000.

<a id="rule-12-2-4"></a>
**12.2.4** Sudden Death When starting, both FPs are set to 0.

<a id="rule-12-2-5"></a>
**12.2.5** Sudden Death proceeds from Lumen Phase to 3 turns with the existing Priority holder maintaining Priority. At the end of the 3 turn, the player with higher HP wins, and if the HP is the same, it is a draw.

<a id="rule-12-2-6"></a>
**12.2.6** In Sudden Death state, if both sides' HP becomes 0 at the same time again, the game is treated as a draw.

---

<a id="appendix-a"></a>
# Appendix A. Glossary

| terminology | definition |
| --- | --- |
| Public Trigger | Effects that activate on face-up cards, etc. Public Information |
| function | Card description without number. Always applied in all zones without separate activation |
| Interrupt | Officially designated processing to stop the current effect's processing unit and process it first. |
| Damage Correction | Processing to further reduce card damage by 100 depending on the combo number |
| Ready | A declaration that places Technique Card face down on Battle Zone and confirms the selection. |
| list | A zone where up to 14 public Technique Card are placed.“discard” moves from hand to list. |
| Break | Sending a card to Break Zone to prevent it from being normally reused in that game |
| Hidden Trigger | Effects that activate in Hidden Information, such as Side Deck |
| use | Present the card according to the relevant procedure and start processing the effects when used. |
| Clash | Attack or Defense Technique's Clash roll to apply both hits and deal with the damage difference, resulting in a draw. |
| speed figures | A number representing the speed of Attack Technique. The lower the faster |
| Reference Speed | Speed that reflects speed change/fixation due to effects and does not reflect FP |
| Final Speed | Final speed reflecting FP in Reference Speed |
| processing unit | Scope of processing a single effect or a set of values applied simultaneously from start to finish |
| Catch | At the end of the battle, an automatic hit attack performed under FP or effect conditions. |
| Combo Time | The procedure of entering a combo judgment or card effect and using an attack followed by a speed value. |
| Priority | When both sides act at the same timing, the authority to select and process the effect first |
| effect | Numbered card description.“I should” is mandatory, “I can” is arbitrary. |

---

<a id="appendix-b"></a>
# Appendix B. Quick Reference Table

## flow of one turn

`Lumen → Ready → Battle → Get → Recovery`

| phase | key actions |
| --- | --- |
| lumen | Lumen Phase Effect processing |
| Ready | Description 1Select sheet, place back, declare ready |
| battle | Reveal, Judgment, Effect, Combo, Catch |
| get | Obtain List Card or Ultimate Attack/Defense |
| recovery | Continuous effect ends after triggering at end of turn |

## Battle processing order

`Reveal → When used → Before judgment → FP → Evasion → Defense → Speed win or loss → Clash → Special processing → Judgment effect → FP → Damage → Check status → After judgment → After use → Combo → Catch → Summary`

## Key results by card combination

| yourself\opponent | attack | defense |
| --- | --- | --- |
| attack | Check evasion → Compare speed → Clash. If the faster one is equal to the counter, Both Hit / Simultaneous Hit | If it matches the opponent Defense Level, it will block/evade, otherwise it will hit. |
| defense | If your Defense Level matches the opponent's attack, you will block/evade. If it does not match, you will be hit. | Both Defense. Process only effects unrelated to judgment results |

> [! IMPORTANT]
> At the end of each effect or batch of simultaneous stat, check your HP 0 and loss cap. Once the combo starts, the Catch chance for that battle disappears.

---

<a id="appendix-c"></a>
# Appendix C. Edit Checklist

The following items must be finalized prior to issuance of formal comprehensive rules:

- [ ] **Document priority:** Correct priority and standard language for errata, card rulings, card text, comprehensive rules, primers, and examples
- [ ] **Public Information:** Whether the contents, number of copies, and order of cards, Lumen Zone, Break Zone, and Side Deck are disclosed by zone
- [ ] **Interrupt Classification:** A list of common phrases, icons, or card-specific rolls to identify which card effects are interrupts.
- [ ] **0 Damage Combo:** Whether or not to revert the effect of a card whose damage has become 0 or less after the effect has been processed during the combo, to return to the hand, to reselect, and to end the combo.
- [ ] **Exception among 2·3 combos:** Revert range when legally declared 2·3 combos become illegal due to unexpected intervention
- [ ] **Standard virtual Technique:** Attack/defense type, position judgment, and speed values of the virtual Technique used when no response is made.

---

<a id="appendix-t"></a>
# Appendix T. Competition/Operating Regulations

Competition progress, participant roles, time limit, Failure to Respond, result reporting, tardiness, Time Extension, and penalties are confirmed based on a separate document, [Lumen Condenser Floor rules](/rules/tournament/).

This comprehensive rulebook covers the core rules of card and game handling, and any judgment regarding tournament operation should be made in conjunction with floor rules and tournament-specific notices.

## T.1 Go to floor rules

- [Competition floor rules](/rules/tournament/)
- [Win/loss decision and Failure to Respond](/rules/tournament/#floor-win-and-no-response)
- [Competition time limit and timeout processing](/rules/tournament/#floor-match-time)
- [Report results, surrender, abstain, be late](/rules/tournament/#floor-participation)
- [penalty](/rules/tournament/#floor-penalties)

---

# Revision history

| version | base date | Highlights | status |
| --- | --- | --- | --- |
| v0.1 | 2026-08-13 | Integration of 65 rule inventories and formal decisions from existing rulebooks | review draft |
| v0.1-web | 2026-08-24 | Markdown for web editing, adding reliable rule anchors and visualization instructions | review draft |
