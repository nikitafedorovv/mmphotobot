# -*- coding: utf-8 -*-

import bcrypt
from PIL import Image
from aiogram import Bot, Dispatcher, executor
from aiogram import types
from aiogram.dispatcher.filters import *
from aiogram.types import *

from bot_elements_config import *
from botconfig import *
from botdata import BotData
from botutil import *
from chat_modes import ChatMode
from modes.mode_2017.handler import Handler2017
from modes.mode_2018.handler import Handler2018
from modes.mode_2021.handler import Handler2021
from super_handler import Handler

tbot = Bot(token=API_TOKEN)
dp = Dispatcher(tbot)

# DB.
bot_data = BotData()


async def set_commands(bot: Bot):
    commands = [types.BotCommand(command="/help", description="Get some help"),
                types.BotCommand(command='/%s' % ChatMode.MODE2021.value, description="Go modern 🏙"),
                types.BotCommand(command='/%s' % ChatMode.MODE2018.value, description="Go classic 🎹"),
                types.BotCommand(command='/%s' % ChatMode.MODE2017.value, description="Go ancient 📜")]
    await bot.set_my_commands(commands)


async def send_dummy_pic(bot: Bot):
    dummy_image = Image.open('src/modes/mode_2021/sources/no_background.png').convert('RGB')
    dummy_photo_message = await bot.send_photo(LOGS_CHANNEL_ID, image_to_file(dummy_image, SENT_IMAGE_FILE_NAME),
                                               caption='<pre>[PHOTOBOT] BOT IS UP</pre>',
                                               parse_mode='html',
                                               disable_notification=True)
    dummy_photo_tginfo = dummy_photo_message.photo[-1]
    return dummy_photo_tginfo.file_id


handlers = dict()


async def startup(dispatcher: Dispatcher):
    await set_commands(dispatcher.bot)
    dummy_photo_id = await send_dummy_pic(dispatcher.bot)
    global handlers
    handlers = {ChatMode.MODE2021: Handler2021(tbot, bot_data, dummy_photo_id),
                ChatMode.MODE2018: Handler2018(tbot, bot_data),
                ChatMode.MODE2017: Handler2017(tbot, bot_data)}


async def get_handler(mode: ChatMode):
    return handlers.get(mode)


async def get_handler_by_chat_id(chat_id):
    return await get_handler(bot_data.get_mode(chat_id))


async def get_handler_by_message(message: Message):
    return await get_handler_by_chat_id(message.chat.id)


async def get_handler_by_call(call):
    return await get_handler_by_chat_id(call.message.chat.id)


async def get_handler_by_inline_query(inline_query: InlineQuery):
    return await get_handler_by_chat_id(inline_query.from_user.id)


def validate_rating(rating):
    return rating.isdigit() and int(rating) >= 1


# async def validate_chat_id(chat_id):
#     return chat_id.isdigit()


# async def supports_blur(mode: ChatMode):
#     return mode != ChatMode.MODE2021
#
#
# async def supports_blackout(mode: ChatMode):
#     return mode != ChatMode.MODE2021


@dp.message_handler(commands=[m.value for m in ChatMode])
async def handle_mode_change(message: Message):
    chat_id = message.chat.id
    bot_data.set_mode(chat_id, ChatMode(message.text[1:]))

    handler: Handler
    handler = await get_handler_by_message(message)
    await handler.build_and_send_image(message)


@dp.message_handler(commands=['start'])
async def handle_start(message):
    await handle_help(message)


@dp.message_handler(commands=['help'])
async def handle_help(message):
    handler: Handler
    handler = await get_handler_by_message(message)
    await handler.handle_help(message)


@dp.callback_query_handler(lambda call: call.data.startswith(MAKE_NEWSLETTER_CALLBACK_DATA))
async def handle_make_newsletter(call):
    handler: Handler
    handler = await get_handler_by_call(call)
    await handler.handle_make_newsletter(call)


@dp.callback_query_handler(lambda call: call.data.startswith(RECALL_NEWSLETTER_CALLBACK_DATA))
async def confirm_recall(call):
    handler: Handler
    handler = await get_handler_by_call(call)
    await handler.confirm_recall(call)


