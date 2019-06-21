# -*- coding: utf-8 -*-

import io
import logging
import re
import time

import cherrypy
import requests
import telebot
from PIL import Image
from telebot import apihelper
from telebot import types

from bot_elements_config import *
from botconfig import *
from botspeech import *
from botutil import *
from chatdata import ChatCache, ChatState
from mmphoto import gen_image

telebot.logger.setLevel(logging.INFO)

# A cache for chat data.
cache = ChatCache()

# A list of chats special messages will be sent to.
mailing_list = set()

last_newsletter_messages = []

reply_to_library = dict()

# Start the bot.
bot = telebot.TeleBot(API_TOKEN, threaded=False)

if PROXY is not None:
    apihelper.proxy = {
        'http': PROXY,
        'https': PROXY
    }

gallery_button = types.InlineKeyboardButton(text=GO_TO_INLINE_BUTTON, switch_inline_query_current_chat=GALLERY_TAG)

go_to_library_reply_markup = types.InlineKeyboardMarkup()
go_to_library_reply_markup.add(gallery_button)

delete_button = types.InlineKeyboardButton(text=HIDE_MENU_BUTTON, callback_data=HIDE_MENU_CALLBACK_DATA)
delete_button_reply_markup = types.InlineKeyboardMarkup()
delete_button_reply_markup.add(delete_button)


def send_message_to_creator(message):
    creator = CREATORS[0]
    return bot.send_message(creator, message, parse_mode='html', reply_markup=delete_button_reply_markup)


def handle_exception(exception):
    send_message_to_creator("<pre>%s</pre>\n\n%s" % (EXCEPTION_MESSAGE_TEXT, str(exception)))


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


inline_stock_images = []


def update_stock_images():
    log_message = send_message_to_creator('<pre>LOADING STOCKS...</pre>')
    global inline_stock_images
    id = 1
    for d, dirs, files in os.walk(PROJECT_DIRECTORY + '/' + STOCK_IMAGES_DIRECTORY):
        for f in files:
            if f.endswith('.png'):
                image = Image.open(PROJECT_DIRECTORY + '/' + STOCK_IMAGES_DIRECTORY + f).convert('RGB')
                message_with_image = bot.send_photo(CACHE_CHANNEL_ID, image_to_file(image, SENT_IMAGE_FILE_NAME))
                file_id = message_with_image.photo[-1].file_id
                inline_stock_images.append(types.InlineQueryResultCachedPhoto(str(id), file_id, parse_mode='html'))
                bot.delete_message(CACHE_CHANNEL_ID, message_with_image.message_id)
                id += 1

    bot.delete_message(log_message.chat.id, log_message.message_id)
    send_message_to_creator('<pre>STOCKS LOADED</pre>')


def has_admin_access(user):
    return str(user) in ADMINS


def has_creator_access(user):
    return str(user) in CREATORS


def how_to_call_this_user(chat):
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

    return '%s %s' % (text, user_id)


def html_inline_link_to_user(chat):
    return '<a href="tg://user?id=%s">%s</a>' % (chat.id, how_to_call_this_user(chat))


def debug_message_processing(message):
    chat_id = message.chat.id

    # Rudimental
    if not has_admin_access(chat_id):
        send_message_to_creator("<pre>MESSAGE FROM </pre>%s\n\n%s" % (html_inline_link_to_user(message.chat),
                                                                      safe_cast(message.text, str,
                                                                                '`/empty_message_text/`')))
    # Rudimental


def show_debug_menu(chat):
    newsletter_button = types.InlineKeyboardButton(text=NEWSLETTER_BUTTON, callback_data=NEWSLETTER_CALLBACK_DATA)
    hide_menu_button = types.InlineKeyboardButton(text=HIDE_MENU_BUTTON, callback_data=HIDE_MENU_CALLBACK_DATA)

    debug_reply_markup = types.InlineKeyboardMarkup()
    debug_reply_markup.add(newsletter_button)
    debug_reply_markup.add(hide_menu_button)
    debug_reply_markup.add(gallery_button)

    bot.send_message(chat.id, '<pre>GREETINGS, %s</pre>' % how_to_call_this_user(chat).upper(),
                     parse_mode='html', reply_markup=debug_reply_markup, disable_notification=True)

    return


