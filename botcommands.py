# -*- coding: utf-8 -*-

SET_HEADING_COMMAND = 'set_heading'
SET_BLACKOUT_COMMAND = 'set_blackout'
SET_BLUR_COMMAND = 'set_blur'
SEND_NEWSLETTER_COMMAND = 'send_newsletter'
SET_MAILING_LIST_COMMAND = 'set_mailing_list'

PHOTO_PARAMETERS_COMMANDS = [SET_HEADING_COMMAND, SET_BLACKOUT_COMMAND, SET_BLUR_COMMAND]


def count_command_list_for_message():
    commands_message_text = ''
    for command in PHOTO_PARAMETERS_COMMANDS:
        commands_message_text += "\n/" + command
    return commands_message_text


PHOTO_PARAMETERS_COMMANDS_AS_STRING = count_command_list_for_message()
