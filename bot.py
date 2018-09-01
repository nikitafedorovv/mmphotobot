# -*- coding: utf-8 -*-

import logging
import re
import time
from datetime import datetime
from io import BytesIO

import cherrypy
import telebot
from PIL import Image
from telebot import types

from botspeech import *
from botutil import image_to_file, get_dolores_emoji, clear_text
from chatdata import ChatCache
from chatdata import ChatState
from mmphoto import gen_image

telebot.logger.setLevel(logging.INFO)

# A cache for chat data.
cache = ChatCache()

# A list of chats special messages will be sent to.
mailing_list = []

# Start the bot.
bot = telebot.TeleBot(API_TOKEN, threaded=False)


def send_message_to_admins(message):
    for admin in ADMINS:
        bot.send_message(admin, message)


def handle_exception(exception):
    send_message_to_admins(EXCEPTION_MESSAGE_TEXT + "\n\n" + str(exception))


# WebhookServer, process webhook calls.
class WebhookServer(object):
    @cherrypy.expose
    def index(self):
        if 'content-length' in cherrypy.request.headers and \
                'content-type' in cherrypy.request.headers and \
                cherrypy.request.headers['content-type'] == 'application/json':
            length = int(cherrypy.request.headers['content-length'])
            json_string = cherrypy.request.body.read(length).decode("utf-8")
            update = telebot.types.Update.de_json(json_string)

            try:
                bot.process_new_messages([update.message])
            except Exception as exception:
                handle_exception(exception)

            return ''
        else:
            raise cherrypy.HTTPError(403)


# Read stock images names, make a keyboard.
stock_images_reply_markup = types.ReplyKeyboardMarkup()
stock_images_reply_markup.add(SEND_OWN_IMAGE_BUTTON_TEXT)
stock_photo_names = []
for d, dirs, files in os.walk(PROJECT_DIRECTORY + '/' + STOCK_IMAGES_DIRECTORY):
    for f in files:
        stock_photo_names.append(f)
        stock_images_reply_markup.add(f)


def is_admin(user):
    return str(user) in ADMINS


def debug_message_processing(message):
    chat_id = message.chat.id

    if not is_admin(chat_id):
        send_message_to_admins("MESSAGE FROM " + str(message.chat.first_name) + " @" + str(
            message.chat.username) + " " + str(chat_id) + "\n\n" + str(message.text))


def handle_free_text(message):
    if message.text in stock_photo_names:
        build_and_send_image(message, Image.open(
            PROJECT_DIRECTORY + '/' + STOCK_IMAGES_DIRECTORY + message.text).convert('RGB'))
    elif message.text == SEND_OWN_IMAGE_BUTTON_TEXT:
        bot.send_message(message.chat.id, OK_SEND_ME_THE_PICTURE_TEXT)
    else:
        bot.send_message(message.chat.id, get_dolores_emoji())
        debug_message_processing(message)


def reply_done(chat_id):
    if cache.heading_set(chat_id) is True:
        reply_markup = stock_images_reply_markup
    else:
        reply_markup = types.ReplyKeyboardRemove()

    bot.send_message(chat_id,
                     DONE_MESSAGE_TEXT + "\n" + PHOTO_PARAMETERS_COMMANDS_AS_STRING +
                     "\n\n" + CHOOSE_BACKGROUND_IMAGE_TEXT, reply_markup=reply_markup)


def set_heading(message):
    chat_id = message.chat.id

    cache.set_heading(chat_id, clear_text(message.text))
    cache.set_state(chat_id, ChatState.FREE)

    reply_done(chat_id)


def validate_blackout(blackout):
    return re.match("^[-+]?[0-9]*\.?[0-9]+$", blackout) is not None and 0 <= float(blackout) <= 1


def set_blackout(message):
    chat_id = message.chat.id
    blackout = message.text

    if validate_blackout(blackout):
        cache.set_blackout(chat_id, float(blackout))
        cache.set_state(chat_id, ChatState.FREE)

        reply_done(message.chat.id)
    else:
        bot.send_message(chat_id, BLACKOUT_VALIDATION_FAIL_MESSAGE_TEXT)


def validate_blur(blur):
    return blur.isdigit() and int(blur) >= 0


def set_blur(message):
    chat_id = message.chat.id
    blur = message.text

    if validate_blur(blur):
        cache.set_blur(chat_id, int(blur))
        cache.set_state(chat_id, ChatState.FREE)

        reply_done(message.chat.id)
    else:
        bot.send_message(chat_id, BLUR_VALIDATION_FAIL_MESSAGE_TEXT)


