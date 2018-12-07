# -*- coding: utf-8 -*-

import io
import logging
import re
import time

import cherrypy
import requests
import telebot
from telebot import types

from botconfig import *
from botspeech import *
from botutil import *
from chatdata import ChatCache, ChatState
from mmphoto import gen_image

telebot.logger.setLevel(logging.INFO)

# A cache for chat data.
cache = ChatCache()

# A list of chats special messages will be sent to.
mailing_list = []

last_newsletter_messages = []

# Start the bot.
bot = telebot.TeleBot(API_TOKEN, threaded=False)

library_button = types.InlineKeyboardButton(text=GO_TO_INLINE_BUTTON, switch_inline_query_current_chat=GALLERY_TAG)

go_to_library_reply_markup = types.InlineKeyboardMarkup()
go_to_library_reply_markup.add(library_button)


def send_message_to_admins(message):
    for admin in ADMINS:
        bot.send_message(admin, message, parse_mode='html')


def handle_exception(exception):
    send_message_to_admins("%s\n\n%s" % (EXCEPTION_MESSAGE_TEXT, str(exception)))


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


stock_photo_ids = []


def load_stock_images_file_ids():
    stock_images_file = open(PROJECT_DIRECTORY + '/' + IMAGES_DIRECTORY + STOCK_IMAGES_FILEIDS_FILE_NAME, 'r')
    global stock_photo_ids
    for photo_id_with_line in stock_images_file.readlines():
        stock_photo_ids.append(photo_id_with_line[:-1])
    stock_images_file.close()


load_stock_images_file_ids()


def update_stock_images_file():
    stock_images_file = open(PROJECT_DIRECTORY + '/' + IMAGES_DIRECTORY + STOCK_IMAGES_FILEIDS_FILE_NAME, 'w')

    for d, dirs, files in os.walk(PROJECT_DIRECTORY + '/' + STOCK_IMAGES_DIRECTORY):
        for f in files:
            image = Image.open(PROJECT_DIRECTORY + '/' + STOCK_IMAGES_DIRECTORY + f).convert('RGB')
            message_with_image = bot.send_photo(ADMINS[0], image_to_file(image, SENT_IMAGE_FILE_NAME))
            file_id = message_with_image.photo[-1].file_id
            stock_images_file.write('%s%s' % (file_id, '\n'))
            bot.delete_message(ADMINS[0], message_with_image.message_id)

    stock_images_file.close()
    load_stock_images_file_ids()


# update_stock_images_file()


def is_admin(user):
    return str(user) in ADMINS


def html_inline_link_to_user(chat):
    username = chat.username
    firstname = chat.first_name
    lastname = chat.last_name
    user_id = chat.id
    if firstname is not None:
        if lastname is not None:
            text = "%s %s" % (firstname, lastname)
        else:
            text = firstname
    elif lastname is not None:
        text = lastname
    elif username is not None:
        text = '@%s' % username
    else:
        text = '/emptyuser/'
    return '<a href="tg://user?id=%s">%s %s</a>' % (user_id, text, user_id)


def debug_message_processing(message):
    chat_id = message.chat.id

    if not is_admin(chat_id):
        send_message_to_admins("<pre>MESSAGE FROM </pre>%s\n\n%s" % (html_inline_link_to_user(message.chat),
                                                                     safe_cast(message.text, str,
                                                                               '`/empty_message_text/`')))


def handle_free_text(message):
    text = message.text
    chat_id = message.chat.id

    if validate_blackout(text) or text == '1.0':
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

    handle_preliminary_admin_command(chat_id,
                                     "<pre>MAILING LIST:\n\n%s\n\nTO SEND A NEWSLETTER TYPE </pre>/%s"
                                     % (str(mailing_list), SEND_NEWSLETTER_COMMAND), ChatState.FREE)


def enter_newsletter_message(message):
    chat_id = message.chat.id

    cache.set_cached_message(chat_id, message)
    message = cache.get_cached_message(chat_id)

    bot.send_message(chat_id, "<pre>YOUR MESSAGE:</pre>", parse_mode='html')
    bot.send_message(chat_id, message.text, parse_mode="markdown", disable_web_page_preview=True)
    bot.send_message(chat_id, "<pre>ENTER CURRENT DAY OF MONTH TO CONFIRM</pre>", parse_mode='html')
    cache.set_state(chat_id, ChatState.CONFIRMING_NEWSLETTER)


