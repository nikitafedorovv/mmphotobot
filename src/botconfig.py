# -*- coding: utf-8 -*-

import os

from chat_modes import ChatMode
from modes.mode_2021.pic_colors import PicColor2021

PROJECT_DIRECTORY = os.path.dirname(os.path.realpath(__file__))

API_TOKEN = os.environ.get('PHOTOBOT_TOKEN')
DEVELOPER_ID = os.environ.get('DEVELOPER_ID')
LOGS_CHANNEL_ID = os.environ.get('LOGS_CHANNEL_ID')
PROD = os.environ.get('PROD')

WEBHOOK_HOST = os.environ.get('HOST_IP')
WEBHOOK_PORT = 8443  # 443, 80, 88 or 8443
PORT_TO_LISTEN = 80
HOST_TO_LISTEN = '127.0.0.1'
WEBHOOK_SSL_CERT = '/certificates/public.pem'
WEBHOOK_SSL_PRIV = '/certificates/private.key'
WEBHOOK_URL_BASE = "https://%s:%s" % (WEBHOOK_HOST, WEBHOOK_PORT)
WEBHOOK_URL_PATH = "/tgmmphotobot/"

MONGO_URL = os.environ.get('MONGO_URL')

PROXY = os.environ.get('PROXY')

DEFAULT_CHAT_MODE = ChatMode.MODE2021
DEFAULT_PIC_COLOR_2021 = PicColor2021.MAIN

# Quick'n'dirty SSL certificate generation:
#
# openssl req -newkey rsa:2048 -sha256 -nodes -keyout private.key -x509 -days 365
# -out public.pem -subj "/C=IT/ST=state/L=location/O=description/CN=<<WEBHOOK_HOST>>"

SENT_IMAGE_FILE_NAME = 'image.jpg'

DEFAULT_HEADING = 'Specify the heading,\nplease'
DEFAULT_BLACKOUT = 0.50
DEFAULT_BLUR = 1

TIMEZONE = 'Europe/Moscow'
