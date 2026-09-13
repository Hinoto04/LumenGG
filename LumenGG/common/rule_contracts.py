import re
from collections import defaultdict

from django.utils.html import strip_tags

from .models import Rule


REFERENCE_TOKEN_RE = re.compile(r'\[\[([^\[\]]+?)\]\]')
NUMBERED_RULE_KEY_RE = re.compile(r'^(?:rule|floor)-\d+(?:-\d+)+$')
SOURCE_SECTION_KEY_RE = re.compile(r'^(?:chapter-\d+|appendix-[a-z]+)$')


# Each entry declares another rule whose definition, procedure, or exception is
# needed to interpret the source rule. Parent rules are intentionally omitted:
# the parent relationship already supplies lexical scope.
COMPREHENSIVE_RULE_DEPENDENCIES = {
    'rule-0-2-2': ('rule-0-2-1',),
    'rule-contract-unit': ('rule-reference-key', 'rule-scope-inheritance', 'rule-dependency-resolution'),
    'rule-reference-key': ('rule-contract-unit',),
    'rule-scope-inheritance': ('rule-contract-unit', 'rule-6-4-1', 'rule-6-4-2'),
    'rule-dependency-resolution': ('rule-contract-unit', 'rule-0-3-1', 'rule-6-5-1'),
    'rule-normative-clause-contract': ('rule-contract-unit', 'rule-6-3-1'),

    'rule-3-2-2': ('rule-3-2-1', 'rule-card-character-information', 'rule-2-1-8'),
    'rule-3-2-3': ('rule-3-2-2', 'rule-1-2-1', 'rule-0-3-1', 'rule-10-1-2'),
    'rule-3-2-4': ('rule-3-2-1', 'rule-card-common-information'),
    'rule-game-object-card': ('rule-game-area-common-rules',),
    'rule-card-common-information': ('rule-3-2-1', 'rule-game-area-common-rules'),
    'rule-card-character-information': ('rule-3-2-2', 'rule-2-1-4'),
    'rule-3-3-1': ('rule-card-common-information', 'rule-2-1-5', 'rule-4-1-1'),
    'rule-3-3-2': ('rule-3-3-1', 'rule-4-1-1'),
    'rule-3-4-1': ('rule-card-common-information', 'rule-2-1-6', 'rule-7-2-1', 'rule-7-7-1'),
    'rule-3-4-2': ('rule-card-common-information', 'rule-2-1-6', 'rule-7-4-1'),
    'rule-11-1-1': ('rule-card-common-information', 'rule-6-1-1', 'rule-10-3-1'),
    'rule-11-1-2': ('rule-2-1-2', 'rule-2-1-7', 'rule-2-1-9', 'rule-2-1-3', 'rule-10-3-1'),
    'rule-11-2-1': ('rule-3-5-1', 'rule-2-1-9'),
    'rule-11-2-2': ('rule-11-2-1', 'rule-1-2-1', 'rule-2-1-1', 'rule-2-1-3'),
    'rule-11-2-3': ('rule-11-1-1', 'rule-11-2-1', 'rule-10-3-3'),
    'rule-11-2-4': ('rule-11-2-2', 'rule-2-1-1'),
    'rule-11-2-5': ('rule-11-2-3', 'rule-2-1-2'),

    'rule-game-area-common-rules': ('rule-3-2-1', 'rule-game-object-card', 'rule-2-2-1'),
    'rule-2-1-4': ('rule-card-character-information', 'rule-4-1-1', 'rule-2-2-1'),
    'rule-2-1-5': ('rule-3-3-1', 'rule-4-1-1', 'rule-2-2-1'),
    'rule-1-2-1': ('rule-3-2-2', 'rule-3-2-3', 'rule-2-2-1', 'rule-10-1-2'),
    'rule-2-1-1': ('rule-5-3-1', 'rule-10-2-1', 'rule-2-2-1'),
    'rule-2-1-2': ('rule-3-5-1', 'rule-4-1-4', 'rule-2-2-1'),
    'rule-2-1-6': ('rule-5-3-1', 'rule-5-4-1', 'rule-2-2-1'),
    'rule-2-1-7': ('rule-11-1-1', 'rule-2-2-1'),
    'rule-2-1-9': ('rule-11-2-1', 'rule-5-5-4', 'rule-2-2-1'),
    'rule-2-1-3': ('rule-10-1-1', 'rule-10-2-1', 'rule-2-2-1'),
    'rule-2-1-8': ('rule-3-2-2', 'rule-6-1-2', 'rule-7-2-2', 'rule-2-2-1'),
    'rule-2-2-1': ('rule-3-2-2', 'rule-card-common-information', 'rule-6-1-2'),

    'rule-3-1-1': ('rule-3-5-1',),
    'rule-3-5-1': ('rule-card-character-information', 'rule-3-3-1', 'rule-3-4-1', 'rule-3-4-2', 'rule-11-1-1', 'rule-11-2-1'),
    'rule-3-5-2': ('rule-3-5-1', 'rule-6-4-1'),
    'rule-3-5-3': ('rule-card-common-information', 'rule-3-5-1'),
    'rule-3-5-4': ('rule-card-common-information', 'rule-3-5-1'),
    'rule-3-5-5': ('rule-card-common-information', 'rule-3-5-1'),
    'rule-3-5-6': ('rule-card-character-information', 'rule-3-3-1', 'rule-3-5-1'),
    'rule-4-1-1': ('rule-2-1-4', 'rule-2-1-5', 'rule-2-1-9'),
    'rule-4-1-2': ('rule-6-1-1',),
    'rule-4-1-3': ('rule-1-2-1', 'rule-2-1-1', 'rule-3-5-1'),
    'rule-4-1-4': ('rule-2-1-2', 'rule-4-1-3'),
    'rule-4-1-5': ('rule-2-1-1', 'rule-4-1-3', 'rule-2-2-1'),
    'rule-4-1-6': ('rule-1-2-1', 'rule-2-2-1'),

    'rule-5-1-2': ('rule-5-2-1', 'rule-5-3-1', 'rule-5-4-1', 'rule-5-5-1', 'rule-5-6-1'),
    'rule-5-2-1': ('rule-6-1-1', 'rule-6-2-1'),
    'rule-5-3-1': ('rule-1-2-1', 'rule-2-1-6'),
    'rule-5-4-1': ('rule-2-1-6', 'rule-7-1-2'),
    'rule-5-4-2': ('rule-7-8-1', 'rule-8-2-5', 'rule-9-2-4', 'rule-10-1-1'),
    'rule-5-5-1': ('rule-6-1-2', 'rule-6-2-1'),
    'rule-5-5-2': ('rule-6-1-1', 'rule-2-1-1', 'rule-1-2-1'),
    'rule-5-5-3': ('rule-3-2-2', 'rule-3-2-3'),
    'rule-5-5-4': ('rule-2-1-9', 'rule-11-2-2'),
    'rule-5-5-5': ('rule-2-1-1', 'rule-5-5-4'),
    'rule-5-6-1': ('rule-6-2-1', 'rule-0-3-1'),

    'rule-1-1-1': ('rule-3-2-2', 'rule-0-3-1', 'rule-12-2-1'),
    'rule-12-2-1': ('rule-1-1-1', 'rule-0-3-1', 'rule-12-2-2'),
    'rule-12-2-2': ('rule-4-1-1', 'rule-3-2-2'),
    'rule-12-2-3': ('rule-12-2-2', 'rule-4-1-5', 'rule-4-1-6'),
    'rule-12-2-4': ('rule-12-2-2', 'rule-2-1-8'),
    'rule-12-2-5': ('rule-12-2-2', 'rule-6-1-1', 'rule-5-1-2'),
    'rule-12-2-6': ('rule-12-2-1', 'rule-12-2-5'),

    'rule-1-3-1': ('rule-card-common-information', 'rule-6-4-1'),
    'rule-1-3-2': ('rule-card-common-information', 'rule-0-3-1', 'rule-6-3-1'),
    'rule-1-3-3': ('rule-3-2-4', 'rule-card-common-information'),
    'rule-0-3-1': ('rule-1-3-2', 'rule-6-5-1'),
    'rule-0-3-2': ('rule-0-3-1', 'rule-1-1-1', 'rule-3-2-3'),
    'rule-0-3-3': ('rule-0-3-1', 'rule-6-5-1'),
    'rule-6-1-1': ('rule-3-2-2',),
    'rule-6-1-2': ('rule-6-1-1', 'rule-2-1-8', 'rule-3-2-2'),
    'rule-6-1-3': ('rule-6-1-2',),
    'rule-6-2-1': ('rule-6-1-1', 'rule-0-3-1', 'rule-6-3-1'),
    'rule-6-2-2': ('rule-card-common-information', 'rule-2-2-1'),
    'rule-6-2-3': ('rule-6-2-1', 'rule-6-2-2'),
    'rule-6-3-1': ('rule-1-3-2', 'rule-6-2-1'),
    'rule-6-4-1': ('rule-0-2-2',),
    'rule-6-4-2': ('rule-0-2-2', 'rule-6-1-1'),
    'rule-6-5-1': ('rule-0-3-1', 'rule-0-3-3'),

    'rule-7-1-1': ('rule-5-4-1',),
    'rule-7-1-2': ('rule-1-3-2', 'rule-6-1-1', 'rule-7-2-2', 'rule-7-6-1', 'rule-7-7-1', 'rule-8-1-1', 'rule-9-1-1'),
    'rule-7-1-3': ('rule-6-1-1', 'rule-6-2-1'),
    'rule-7-1-4': ('rule-7-3-1', 'rule-7-4-1', 'rule-7-5-3'),
    'rule-7-1-5': ('rule-7-9-2', 'rule-0-3-1'),
    'rule-7-1-6': ('rule-6-2-1', 'rule-8-1-1'),
    'rule-7-1-7': ('rule-6-2-1',),
    'rule-7-1-8': ('rule-7-6-1', 'rule-7-7-1', 'rule-0-3-1'),
    'rule-7-1-9': ('rule-6-1-1', 'rule-6-2-1'),
    'rule-7-2-2': ('rule-7-2-1', 'rule-2-1-8'),
    'rule-7-2-3': ('rule-2-1-8', 'rule-7-2-4'),
    'rule-7-2-4': ('rule-7-2-5', 'rule-7-2-6'),
    'rule-7-2-5': ('rule-7-2-4',),
    'rule-7-2-6': ('rule-7-2-1', 'rule-7-2-4'),
    'rule-7-2-7': ('rule-7-2-2', 'rule-7-4-1', 'rule-7-5-3'),
    'rule-7-2-8': ('rule-7-2-1',),
    'rule-7-2-9': ('rule-7-2-4', 'rule-6-4-2'),
    'rule-7-3-1': ('rule-7-4-1',),
    'rule-7-3-2': ('rule-7-7-1', 'rule-8-1-1'),
    'rule-7-3-3': ('rule-7-2-2', 'rule-7-9-1'),
    'rule-7-3-4': ('rule-7-7-1', 'rule-8-1-1'),
    'rule-7-3-5': ('rule-7-2-2', 'rule-7-9-1'),
    'rule-7-3-6': ('rule-7-3-5', 'rule-7-7-1'),
    'rule-7-3-7': ('rule-7-3-5', 'rule-7-1-1'),
    'rule-7-3-8': ('rule-1-3-1', 'rule-7-3-3'),
    'rule-7-3-9': ('rule-7-3-3', 'rule-7-9-1'),
    'rule-7-4-1': ('rule-3-4-2', 'rule-3-4-1', 'rule-7-2-7'),
    'rule-7-4-2': ('rule-7-4-1', 'rule-7-7-1'),
    'rule-7-4-3': ('rule-7-4-1', 'rule-7-7-1'),
    'rule-7-4-4': ('rule-7-4-2', 'rule-7-6-1'),
    'rule-7-4-5': ('rule-7-4-3',),
    'rule-7-4-6': ('rule-7-4-1', 'rule-7-7-1'),
    'rule-7-5-1': ('rule-7-2-2', 'rule-7-1-8'),
    'rule-7-5-2': ('rule-7-5-1', 'rule-6-1-1', 'rule-7-1-8'),
    'rule-7-5-3': ('rule-7-9-1', 'rule-7-2-7'),
    'rule-7-5-4': ('rule-7-5-3', 'rule-7-2-2'),
    'rule-7-5-5': ('rule-7-5-3',),
    'rule-7-5-6': ('rule-7-5-4', 'rule-7-5-5'),
    'rule-7-5-7': ('rule-7-5-3', 'rule-7-1-8', 'rule-7-7-1'),
    'rule-7-5-8': ('rule-3-4-2', 'rule-7-7-1'),
    'rule-7-5-9': ('rule-3-4-2', 'rule-6-2-1'),
    'rule-7-5-10': ('rule-7-4-3', 'rule-7-1-1'),
    'rule-7-5-11': ('rule-7-5-9', 'rule-7-1-1'),
    'rule-7-6-1': ('rule-3-4-1', 'rule-2-1-8'),
    'rule-7-7-1': ('rule-3-4-1', 'rule-3-2-2'),
    'rule-7-7-2': ('rule-7-4-2', 'rule-card-common-information', 'rule-3-2-2'),
    'rule-7-8-1': ('rule-1-2-1', 'rule-2-1-1', 'rule-2-1-3', 'rule-6-1-1'),
    'rule-7-9-1': ('rule-card-common-information',),
    'rule-7-9-2': ('rule-7-9-1', 'rule-10-1-1'),
    'rule-7-9-3': ('rule-7-9-2', 'rule-5-3-1', 'rule-2-1-8'),

    'rule-8-1-1': ('rule-7-3-2', 'rule-7-3-4'),
    'rule-8-1-2': ('rule-1-2-1', 'rule-card-common-information'),
    'rule-8-1-3': ('rule-8-1-2', 'rule-2-2-1'),
    'rule-8-2-1': ('rule-6-2-1', 'rule-7-7-1'),
    'rule-8-2-2': ('rule-7-3-2', 'rule-7-3-4'),
    'rule-8-2-3': ('rule-7-7-1',),
    'rule-8-2-4': ('rule-8-2-1', 'rule-8-2-3'),
    'rule-8-2-5': ('rule-2-1-1', 'rule-7-8-1'),
    'rule-8-2-6': ('rule-9-1-1', 'rule-5-4-2'),
    'rule-8-2-7': ('rule-8-2-4', 'rule-0-3-1'),
    'rule-8-3-1': ('rule-8-1-1', 'rule-7-2-1'),
    'rule-8-3-2': ('rule-8-3-1', 'rule-8-1-2'),
    'rule-8-3-3': ('rule-8-3-1', 'rule-7-2-1'),
    'rule-8-4-1': ('rule-8-1-1', 'rule-8-2-5'),
    'rule-8-4-2': ('rule-2-1-8',),
    'rule-8-4-3': ('rule-8-1-1', 'rule-8-1-2'),
    'rule-8-4-4': ('rule-7-2-1', 'rule-8-3-3'),
    'rule-8-4-5': ('rule-7-2-6', 'rule-8-3-3'),
    'rule-8-4-6': ('rule-10-2-1', 'rule-0-3-1', 'rule-8-4-7'),
    'rule-8-4-7': ('rule-8-1-2', 'rule-8-3-1'),
    'rule-8-4-8': ('rule-6-5-1', 'rule-0-3-1'),
    'rule-8-4-9': ('rule-8-4-7', 'rule-6-3-1'),
    'rule-8-5-1': ('rule-7-5-1', 'rule-7-1-8', 'rule-6-1-1'),
    'rule-8-5-2': ('rule-7-5-3', 'rule-8-2-6'),
    'rule-9-1-1': ('rule-7-1-2', 'rule-5-4-2'),
    'rule-9-1-2': ('rule-2-1-8', 'rule-7-2-1'),
    'rule-9-1-3': ('rule-2-1-8', 'rule-7-2-1'),
    'rule-9-1-4': ('rule-1-3-2', 'rule-8-1-2'),
    'rule-9-2-1': ('rule-2-1-8',),
    'rule-9-2-2': ('rule-7-3-2', 'rule-7-9-2', 'rule-8-1-1'),
    'rule-9-2-3': ('rule-6-2-1', 'rule-7-7-1'),
    'rule-9-2-4': ('rule-2-1-1', 'rule-5-4-2'),
    'rule-9-3-1': ('rule-9-1-1', 'rule-9-1-2', 'rule-9-1-3'),
    'rule-9-3-2': ('rule-7-9-2', 'rule-10-1-1'),
    'rule-9-3-3': ('rule-9-3-2', 'rule-7-9-3'),
    'rule-9-3-4': ('rule-9-1-4', 'rule-9-1-2', 'rule-9-1-3'),
    'rule-9-3-5': ('rule-6-1-1', 'rule-9-3-1', 'rule-7-9-3'),

    'rule-10-1-1': ('rule-2-1-3',),
    'rule-10-1-2': ('rule-1-2-1', 'rule-2-1-1', 'rule-10-1-1'),
    'rule-10-2-1': ('rule-10-1-1', 'rule-2-1-2', 'rule-2-1-1', 'rule-6-5-1'),
    'rule-10-2-2': ('rule-2-1-3',),
    'rule-10-2-4': ('rule-11-2-2', 'rule-10-2-1'),
    'rule-10-3-1': ('rule-11-1-2', 'rule-10-1-1'),
    'rule-10-3-2': ('rule-11-1-1', 'rule-10-2-1'),
    'rule-10-3-3': ('rule-11-2-3', 'rule-10-3-1'),
    'rule-12-1-1': ('rule-5-4-1',),
    'rule-12-1-2': ('rule-12-1-1', 'rule-10-1-1', 'rule-10-2-1'),
}