def confirm_and_make_newsletter(message):
    global last_newsletter_messages
    chat_id = message.chat.id
    message_to_send = cache.get_cached_message(chat_id).text

    if message.text == str(current_time().day):
        last_newsletter_messages = []
        if len(mailing_list) > 0:
            log_message = bot.send_message(chat_id, '<pre>MAKING NEWSLETTER...\n</pre>', parse_mode='html')
            for chat_id_from_list in mailing_list:
                try:
                    bot.edit_message_text('<pre>%s\nSENDING TO %s...</pre>' % (log_message.text, chat_id_from_list),
                                          message_id=log_message.message_id, chat_id=chat_id, parse_mode='html')

                    sent_message = bot.send_message(chat_id_from_list, message_to_send,
                                                    parse_mode="markdown",
                                                    disable_web_page_preview=True,
                                                    reply_markup=go_to_library_reply_markup)
                    last_newsletter_messages.append(
                        {'chat_id': chat_id_from_list, 'message_id': sent_message.message_id})

                    log_message = bot.edit_message_text('<pre>%s\nSENT TO %s. MESSAGE ID: %s</pre>' % (
                        log_message.text, chat_id_from_list, sent_message.message_id),
                                                        message_id=log_message.message_id, chat_id=chat_id,
                                                        parse_mode='html')
                except telebot.apihelper.ApiException as e:
                    time.sleep(1)
                    chat = bot.get_chat(chat_id_from_list)
                    log_message = bot.edit_message_text(
                        '<pre>%s\nEXCEPTION THROWN WHILE SENDING TO </pre>%s: <pre>%s</pre>' % (
                            log_message.text, html_inline_link_to_user(chat), str(e)),
                        message_id=log_message.message_id, chat_id=chat_id,
                        parse_mode='html')
            bot.edit_message_text('<pre>%s\nFINISHED</pre>' % log_message.text,
                                  message_id=log_message.message_id, chat_id=chat_id, parse_mode='html')
            cache.set_state(chat_id, ChatState.FREE)
        else:
            bot.send_message(chat_id, 'MAILING LIST IS EMPTY')
            cache.set_state(chat_id, ChatState.FREE)
    else:
        bot.send_message(chat_id, 'WRONG. TRY AGAIN')


def handle_preliminary_admin_command(chat_id, text_to_send, state_to_set):
    cache.set_state(chat_id, state_to_set)
    bot.send_message(chat_id, text_to_send, parse_mode='html')


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


def build_image(heading, blackout, blur, background_image):
    return gen_image(heading, background_image, blackout, blur)


def send_photo_debug_info(chat, photo, timestamp):
    chat_id = chat.id

    if not is_admin(chat_id):
        caption = "<pre>PHOTO BY </pre>%s<pre>\n%s</pre>" % (
            html_inline_link_to_user(chat),
            str(timezoned_time(timestamp)))
        for admin in ADMINS:
            bot.send_photo(admin, image_to_file(photo, SENT_IMAGE_FILE_NAME), caption=caption, parse_mode='html')


def build_and_send_image(message):
    chat_id = message.chat.id

    heading = cache.get_heading(chat_id)
    blackout = cache.get_blackout(chat_id)
    blur = cache.get_blur(chat_id)
    background_image = cache.get_image(chat_id)

    wait_for_an_image_message = bot.send_message(chat_id, WAIT_FOR_AN_IMAGE_MESSAGE_TEXT,
                                                 reply_markup=types.ReplyKeyboardRemove())

    built_image = build_image(heading, blackout, blur, background_image)

    get_as_file_button = types.InlineKeyboardButton(text=GET_AS_FILE_BUTTON, callback_data=GET_AS_FILE_CALLBACK_DATA)
    get_as_doc_reply_markup = types.InlineKeyboardMarkup()
    get_as_doc_reply_markup.add(get_as_file_button)
    get_as_doc_reply_markup.add(library_button)

    bot.send_photo(chat_id, image_to_file(built_image, SENT_IMAGE_FILE_NAME), reply_markup=get_as_doc_reply_markup)
    bot.delete_message(chat_id, wait_for_an_image_message.message_id)
    # bot.send_message(chat_id, get_dolores_emoji(), reply_markup=go_to_library_reply_markup)

    send_photo_debug_info(message.chat, built_image, message.date)


@bot.message_handler(commands=['start'])
def handle_start_help(message):
    chat_id = message.chat.id

    cache.set_state(chat_id, ChatState.FREE)
    bot.send_message(chat_id, START_MESSAGE_TEXT, reply_markup=go_to_library_reply_markup)

    if is_admin(chat_id):
        bot.send_message(chat_id, START_MESSAGE_ADMIN_TEXT)


@bot.message_handler(commands=[SET_MAILING_LIST_COMMAND])
def handle_mailing_list_setter(message):
    handle_preliminary_command(message,
                               "<pre>CURRENT MAILING LIST:\n\n%s\n\nENTER NEW MAILING LIST</pre>"
                               % str(mailing_list),
                               ChatState.SPECIFYING_MAILING_LIST)


@bot.message_handler(commands=[SEND_NEWSLETTER_COMMAND])
def handle_make_newsletter(message):
    handle_preliminary_command(message,
                               "<pre>ENTER NEWSLETTER MESSAGE</pre>",
                               ChatState.ENTERING_NEWSLETTER_MESSAGE)


@bot.message_handler(commands=[UPDATE_INLINE_STOCKS_COMMAND])
def handle_update_stocks(message):
    if not is_admin(message.chat.id):
        handle_free_text(message)
    else:
        update_stock_images_file()
        bot.send_message(message.chat.id, "<pre>DONE</pre>", parse_mode='html')


