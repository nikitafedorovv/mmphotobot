# -*- coding: utf-8 -*-

import os

PROJECT_DIRECTORY = os.path.dirname(os.path.realpath(__file__))

API_TOKEN = os.environ.get('PHOTOBOT_TOKEN')
ADMINS = os.environ.get('PHOTOBOT_ADMINS').split(',')
PROD = os.environ.get('PROD')
WEBHOOK_HOST = os.environ.get('HOST_IP')

WEBHOOK_PORT = 8443  # 443, 80, 88 or 8443
PORT_TO_LISTEN = 7771
HOST_TO_LISTEN = '127.0.0.1'

WEBHOOK_SSL_CERT = '/cert/public.pem'
WEBHOOK_SSL_PRIV = '/cert/private.key'

# Quick'n'dirty SSL certificate generation:
#
# openssl req -newkey rsa:2048 -sha256 -nodes -keyout private.key -x509 -days 365
# -out public.pem -subj "/C=IT/ST=state/L=location/O=description/CN=<<WEBHOOK_HOST>>"

WEBHOOK_URL_BASE = "https://%s:%s" % (WEBHOOK_HOST, WEBHOOK_PORT)
WEBHOOK_URL_PATH = "/tgmmphotobot/"

STOCK_IMAGES_DIRECTORY = 'images/stock/'
SENT_IMAGE_FILE_NAME = 'image.jpg'

ALL_CONTENT_TYPES = ["text",
                     "audio",
                     "document",
                     "photo",
                     "sticker",
                     "video",
                     "video_note",
                     "voice",
                     "location",
                     "contact",
                     "new_chat_members",
                     "left_chat_member",
                     "new_chat_title",
                     "new_chat_photo",
                     "delete_chat_photo",
                     "group_chat_created",
                     "supergroup_chat_created",
                     "channel_chat_created",
                     "migrate_to_chat_id",
                     "migrate_from_chat_id",
                     "pinned_message"]

DEFAULT_HEADING = 'Specify the heading,\nplease'
DEFAULT_BLACKOUT = 0.7
DEFAULT_BLUR = 5

SEND_OWN_IMAGE_BUTTON_TEXT = 'Use a custom image from device'