def reference_keys(rule):
    return [rule.reference_name, *(rule.reference_aliases or [])]


def preferred_reference_key(rule):
    keys = [key for key in reference_keys(rule) if key]
    numbered = next((key for key in keys if NUMBERED_RULE_KEY_RE.fullmatch(key)), None)
    if numbered:
        return numbered
    source_section = next((key for key in keys if SOURCE_SECTION_KEY_RE.fullmatch(key)), None)
    if source_section:
        return source_section
    return rule.reference_name


def extract_reference_tokens(value):
    references = []
    for match in REFERENCE_TOKEN_RE.finditer(str(value or '')):
        reference = match.group(1).partition('|')[0].strip()
        if reference.startswith(('rule-', 'floor-')) and reference not in references:
            references.append(reference)
    return references


def configured_dependency_keys(rule):
    for key in reference_keys(rule):
        if key in COMPREHENSIVE_RULE_DEPENDENCIES:
            return list(COMPREHENSIVE_RULE_DEPENDENCIES[key])
    return []


def synchronize_rule_contracts(rulebook):
    rules = list(
        Rule.objects
        .filter(rulebook=rulebook)
        .prefetch_related('translations')
    )
    all_rules = list(Rule.objects.all())
    aliases = {
        key: rule
        for rule in all_rules
        for key in reference_keys(rule)
        if key
    }
    changed = []
    for rule in rules:
        requested = [*(rule.reference_targets or []), *configured_dependency_keys(rule)]
        for translation in rule.translations.all():
            requested.extend(extract_reference_tokens(translation.content))
        targets = []
        for reference in requested:
            target = aliases.get(reference)
            if target is None or target.pk == rule.pk:
                continue
            canonical = target.reference_name
            if canonical not in targets:
                targets.append(canonical)
        if targets != (rule.reference_targets or []):
            rule.reference_targets = targets
            changed.append(rule)
    if changed:
        Rule.objects.bulk_update(changed, ['reference_targets'])
    return len(changed)


