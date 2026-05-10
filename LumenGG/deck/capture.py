import hashlib
import math
import re
import time
from io import BytesIO
from pathlib import Path

import requests
from django.conf import settings
from django.utils import timezone
from PIL import Image, ImageDraw, ImageFont, ImageOps, UnidentifiedImageError

from collection.models import Pack
from .models import CardInDeck, DeckLike


CAPTURE_TTL_SECONDS = 6 * 60 * 60
CAPTURE_LAYOUT_VERSION = '20260510-font-weight-v1'

CANVAS_W = 1400
PAGE_PAD = 32
GAP = 16
HEADER_PAD = 24
ZONE_PAD = 14
CARD_GAP = 8
SIDE_W = 250
BOARD_W = CANVAS_W - PAGE_PAD * 2
LEFT_W = BOARD_W - SIDE_W - GAP
CARD_COLS = 5
CARD_W = (LEFT_W - ZONE_PAD * 2 - CARD_GAP * (CARD_COLS - 1)) // CARD_COLS
CARD_H = int(CARD_W * 1.397)
SIDE_CARD_W = SIDE_W - ZONE_PAD * 2
SIDE_CARD_H = int(SIDE_CARD_W * 1.397)
ZONE_HEAD_H = 38
HEADER_H = 392
ULTIMATE_CARD_W = 200
ULTIMATE_CARD_H = int(ULTIMATE_CARD_W * 1.397)
HEADER_CHARACTER_W = 300
HEADER_CHARACTER_GAP = 28

COLORS = {
    'bg': '#111111',
    'surface': '#1b1b1b',
    'surface2': '#242424',
    'surface3': '#303030',
    'line': '#3b3b3b',
    'text': '#f4f1ea',
    'muted': '#b8b0a4',
    'faint': '#857d73',
    'accent': '#e0b45b',
    'red': '#d96969',
}


def generate_deck_capture(deck):
    cards = list(
        CardInDeck.objects.filter(deck=deck)
        .select_related('card', 'card__character')
        .order_by('-card__type', 'card__frame', 'card__name')
    )
    likecount = DeckLike.objects.filter(deck=deck, like=True).count()
    output_dir = Path(settings.MEDIA_ROOT) / 'generated' / 'deck_captures'
    output_dir.mkdir(parents=True, exist_ok=True)
    cleanup_old_captures(output_dir)

    signature = get_capture_signature(deck, cards, likecount)
    output_path = output_dir / f'deck_{deck.id}_{signature}.png'
    if output_path.exists():
        return output_path

    image_cache = {}
    main_entries, hand_entries, side_entries, ultimate_entries = split_deck_entries(cards)
    unreleased_codes = list(Pack.objects.filter(released__gt=timezone.now().date()).values_list('code', flat=True))

    list_h = get_zone_height(len(main_entries), CARD_W, CARD_H)
    hand_h = get_zone_height(len(hand_entries), CARD_W, CARD_H)
    board_h = list_h + GAP + hand_h
    total_h = PAGE_PAD + HEADER_H + GAP + board_h + PAGE_PAD + 34

    canvas = Image.new('RGB', (CANVAS_W, total_h), COLORS['bg'])
    draw = ImageDraw.Draw(canvas)

    fonts = {
        'kicker': load_font(24, bold=True),
        'title': load_font(48, weight='black'),
        'section': load_font(24, weight='extra_bold'),
        'body': load_font(22),
        'small': load_font(18),
        'chip': load_font(17, bold=True),
        'label': load_font(18, weight='extra_bold'),
        'ultimate_name': load_font(18, weight='extra_bold'),
        'footer': load_font(16),
    }

    draw_header(canvas, draw, deck, likecount, ultimate_entries, image_cache, fonts, unreleased_codes)
    board_y = PAGE_PAD + HEADER_H + GAP
    draw_zone(
        canvas,
        draw,
        (PAGE_PAD, board_y, PAGE_PAD + LEFT_W, board_y + list_h),
        '리스트',
        f'{len(main_entries)}장',
        main_entries,
        CARD_W,
        CARD_H,
        CARD_COLS,
        image_cache,
        fonts,
        unreleased_codes,
    )
    draw_zone(
        canvas,
        draw,
        (PAGE_PAD, board_y + list_h + GAP, PAGE_PAD + LEFT_W, board_y + board_h),
        '손패',
        f'{len(hand_entries)}장',
        hand_entries,
        CARD_W,
        CARD_H,
        CARD_COLS,
        image_cache,
        fonts,
        unreleased_codes,
    )
    draw_side_zone(
        canvas,
        draw,
        (PAGE_PAD + LEFT_W + GAP, board_y, PAGE_PAD + BOARD_W, board_y + board_h),
        side_entries,
        image_cache,
        fonts,
        unreleased_codes,
    )

    footer = 'LumenDB Deck Capture'
    draw.text((PAGE_PAD, total_h - PAGE_PAD), footer, fill=COLORS['faint'], font=fonts['footer'])
    canvas.save(output_path, 'PNG', optimize=True)
    return output_path


