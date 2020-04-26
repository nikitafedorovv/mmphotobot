# -*- coding: utf-8 -*-
import pymongo
from bson.objectid import ObjectId

from botconfig import *
from chat_states import ChatState


def get_new_chat(new_chat_id):
    return {
        'chat_id': new_chat_id,
        'heading': DEFAULT_HEADING,
        'blackout': DEFAULT_BLACKOUT,
        'blur': DEFAULT_BLUR,
        'cached_message': None,
        'state': str(ChatState.FREE),
        'image': None
    }


def get_new_image_info(new_image_id, owner_id):
    return {
        'image_id': new_image_id,
        'rating': 0,
        'owner_id': owner_id
    }


class BotData:
    __mongodb = None

    def __init__(self):
        self.__mongodb = pymongo.MongoClient(MONGO_URL)['mmphotobot']
        pass

    def exist(self, object_id):
        gallery_coll = self.__mongodb["gallery"]
        return gallery_coll.find_one({"_id": ObjectId(object_id)}) is not None

    def __get_image_info_or_create(self, image_id, owner_id):
        gallery_coll = self.__mongodb["gallery"]
        image_info = gallery_coll.find_one({"image_id": str(image_id)})

        if image_info is None:
            gallery_coll.save(get_new_image_info(str(image_id), str(owner_id)))
            image_info = gallery_coll.find_one({"image_id": str(image_id)})

        return image_info

    def increment_rating(self, image_id, user_id):
        image_info = self.__get_image_info_or_create(image_id, user_id)
        image_info['rating'] += 1
        self.__mongodb["gallery"].save(image_info)

    def get_images_sorted_by_rating(self):
        return self.__mongodb["gallery"].find({}).sort([("rating", -1)])

    def get_image_id_by_object_id(self, object_id):
        return str(self.__mongodb["gallery"].find_one({"_id": ObjectId(object_id)})['image_id'])

    def get_object_id_by_image_id(self, image_id):
        return str(self.__mongodb["gallery"].find_one({"image_id": str(image_id)})['_id'])

    def remove_image(self, object_id):
        res = self.__mongodb["gallery"].delete_one({"_id": ObjectId(object_id)}).deleted_count

        return res

    def is_owner(self, user_id, object_id):
        image_info = self.__mongodb["gallery"].find_one({"_id": ObjectId(object_id)})
        if image_info is not None:
            return str(image_info['owner_id']) == str(user_id)
        else:
            return None

    def image_exists(self, image_id):
        image_info = self.__mongodb["gallery"].find_one({"image_id": str(image_id)})
        return image_info is not None

    def get_mailing_list(self):
        chats_coll = self.__mongodb["chats"]
        chats = chats_coll.find({})
        res = []

        for chat in chats:
            res.append(chat['chat_id'])

        return res

    def set_last_newsletter_messages(self, last_newsletter_messages):
        newsletter_coll = self.__mongodb["newsletter"]
        newsletter_coll.delete_many({})

        for message in last_newsletter_messages:
            newsletter_coll.save(message)

    def get_last_newsletter_messages(self):
        return self.__mongodb["newsletter"].find({})

    def __get_chat_data(self, chat_id):
        chats_coll = self.__mongodb["chats"]
        chat = chats_coll.find_one({"chat_id": str(chat_id)})

        if chat is None:
            chats_coll.save(get_new_chat(str(chat_id)))
            chat = chats_coll.find_one({"chat_id": str(chat_id)})

        return chat

    def set_heading(self, chat_id, value):
        chat = self.__get_chat_data(chat_id)
        chat['heading'] = value
        self.__mongodb["chats"].save(chat)

        pass

    def set_blackout(self, chat_id, value):
        chat = self.__get_chat_data(chat_id)
        chat['blackout'] = value
        self.__mongodb["chats"].save(chat)
        pass

    def set_blur(self, chat_id, value):
        chat = self.__get_chat_data(chat_id)
        chat['blur'] = value
        self.__mongodb["chats"].save(chat)
        pass

    def set_cached_message(self, chat_id, value):
        chat = self.__get_chat_data(chat_id)
        chat['cached_message'] = value
        self.__mongodb["chats"].save(chat)
        pass

    def set_state(self, chat_id, value):
        chat = self.__get_chat_data(chat_id)
        chat['state'] = str(value)
        self.__mongodb["chats"].save(chat)
        pass

    def set_image(self, chat_id, value):
        chat = self.__get_chat_data(chat_id)
        chat['image'] = value
        self.__mongodb["chats"].save(chat)
        pass

    def get_heading(self, chat_id):
        return self.__get_chat_data(chat_id)['heading']

    def get_blackout(self, chat_id):
        return self.__get_chat_data(chat_id)['blackout']

    def get_blur(self, chat_id):
        return self.__get_chat_data(chat_id)['blur']

    def get_cached_message(self, chat_id):
        return self.__get_chat_data(chat_id)['cached_message']

    def get_state(self, chat_id):
        state_str = self.__get_chat_data(chat_id)['state']
        state_name = state_str[10:]
        return ChatState(state_name)

    def get_image(self, chat_id):
        return self.__get_chat_data(chat_id)['image']

    def heading_set(self, chat_id):
        chat_data = self.__get_chat_data(chat_id)
        return chat_data['heading'] != DEFAULT_HEADING