def rule_contract_graph(rules):
    rules = list(rules)
    aliases = {
        key: rule
        for rule in rules
        for key in reference_keys(rule)
        if key
    }
    outgoing = defaultdict(list)
    incoming = defaultdict(list)
    for rule in rules:
        requested = list(rule.reference_targets or [])
        for translation in rule.translations.all():
            requested.extend(extract_reference_tokens(translation.content))
        seen = set()
        for reference in requested:
            target = aliases.get(reference)
            if target is None or target.pk == rule.pk or target.pk in seen:
                continue
            seen.add(target.pk)
            outgoing[rule.pk].append(target)
            incoming[target.pk].append(rule)
    return {'outgoing': outgoing, 'incoming': incoming, 'aliases': aliases}


def unresolved_rule_references(rulebook):
    aliases = {
        key
        for rule in Rule.objects.all()
        for key in reference_keys(rule)
        if key
    }
    issues = []
    rules = (
        Rule.objects
        .filter(rulebook=rulebook)
        .prefetch_related('translations')
    )
    for rule in rules:
        requested = list(rule.reference_targets or [])
        for translation in rule.translations.all():
            requested.extend(extract_reference_tokens(translation.content))
        for reference in dict.fromkeys(requested):
            if reference not in aliases:
                issues.append({
                    'source': preferred_reference_key(rule),
                    'target': reference,
                    'title': strip_tags(
                        next(
                            (item.title for item in rule.translations.all() if item.language == 'ko'),
                            rule.reference_name,
                        )
                    ),
                })
    return issues