def handle_free_text(message):
    text = message.text
    chat_id = message.chat.id

    if has_creator_access(message.chat.id):
        if text == '/':
            bot.delete_message(message.chat.id, message.message_id)
            show_debug_menu(message.chat)
            return
    if validate_blackout(text) or text == '1.0':
        cache.set_blackout(chat_id, float(text))
        build_and_send_image(message)
    elif validate_blur(text) or text == '1':
        cache.set_blur(chat_id, int(text))
        build_and_send_image(message)
    else:
        cache.set_message_id_to_reply(chat_id, message.message_id)
        cache.set_heading(chat_id, clear_text(message.text))
        build_and_send_image(message)


def validate_blackout(blackout):
    return re.match("^[-+]?[0-9]*\.?[0-9]+$", blackout) is not None and 0 <= float(blackout) < 1


def validate_blur(blur):
    return blur.isdigit() and int(blur) > 1


def validate_chat_id(chat_id):
    return chat_id.isdigit()


def add_recipients_to_list(set_of_chat_ids):
    global mailing_list
    mailing_list |= set(set_of_chat_ids)


def set_mailing_list(message):
    mailing_list.clear()

    for chat_id_for_list in message.text.split('\n'):
        if validate_chat_id(chat_id_for_list):
            add_recipients_to_list({chat_id_for_list})

    make_newsletter_button = types.InlineKeyboardButton(text=MAKE_NEWSLETTER_BUTTON,
                                                        callback_data=MAKE_NEWSLETTER_CALLBACK_DATA)
    add_recipients_button = types.InlineKeyboardButton(text=ADD_RECIPIENTS_BUTTON,
                                                       callback_data=ADD_RECIPIENTS_CALLBACK_DATA)
    false_alarm_button = types.InlineKeyboardButton(text=FALSE_ALARM_BUTTON,
                                                    callback_data=FALSE_ALARM_CALLBACK_DATA)
    recepients_added_reply_markup = types.InlineKeyboardMarkup()
    recepients_added_reply_markup.add(make_newsletter_button)
    recepients_added_reply_markup.add(add_recipients_button)
    recepients_added_reply_markup.add(false_alarm_button)

    handle_preliminary_command(message, "<pre>MAILING LIST:\n\n%s</pre>" % (str(mailing_list)), ChatState.FREE,
                               reply_markup=recepients_added_reply_markup)


false_alarm_button = types.InlineKeyboardButton(text=FALSE_ALARM_BUTTON,
                                                callback_data=FALSE_ALARM_CALLBACK_DATA)
false_alarm_reply_markup = types.InlineKeyboardMarkup()
false_alarm_reply_markup.add(false_alarm_button)


def enter_newsletter_message(message):
    chat_id = message.chat.id

    cache.set_cached_message(chat_id, message)
    message = cache.get_cached_message(chat_id)

    bot.send_message(chat_id, "<pre>YOUR MESSAGE:</pre>", parse_mode='html')
    bot.send_message(chat_id, message.text, parse_mode="markdown", disable_web_page_preview=True)
    bot.send_message(chat_id, "<pre>ENTER CURRENT DAY OF MONTH TO CONFIRM</pre>", parse_mode='html',
                     reply_markup=false_alarm_reply_markup)
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
                    time.sleep(1)
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
            bot.send_message(chat_id, '<pre>MAILING LIST IS EMPTY</pre>', parse_mode='html')
            cache.set_state(chat_id, ChatState.FREE)
    else:
        bot.send_message(chat_id, '<pre>WRONG. TRY AGAIN</pre>', parse_mode='html')


