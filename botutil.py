# -*- coding: utf-8 -*-

import random
from datetime import datetime
import pytz
from io import BytesIO
from botconfig import TIMEZONE

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


def current_time():
    return datetime.now(tz=pytz.timezone(TIMEZONE))


def timezoned_date(timestamp):
    return datetime.fromtimestamp(timestamp).astimezone(pytz.timezone(TIMEZONE))