@bot.message_handler(commands=[RECALL_NEWSLETTER_COMMAND])
def recall_newsletter(message):
    if not is_admin(message.chat.id):
        handle_free_text(message)
    else:
        global last_newsletter_messages
        for message_info in last_newsletter_messages:
            bot.delete_message(message_info['chat_id'], message_info['message_id'])
            bot.send_message(message.chat.id,
                             '<pre>MESSAGE %s DELETED FROM CHAT %s</pre>' % (
                                 message_info['message_id'], message_info['chat_id'])
                             , parse_mode='html')

        bot.send_message(message.chat.id, "<pre>RECALL OPERATION COMPLETED SUCCESSFULLY</pre>", parse_mode='html')


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

        bot.send_message(chat_id, get_dolores_emoji(), reply_markup=go_to_library_reply_markup)


inline_query_results = []


def update_inline_query_results():
    global inline_query_results
    id = 1
    for file_id in stock_photo_ids:
        inline_query_results.append(types.InlineQueryResultCachedPhoto(str(id), file_id, parse_mode='html'))
        # url = 'https://www.iea.org/media/news/2017/171113WEO2017MainImage.jpg'
        # inline_query_results.append(types.InlineQueryResultPhoto(str(id), url, url))
        id += 1


update_inline_query_results()


@bot.inline_handler(lambda query: query.query.startswith(
    GALLERY_TAG) or query.query + '\n' == GALLERY_TAG)  # lambda query: query.query == 'text'
def query_text(inline_query):
    global inline_query_results
    try:
        if len(inline_query.query) > len(GALLERY_TAG):
            text = inline_query.query[len(GALLERY_TAG):]
            cache.set_heading(inline_query.from_user.id, clear_text(text))
        bot.answer_inline_query(inline_query.id, inline_query_results)
    except Exception as e:
        print(e)


def as_file_reply_markup(file_id):
    get_as_file_button = types.InlineKeyboardButton(text=GET_AS_FILE_BUTTON,
                                                    callback_data='%s%s' % (GET_AS_FILE_CALLBACK_DATA, file_id))
    get_as_file_reply_markup = types.InlineKeyboardMarkup()
    get_as_file_reply_markup.add(get_as_file_button)
    get_as_file_reply_markup.add(library_button)

    return get_as_file_reply_markup


def as_photo_reply_markup(file_id):
    get_as_photo_button = types.InlineKeyboardButton(text=GET_AS_PHOTO_BUTTON,
                                                     callback_data='%s%s' % (GET_AS_PHOTO_CALLBACK_DATA, file_id))
    get_as_photo_reply_markup = types.InlineKeyboardMarkup()
    get_as_photo_reply_markup.add(get_as_photo_button)
    get_as_photo_reply_markup.add(library_button)

    return get_as_photo_reply_markup


@bot.callback_query_handler(lambda call: call.data.startswith(GET_AS_FILE_CALLBACK_DATA))
def get_as_file_callback(call):
    message = call.message
    chat_id = message.chat.id
    message_id = message.message_id
    if len(call.data) == len(GET_AS_FILE_CALLBACK_DATA):
        file_id = message.photo[-1].file_id
    else:
        file_id = call.data[len(GET_AS_FILE_CALLBACK_DATA):]

    url = 'https://api.telegram.org/file/bot%s/%s' % (API_TOKEN, bot.get_file(file_id).file_path)
    r = requests.get(url)
    with io.BytesIO(r.content) as f:
        f.name = 'image.jpg'
        try:
            bot.edit_message_caption('', chat_id, message_id, reply_markup=as_file_reply_markup(file_id))
            bot.send_document(chat_id, f, reply_markup=as_photo_reply_markup(file_id))
            bot.delete_message(chat_id, message_id)
        except telebot.apihelper.ApiException as e:
            True  # Do nothing. If the button was pressed many times, caption editing will throw an exception

        bot.answer_callback_query(call.id)


@bot.callback_query_handler(lambda call: call.data.startswith(GET_AS_PHOTO_CALLBACK_DATA))
def get_as_photo_callback(call):
    message = call.message
    chat_id = message.chat.id
    message_id = message.message_id
    file_id = call.data[len(GET_AS_PHOTO_CALLBACK_DATA):]

    url = 'https://api.telegram.org/file/bot%s/%s' % (API_TOKEN, bot.get_file(file_id).file_path)
    r = requests.get(url)
    with io.BytesIO(r.content) as f:
        try:
            bot.edit_message_caption('', chat_id, message_id, reply_markup=as_photo_reply_markup(file_id))
            bot.send_photo(chat_id, f, reply_markup=as_file_reply_markup(file_id))
            bot.delete_message(chat_id, message_id)
        except telebot.apihelper.ApiException as e:
            True  # Do nothing. If the button was pressed many times, caption editing will throw an exception

        bot.answer_callback_query(call.id)


while True:
    try:
        send_message_to_admins('<pre>I AM UP 🌚</pre>')
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
        send_message_to_admins('<pre>SEE YA 👋</pre>')
        break