def handle_preliminary_command(message, text_to_send, state_to_set, reply_markup=None):
    chat_id = message.chat.id
    if not has_creator_access(chat_id):
        handle_free_text(message.text)
    else:
        cache.set_state(chat_id, state_to_set)
        bot.send_message(chat_id, text_to_send, parse_mode='html', reply_markup=reply_markup, disable_notification=True)


def get_image_from_file_id(file_id):
    file_info = bot.get_file(file_id)
    downloaded_file = bot.download_file(file_info.file_path)
    image = Image.open(BytesIO(downloaded_file))

    return image


def build_image(heading, blackout, blur, background_image):
    return gen_image(heading, background_image, blackout, blur)


def send_photo_debug_info(chat, built_image, timestamp, file_id=None):
    chat_id = chat.id
    message_id_to_reply = cache.get_message_id_to_reply(chat_id)

    if not has_creator_access(chat_id):
        debug_photo_reply_markup = types.InlineKeyboardMarkup()

        if message_id_to_reply is not None:
            reply_button = types.InlineKeyboardButton(text=REPLY_BUTTON,
                                                      callback_data='%s %s %s' % (
                                                          REPLY_CALLBACK_DATA, chat_id, message_id_to_reply))
            debug_photo_reply_markup.add(reply_button)

        background_photo_button = types.InlineKeyboardButton(text=BACKGROUND_PHOTO_BUTTON,
                                                             callback_data='%s%s' % (
                                                                 BACKGROUND_PHOTO_CALLBACK_DATA, file_id))
        debug_photo_reply_markup.add(background_photo_button)
        debug_photo_reply_markup.add(delete_button)

        caption = "<pre>PHOTO BY </pre>%s<pre>\n%s</pre>" % (
            html_inline_link_to_user(chat),
            str(timezoned_time(timestamp)))
        for admin in ADMINS:
            if str(chat_id) != str(admin):
                bot.send_photo(admin,
                               image_to_file(built_image, SENT_IMAGE_FILE_NAME),
                               caption=caption,
                               parse_mode='html',
                               reply_markup=debug_photo_reply_markup)


def build_and_send_image(message):
    chat_id = message.chat.id

    heading = cache.get_heading(chat_id)
    blackout = cache.get_blackout(chat_id)
    blur = cache.get_blur(chat_id)

    file_id = cache.get_image(chat_id)
    background_image = get_image_from_file_id(file_id)

    if message.photo is not None or validate_blackout(message.text) or validate_blur(message.text):
        bot.delete_message(chat_id, message.message_id)
    wait_for_an_image_message = bot.send_message(chat_id, WAIT_FOR_AN_IMAGE_MESSAGE_TEXT,
                                                 reply_markup=types.ReplyKeyboardRemove(), disable_notification=True)

    built_image = build_image(heading, blackout, blur, background_image)

    get_as_file_button = types.InlineKeyboardButton(text=GET_AS_FILE_BUTTON, callback_data=GET_AS_FILE_CALLBACK_DATA)
    get_as_doc_reply_markup = types.InlineKeyboardMarkup()
    get_as_doc_reply_markup.add(get_as_file_button)
    get_as_doc_reply_markup.add(gallery_button)

    bot.send_photo(chat_id, image_to_file(built_image, SENT_IMAGE_FILE_NAME), reply_markup=get_as_doc_reply_markup,
                   disable_notification=True)
    bot.delete_message(chat_id, wait_for_an_image_message.message_id)

    send_photo_debug_info(message.chat, built_image, message.date, file_id=file_id)


@bot.message_handler(commands=['start'])
def handle_start(message):
    handle_help(message)


@bot.message_handler(commands=['help'])
def handle_help(message):
    chat_id = message.chat.id

    cache.set_state(chat_id, ChatState.FREE)
    bot.send_message(chat_id, START_MESSAGE_TEXT, reply_markup=go_to_library_reply_markup)


def get_user_id_to_reply(message_id):
    return reply_to_library.get(message_id, None)


