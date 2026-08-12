from django import template

from common.language import (
    game_term,
    render_localized_markup,
    translated_card_field,
    translated_character_field,
    translated_pack_field,
    translate_key,
    ui_text,
)

register = template.Library()


@register.simple_tag(takes_context=True)
def tr(context, text):
    return ui_text(text, context.get('current_language'))


@register.simple_tag(takes_context=True)
def tr_key(context, key, fallback=''):
    return translate_key(key, context.get('current_language'), fallback=fallback or None)


@register.filter(name='ui')
def ui(value, language):
    return ui_text(value, language)


@register.filter(name='term')
def term(value, language):
    return game_term(value, language)


@register.filter(name='localized_text')
def localized_text(value, language):
    return render_localized_markup(value, language)


@register.filter(name='card_name')
def card_name(card, language):
    return translated_card_field(card, language, 'name')


@register.filter(name='card_ruby')
def card_ruby(card, language):
    return translated_card_field(card, language, 'ruby')


@register.filter(name='card_text')
def card_text(card, language):
    return translated_card_field(card, language, 'text')


@register.filter(name='card_detail_text')
def card_detail_text(card, language):
    return translated_card_field(card, language, 'detail_text')


@register.filter(name='card_keyword')
def card_keyword(card, language):
    return translated_card_field(card, language, 'keyword')


@register.filter(name='character_name')
def character_name(character, language):
    return translated_character_field(character, language, 'name')


@register.filter(name='character_group')
def character_group(character, language):
    return translated_character_field(character, language, 'group')


@register.filter(name='pack_name')
def pack_name(pack, language):
    return translated_pack_field(pack, language, 'name')


@register.filter(name='keywords_i18n')
def keywords_i18n(value, language):
    if not value:
        return ui_text('태그 없음', language)
    keywords = [keyword for keyword in str(value).split('/') if keyword]
    if not keywords:
        return ui_text('태그 없음', language)
    return '#' + ' #'.join(game_term(keyword, language) for keyword in keywords)