def validate_chat_id(chat_id):
    return chat_id.isdigit()


def set_mailing_list(message):
    chat_id = message.chat.id

    mailing_list.clear()

    for chat_id_for_list in message.text.split('\n'):
        if validate_chat_id(chat_id_for_list):
            mailing_list.append(chat_id_for_list)

    bot.send_message(chat_id, "MAILING LIST:\n\n" + str(mailing_list)
                     + "\n\nTO SEND A NEWSLETTER TYPE /" + SEND_NEWSLETTER_COMMAND)
    cache.set_state(chat_id, ChatState.FREE)


def enter_newsletter_message(message):
    chat_id = message.chat.id

    cache.set_cached_message(chat_id, message)
    message = cache.get_cached_message(chat_id)

    bot.send_message(chat_id, "YOUR MESSAGE:")
    bot.send_message(chat_id, message.text, parse_mode="markdown", disable_web_page_preview=True)
    bot.send_message(chat_id, "ENTER CURRENT DAY OF MONTH TO CONFIRM")
    cache.set_state(chat_id, ChatState.CONFIRMING_NEWSLETTER)


def confirm_and_make_newsletter(message):
    chat_id = message.chat.id
    message_to_send = cache.get_cached_message(chat_id).text

    if message.text == str(datetime.now().day):
        if len(mailing_list) > 0:
            for chat_id_from_list in mailing_list:
                try:
                    message_to_delete = bot.send_message(chat_id, "SENDING TO " + chat_id_from_list + "...")

                    sent_message = bot.send_message(chat_id_from_list, message_to_send, parse_mode="markdown",
                                                    disable_web_page_preview=True)

                    bot.delete_message(chat_id, message_to_delete.message_id)
                    bot.send_message(chat_id,
                                     "SENT TO " + str(chat_id_from_list) + ". MESSAGE ID: " + str(
                                         sent_message.message_id))
                except telebot.apihelper.ApiException as e:
                    time.sleep(1)
                    chat = bot.get_chat(chat_id_from_list)
                    bot.send_message(chat_id,
                                     'EXCEPTION THROWN WHILE SENDING TO '
                                     + '@' + chat.username + ' ' + chat.first_name + ' ' + chat.last_name)
                    handle_exception(e)
            bot.send_message(chat_id, 'ALL SENT')
            cache.set_state(chat_id, ChatState.FREE)
        else:
            bot.send_message(chat_id, 'MAILING LIST IS EMPTY')
            cache.set_state(chat_id, ChatState.FREE)
    else:
        bot.send_message(chat_id, 'WRONG. TRY AGAIN')


def handle_preliminary_admin_command(chat_id, text_to_send, state_to_set):
    cache.set_state(chat_id, state_to_set)
    bot.send_message(chat_id, text_to_send, reply_markup=types.ReplyKeyboardRemove())


def handle_preliminary_command(message, text_to_send, state_to_set):
    chat_id = message.chat.id

    if not is_admin(chat_id):
        handle_free_text(message)
    else:
        handle_preliminary_admin_command(chat_id, text_to_send, state_to_set)


def get_image_from_message(message):
    received_photo = message.photo
    file_id = received_photo[-1].file_id
    file_info = bot.get_file(file_id)
    downloaded_file = bot.download_file(file_info.file_path)
    image = Image.open(BytesIO(downloaded_file))

    return image


def build_image(chat_id, background_image):
    heading = cache.get_heading(chat_id)
    blackout = cache.get_blackout(chat_id)
    blur = cache.get_blur(chat_id)

    return gen_image(heading, background_image, blackout, blur)


def send_photo_debug_info(chat, photo, date):
    chat_id = chat.id

    if not is_admin(chat_id):
        first_name = chat.first_name
        last_name = chat.last_name
        username = chat.username
        caption = "PHOTO BY " + str(first_name) + " " + str(last_name) + " @" + str(username) + " " + str(chat_id) \
                  + ", " + str(datetime.fromtimestamp(int(date)).strftime('%Y-%m-%d %H:%M:%S'))
        for admin in ADMINS:
            bot.send_photo(admin, image_to_file(photo, SENT_IMAGE_FILE_NAME), caption=caption)


def build_and_send_image(message, background_image):
    chat_id = message.chat.id

    wait_for_an_image_message = bot.send_message(chat_id, WAIT_FOR_AN_IMAGE_MESSAGE_TEXT)

    built_image = build_image(chat_id, background_image)

    bot.send_document(chat_id, image_to_file(built_image, SENT_IMAGE_FILE_NAME))
    bot.send_photo(chat_id, image_to_file(built_image, SENT_IMAGE_FILE_NAME))
    bot.delete_message(chat_id, wait_for_an_image_message.message_id)
    bot.send_message(chat_id, get_dolores_emoji(), reply_markup=stock_images_reply_markup)

    send_photo_debug_info(message.chat, built_image, message.date)