def remember_user_id_to_reply(user_id, message_id, cash_size):
    counter = 0
    for key in reply_to_library.keys():
        if reply_to_library.get(key) == user_id:
            counter += 1
    if counter == cash_size:
        for key in reply_to_library.keys():
            if reply_to_library.get(key) == user_id:
                reply_to_library.pop(key)

    reply_to_library[message_id] = user_id


def send_custom_message(message, chat_id):
    if message.content_type == "text":
        bot.send_message(chat_id, message.text, parse_mode='markdown', reply_markup=types.ForceReply())
    elif message.content_type == "audio":
        bot.send_audio(chat_id, message.audio.file_id, reply_markup=types.ForceReply())
    elif message.content_type == "document":
        bot.send_document(chat_id, message.document.file_id, reply_markup=types.ForceReply())
    elif message.content_type == "photo":
        bot.send_photo(chat_id, message.photo[-1].file_id, reply_markup=types.ForceReply())
    elif message.content_type == "sticker":
        bot.send_sticker(chat_id, message.sticker.file_id, reply_markup=types.ForceReply())
    elif message.content_type == "video":
        bot.send_video(chat_id, message.video.file_id, reply_markup=types.ForceReply())
    elif message.content_type == "video_note":
        bot.send_video_note(chat_id, message.video_note.file_id, reply_markup=types.ForceReply())
    elif message.content_type == "voice":
        bot.send_voice(chat_id, message.voice.file_id, reply_markup=types.ForceReply())
    elif message.content_type == "location":
        try:
            live_period = message.location.live_period
        except Exception as e:
            live_period = None
        bot.send_location(chat_id, latitude=message.location.latitude,
                          longitude=message.location.longitude,
                          live_period=live_period, reply_markup=types.ForceReply())


@bot.message_handler(
    content_types=["text",
                   "audio",
                   "document",
                   "photo",
                   "sticker",
                   "video",
                   "video_note",
                   "voice",
                   "location"],
    func=lambda message: message.reply_to_message is not None
                         and (message.reply_to_message.forward_from is not None
                              or message.reply_to_message.forward_from_chat is not None)
                         and has_admin_access(message.chat.id))
def reply_to_debug_message(message):
    user_id = message.chat.id
    if message.reply_to_message.forward_from is None:
        user_id_to_reply = get_user_id_to_reply(message.reply_to_message.message_id)
    else:
        user_id_to_reply = message.reply_to_message.forward_from.id

    if user_id_to_reply is None:
        bot.send_message(user_id,
                         '<pre>MESSAGE HAS NOT BEEN SENT. TO REPLY PLEASE USE THE LAST MESSAGE FROM THIS USER</pre>',
                         parse_mode='html',
                         disable_notification=True, reply_markup=delete_button_reply_markup)

    to_delete = bot.send_message(user_id, '<pre>SENDING TO %s...</pre>'
                                 % how_to_call_this_user(bot.get_chat(user_id_to_reply)), parse_mode='html',
                                 disable_notification=True)
    if str(user_id) in CREATORS:
        role = 'CREATOR'
    else:
        role = 'ADMIN'

    for admin_id in ADMINS:
        if str(admin_id) != str(user_id):
            bot.send_message(admin_id, "<pre>ANSWER FROM %s</pre> %s. <pre>MESSAGE:</pre>" % (
                role, html_inline_link_to_user(message.chat)),
                             parse_mode='html')
            send_custom_message(message, admin_id)

    send_custom_message(message, user_id_to_reply)

    bot.send_message(message.chat.id, '<pre>SENT TO %s</pre>'
                     % how_to_call_this_user(bot.get_chat(user_id_to_reply)), parse_mode='html',
                     disable_notification=True, reply_markup=delete_button_reply_markup)
    bot.delete_message(to_delete.chat.id, to_delete.message_id)


@bot.message_handler(content_types=["text",
                                    "audio",
                                    "document",
                                    "photo",
                                    "sticker",
                                    "video",
                                    "video_note",
                                    "voice",
                                    "location",
                                    "contact"],
                     func=lambda message: (message.reply_to_message is not None
                                           and message.reply_to_message.from_user.id == bot.get_me().id
                                           or message.reply_to_message is None and message.content_type != 'text'
                                           and message.content_type != 'photo')
                                          and not has_creator_access(message.chat.id))
