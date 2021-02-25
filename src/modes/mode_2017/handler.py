# -*- coding: utf-8 -*-

from PIL import Image

from botspeech import START_MESSAGE_TEXT
from botutil import validate_blur, validate_blackout, clear_text
from chat_states import ChatState
from modes.mode_2017.image_generator import generate_image
from super_handler import Handler


class Handler2017(Handler):

    async def handle_help(self, chat_id):
        await self.log(
            '<pre>[PHOTOBOT] </pre>%s <pre>ASKED FOR HELP</pre>' % await self.html_inline_link_to_user(chat_id))

        self.bot_data.set_state(chat_id, ChatState.FREE)
        await self.bot.send_message(chat_id, START_MESSAGE_TEXT, reply_markup=self.get_go_to_library_reply_markup(),
                                    parse_mode='html')

    async def handle_free_text(self, message):
        text = message.text
        chat_id = message.chat.id

        if self.is_developer(message.chat.id):
            if text == '/':
                await self.bot.delete_message(message.chat.id, message.message_id)
                await self.newsletter_menu(message.chat)
                return
        if validate_blackout(text) or text == '1.0':
            self.bot_data.set_blackout(chat_id, float(text))
            await self.build_and_send_image(message)
        elif validate_blur(text) or text == '1':
            self.bot_data.set_blur(chat_id, int(text))
            await self.build_and_send_image(message)
        else:
            self.bot_data.set_heading(chat_id, clear_text(message.text))
            await self.build_and_send_image(message)

    async def build_image(self, chat_id):
        heading_split = self.bot_data.get_heading(chat_id).split("\n")
        title = heading_split[0]

        if len(heading_split) > 1:
            subtitle = heading_split[1]
        else:
            subtitle = "Second line"

        blackout = self.bot_data.get_blackout(chat_id)
        blur = self.bot_data.get_blur(chat_id)

        file_id = self.bot_data.get_image(chat_id)

        background_image = await self.get_image_from_file_id(file_id) if file_id is not None else Image.new(mode='RGB',
                                                                                                            size=(
                                                                                                                1920,
                                                                                                                1080),
                                                                                                            color=(
                                                                                                                41, 54,
                                                                                                                72))

        return generate_image(title, subtitle, background_image, blackout, blur)
