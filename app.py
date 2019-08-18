# -*- coding: utf-8 -*-
import re
import time

import requests
import telebot
from PIL import Image

from botconfig import *
from botdata import BotData
from botspeech import *
from botutil import *
from chat_states import ChatState
from mm_image_generator import generate_image
from ui_elements import *

if PROXY is not None:
    telebot.apihelper.proxy = {
        'http': PROXY,
        'https': PROXY
    }
bot = telebot.TeleBot(API_TOKEN, threaded=False)

# DB.
bot_data = BotData()


def log(message):
    return bot.send_message(LOGS_CHANNEL_ID, message, parse_mode='html')


def handle_exception(exception):
    log("<pre>%s</pre>\n\n%s" % (EXCEPTION_MESSAGE_TEXT, str(exception)))


def is_developer(user_id):
    return str(DEVELOPER_ID) == str(user_id)


def can_remove_this_image(user_id, image_id):
    return is_developer(user_id) or bot_data.is_owner(user_id, image_id)


def get_image_from_file_id(file_id):
    file_info = bot.get_file(file_id)
    downloaded_file = bot.download_file(file_info.file_path)
    image = Image.open(BytesIO(downloaded_file))

    return image


def how_to_call_this_user(chat_id):
    chat = bot.get_chat(chat_id)
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


def html_inline_link_to_user(chat_id):
    return '<a href="tg://user?id=%s">%s</a>' % (chat_id, how_to_call_this_user(chat_id))


def validate_blackout(blackout):
    return re.match("^[-+]?[0-9]*\.?[0-9]+$", blackout) is not None and 0 <= float(blackout) < 1


def validate_blur(blur):
    return blur.isdigit() and int(blur) > 1


def validate_chat_id(chat_id):
    return chat_id.isdigit()


def log_photo(chat_id, built_image, timestamp):
    if not is_developer(chat_id):
        caption = "<pre>PHOTO BY </pre> %s <pre>\n%s</pre>" % (
            html_inline_link_to_user(chat_id), str(timezoned_time(timestamp)))

        bot.send_photo(LOGS_CHANNEL_ID,
                       image_to_file(built_image, SENT_IMAGE_FILE_NAME),
                       caption=caption,
                       parse_mode='html')


def build_and_send_image(message):
    chat_id = message.chat.id

    heading = bot_data.get_heading(chat_id)
    blackout = bot_data.get_blackout(chat_id)
    blur = bot_data.get_blur(chat_id)

    file_id = bot_data.get_image(chat_id)
    background_image = get_image_from_file_id(file_id) if file_id is not None else Image.new(mode='RGB',
                                                                                             size=(1920, 1080),
                                                                                             color=(41, 54, 72))

    wait_for_an_image_message = bot.send_message(chat_id, WAIT_FOR_AN_IMAGE_MESSAGE_TEXT,
                                                 reply_markup=types.ReplyKeyboardRemove(), disable_notification=True)
    bot.delete_message(chat_id, message.message_id)
    built_image = generate_image(heading, background_image, blackout, blur)
    can_remove = can_remove_this_image(chat_id, file_id)
    image_exists = bot_data.image_exists(file_id)
    bot.send_photo(chat_id, image_to_file(built_image, SENT_IMAGE_FILE_NAME),
                   reply_markup=get_as_file_reply_markup('', file_id, can_remove, image_exists),
                   disable_notification=True)
    bot.delete_message(chat_id, wait_for_an_image_message.message_id)

    log_photo(chat_id, built_image, message.date)


def handle_free_text(message):
    text = message.text
    chat_id = message.chat.id

    if is_developer(message.chat.id):
        if text == '/':
            bot.delete_message(message.chat.id, message.message_id)
            newsletter_menu(message.chat)
            return
    if validate_blackout(text) or text == '1.0':
        bot_data.set_blackout(chat_id, float(text))
        build_and_send_image(message)
    elif validate_blur(text) or text == '1':
        bot_data.set_blur(chat_id, int(text))
        build_and_send_image(message)
    else:
        bot_data.set_heading(chat_id, clear_text(message.text))
        build_and_send_image(message)


@bot.message_handler(commands=['start'])
def handle_start(message):
    handle_help(message)


@bot.message_handler(commands=['help'])
def handle_help(message):
    chat_id = message.chat.id

    log('%s <pre>ASKED FOR HELP</pre>' % html_inline_link_to_user(message.chat.id))

    bot_data.set_state(chat_id, ChatState.FREE)
    bot.send_message(chat_id, START_MESSAGE_TEXT, reply_markup=get_go_to_library_reply_markup())