def reply_to_debug_message_not_from_admin(message):
    for admin in ADMINS:
        if str(message.chat.id) != str(admin):
            if message.content_type == "audio" or message.content_type == "sticker":
                bot.send_message(admin, '<pre>FROM %s</pre>:' % how_to_call_this_user(message.chat), parse_mode='html')
            forwarded_message = bot.forward_message(admin, message.chat.id, message.message_id)
            if forwarded_message.forward_from is None:
                remember_user_id_to_reply(message.chat.id, forwarded_message.message_id, len(ADMINS))


@bot.message_handler(content_types=['text'], func=lambda message: message.reply_to_message is None)
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


@bot.message_handler(content_types=["photo"], func=lambda message: message.reply_to_message is None)
def handle_photo(message):
    file_id = message.photo[-1].file_id
    # received_image = get_image_from_message(message)
    cache.set_image(message.chat.id, file_id)
    build_and_send_image(message)


@bot.inline_handler(lambda query: query.query.startswith(
    GALLERY_TAG) or query.query + '\n' == GALLERY_TAG)
def query_text(inline_query):
    global inline_stock_images
    try:
        if len(inline_query.query) > len(GALLERY_TAG):
            text = inline_query.query[len(GALLERY_TAG):]
            cache.set_heading(inline_query.from_user.id, clear_text(text))
        bot.answer_inline_query(inline_query.id, inline_stock_images)
    except Exception as e:
        handle_exception(e)


def as_file_reply_markup(file_id):
    get_as_file_button = types.InlineKeyboardButton(text=GET_AS_FILE_BUTTON,
                                                    callback_data='%s%s' % (GET_AS_FILE_CALLBACK_DATA, file_id))
    get_as_file_reply_markup = types.InlineKeyboardMarkup()
    get_as_file_reply_markup.add(get_as_file_button)
    get_as_file_reply_markup.add(gallery_button)

    return get_as_file_reply_markup


def as_photo_reply_markup(file_id):
    get_as_photo_button = types.InlineKeyboardButton(text=GET_AS_PHOTO_BUTTON,
                                                     callback_data='%s%s' % (GET_AS_PHOTO_CALLBACK_DATA, file_id))
    get_as_photo_reply_markup = types.InlineKeyboardMarkup()
    get_as_photo_reply_markup.add(get_as_photo_button)
    get_as_photo_reply_markup.add(gallery_button)

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

    try:
        url = 'https://api.telegram.org/file/bot%s/%s' % (API_TOKEN, bot.get_file(file_id).file_path)
        r = requests.get(url)
        with io.BytesIO(r.content) as f:
            f.name = 'image.jpg'
            bot.delete_message(chat_id, message_id)
            bot.send_document(chat_id, f, reply_markup=as_photo_reply_markup(file_id),
                              disable_notification=True)
    except telebot.apihelper.ApiException as e:
        True  # Do nothing. If the button was pressed many times, caption editing will throw an exception

    bot.answer_callback_query(call.id)


@bot.callback_query_handler(lambda call: call.data.startswith(GET_AS_PHOTO_CALLBACK_DATA))
def get_as_photo_callback(call):
    message = call.message
    chat_id = message.chat.id
    message_id = message.message_id
    file_id = call.data[len(GET_AS_PHOTO_CALLBACK_DATA):]

    try:
        bot.delete_message(chat_id, message_id)
        bot.send_photo(chat_id, file_id, reply_markup=as_file_reply_markup(file_id),
                       disable_notification=True)
    except telebot.apihelper.ApiException as e:
        True  # Do nothing. If the button was pressed many times, caption editing will throw an exception

    bot.answer_callback_query(call.id)


