# -*- coding: utf-8 -*-

from enum import Enum

from botconfig import *

default_image = None


def load_stock_images_file_ids():
    stock_images_file = open(PROJECT_DIRECTORY + '/' + IMAGES_DIRECTORY + STOCK_IMAGES_FILEIDS_FILE_NAME, 'r')
    global default_image
    default_image = stock_images_file.readline()[:-1]
    stock_images_file.close()


load_stock_images_file_ids()


class ChatState(Enum):
    FREE = '/cancel'
    SPECIFYING_MAILING_LIST = "setting_mailing_list"
    ENTERING_NEWSLETTER_MESSAGE = "entering_newsletter_message"
    CONFIRMING_NEWSLETTER = 'confirming_newsletter'


class ChatData:
    chat_id = 0
    heading = DEFAULT_HEADING
    blackout = DEFAULT_BLACKOUT
    blur = DEFAULT_BLUR
    cached_message = None
    state = ChatState.FREE
    image = default_image

    def __init__(self, chat_id):
        self.chat_id = chat_id
        pass


class ChatCache:
    cache = {}

    def __init__(self):
        self.cache = {}
        pass

    def get_chat_data_from_cache(self, chat_id):
        if chat_id not in self.cache.keys():
            self.cache[chat_id] = ChatData(chat_id)
        return self.cache.get(chat_id)

    def set_heading(self, chat_id, value):
        self.get_chat_data_from_cache(chat_id).heading = value
        pass

    def set_blackout(self, chat_id, value):
        self.get_chat_data_from_cache(chat_id).blackout = value
        pass

    def set_blur(self, chat_id, value):
        self.get_chat_data_from_cache(chat_id).blur = value
        pass

    def set_cached_message(self, chat_id, value):
        self.get_chat_data_from_cache(chat_id).cached_message = value
        pass

    def set_state(self, chat_id, value):
        self.get_chat_data_from_cache(chat_id).state = value
        pass

    def set_image(self, chat_id, value):
        self.get_chat_data_from_cache(chat_id).image = value
        pass

    def get_heading(self, chat_id):
        return self.get_chat_data_from_cache(chat_id).heading

    def get_blackout(self, chat_id):
        return self.get_chat_data_from_cache(chat_id).blackout

    def get_blur(self, chat_id):
        return self.get_chat_data_from_cache(chat_id).blur

    def get_cached_message(self, chat_id):
        return self.get_chat_data_from_cache(chat_id).cached_message

    def get_state(self, chat_id):
        return self.get_chat_data_from_cache(chat_id).state

    def get_image(self, chat_id):
        return self.get_chat_data_from_cache(chat_id).image

    def heading_set(self, chat_id):
        chat_data = self.get_chat_data_from_cache(chat_id)
        return chat_data.heading != DEFAULT_HEADING