def newsletter_menu(chat):
    bot.send_message(chat.id,
                     '<pre>GREETINGS, %s</pre>' % how_to_call_this_user(chat.id).upper(),
                     parse_mode='html', disable_notification=True, reply_markup=get_newsletter_menu_reply_markup())


@bot.callback_query_handler(lambda call: call.data.startswith(MAKE_NEWSLETTER_CALLBACK_DATA))
def handle_make_newsletter(call):
    if is_developer(call.message.chat.id):
        message = call.message
        chat_id = message.chat.id
        message_id = message.message_id
        bot.answer_callback_query(call.id)
        bot.delete_message(chat_id, message_id)

        chat_id = call.message.chat.id
        if not is_developer(chat_id):
            handle_free_text(message.text)
        else:
            bot_data.set_state(chat_id, ChatState.ENTERING_NEWSLETTER_MESSAGE)
            bot.send_message(chat_id, "<pre>ENTER NEWSLETTER MESSAGE</pre>", parse_mode='html',
                             reply_markup=get_delete_button_reply_markup(),
                             disable_notification=True)
    else:
        bot.answer_callback_query(call.id)


def confirming_newsletter(message):
    chat_id = message.chat.id

    bot_data.set_cached_message(chat_id, message.text)
    message_text = bot_data.get_cached_message(chat_id)

    bot.send_message(chat_id, "<pre>YOUR MESSAGE:</pre>", parse_mode='html',
                     reply_markup=get_delete_button_reply_markup(), disable_notification=True)
    bot.send_message(chat_id, message_text, parse_mode="markdown", reply_markup=get_delete_button_reply_markup(),
                     disable_notification=True)
    bot.send_message(chat_id, "<pre>ENTER CURRENT DAY OF MONTH TO CONFIRM</pre>", parse_mode='html',
                     reply_markup=get_delete_button_reply_markup(), disable_notification=True)
    bot_data.set_state(chat_id, ChatState.CONFIRMING_NEWSLETTER)


def confirm_and_make_newsletter(message):
    chat_id = message.chat.id
    message_to_send = bot_data.get_cached_message(chat_id)

    mailing_list = bot_data.get_mailing_list()

    if message.text == str(current_time().day):
        last_newsletter_messages = []
        if len(mailing_list) > 0:
            log_message = bot.send_message(chat_id, '<pre>MAKING NEWSLETTER...\n</pre>', parse_mode='html',
                                           reply_markup=get_delete_button_reply_markup())
            for chat_id_from_list in mailing_list:
                try:
                    time.sleep(1)
                    bot.edit_message_text('<pre>%s\nSENDING TO %s...</pre>' % (log_message.text, chat_id_from_list),
                                          message_id=log_message.message_id, chat_id=chat_id, parse_mode='html')

                    sent_message = bot.send_message(chat_id_from_list, message_to_send,
                                                    parse_mode="markdown",
                                                    disable_web_page_preview=True,
                                                    reply_markup=get_go_to_library_reply_markup())
                    last_newsletter_messages.append(
                        {'chat_id': chat_id_from_list, 'message_id': sent_message.message_id})

                    log_message = bot.edit_message_text('<pre>%s\nSENT TO %s. MESSAGE ID: %s</pre>' % (
                        log_message.text, how_to_call_this_user(chat_id_from_list), sent_message.message_id),
                                                        message_id=log_message.message_id, chat_id=chat_id,
                                                        parse_mode='html',
                                                        reply_markup=get_delete_button_reply_markup())
                except telebot.apihelper.ApiException as e:
                    time.sleep(1)
                    chat = bot.get_chat(chat_id_from_list)
                    log_message = bot.edit_message_text(
                        '<pre>%s\nEXCEPTION THROWN WHILE SENDING TO </pre>%s: <pre>%s</pre>' % (
                            log_message.text, html_inline_link_to_user(chat.id), str(e)),
                        message_id=log_message.message_id, chat_id=chat_id,
                        parse_mode='html')
            bot.edit_message_text('<pre>%s\nFINISHED</pre>' % log_message.text,
                                  message_id=log_message.message_id, chat_id=chat_id, parse_mode='html',
                                  reply_markup=get_delete_button_reply_markup())
            bot_data.set_state(chat_id, ChatState.FREE)
        else:
            bot.send_message(chat_id, '<pre>MAILING LIST IS EMPTY</pre>', parse_mode='html')
            bot_data.set_state(chat_id, ChatState.FREE)

        bot_data.set_last_newsletter_messages(last_newsletter_messages)
    else:
        bot.send_message(chat_id, '<pre>WRONG. TRY AGAIN</pre>', parse_mode='html')