def cleanup_old_captures(output_dir):
    now = time.time()
    for path in output_dir.glob('deck_*.png'):
        try:
            if now - path.stat().st_mtime > CAPTURE_TTL_SECONDS:
                path.unlink()
        except OSError:
            pass


def get_capture_signature(deck, cards, likecount):
    parts = [
        CAPTURE_LAYOUT_VERSION,
        str(deck.id),
        str(deck.name or ''),
        str(deck.version or ''),
        str(deck.visibility or ''),
        str(deck.keyword or ''),
        str(deck.tags or ''),
        str(deck.author.username or ''),
        str(deck.character.name or ''),
        str(deck.character.body_img or deck.character.sd_img or deck.character.img or ''),
        str(deck.created),
        str(likecount),
    ]
    for cid in cards:
        parts.extend([
            str(cid.card_id),
            cid.card.name,
            cid.card.img_mid or cid.card.img or '',
            str(cid.count),
            str(cid.hand),
            str(cid.side),
            str(cid.card.ultimate),
        ])
    raw = '\n'.join(parts).encode('utf-8', errors='ignore')
    return hashlib.sha256(raw).hexdigest()[:16]


def split_deck_entries(cards):
    main_entries = []
    hand_entries = []
    side_entries = []
    ultimate_entries = []
    for cid in cards:
        if cid.card.ultimate:
            ultimate_entries.extend([cid] * max(cid.count, 1))
            continue
        main_entries.extend([cid] * max(cid.count - cid.hand - cid.side, 0))
        hand_entries.extend([cid] * max(cid.hand, 0))
        side_entries.extend([cid] * max(cid.side, 0))
    return main_entries, hand_entries, side_entries, ultimate_entries


def get_zone_height(card_count, card_w, card_h):
    rows = max(math.ceil(card_count / CARD_COLS), 1)
    card_area_h = rows * card_h + max(rows - 1, 0) * CARD_GAP
    return ZONE_PAD * 2 + ZONE_HEAD_H + card_area_h


