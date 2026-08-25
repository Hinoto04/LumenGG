import re
from html import escape
from html.parser import HTMLParser


REFERENCE_PATTERN = re.compile(r'\[\[([^\[\]]+?)\]\]')
NUMBER_LABEL_PATTERN = re.compile(r'^\d+(?:\.\d+)*$')
SKIP_TAGS = {'a', 'code', 'pre', 'script', 'style'}


class _RuleReferenceParser(HTMLParser):
    def __init__(self, targets):
        super().__init__(convert_charrefs=False)
        self.targets = targets
        self.output = []
        self.skip_depth = 0

    def handle_starttag(self, tag, attrs):
        self.output.append(self.get_starttag_text())
        if tag.lower() in SKIP_TAGS:
            self.skip_depth += 1

    def handle_startendtag(self, tag, attrs):
        self.output.append(self.get_starttag_text())

    def handle_endtag(self, tag):
        self.output.append(f'</{tag}>')
        if tag.lower() in SKIP_TAGS and self.skip_depth:
            self.skip_depth -= 1

    def handle_data(self, data):
        if self.skip_depth:
            self.output.append(data)
            return
        self.output.append(REFERENCE_PATTERN.sub(self._replace_reference, data))

    def handle_entityref(self, name):
        self.output.append(f'&{name};')

    def handle_charref(self, name):
        self.output.append(f'&#{name};')

    def handle_comment(self, data):
        self.output.append(f'<!--{data}-->')

    def handle_decl(self, decl):
        self.output.append(f'<!{decl}>')

    def handle_pi(self, data):
        self.output.append(f'<?{data}>')

    def _replace_reference(self, match):
        raw_reference = match.group(1).strip()
        reference_name, separator, custom_label = raw_reference.partition('|')
        reference_name = reference_name.strip()
        target = self.targets.get(reference_name)
        if target is None:
            return (
                '<span class="v2-rule-reference-missing" '
                f'title="존재하지 않는 규칙 참조: {escape(reference_name, quote=True)}">'
                f'{escape(match.group(0))}</span>'
            )

        label = custom_label.strip() if separator and custom_label.strip() else target['label']
        if NUMBER_LABEL_PATTERN.fullmatch(label) and target.get('number'):
            label = target['number']
        return (
            '<a class="v2-rule-reference" '
            f'href="{escape(target["href"], quote=True)}">{escape(label)}</a>'
        )


def link_rule_references(html, targets):
    parser = _RuleReferenceParser(targets)
    parser.feed(str(html or ''))
    parser.close()
    return ''.join(parser.output)