@bot.callback_query_handler(lambda call: call.data.startswith(RECALL_NEWSLETTER_CALLBACK_DATA))
def confirm_recall(call):
    if is_developer(call.message.chat.id):

        chat_id = call.message.chat.id
        message_id = call.message.message_id
        bot.answer_callback_query(call.id)
        bot.delete_message(chat_id, message_id)
        bot.send_message(chat_id, '<pre>CONFIRM RECALL</pre>', parse_mode='html', disable_notification=True,
                         reply_markup=get_confirm_recall_reply_markup())
    else:
        bot.answer_callback_query(call.id)


@bot.callback_query_handler(lambda call: call.data.startswith(RECALL_CONFIRMED_CALLBACK_DATA))
def recall(call):
    if is_developer(call.message.chat.id):
        message = call.message
        chat_id = message.chat.id
        message_id = message.message_id
        bot.answer_callback_query(call.id)
        bot.delete_message(chat_id, message_id)
        log_message = bot.send_message(chat_id, '<pre>RECALL OPERATION INITIATED...</pre>', parse_mode='html',
                                       reply_markup=get_delete_button_reply_markup())

        last_newsletter_messages = bot_data.get_last_newsletter_messages()

        for message_info in last_newsletter_messages:
            bot.delete_message(message_info['chat_id'], message_info['message_id'])
            log_message = bot.edit_message_text(
                '<pre>%s\nMESSAGE %s DELETED FROM %s</pre>' % (
                    log_message.text, message_info['message_id'], how_to_call_this_user(message_info['chat_id'])),
                chat_id=log_message.chat.id, message_id=log_message.message_id, parse_mode='html',
                reply_markup=get_delete_button_reply_markup())

        bot.edit_message_text("<pre>%s\nRECALL OPERATION COMPLETED SUCCESSFULLY</pre>" % log_message.text,
                              chat_id=message.chat.id, message_id=log_message.message_id, parse_mode='html',
                              reply_markup=get_delete_button_reply_markup())
    else:
        bot.answer_callback_query(call.id)


@bot.message_handler(content_types=['text'], func=lambda message: message.reply_to_message is None)
def handle_text(message):
    state = bot_data.get_state(message.chat.id)

    if state == ChatState.FREE:
        handle_free_text(message)
    elif state == ChatState.ENTERING_NEWSLETTER_MESSAGE:
        bot.delete_message(message.chat.id, message.message_id)
        confirming_newsletter(message)
    elif state == ChatState.CONFIRMING_NEWSLETTER:
        bot.delete_message(message.chat.id, message.message_id)
        confirm_and_make_newsletter(message)


@bot.message_handler(content_types=["photo"], func=lambda message: message.reply_to_message is None)
def handle_photo(message):
    file_id = message.photo[-1].file_id
    bot_data.set_image(message.chat.id, file_id)
    bot_data.increment_rating(file_id, message.chat.id)

    build_and_send_image(message)


def make_inline_query_result_from_images_info(images_info):
    res = []
    idd = 0
    for image_info in images_info:
        res.append((types.InlineQueryResultCachedPhoto(str(idd), image_info['image_id'], parse_mode='html')))
        idd += 1

    return res


@bot.inline_handler(lambda query: query.query.startswith(GALLERY_TAG) or query.query + '\n' == GALLERY_TAG)
def query_text(inline_query):
    if inline_query.offset == '':
        offset = 0
    else:
        offset = int(inline_query.offset)
    images_info = bot_data.get_images_sorted_by_rating()
    inline_stock_images = make_inline_query_result_from_images_info(images_info)
    next_offset = offset + 1

    if next_offset * 50 < len(inline_stock_images):
        next_offset = str(next_offset)
        left = offset * 50
        right = left + 50
    else:
        next_offset = ''
        left = offset * 50
        right = len(inline_stock_images)

    try:
        bot.answer_inline_query(inline_query.id, inline_stock_images[left:right], cache_time=1, next_offset=next_offset)
    except Exception as e:
        handle_exception(e)


@bot.callback_query_handler(lambda call: call.data.startswith(REMOVE_FROM_GALLERY_CALLBACK_DATA))
def remove_image_from_gallery(call):
    image_to_remove = call.data[len(REMOVE_FROM_GALLERY_CALLBACK_DATA):]
    can_remove = can_remove_this_image(call.message.chat.id, image_to_remove)

    if can_remove:
        bot.send_photo(call.message.chat.id, image_to_remove, ARE_YOU_SURE_TO_DELETE_IMAGE,
                       reply_markup=get_confirm_removing_reply_markup(image_to_remove))
        bot.answer_callback_query(call.id)
    elif can_remove is None:
        bot.answer_callback_query(call.id, text=ALREADY_REMOVED_ANSWER)
    else:
        bot.answer_callback_query(call.id, text=NOT_YOURS_ANSWER)