@bot.callback_query_handler(lambda call: call.data.startswith(RECALL_NEWSLETTER_CALLBACK_DATA))
def confirm_recall(call):
    if has_creator_access(call.message.chat.id):
        confirm_recall_button = types.InlineKeyboardButton(text=CONFIRM_RECALL_BUTTON,
                                                           callback_data=RECALL_CONFIRMED_CALLBACK_DATA)
        false_alarm_button = types.InlineKeyboardButton(text=FALSE_ALARM_BUTTON,
                                                        callback_data=FALSE_ALARM_CALLBACK_DATA)
        confirm_recall_reply_markup = types.InlineKeyboardMarkup()
        confirm_recall_reply_markup.add(confirm_recall_button)
        confirm_recall_reply_markup.add(false_alarm_button)

        chat_id = call.message.chat.id
        message_id = call.message.message_id
        # bot.edit_message_reply_markup(chat_id, message_id, reply_markup=confirm_recall_reply_markup)
        bot.answer_callback_query(call.id)
        bot.delete_message(chat_id, message_id)
        bot.send_message(chat_id, '<pre>CONFIRM RECALL</pre>', parse_mode='html', disable_notification=True,
                         reply_markup=confirm_recall_reply_markup)
    else:
        bot.answer_callback_query(call.id)


@bot.callback_query_handler(lambda call: call.data.startswith(RECALL_CONFIRMED_CALLBACK_DATA))
def recall(call):
    if has_creator_access(call.message.chat.id):
        message = call.message
        chat_id = message.chat.id
        message_id = message.message_id
        bot.answer_callback_query(call.id)
        bot.delete_message(chat_id, message_id)
        log_message = bot.send_message(chat_id, '<pre>RECALL OPERATION INITIATED...</pre>', parse_mode='html')
        global last_newsletter_messages
        for message_info in last_newsletter_messages:
            bot.delete_message(message_info['chat_id'], message_info['message_id'])
            log_message = bot.edit_message_text(
                '<pre>%s\nMESSAGE %s DELETED FROM CHAT %s</pre>' % (
                    log_message.text, message_info['message_id'], message_info['chat_id']),
                chat_id=log_message.chat.id, message_id=log_message.message_id, parse_mode='html')

        bot.edit_message_text("<pre>%s\nRECALL OPERATION COMPLETED SUCCESSFULLY</pre>" % log_message.text,
                              chat_id=message.chat.id, message_id=log_message.message_id, parse_mode='html')
    else:
        bot.answer_callback_query(call.id)


@bot.callback_query_handler(lambda call: call.data.startswith(NEWSLETTER_CALLBACK_DATA))
def show_newsletter_control_panel(call):
    if has_creator_access(call.message.chat.id):
        false_alarm_button = types.InlineKeyboardButton(text=FALSE_ALARM_BUTTON,
                                                        callback_data=FALSE_ALARM_CALLBACK_DATA)
        make_newsletter_button = types.InlineKeyboardButton(text=MAKE_NEWSLETTER_BUTTON,
                                                            callback_data=MAKE_NEWSLETTER_CALLBACK_DATA)
        recall_newsletter_button = types.InlineKeyboardButton(text=RECALL_NEWSLETTER_BUTTON,
                                                              callback_data=RECALL_NEWSLETTER_CALLBACK_DATA)
        add_recipients_button = types.InlineKeyboardButton(text=ADD_RECIPIENTS_BUTTON,
                                                           callback_data=ADD_RECIPIENTS_CALLBACK_DATA)
        newsletter_panel_reply_markup = types.InlineKeyboardMarkup()
        newsletter_panel_reply_markup.add(make_newsletter_button)
        newsletter_panel_reply_markup.add(add_recipients_button)
        newsletter_panel_reply_markup.add(recall_newsletter_button)
        newsletter_panel_reply_markup.add(false_alarm_button)

        bot.answer_callback_query(call.id)
        bot.delete_message(call.message.chat.id, call.message.message_id)
        bot.send_message(call.message.chat.id, '<pre>NEWSLETTER MANAGEMENT</pre>', parse_mode='html',
                         disable_notification=True,
                         reply_markup=newsletter_panel_reply_markup)
    else:
        bot.answer_callback_query(call.id)