@bot.message_handler(commands=['start'])
def handle_start_help(message):
    chat_id = message.chat.id

    cache.set_state(chat_id, ChatState.FREE)
    bot.send_message(chat_id, START_MESSAGE_TEXT + "\n" + PHOTO_PARAMETERS_COMMANDS_AS_STRING)

    if is_admin(chat_id):
        bot.send_message(chat_id, START_MESSAGE_ADMIN_TEXT)


@bot.message_handler(commands=['cancel'])
def handle_cancel(message):
    chat_id = message.chat.id

    cache.set_state(chat_id, ChatState.FREE)
    bot.send_message(chat_id, CANCEL_MESSAGE_TEXT, reply_markup=stock_images_reply_markup)


def clarification_text(command):
    if command == SET_HEADING_COMMAND:
        return HEADING_CLARIFICATION_TEXT
    elif command == SET_BLACKOUT_COMMAND:
        return BLACKOUT_CLARIFICATION_TEXT
    elif command == SET_BLUR_COMMAND:
        return BLUR_CLARIFICATION_TEXT


@bot.message_handler(commands=PHOTO_PARAMETERS_COMMANDS)
def handle_setter(message):
    chat_id = message.chat.id

    cache.set_state(chat_id, ChatState(message.text))
    answer = SEND_ME_PHOTO_PARAMETER_TEXT + clarification_text(message.text[1:])
    bot.send_message(chat_id, answer, reply_markup=types.ReplyKeyboardRemove())


@bot.message_handler(commands=[SET_MAILING_LIST_COMMAND])
def handle_mailing_list_setter(message):
    handle_preliminary_command(message,
                               "CURRENT MAILING LIST: \n\n" + str(mailing_list) + "\n\nENTER NEW MAILING LIST",
                               ChatState.SPECIFYING_MAILING_LIST)


@bot.message_handler(commands=[SEND_NEWSLETTER_COMMAND])
def handle_make_newsletter(message):
    handle_preliminary_command(message,
                               "ENTER NEWSLETTER MESSAGE",
                               ChatState.ENTERING_NEWSLETTER_MESSAGE)


@bot.message_handler(content_types=['text'])
def handle_text(message):
    state = cache.get_state(message.chat.id)

    if state == ChatState.FREE:
        handle_free_text(message)
    elif state == ChatState.SETTING_HEADING:
        set_heading(message)
    elif state == ChatState.SETTING_BLACKOUT:
        set_blackout(message)
    elif state == ChatState.SETTING_BLUR:
        set_blur(message)
    elif state == ChatState.SPECIFYING_MAILING_LIST:
        set_mailing_list(message)
    elif state == ChatState.ENTERING_NEWSLETTER_MESSAGE:
        enter_newsletter_message(message)
    elif state == ChatState.CONFIRMING_NEWSLETTER:
        confirm_and_make_newsletter(message)


@bot.message_handler(content_types=["photo"])
def handle_photo(message):
    received_image = get_image_from_message(message)
    build_and_send_image(message, received_image)


@bot.message_handler(content_types=ALL_CONTENT_TYPES)
def handle_any_other_message(message):
    chat_id = message.chat.id

    if not is_admin(chat_id):
        # Forward.
        message_id = message.message_id

        for admin in ADMINS:
            bot.forward_message(admin, chat_id, message_id)

        bot.send_message(chat_id, get_dolores_emoji())


while True:
    try:
        send_message_to_admins(UP_MESSAGE_TEXT)
        # Remove webhook, it fails sometimes the set if there is a previous webhook
        bot.remove_webhook()

        if PROD == 'TRUE':

            # Set webhook
            bot.set_webhook(url=WEBHOOK_URL_BASE + WEBHOOK_URL_PATH,
                            certificate=open(WEBHOOK_SSL_CERT, 'r'))

            time.sleep(1)

            # Start cherrypy server
            cherrypy.config.update({
                'server.socket_host': HOST_TO_LISTEN,
                'server.socket_port': PORT_TO_LISTEN,
                'engine.autoreload.on': False
            })

            cherrypy.quickstart(WebhookServer(), '/', {'/': {}})
        else:
            bot.polling(none_stop=True)

    except Exception as e:
        handle_exception(e)
    else:

        send_message_to_admins(SHUTDOWN_MESSAGE_TEXT)
        break