@bot.callback_query_handler(lambda call: call.data.startswith(CONFIRMED_REMOVE_FROM_GALLERY_CALLBACK_DATA))
def confirmed_remove(call):
    image_to_remove = call.data[len(CONFIRMED_REMOVE_FROM_GALLERY_CALLBACK_DATA):]
    can_remove = can_remove_this_image(call.message.chat.id, image_to_remove)
    if can_remove:
        result = bot_data.remove_image(image_to_remove)
        bot.delete_message(call.message.chat.id, call.message.message_id)
    elif can_remove is None:
        result = 0
    else:
        result = -1

    if result == 1:
        bot.answer_callback_query(call.id, text=SUCCESSFULLY_REMOVED_ANSWER)
    elif result == 0:
        bot.answer_callback_query(call.id, text=ALREADY_REMOVED_ANSWER)
    elif result == -1:
        bot.answer_callback_query(call.id, text=NOT_YOURS_ANSWER)


@bot.callback_query_handler(lambda call: call.data.startswith(GET_AS_FILE_CALLBACK_DATA))
def get_as_file_callback(call):
    message = call.message
    chat_id = message.chat.id
    message_id = message.message_id
    if len(call.data) == len(GET_AS_FILE_CALLBACK_DATA):
        file_id = message.photo[-1].file_id
    else:
        file_id = call.data[len(GET_AS_FILE_CALLBACK_DATA):]

    # TODO: IS_OWNER_CALLBACK_DATA

    image_from_library_id = bot_data.get_image(chat_id)
    can_remove = can_remove_this_image(chat_id, image_from_library_id)
    image_exists = bot_data.image_exists(image_from_library_id)

    try:
        url = 'https://api.telegram.org/file/bot%s/%s' % (API_TOKEN, bot.get_file(file_id).file_path)
        r = requests.get(url)
        with BytesIO(r.content) as f:
            f.name = 'image.jpg'
            bot.delete_message(chat_id, message_id)
            bot.send_document(chat_id, f,
                              reply_markup=get_as_photo_reply_markup(file_id, image_from_library_id, can_remove,
                                                                     image_exists),
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

    # TODO: IS_OWNER_CALLBACK_DATA

    image_from_library_id = bot_data.get_image(chat_id)
    can_remove = can_remove_this_image(chat_id, image_from_library_id)
    image_exists = bot_data.image_exists(image_from_library_id)

    try:
        bot.delete_message(chat_id, message_id)
        bot.send_photo(chat_id, file_id,
                       reply_markup=get_as_file_reply_markup(file_id, image_from_library_id, can_remove, image_exists),
                       disable_notification=True)
    except telebot.apihelper.ApiException as e:
        True  # Do nothing. If the button was pressed many times, caption editing will throw an exception

    bot.answer_callback_query(call.id)


@bot.callback_query_handler(lambda call: call.data.startswith(HIDE_MENU_CALLBACK_DATA))
def hide_menu(call):
    if is_developer(call.message.chat.id):
        bot_data.set_state(call.message.chat.id, ChatState.FREE)
        bot.answer_callback_query(call.id)
        bot.delete_message(call.message.chat.id, call.message.message_id)
    else:
        bot.answer_callback_query(call.id)


if __name__ == '__main__':
    while True:
        try:
            log('<pre>BOT IS UP</pre>')

            # Remove webhook, it fails sometimes the set if there is a previous webhook
            bot.remove_webhook()

            # if PROD == 'TRUE':
            #
            #     # Set webhook
            #     bot.set_webhook(url=WEBHOOK_URL_BASE + WEBHOOK_URL_PATH,
            #                     certificate=open(WEBHOOK_SSL_CERT, 'r'))
            #
            #     time.sleep(1)
            #
            #     # Start cherrypy server
            #     cherrypy.config.update({
            #         'server.socket_host': HOST_TO_LISTEN,
            #         'server.socket_port': PORT_TO_LISTEN,
            #         'engine.autoreload.on': False
            #     })
            #
            #     cherrypy.quickstart(WebhookServer(), '/', {'/': {}})
            # else:
            #     bot.polling(none_stop=True)

            bot.polling(none_stop=True)

        except Exception as e:
            handle_exception(e)
        else:
            log('<pre>SEE YA</pre>')
            break
