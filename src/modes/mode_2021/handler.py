# -*- coding: utf-8 -*-

from aiogram import Bot
from aiogram.types import InputMediaPhoto, InputMediaDocument, InlineKeyboardMarkup, InlineKeyboardButton, \
    CallbackQuery
from aiogram.utils.exceptions import MessageNotModified

from bot_elements_config import CHANGE_PIC_COLOR_2021_CALLBACK_DATA, MMNEWS_CALLBACK_DATA, MMNEWS_TURN_ON, \
    MMNEWS_TURN_OFF
from botconfig import SENT_IMAGE_FILE_NAME
from botdata import BotData
from botspeech import START_MESSAGE_TEXT
from botutil import clear_text, image_to_file
from chat_states import ChatState
from modes.mode_2021.image_generator import generate_image
from modes.mode_2021.pic_colors import PicColor2021
from super_handler import Handler


class Handler2021(Handler):
    __dummy_photo_id: str

    def __init__(self, bot: Bot, bot_data: BotData, dummy_photo_id):
        super().__init__(bot, bot_data)
        self.__dummy_photo_id = str(dummy_photo_id)

    async def handle_help(self, message):
        chat_id = message.chat.id
        await self.log(
            '<pre>[PHOTOBOT] </pre>%s <pre>ASKED FOR HELP</pre>' % await self.html_inline_link_to_user(chat_id))

        self.bot_data.set_state(chat_id, ChatState.FREE)
        await self.bot.send_message(chat_id, START_MESSAGE_TEXT, reply_markup=self.get_go_to_library_reply_markup(),
                                    parse_mode='html')

    async def handle_free_text(self, message):
        text = message.text
        chat_id = message.chat.id

        if self.is_developer(message.chat.id) and text == '/':
            await self.bot.delete_message(message.chat.id, message.message_id)
            await self.newsletter_menu(message.chat)
            return
        # if validate_blackout(text) or text == '1.0':
        #     self.bot_data.set_blackout(chat_id, float(text))
        #     await self.build_and_send_image(message)
        # elif validate_blur(text) or text == '1':
        #     self.bot_data.set_blur(chat_id, int(text))
        #     await self.build_and_send_image(message)
        else:
            self.bot_data.set_heading(chat_id, clear_text(message.text))
            await self.build_and_send_image(message)

    async def build_image(self, chat_id, mmnews_enabled=False):
        heading = self.bot_data.get_heading(chat_id)
        pic_color_2021 = self.bot_data.get_pic_color_2021(chat_id)
        # blackout = self.bot_data.get_blackout(chat_id)
        # blur = self.bot_data.get_blur(chat_id)

        # file_id = self.bot_data.get_image(chat_id)
        # background_image = await self.get_image_from_file_id(file_id) if file_id is not None else Image.new(mode='RGB',
        #                                                                                                             size=(
        #                                                                                                                 1920,
        #                                                                                                                 1080),
        #                                                                                                             color=(
        #                                                                                                                 41, 54,
        #                                                                                                                 72))
        # await self.bot.delete_message(chat_id, message.message_id)
        # result_photo_message = await self.bot.send_photo(chat_id, self.dummy_photo_id,
        #                                                  reply_markup=self.get_go_to_library_reply_markup())

        return generate_image(heading, pic_color_2021.value, mmnews_enabled)

    async def change_pic_color_2021(self, call: CallbackQuery):
        chat_id = call.message.chat.id
        pic_color = PicColor2021(call.data[len(CHANGE_PIC_COLOR_2021_CALLBACK_DATA):])
        self.bot_data.set_pic_color_2021(chat_id, pic_color)

        new_image = await self.build_image(chat_id, self.is_mmnews_enabled(call.message))

        try:
            if len(call.message.photo) != 0:
                await call.message.edit_media(InputMediaPhoto(image_to_file(new_image, SENT_IMAGE_FILE_NAME)),
                                              reply_markup=call.message.reply_markup)
            else:
                await call.message.edit_media(InputMediaDocument(image_to_file(new_image, SENT_IMAGE_FILE_NAME)),
                                              reply_markup=call.message.reply_markup)
        except MessageNotModified:
            pass

        await self.bot.answer_callback_query(call.id)

    async def switch_mmnews(self, call: CallbackQuery):
        chat_id = call.message.chat.id

        mmnews_enabled = call.data[len(MMNEWS_CALLBACK_DATA):] == MMNEWS_TURN_ON
        image = await self.build_image(chat_id, mmnews_enabled)
        file_id = self.bot_data.get_image(chat_id)
        can_remove = self.can_remove_this_image(chat_id, file_id)
        image_exists = self.bot_data.image_exists(file_id)

        if len(call.message.photo) != 0:
            await call.message.edit_media(InputMediaPhoto(image_to_file(image, SENT_IMAGE_FILE_NAME)),
                                          reply_markup=self.get_as_file_reply_markup(file_id, can_remove,
                                                                                     image_exists, mmnews_enabled))
        else:
            await call.message.edit_media(InputMediaDocument(image_to_file(image, SENT_IMAGE_FILE_NAME)),
                                          reply_markup=self.get_as_photo_reply_markup(file_id, can_remove,
                                                                                      image_exists, mmnews_enabled))
        await self.bot.answer_callback_query(call.id)

    def __get_color_buttons(self):
        return [
            InlineKeyboardButton("🟦", callback_data=CHANGE_PIC_COLOR_2021_CALLBACK_DATA + "main"),
            InlineKeyboardButton("🟣", callback_data=CHANGE_PIC_COLOR_2021_CALLBACK_DATA + "pink"),
            InlineKeyboardButton("🟡", callback_data=CHANGE_PIC_COLOR_2021_CALLBACK_DATA + "yellow"),
            InlineKeyboardButton("🔵", callback_data=CHANGE_PIC_COLOR_2021_CALLBACK_DATA + "blue")]

    def __get_turn_mmnews_on_button(self):
        return InlineKeyboardButton(text="💅", callback_data=MMNEWS_CALLBACK_DATA + MMNEWS_TURN_ON)

    def __get_turn_mmnews_off_button(self):
        return InlineKeyboardButton(text="🧑‍🎓", callback_data=MMNEWS_CALLBACK_DATA + MMNEWS_TURN_OFF)

    def get_as_file_reply_markup(self, image_from_library_id, is_owner, image_exists, mmnews_enabled=False):
        get_as_file_reply_markup: InlineKeyboardMarkup
        get_as_file_reply_markup = super().get_as_file_reply_markup(image_from_library_id, is_owner, image_exists)

        # TODO: Remove after implementing photo backgrounds support
        # self.__dummy_photo_id
        get_as_file_reply_markup.inline_keyboard[0].pop()
        if len(get_as_file_reply_markup.inline_keyboard[0]) == 2:
            get_as_file_reply_markup.inline_keyboard[0].pop()
        #

        if mmnews_enabled:
            get_as_file_reply_markup.inline_keyboard[0].append(self.__get_turn_mmnews_off_button())
        else:
            get_as_file_reply_markup.inline_keyboard[0].append(self.__get_turn_mmnews_on_button())
        get_as_file_reply_markup.inline_keyboard.append(self.__get_color_buttons())

        return get_as_file_reply_markup

    def get_as_photo_reply_markup(self, image_from_library_id, is_owner, image_exists, mmnews_enabled=False):
        get_as_photo_reply_markup: InlineKeyboardMarkup
        get_as_photo_reply_markup = super().get_as_photo_reply_markup(image_from_library_id, is_owner, image_exists)

        # TODO: Remove after implementing photo backgrounds support
        get_as_photo_reply_markup.inline_keyboard[0].pop()
        if len(get_as_photo_reply_markup.inline_keyboard[0]) == 2:
            get_as_photo_reply_markup.inline_keyboard[0].pop()
        #

        if mmnews_enabled:
            get_as_photo_reply_markup.inline_keyboard[0].append(self.__get_turn_mmnews_off_button())
        else:
            get_as_photo_reply_markup.inline_keyboard[0].append(self.__get_turn_mmnews_on_button())
        get_as_photo_reply_markup.inline_keyboard.append(self.__get_color_buttons())

        return get_as_photo_reply_markup
