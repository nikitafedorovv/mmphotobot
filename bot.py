# -*- coding: utf-8 -*-

import logging
import re
import time
from io import BytesIO

import cherrypy
import telebot
from telebot import types

from botspeech import *
from botutil import image_to_file, get_dolores_emoji, clear_text, safe_cast, current_time, timezoned_date
from chatdata import ChatCache
from chatdata import ChatState
from mmphoto import gen_image
from botconfig import *

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
                bot.process_new_updates([update])
            except Exception as exception:
                handle_exception(exception)

            return ''
        else:
            raise cherrypy.HTTPError(403)


# Read stock images names, make a keyboard.
stock_images_reply_markup = types.ReplyKeyboardMarkup()
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
        send_message_to_admins("MESSAGE FROM " + safe_cast(message.chat.first_name, str, '/empty_first_name/')
                               + " @" + safe_cast(message.chat.username, str, '/empty_username/')
                               + " " + str(chat_id) + "\n\n" + safe_cast(message.text, str, '/empty_message_text/'))


def handle_free_text(message):
    text = message.text
    chat_id = message.chat.id

    if text in stock_photo_names:
        cache.set_image(chat_id,
                        Image.open(PROJECT_DIRECTORY + '/' + STOCK_IMAGES_DIRECTORY + message.text).convert('RGB'))
        build_and_send_image(message)
    elif validate_blackout(text) or text == '1.0':
        cache.set_blackout(chat_id, float(text))
        build_and_send_image(message)
    elif validate_blur(text) or text == '1':
        cache.set_blur(chat_id, int(text))
        build_and_send_image(message)
    else:
        cache.set_heading(chat_id, clear_text(message.text))
        build_and_send_image(message)


def validate_blackout(blackout):
    return re.match("^[-+]?[0-9]*\.?[0-9]+$", blackout) is not None and 0 <= float(blackout) < 1


def validate_blur(blur):
    return blur.isdigit() and int(blur) > 1


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

    if message.text == str(current_time().day):
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
                                     + '@' + safe_cast(chat.username, str, '/empty_username/')
                                     + ' ' + safe_cast(chat.first_name, str, '/empty_first_name/')
                                     + ' ' + safe_cast(chat.last_name, str, '/empty_last_name/'))
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


def send_photo_debug_info(chat, photo, timestamp):
    chat_id = chat.id

    if not is_admin(chat_id):
        first_name = chat.first_name
        last_name = chat.last_name
        username = chat.username
        caption = "PHOTO BY " + safe_cast(first_name, str, '/empty_first_name/') \
                  + " " + safe_cast(last_name, str, '/empty_last_name/') \
                  + " @" + safe_cast(username, str, '/empty_username/') \
                  + " " + str(chat_id) \
                  + ", " + str(timezoned_date(timestamp))
        for admin in ADMINS:
            bot.send_photo(admin, image_to_file(photo, SENT_IMAGE_FILE_NAME), caption=caption)


def build_and_send_image(message):
    chat_id = message.chat.id
    background_image = cache.get_image(chat_id)

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
    bot.send_message(chat_id, START_MESSAGE_TEXT)

    if is_admin(chat_id):
        bot.send_message(chat_id, START_MESSAGE_ADMIN_TEXT)


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
    elif state == ChatState.SPECIFYING_MAILING_LIST:
        set_mailing_list(message)
    elif state == ChatState.ENTERING_NEWSLETTER_MESSAGE:
        enter_newsletter_message(message)
    elif state == ChatState.CONFIRMING_NEWSLETTER:
        confirm_and_make_newsletter(message)


@bot.message_handler(content_types=["photo"])
def handle_photo(message):
    received_image = get_image_from_message(message)
    cache.set_image(message.chat.id, received_image)
    build_and_send_image(message)


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
