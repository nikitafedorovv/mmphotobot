# -*- coding: utf-8 -*-

from botcommands import *

DOLORES_EMOJIS = ['👀', '👻', '🌚', '☃️', '🌝', '🐈', '🦔', '🐙']

START_MESSAGE_TEXT = 'Hello.\n\n— Send a text to set the heading\n— Choose or send a picture to set background picture' \
                     ' (you can use your own picture from device)' \
                     '\n— Send a float from 0.0 to 1.0 to set blackout (0.6 usually looks nice)' \
                     '\n— Send positive integer number to set blur (recommended values are from 1 to 20)' \
                     '\n\nIf you do not want to set any heading just send a symbol \'.\''
EXCEPTION_MESSAGE_TEXT = '‼️ Exception has been thrown'
START_MESSAGE_ADMIN_TEXT = "Set mailing list (admin option): /" + SET_MAILING_LIST_COMMAND \
                           + "\nSend a newsletter (admin option): /" + SEND_NEWSLETTER_COMMAND \
                           + "\nRecall newsletter (admin option, type it by yourself): / " + RECALL_NEWSLETTER_COMMAND \
                           + "\n\nUpdate inline stocks (admin option): /" + UPDATE_INLINE_STOCKS_COMMAND
GO_TO_INLINE_BUTTON = "🌄🌌 Gallery 🌃🎇"
GET_AS_FILE_BUTTON = "View as file"
GET_AS_PHOTO_BUTTON = "View as photo"
GET_AS_FILE_CALLBACK_DATA = "F"
GET_AS_PHOTO_CALLBACK_DATA = "P"
GALLERY_TAG = "heading:\n"
WAIT_FOR_AN_IMAGE_MESSAGE_TEXT = "One moment... ⏳"
