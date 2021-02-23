# -*- coding: utf-8 -*-

import time
from abc import ABCMeta, abstractmethod
from io import BytesIO

import requests
from PIL import Image
from aiogram import Bot
from aiogram import types
from aiogram.utils.exceptions import TelegramAPIError, AIOGramWarning, RetryAfter, MessageToDeleteNotFound

from bot_elements_config import *
from botconfig import *
from botdata import BotData
from botspeech import *
from botutil import timezoned_time, current_time, image_to_file
from chat_states import ChatState


class Handler:
    __metaclass__ = ABCMeta
    bot: Bot
    bot_data: BotData

    def __init__(self, bot: Bot, bot_data: BotData):
        self.bot = bot
        self.bot_data = bot_data
        pass

    @abstractmethod
    async def handle_free_text(self, message):
        pass

    @abstractmethod
    async def build_image(self, message):
        pass

    @abstractmethod
    async def handle_help(self, chat_id):
        pass

    @abstractmethod
    async def change_pic_color_2021(self, call):
        pass

    @abstractmethod
    async def switch_mmnews(self, call):
        pass

    # async def handle_mode_change(self, message: types.Message):
    #     chat_id = message.chat.id
    #     self.bot_data.set_mode(chat_id, ChatMode(message.text[1:]))
    #     await self.build_and_send_image(message)

    async def build_and_send_image(self, message):
        await self.bot.delete_message(message.chat.id, message.message_id)
        await self.send_image(await self.build_image(message.chat.id), message)

    async def send_image(self, image, message):
        chat_id = message.chat.id
        file_id = self.bot_data.get_image(chat_id)
        can_remove = self.can_remove_this_image(chat_id, file_id)
        image_exists = self.bot_data.image_exists(file_id)
        photo_message = await self.bot.send_photo(chat_id, image_to_file(image, SENT_IMAGE_FILE_NAME),
                                                  reply_markup=self.get_as_file_reply_markup(file_id, can_remove,
                                                                                             image_exists))
        cached_photo_id = photo_message.photo[-1].file_id

        await self.log_photo(chat_id, cached_photo_id, message.date.timestamp())

    async def handle_text(self, message: types.Message):
        state = self.bot_data.get_state(message.chat.id)

        if state == ChatState.FREE:
            await self.handle_free_text(message)
        elif state == ChatState.ENTERING_NEWSLETTER_MESSAGE:
            await self.bot.delete_message(message.chat.id, message.message_id)
            await self.confirming_newsletter(message)
        elif state == ChatState.CONFIRMING_NEWSLETTER:
            await self.bot.delete_message(message.chat.id, message.message_id)
            await self.confirm_and_make_newsletter(message)

    async def handle_photo(self, message: types.Message):
        file_id = message.photo[-1].file_unique_id
        file_reuse_id = message.photo[-1].file_id
        self.bot_data.set_image(message.chat.id, file_id)
        self.bot_data.remember_reuse_id(file_id, file_reuse_id)
        self.bot_data.increment_rating(file_id, message.chat.id)

        await self.build_and_send_image(message)

    def make_inline_query_result_from_images_info(self, images_info):
        res = []
        idd = 0
        for image_info in images_info:
            res.append(
                (types.InlineQueryResultCachedPhoto(id=str(idd),
                                                    photo_file_id=self.bot_data.get_reuse_id(image_info['image_id']))))
            idd += 1

        return res

    async def gallery_query(self, inline_query):
        if inline_query.offset == '':
            offset = 0
        else:
            offset = int(inline_query.offset)
        images_info = self.bot_data.get_images_sorted_by_rating()
        inline_stock_images = self.make_inline_query_result_from_images_info(images_info)
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
            await self.bot.answer_inline_query(inline_query.id, inline_stock_images[left:right], cache_time=1,
                                               next_offset=next_offset)
        except Exception as e:
            await self.handle_exception(e)

    async def remove_image_from_gallery(self, call):
        image_to_remove = call.data[len(REMOVE_FROM_GALLERY_CALLBACK_DATA):]
        can_remove = self.can_remove_this_image(call.message.chat.id, image_to_remove)

        if can_remove:
            await self.bot.send_photo(call.message.chat.id, self.bot_data.get_reuse_id(image_to_remove),
                                      DO_YOU_WANT_TO_DELETE_IMAGE,
                                      reply_markup=self.get_confirm_removing_reply_markup(image_to_remove))
            await self.bot.answer_callback_query(call.id)
        elif can_remove is None:
            await self.bot.answer_callback_query(call.id, text=ALREADY_REMOVED_ANSWER)

    async def confirmed_remove(self, call):
        image_to_remove = call.data[len(CONFIRMED_REMOVE_FROM_GALLERY_CALLBACK_DATA):]
        result = self.bot_data.remove_image(image_to_remove)
        try:
            await self.bot.delete_message(call.message.chat.id, call.message.message_id)
        except MessageToDeleteNotFound:
            pass

        if result == 1:
            await self.bot.answer_callback_query(call.id, text=SUCCESSFULLY_REMOVED_ANSWER)
        elif result == 0:
            await self.bot.answer_callback_query(call.id, text=ALREADY_REMOVED_ANSWER)

    def get_button_position_by_callback_data(self, message: types.Message, callback_data):
        keyboard = message.reply_markup.inline_keyboard
        for line in keyboard:
            for button in line:
                if button.callback_data == callback_data:
                    return [keyboard.index(line), line.index(button)]
        return None

    async def get_as_file_callback(self, call):
        message: types.Message
        message = call.message
        file_reuse_id = message.photo[-1].file_id

        reply_markup = message.reply_markup
        position = self.get_button_position_by_callback_data(message, GET_AS_FILE_CALLBACK_DATA)
        reply_markup.inline_keyboard[position[0]][position[1]] = self.get_as_photo_button()

        url = 'https://api.telegram.org/file/bot%s/%s' % (API_TOKEN, (await self.bot.get_file(file_reuse_id)).file_path)
        r = requests.get(url)
        with BytesIO(r.content) as f:
            f.name = 'image.jpg'
            await message.edit_media(types.input_media.InputMediaDocument(f),
                                     reply_markup=reply_markup)

        await self.bot.answer_callback_query(call.id)

    async def get_as_photo_callback(self, call):
        message = call.message
        file_reuse_id = message.document.file_id

        reply_markup = message.reply_markup
        position = self.get_button_position_by_callback_data(message, GET_AS_PHOTO_CALLBACK_DATA)
        reply_markup.inline_keyboard[position[0]][position[1]] = self.get_as_file_button()

        url = 'https://api.telegram.org/file/bot%s/%s' % (API_TOKEN, (await self.bot.get_file(file_reuse_id)).file_path)
        r = requests.get(url)
        with BytesIO(r.content) as f:
            f.name = 'image.jpg'
            await message.edit_media(types.input_media.InputMediaPhoto(f),
                                     reply_markup=reply_markup)

        await self.bot.answer_callback_query(call.id)

    async def remove_this_message(self, call):
        try:
            await self.bot.delete_message(call.message.chat.id, call.message.message_id)
        except MessageToDeleteNotFound:
            pass
        self.bot_data.set_state(call.message.chat.id, ChatState.FREE)
        await self.bot.answer_callback_query(call.id)

    def is_developer(self, user_id):
        return str(DEVELOPER_ID) == str(user_id)

    async def html_inline_link_to_user(self, chat_id):
        return '<a href="tg://user?id=%s">%s</a>' % (chat_id, await self.how_to_call_this_user(chat_id))

    async def log(self, message):
        return await self.bot.send_message(LOGS_CHANNEL_ID, message, parse_mode='html')

    async def log_photo(self, chat_id, cached_photo, timestamp):
        if not self.is_developer(chat_id):
            html_link = await self.html_inline_link_to_user(chat_id)
            caption = "<pre>[PHOTOBOT] PHOTO BY </pre> %s <pre>\n%s</pre>" % (html_link, str(timezoned_time(timestamp)))
            await self.bot.send_photo(LOGS_CHANNEL_ID,
                                      cached_photo,
                                      caption=caption,
                                      parse_mode='html')

    async def handle_exception(self, exception):
        await self.log("<pre>[PHOTOBOT] %s</pre>\n\n%s" % (EXCEPTION_MESSAGE_TEXT, str(exception)))

    def can_remove_this_image(self, user_id, image_id):
        return self.is_developer(user_id) or self.bot_data.is_owner(user_id, image_id)

    async def get_image_from_file_id(self, file_id):
        reuse_id = self.bot_data.get_reuse_id(file_id)
        file_info = await self.bot.get_file(reuse_id)
        downloaded_file = await self.bot.download_file(file_info.file_path)
        image = Image.open(downloaded_file)

        return image

    async def newsletter_menu(self, chat):
        await self.bot.send_message(chat.id,
                                    '<pre>GREETINGS, %s</pre>' % (await self.how_to_call_this_user(chat.id)).upper(),
                                    parse_mode='html', disable_notification=True,
                                    reply_markup=self.get_newsletter_menu_reply_markup())

    async def how_to_call_this_user(self, chat_id):
        chat = await self.bot.get_chat(chat_id)
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

    async def remove_some_photos(self, message: types.Message):
        try:
            await self.bot.delete_message(message.chat.id, message.message_id)
            all_images = self.bot_data.get_images_sorted_by_rating()
            listed_images = list()
            for image in all_images:
                listed_images.append(image)

            while len(listed_images) > 0:
                try:
                    for image in listed_images:
                        await self.bot.send_photo(message.chat.id, self.bot_data.get_reuse_id(image['image_id']),
                                                  "%s\n\n<pre>Rating: %s</pre>" % (
                                                      DO_YOU_WANT_TO_DELETE_IMAGE, str(image['rating'])),
                                                  reply_markup=self.get_confirm_removing_reply_markup(
                                                      image['image_id']),
                                                  parse_mode=types.ParseMode.HTML, disable_notification=True)
                        listed_images.remove(image)
                        time.sleep(2)
                except RetryAfter as e:
                    time.sleep(int(e.timeout) + 1)
        except MessageToDeleteNotFound:
            pass

    async def remove_some_photos_2(self, message: types.Message):
        try:
            await self.bot.delete_message(message.chat.id, message.message_id)
            rating = message.text[1:].split()[1]
            self.bot_data.remove_with_this_rating_and_lower(int(rating))
            await self.bot.send_message(message.chat.id, "Done 👌", reply_markup=self.get_delete_button_reply_markup())
        except MessageToDeleteNotFound:
            pass

    #
    #
    #      Buttons etc:
    #
    #

    def get_delete_button(self):
        return types.InlineKeyboardButton(text=HIDE_MENU_BUTTON, callback_data=REMOVE_CURRENT_MESSAGE_CALLBACK_DATA)

    def get_gallery_button(self):
        return types.InlineKeyboardButton(text=GO_TO_GALLERY_INLINE_BUTTON,
                                          switch_inline_query_current_chat=GALLERY_TAG)

    def remove_from_gallery_button(self, image_id):
        return types.InlineKeyboardButton(text=REMOVE_FROM_GALLERY_BUTTON,
                                          callback_data='%s%s' % (REMOVE_FROM_GALLERY_CALLBACK_DATA, image_id))

    def get_go_to_library_reply_markup(self):
        go_to_library_reply_markup = types.InlineKeyboardMarkup()
        go_to_library_reply_markup.add(self.get_gallery_button())
        return go_to_library_reply_markup

    def get_delete_button_reply_markup(self):
        delete_button_reply_markup = types.InlineKeyboardMarkup()
        delete_button_reply_markup.add(self.get_delete_button())
        return delete_button_reply_markup

    def get_as_file_reply_markup(self, image_from_library_id, is_owner, image_exists, mmnews_enabled=False):
        return self.get_as_something_reply_markup(image_from_library_id, is_owner, image_exists, "file")

    def get_as_photo_reply_markup(self, image_from_library_id, is_owner, image_exists, mmnews_enabled=False):
        return self.get_as_something_reply_markup(image_from_library_id, is_owner, image_exists, "photo")

    def get_as_file_button(self):
        return types.InlineKeyboardButton(text=GET_AS_FILE_BUTTON,
                                          callback_data=GET_AS_FILE_CALLBACK_DATA)

    def get_as_photo_button(self):
        return types.InlineKeyboardButton(text=GET_AS_PHOTO_BUTTON,
                                          callback_data=GET_AS_PHOTO_CALLBACK_DATA)

    def get_as_something_reply_markup(self, image_from_library_id, is_owner, image_exists, something):
        as_something_button = None
        if something == "file":
            as_something_button = self.get_as_file_button()
        elif something == "photo":
            as_something_button = self.get_as_photo_button()
        as_smthng_reply_markup = types.InlineKeyboardMarkup()

        if is_owner and image_exists:
            as_smthng_reply_markup.row(as_something_button, self.remove_from_gallery_button(image_from_library_id),
                                       self.get_gallery_button())
        else:
            as_smthng_reply_markup.row(as_something_button, self.get_gallery_button())

        return as_smthng_reply_markup

    def get_confirm_removing_reply_markup(self, image_to_remove_id):
        yes_button = types.InlineKeyboardButton(text=YES_REMOVE_BUTTON_TEXT,
                                                callback_data='%s%s' % (
                                                    CONFIRMED_REMOVE_FROM_GALLERY_CALLBACK_DATA, image_to_remove_id))
        cancel_button = types.InlineKeyboardButton(text=CANCEL_REMOVING_BUTTON_TEXT,
                                                   callback_data=REMOVE_CURRENT_MESSAGE_CALLBACK_DATA)
        res = types.InlineKeyboardMarkup(5)
        res.add(cancel_button)
        res.add(cancel_button, yes_button, cancel_button, cancel_button, cancel_button)
        res.add(cancel_button)

        return res

    def get_newsletter_menu_reply_markup(self):
        make_newsletter_button = types.InlineKeyboardButton(text=MAKE_NEWSLETTER_BUTTON,
                                                            callback_data=MAKE_NEWSLETTER_CALLBACK_DATA)
        recall_newsletter_button = types.InlineKeyboardButton(text=RECALL_NEWSLETTER_BUTTON,
                                                              callback_data=RECALL_NEWSLETTER_CALLBACK_DATA)
        newsletter_panel_reply_markup = types.InlineKeyboardMarkup()
        newsletter_panel_reply_markup.add(make_newsletter_button)
        newsletter_panel_reply_markup.add(recall_newsletter_button)
        newsletter_panel_reply_markup.add(self.get_delete_button())

        return newsletter_panel_reply_markup

    def get_confirm_recall_reply_markup(self):
        confirm_recall_button = types.InlineKeyboardButton(text=CONFIRM_RECALL_BUTTON,
                                                           callback_data=RECALL_CONFIRMED_CALLBACK_DATA)
        confirm_recall_reply_markup = types.InlineKeyboardMarkup()
        confirm_recall_reply_markup.add(confirm_recall_button)
        confirm_recall_reply_markup.add(self.get_delete_button())

        return confirm_recall_reply_markup

    #
    #
    #
    #
    #

    async def confirming_newsletter(self, message):
        chat_id = message.chat.id

        self.bot_data.set_cached_message(chat_id, message.text)
        message_text = self.bot_data.get_cached_message(chat_id)

        await self.bot.send_message(chat_id, "<pre>YOUR MESSAGE:</pre>", parse_mode='html',
                                    reply_markup=self.get_delete_button_reply_markup(), disable_notification=True)
        await self.bot.send_message(chat_id, message_text, parse_mode="markdown",
                                    reply_markup=self.get_delete_button_reply_markup(),
                                    disable_notification=True)
        await self.bot.send_message(chat_id, "<pre>ENTER CURRENT DAY OF MONTH TO CONFIRM</pre>", parse_mode='html',
                                    reply_markup=self.get_delete_button_reply_markup(), disable_notification=True)
        self.bot_data.set_state(chat_id, ChatState.CONFIRMING_NEWSLETTER)

    async def confirm_and_make_newsletter(self, message):
        chat_id = message.chat.id
        message_to_send = self.bot_data.get_cached_message(chat_id)

        mailing_list = self.bot_data.get_mailing_list()

        if message.text == str(current_time().day):
            last_newsletter_messages = []
            if len(mailing_list) > 0:
                log_message = await self.bot.send_message(chat_id, '<pre>MAKING NEWSLETTER...\n</pre>',
                                                          parse_mode='html',
                                                          reply_markup=self.get_delete_button_reply_markup())
                for chat_id_from_list in mailing_list:
                    try:
                        time.sleep(1)
                        await self.bot.edit_message_text(
                            '<pre>%s\nSENDING TO %s...</pre>' % (log_message.text, chat_id_from_list),
                            message_id=log_message.message_id, chat_id=chat_id, parse_mode='html')

                        sent_message = await self.bot.send_message(chat_id_from_list, message_to_send,
                                                                   parse_mode="markdown",
                                                                   disable_web_page_preview=True
                                                                   # ,
                                                                   # reply_markup=self.get_go_to_library_reply_markup()
                                                                   )
                        last_newsletter_messages.append(
                            {'chat_id': chat_id_from_list, 'message_id': sent_message.message_id})

                        log_message = await self.bot.edit_message_text('<pre>%s\nSENT TO %s. MESSAGE ID: %s</pre>' % (
                            log_message.text, await self.how_to_call_this_user(chat_id_from_list),
                            sent_message.message_id),
                                                                       message_id=log_message.message_id,
                                                                       chat_id=chat_id,
                                                                       parse_mode='html',
                                                                       reply_markup=self.get_delete_button_reply_markup())
                    except (TelegramAPIError, AIOGramWarning) as e:
                        time.sleep(1)
                        chat = await self.bot.get_chat(chat_id_from_list)
                        log_message = await self.bot.edit_message_text(
                            '<pre>%s\nEXCEPTION THROWN WHILE SENDING TO </pre>%s: <pre>%s</pre>' % (
                                log_message.text, await self.html_inline_link_to_user(chat.id), str(e)),
                            message_id=log_message.message_id, chat_id=chat_id,
                            parse_mode='html',
                            reply_markup=self.get_delete_button_reply_markup())
                await self.bot.edit_message_text('<pre>%s\nFINISHED</pre>' % log_message.text,
                                                 message_id=log_message.message_id, chat_id=chat_id, parse_mode='html',
                                                 reply_markup=self.get_delete_button_reply_markup())
                self.bot_data.set_state(chat_id, ChatState.FREE)
            else:
                await self.bot.send_message(chat_id, '<pre>MAILING LIST IS EMPTY</pre>', parse_mode='html')
                self.bot_data.set_state(chat_id, ChatState.FREE)

            self.bot_data.set_last_newsletter_messages(last_newsletter_messages)
        else:
            await self.bot.send_message(chat_id, '<pre>WRONG. TRY AGAIN</pre>', parse_mode='html',
                                        reply_markup=self.get_delete_button_reply_markup())

    async def handle_make_newsletter(self, call):
        if self.is_developer(call.message.chat.id):
            message = call.message
            chat_id = message.chat.id
            message_id = message.message_id
            await self.bot.answer_callback_query(call.id)
            await self.bot.delete_message(chat_id, message_id)

            chat_id = call.message.chat.id
            if not self.is_developer(chat_id):
                await self.handle_free_text(message.text)
            else:
                self.bot_data.set_state(chat_id, ChatState.ENTERING_NEWSLETTER_MESSAGE)
                await self.bot.send_message(chat_id, "<pre>ENTER NEWSLETTER MESSAGE</pre>", parse_mode='html',
                                            reply_markup=self.get_delete_button_reply_markup(),
                                            disable_notification=True)
        else:
            await self.bot.answer_callback_query(call.id)

    async def confirm_recall(self, call):
        if self.is_developer(call.message.chat.id):

            chat_id = call.message.chat.id
            message_id = call.message.message_id
            await self.bot.answer_callback_query(call.id)
            await self.bot.delete_message(chat_id, message_id)
            await self.bot.send_message(chat_id, '<pre>CONFIRM RECALL</pre>', parse_mode='html',
                                        disable_notification=True,
                                        reply_markup=self.get_confirm_recall_reply_markup())
        else:
            await self.bot.answer_callback_query(call.id)

    async def recall(self, call):
        if self.is_developer(call.message.chat.id):
            message = call.message
            chat_id = message.chat.id
            message_id = message.message_id
            await self.bot.answer_callback_query(call.id)
            await self.bot.delete_message(chat_id, message_id)
            log_message = await self.bot.send_message(chat_id, '<pre>RECALL OPERATION INITIATED...</pre>',
                                                      parse_mode='html',
                                                      reply_markup=self.get_delete_button_reply_markup())

            last_newsletter_messages = self.bot_data.get_last_newsletter_messages()

            for message_info in last_newsletter_messages:
                await self.bot.delete_message(message_info['chat_id'], message_info['message_id'])
                log_message = await self.bot.edit_message_text(
                    '<pre>%s\nMESSAGE %s DELETED FROM %s</pre>' % (
                        log_message.text, message_info['message_id'],
                        await self.how_to_call_this_user(message_info['chat_id'])),
                    chat_id=log_message.chat.id, message_id=log_message.message_id, parse_mode='html',
                    reply_markup=self.get_delete_button_reply_markup())

            await self.bot.edit_message_text(
                "<pre>%s\nRECALL OPERATION COMPLETED SUCCESSFULLY</pre>" % log_message.text,
                chat_id=message.chat.id, message_id=log_message.message_id, parse_mode='html',
                reply_markup=self.get_delete_button_reply_markup())
        else:
            await self.bot.answer_callback_query(call.id)