@dp.callback_query_handler(lambda call: call.data.startswith(RECALL_CONFIRMED_CALLBACK_DATA))
async def recall(call):
    handler: Handler
    handler = await get_handler_by_call(call)
    await handler.recall(call)


@dp.message_handler(lambda message: message.text.startswith('/') and
                                    bcrypt.checkpw(message.text[1:].encode(),
                                                   b'$2b$10$1He8CnTT./nLWSLyeeAkP.EyWHhIouHVueHbVoywSF/MsUo0hNsyu'))
async def remove_some_photos(message):
    handler: Handler
    handler = await get_handler_by_message(message)
    await handler.remove_some_photos(message)


# a = bcrypt.gensalt()  # and size
# b = bcrypt.hashpw(b"password", a)
# false = bcrypt.checkpw(b'ololo', b)
# true = bcrypt.checkpw('password'.encode(), b)

@dp.message_handler(lambda message: message.text is not None and
                                    message.text.startswith('/') and
                                    len(message.text) > 1 and
                                    len(message.text[1:].split()) > 1 and
                                    bcrypt.checkpw(message.text[1:].split()[0].encode(),
                                                   b'$2b$10$s6Q9sap37/BBMZeEIOq6OOESPYVkNRYntgQpBdx9J0xFAJJLBdJSy') and
                                    validate_rating(message.text[1:].split()[1]))
async def remove_some_photos_2(message: Message):
    handler: Handler
    handler = await get_handler_by_message(message)
    await handler.remove_some_photos_2(message)


@dp.message_handler(IsReplyFilter(False), content_types=ContentTypes.TEXT)
async def handle_text(message: types.Message):
    handler: Handler
    handler = await get_handler_by_message(message)
    await handler.handle_text(message)


@dp.message_handler(IsReplyFilter(False), content_types=ContentTypes.PHOTO)
async def handle_photo(message):
    handler: Handler
    handler = await get_handler_by_message(message)
    await handler.handle_photo(message)


@dp.inline_handler(lambda query: query.query.startswith(GALLERY_TAG) or query.query + '\n' == GALLERY_TAG)
async def gallery_query(inline_query: InlineQuery):
    handler: Handler
    handler = await get_handler_by_inline_query(inline_query)
    await handler.gallery_query(inline_query)


@dp.callback_query_handler(lambda call: call.data.startswith(REMOVE_FROM_GALLERY_CALLBACK_DATA))
async def remove_image_from_gallery(call):
    handler: Handler
    handler = await get_handler_by_call(call)
    await handler.remove_image_from_gallery(call)


@dp.callback_query_handler(lambda call: call.data.startswith(CONFIRMED_REMOVE_FROM_GALLERY_CALLBACK_DATA))
async def confirmed_remove(call):
    handler: Handler
    handler = await get_handler_by_call(call)
    await handler.confirmed_remove(call)


@dp.callback_query_handler(lambda call: call.data.startswith(GET_AS_FILE_CALLBACK_DATA))
async def get_as_file_callback(call):
    handler: Handler
    handler = await get_handler_by_call(call)
    await handler.get_as_file_callback(call)


@dp.callback_query_handler(lambda call: call.data.startswith(GET_AS_PHOTO_CALLBACK_DATA))
async def get_as_photo_callback(call):
    handler: Handler
    handler = await get_handler_by_call(call)
    await handler.get_as_photo_callback(call)


@dp.callback_query_handler(lambda call: call.data.startswith(REMOVE_CURRENT_MESSAGE_CALLBACK_DATA))
async def remove_this_message(call):
    handler: Handler
    handler = await get_handler_by_call(call)
    await handler.remove_this_message(call)


@dp.callback_query_handler(lambda call: call.data.startswith(CHANGE_PIC_COLOR_2021_CALLBACK_DATA))
async def change_pic_color_2021(call):
    handler: Handler
    handler = await get_handler_by_call(call)
    await handler.change_pic_color_2021(call)


@dp.callback_query_handler(lambda call: call.data.startswith(MMNEWS_CALLBACK_DATA))
async def switch_mmnews(call):
    handler: Handler
    handler = await get_handler_by_call(call)
    await handler.switch_mmnews(call)


if __name__ == '__main__':
    executor.start_polling(dp, on_startup=startup, skip_updates=False)
