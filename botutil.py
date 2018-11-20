# -*- coding: utf-8 -*-

import random
from io import BytesIO

from botspeech import DOLORES_EMOJIS


def image_to_file(image, name):
    bio = BytesIO()
    bio.name = name
    image.save(bio, 'JPEG')
    bio.seek(0)
    return bio


def get_dolores_emoji():
    r = random.randint(0, len(DOLORES_EMOJIS) - 1)
    return DOLORES_EMOJIS[r]


def clear_text(text):
    if text == '.':
        text = ''

    return text


def safe_cast(val, to_type, default=None):
    try:
        return to_type(val)
    except (ValueError, TypeError):
        return default
