# -*- coding: utf-8 -*-

from botcommands import *

DOLORES_EMOJIS = ['👀', '👻', '🌚', '☃️', '🌝', '🐈', '🦔', '🐙']

START_MESSAGE_TEXT = 'Hello.\n\n— Send a text to set the heading\n— Choose or send a picture to set background picture' \
                     ' (you can use your own picture from device)' \
                     '\n— Send a float from 0.0 to 1.0 to set blackout (0.7 usually looks nice)' \
                     '\n— Send positive integer number to set blur (recommended values are from 1 to 20)' \
                     '\n\nIf you do not want to set any heading just send a symbol \'.\''
UP_MESSAGE_TEXT = 'I am up 🌚'
EXCEPTION_MESSAGE_TEXT = '‼️ Exception has been thrown'
SHUTDOWN_MESSAGE_TEXT = 'See ya 👋'
START_MESSAGE_ADMIN_TEXT = "Set mailing list (admin option): /" + SET_MAILING_LIST_COMMAND \
                           + "\nSend a newsletter (admin option): /" + SEND_NEWSLETTER_COMMAND
WAIT_FOR_AN_IMAGE_MESSAGE_TEXT = "One moment... ⏳"
