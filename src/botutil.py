# -*- coding: utf-8 -*-

import re
from datetime import datetime
from io import BytesIO

import pytz

from botconfig import TIMEZONE


def image_to_file(image, name):
    bio = BytesIO()
    bio.name = name
    image.save(bio, 'PNG')
    bio.seek(0)
    return bio


def clear_text(text):
    if text == '.':
        text = ''

    return text


def validate_blackout(blackout):
    return re.match("^[-+]?[0-9]*\.?[0-9]+$", blackout) is not None and 0 <= float(blackout) < 1


def validate_blur(blur):
    return blur.isdigit() and int(blur) > 1


def safe_cast(val, to_type, default=None):
    if val is None:
        return default
    try:
        return to_type(val)
    except (ValueError, TypeError):
        return default


def current_time():
    return datetime.now(tz=pytz.timezone(TIMEZONE))


def timezoned_time(timestamp):
    return datetime.fromtimestamp(timestamp, tz=pytz.timezone(TIMEZONE))