@bot.callback_query_handler(lambda call: call.data.startswith(ADD_RECIPIENTS_CALLBACK_DATA))
def add_recipients(call):
    if has_creator_access(call.message.chat.id):

        handle_preliminary_command(call.message,
                                   "<pre>CURRENT MAILING LIST:\n\n%s\n\nENTER NEW MAILING LIST</pre>"
                                   % str(mailing_list), ChatState.SPECIFYING_MAILING_LIST,
                                   reply_markup=false_alarm_reply_markup)

        bot.answer_callback_query(call.id)
        bot.delete_message(call.message.chat.id, call.message.message_id)
    else:
        bot.answer_callback_query(call.id)


@bot.callback_query_handler(lambda call: call.data.startswith(MAKE_NEWSLETTER_CALLBACK_DATA))
def handle_make_newsletter(call):
    if has_creator_access(call.message.chat.id):
        message = call.message
        chat_id = message.chat.id
        message_id = message.message_id
        bot.answer_callback_query(call.id)
        bot.delete_message(chat_id, message_id)

        handle_preliminary_command(call.message,
                                   "<pre>ENTER NEWSLETTER MESSAGE</pre>",
                                   ChatState.ENTERING_NEWSLETTER_MESSAGE, false_alarm_reply_markup)
    else:
        bot.answer_callback_query(call.id)


@bot.callback_query_handler(lambda call: call.data.startswith(FALSE_ALARM_CALLBACK_DATA))
def false_alarm(call):
    if has_creator_access(call.message.chat.id):
        message = call.message
        chat_id = message.chat.id
        message_id = message.message_id
        bot.answer_callback_query(call.id)
        bot.delete_message(chat_id, message_id)
        show_debug_menu(call.message.chat)
        cache.set_state(chat_id, ChatState.FREE)
    else:
        bot.answer_callback_query(call.id)


@bot.callback_query_handler(lambda call: call.data.startswith(HIDE_MENU_CALLBACK_DATA))
def hide_menu(call):
    if has_creator_access(call.message.chat.id):
        cache.set_state(call.message.chat.id, ChatState.FREE)
        bot.answer_callback_query(call.id)
        bot.delete_message(call.message.chat.id, call.message.message_id)
    else:
        bot.answer_callback_query(call.id)


@bot.callback_query_handler(lambda call: call.data.startswith(REPLY_CALLBACK_DATA))
def force_reply_to_debug_message(call):
    if has_admin_access(call.message.chat.id):
        chat_id = call.message.chat.id
        calldata = call.data.split()
        user_id_to_reply = calldata[1]
        message_id_to_reply = calldata[2]
        forwarded_message = bot.forward_message(chat_id, user_id_to_reply, message_id_to_reply,
                                                disable_notification=True)

        if forwarded_message.forward_from is None:
            remember_user_id_to_reply(user_id_to_reply, forwarded_message.message_id, len(ADMINS))

        bot.answer_callback_query(call.id)
    else:
        bot.answer_callback_query(call.id)


@bot.callback_query_handler(lambda call: call.data.startswith(BACKGROUND_PHOTO_CALLBACK_DATA))
def save_photo(call):
    if has_admin_access(call.message.chat.id):
        file_id = call.data[len(BACKGROUND_PHOTO_CALLBACK_DATA):]
        url = 'https://api.telegram.org/file/bot%s/%s' % (API_TOKEN, bot.get_file(file_id).file_path)
        r = requests.get(url)
        with io.BytesIO(r.content) as f:
            f.name = 'image.jpg'
            bot.send_photo(call.message.chat.id, f, parse_mode='html', disable_notification=True)
        bot.answer_callback_query(call.id)
    else:
        bot.answer_callback_query(call.id)


while True:
    try:
        send_message_to_creator('<pre>I AM UP 🌚</pre>')
        update_stock_images()

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
        send_message_to_creator('<pre>SEE YA 👋</pre>')
        break