def draw_header(canvas, draw, deck, likecount, ultimate_entries, image_cache, fonts, unreleased_codes):
    x0, y0 = PAGE_PAD, PAGE_PAD
    x1, y1 = PAGE_PAD + BOARD_W, PAGE_PAD + HEADER_H
    draw.rounded_rectangle((x0, y0, x1, y1), radius=12, fill=COLORS['surface'], outline=COLORS['line'], width=2)

    content_x = x0 + HEADER_PAD
    content_y = y0 + 24
    ultimate_x = None
    if ultimate_entries:
        ultimate_x = x1 - HEADER_PAD - ULTIMATE_CARD_W
        character_x = ultimate_x - HEADER_CHARACTER_GAP - HEADER_CHARACTER_W
        text_max_w = max(560, character_x - content_x - HEADER_PAD)
    else:
        character_x = x1 - HEADER_PAD - 360
        text_max_w = max(720, character_x - content_x - HEADER_PAD)

    character_url = deck.character.body_img or deck.character.sd_img or deck.character.img
    if character_url:
        character_img = get_remote_image(character_url, image_cache)
        if character_img:
            paste_faint_character(canvas, character_img, character_x, y0 + 10, HEADER_CHARACTER_W if ultimate_entries else 360, HEADER_H - 20)

    draw.text((content_x, content_y), deck.character.name, fill=COLORS['accent'], font=fonts['kicker'])
    title_y = content_y + 34
    draw_wrapped_text(draw, deck.name, content_x, title_y, text_max_w, fonts['title'], COLORS['text'], line_gap=4, max_lines=2)

    tag_text = get_tag_text(deck.keyword or deck.tags)
    draw_wrapped_text(draw, tag_text, content_x, y1 - 92, text_max_w, fonts['body'], COLORS['muted'], line_gap=4, max_lines=2)

    chips = [
        f'추천 {likecount}',
        f'ver. {deck.version}',
        deck.get_visibility_display(),
        deck.author.username,
        deck.created.strftime('%Y-%m-%d'),
    ]
    chip_x = content_x
    chip_y = y1 - 42
    for chip in chips:
        chip_x = draw_chip(draw, chip, chip_x, chip_y, fonts['chip']) + 8

    if ultimate_entries:
        ultimate = ultimate_entries[0]
        ux = ultimate_x
        uy = y0 + 22
        draw.text((ux, uy), '얼티밋 카드', fill=COLORS['accent'], font=fonts['section'])
        card_img = get_card_image(ultimate.card, image_cache)
        card_y = uy + text_height(draw, '얼티밋 카드', fonts['section']) + 12
        draw_card_tile(canvas, draw, card_img, ux, card_y, ULTIMATE_CARD_W, ULTIMATE_CARD_H, is_unreleased(ultimate, unreleased_codes), fonts)
        draw_text_ellipsis(draw, ultimate.card.name, ux, card_y + ULTIMATE_CARD_H + 8, ULTIMATE_CARD_W, fonts['ultimate_name'], COLORS['text'])


def draw_zone(canvas, draw, box, title, count_text, entries, card_w, card_h, cols, image_cache, fonts, unreleased_codes):
    x0, y0, x1, y1 = box
    draw.rounded_rectangle(box, radius=12, fill=COLORS['surface'], outline=COLORS['line'], width=2)
    draw.text((x0 + ZONE_PAD, y0 + ZONE_PAD), title, fill=COLORS['text'], font=fonts['section'])
    draw.text((x1 - ZONE_PAD - text_width(draw, count_text, fonts['small']), y0 + ZONE_PAD + 4), count_text, fill=COLORS['faint'], font=fonts['small'])

    start_x = x0 + ZONE_PAD
    start_y = y0 + ZONE_PAD + ZONE_HEAD_H
    for index, cid in enumerate(entries):
        col = index % cols
        row = index // cols
        cx = start_x + col * (card_w + CARD_GAP)
        cy = start_y + row * (card_h + CARD_GAP)
        draw_card_tile(canvas, draw, get_card_image(cid.card, image_cache), cx, cy, card_w, card_h, is_unreleased(cid, unreleased_codes), fonts)


def draw_side_zone(canvas, draw, box, entries, image_cache, fonts, unreleased_codes):
    x0, y0, x1, y1 = box
    draw.rounded_rectangle(box, radius=12, fill=COLORS['surface'], outline=COLORS['line'], width=2)
    draw.text((x0 + ZONE_PAD, y0 + ZONE_PAD), '사이드', fill=COLORS['text'], font=fonts['section'])
    count_text = f'{len(entries)}장'
    draw.text((x1 - ZONE_PAD - text_width(draw, count_text, fonts['small']), y0 + ZONE_PAD + 4), count_text, fill=COLORS['faint'], font=fonts['small'])

    if not entries:
        return

    start_x = x0 + ZONE_PAD
    start_y = y0 + ZONE_PAD + ZONE_HEAD_H
    available = max((y1 - ZONE_PAD) - start_y - SIDE_CARD_H, 0)
    offset = 0 if len(entries) == 1 else min(92, available / (len(entries) - 1))
    offset = max(offset, 28 if len(entries) > 1 else 0)
    for index, cid in enumerate(entries):
        cy = start_y + int(index * offset)
        if index == len(entries) - 1:
            cy = min(cy, y1 - ZONE_PAD - SIDE_CARD_H)
        draw_card_tile(canvas, draw, get_card_image(cid.card, image_cache), start_x, cy, SIDE_CARD_W, SIDE_CARD_H, is_unreleased(cid, unreleased_codes), fonts)


def draw_card_tile(canvas, draw, card_img, x, y, w, h, unreleased, fonts):
    draw.rounded_rectangle((x, y, x + w, y + h), radius=10, fill=COLORS['surface2'])
    if card_img:
        fitted = fit_card_image(card_img, w, h)
    else:
        fitted = make_card_placeholder(w, h, fonts)
    paste_rounded(canvas, fitted, x, y, 10)
    draw.rounded_rectangle((x, y, x + w, y + h), radius=10, outline=COLORS['surface'], width=3)
    if unreleased:
        draw_label(draw, '미발매', x + 8, y + 8, fonts['label'])


def fit_card_image(image, width, height):
    img = image.convert('RGB')
    if img.width > 8 and img.height > 8:
        img = img.crop((2, 2, img.width - 2, img.height - 2))
    return ImageOps.fit(img, (width, height), method=Image.Resampling.LANCZOS, centering=(0.5, 0.5))


def paste_rounded(canvas, image, x, y, radius):
    mask = Image.new('L', image.size, 0)
    mask_draw = ImageDraw.Draw(mask)
    mask_draw.rounded_rectangle((0, 0, image.width, image.height), radius=radius, fill=255)
    canvas.paste(image, (int(x), int(y)), mask)


def paste_faint_character(canvas, image, x, y, width, height):
    img = image.convert('RGBA')
    img.thumbnail((width, height), Image.Resampling.LANCZOS)
    alpha = img.getchannel('A').point(lambda value: int(value * 0.15))
    img.putalpha(alpha)
    canvas.paste(img, (int(x + width - img.width), int(y + (height - img.height) / 2)), img)


def get_card_image(card, image_cache):
    return get_remote_image(card.img_mid or card.img_sm or card.img, image_cache)


def get_remote_image(url, image_cache):
    if not url:
        return None
    if url in image_cache:
        return image_cache[url]
    try:
        response = requests.get(url, timeout=8, headers={'User-Agent': 'LumenDB deck capture'})
        response.raise_for_status()
        img = Image.open(BytesIO(response.content)).convert('RGBA')
    except (requests.RequestException, UnidentifiedImageError, OSError):
        img = None
    image_cache[url] = img
    return img


def make_card_placeholder(width, height, fonts):
    img = Image.new('RGB', (width, height), COLORS['surface3'])
    draw = ImageDraw.Draw(img)
    text = '이미지 없음'
    draw.text(
        ((width - text_width(draw, text, fonts['small'])) / 2, height / 2 - 10),
        text,
        fill=COLORS['muted'],
        font=fonts['small'],
    )
    return img


def draw_label(draw, text, x, y, font):
    pad_x = 8
    pad_y = 3
    tw = text_width(draw, text, font)
    th = text_height(draw, text, font)
    draw.rounded_rectangle((x, y, x + tw + pad_x * 2, y + th + pad_y * 2), radius=7, fill=COLORS['red'])
    draw.text((x + pad_x, y + pad_y - 1), text, fill='#ffffff', font=font)


def draw_chip(draw, text, x, y, font):
    pad_x = 10
    pad_y = 4
    tw = text_width(draw, text, font)
    th = text_height(draw, text, font)
    x2 = x + tw + pad_x * 2
    y2 = y + th + pad_y * 2
    draw.rounded_rectangle((x, y, x2, y2), radius=8, fill='#242424', outline=COLORS['line'], width=1)
    draw.text((x + pad_x, y + pad_y - 1), text, fill=COLORS['muted'], font=font)
    return x2


def draw_wrapped_text(draw, text, x, y, max_width, font, fill, line_gap=2, max_lines=3):
    lines = wrap_text(draw, text, max_width, font, max_lines)
    line_height = text_height(draw, '가나다', font) + line_gap
    for index, line in enumerate(lines):
        draw.text((x, y + line_height * index), line, fill=fill, font=font)


def wrap_text(draw, text, max_width, font, max_lines):
    text = re.sub(r'\s+', ' ', str(text or '')).strip()
    if not text:
        return []
    words = text.split(' ')
    lines = []
    current = ''
    for word in words:
        if text_width(draw, word, font) > max_width:
            split_words = split_long_word(draw, word, max_width, font)
        else:
            split_words = [word]
        for split_word in split_words:
            candidate = f'{current} {split_word}'.strip()
            if not current or text_width(draw, candidate, font) <= max_width:
                current = candidate
                continue
            lines.append(current)
            current = split_word
            if len(lines) >= max_lines:
                break
        if len(lines) >= max_lines:
            break
    if current and len(lines) < max_lines:
        lines.append(current)
    if len(lines) == max_lines and text_width(draw, lines[-1], font) > max_width:
        lines[-1] = ellipsize(draw, lines[-1], max_width, font)
    return lines


def split_long_word(draw, word, max_width, font):
    chunks = []
    current = ''
    for char in word:
        candidate = f'{current}{char}'
        if not current or text_width(draw, candidate, font) <= max_width:
            current = candidate
            continue
        chunks.append(current)
        current = char
    if current:
        chunks.append(current)
    return chunks


def draw_text_ellipsis(draw, text, x, y, max_width, font, fill):
    draw.text((x, y), ellipsize(draw, text, max_width, font), fill=fill, font=font)


def ellipsize(draw, text, max_width, font):
    text = str(text or '')
    if text_width(draw, text, font) <= max_width:
        return text
    suffix = '...'
    while text and text_width(draw, text + suffix, font) > max_width:
        text = text[:-1]
    return text + suffix


def text_width(draw, text, font):
    return draw.textbbox((0, 0), str(text), font=font)[2]


def text_height(draw, text, font):
    bbox = draw.textbbox((0, 0), str(text), font=font)
    return bbox[3] - bbox[1]


def get_tag_text(raw_value):
    if not raw_value:
        return '태그 없음'
    tags = [tag.strip().lstrip('#') for tag in str(raw_value).split('/') if tag.strip()]
    return '#' + ' #'.join(tags) if tags else '태그 없음'


def is_unreleased(card_in_deck, unreleased_codes):
    code = card_in_deck.card.code or ''
    return any(pack_code and pack_code in code for pack_code in unreleased_codes)


def load_font(size, bold=False, weight=None):
    weight = weight or ('bold' if bold else 'regular')
    static_fonts = Path(settings.BASE_DIR) / 'static' / 'fonts'
    pretendard_by_weight = {
        'black': 'Pretendard-Black.ttf',
        'extra_bold': 'Pretendard-ExtraBold.ttf',
        'bold': 'Pretendard-Bold.ttf',
        'regular': 'Pretendard-Regular.ttf',
    }
    nanum_by_weight = {
        'black': 'NanumGothicExtraBold.ttf',
        'extra_bold': 'NanumGothicExtraBold.ttf',
        'bold': 'NanumGothicBold.ttf',
        'regular': 'NanumGothic.ttf',
    }
    candidates = [
        static_fonts / pretendard_by_weight.get(weight, pretendard_by_weight['regular']),
        static_fonts / ('Pretendard-SemiBold.ttf' if weight in ('bold', 'extra_bold', 'black') else 'Pretendard-Medium.ttf'),
        static_fonts / nanum_by_weight.get(weight, nanum_by_weight['regular']),
        static_fonts / ('NanumGothicExtraBold.ttf' if weight in ('bold', 'extra_bold', 'black') else 'NanumGothicLight.ttf'),
        r'C:\Windows\Fonts\malgunbd.ttf' if bold else r'C:\Windows\Fonts\malgun.ttf',
        '/usr/share/fonts/truetype/nanum/NanumGothicBold.ttf' if bold else '/usr/share/fonts/truetype/nanum/NanumGothic.ttf',
        '/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc' if bold else '/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc',
        '/usr/share/fonts/truetype/noto/NotoSansCJK-Bold.ttc' if bold else '/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc',
        '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf' if bold else '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
    ]
    for path in candidates:
        try:
            if path and Path(path).exists():
                return ImageFont.truetype(path, size)
        except OSError:
            continue
    return ImageFont.load_default()
