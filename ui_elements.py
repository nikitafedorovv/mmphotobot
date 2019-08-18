# -*- coding: utf-8 -*-

from telebot import types

from bot_elements_config import *


def get_delete_button():
    return types.InlineKeyboardButton(text=HIDE_MENU_BUTTON, callback_data=HIDE_MENU_CALLBACK_DATA)


def get_gallery_button():
    return types.InlineKeyboardButton(text=GO_TO_GALLERY_INLINE_BUTTON, switch_inline_query_current_chat=GALLERY_TAG)


def remove_from_gallery_button(image_id):
    return types.InlineKeyboardButton(text=REMOVE_FROM_GALLERY_BUTTON,
                                      callback_data='%s%s' % (REMOVE_FROM_GALLERY_CALLBACK_DATA, image_id))


def get_go_to_library_reply_markup():
    go_to_library_reply_markup = types.InlineKeyboardMarkup()
    go_to_library_reply_markup.add(get_gallery_button())
    return go_to_library_reply_markup


def get_delete_button_reply_markup():
    delete_button_reply_markup = types.InlineKeyboardMarkup()
    delete_button_reply_markup.add(get_delete_button())
    return delete_button_reply_markup


def get_as_file_reply_markup(file_id, image_from_library_id, is_owner, image_exists):
    as_file_button = types.InlineKeyboardButton(text=GET_AS_FILE_BUTTON,
                                                callback_data='%s%s' % (GET_AS_FILE_CALLBACK_DATA, file_id))
    as_file_reply_markup = types.InlineKeyboardMarkup()
    as_file_reply_markup.add(as_file_button)
    if is_owner and image_exists:
        as_file_reply_markup.add(remove_from_gallery_button(image_from_library_id))
    as_file_reply_markup.add(get_gallery_button())

    return as_file_reply_markup


def get_as_photo_reply_markup(file_id, image_from_library_id, is_owner, image_exists):
    as_photo_button = types.InlineKeyboardButton(text=GET_AS_PHOTO_BUTTON,
                                                 callback_data='%s%s' % (GET_AS_PHOTO_CALLBACK_DATA, file_id))
    as_photo_reply_markup = types.InlineKeyboardMarkup()
    as_photo_reply_markup.add(as_photo_button)
    if is_owner and image_exists:
        as_photo_reply_markup.add(remove_from_gallery_button(image_from_library_id))
    as_photo_reply_markup.add(get_gallery_button())

    return as_photo_reply_markup


def get_confirm_removing_reply_markup(image_to_remove_id):
    yes_button = types.InlineKeyboardButton(text=YES_REMOVE_BUTTON_TEXT,
                                            callback_data='%s%s' % (
                                                CONFIRMED_REMOVE_FROM_GALLERY_CALLBACK_DATA, image_to_remove_id))
    cancel_button = types.InlineKeyboardButton(text=CANCEL_REMOVING_BUTTON_TEXT, callback_data=HIDE_MENU_CALLBACK_DATA)
    res = types.InlineKeyboardMarkup()
    res.add(yes_button)
    res.add(cancel_button)

    return res


def get_newsletter_menu_reply_markup():
    make_newsletter_button = types.InlineKeyboardButton(text=MAKE_NEWSLETTER_BUTTON,
                                                        callback_data=MAKE_NEWSLETTER_CALLBACK_DATA)
    recall_newsletter_button = types.InlineKeyboardButton(text=RECALL_NEWSLETTER_BUTTON,
                                                          callback_data=RECALL_NEWSLETTER_CALLBACK_DATA)
    newsletter_panel_reply_markup = types.InlineKeyboardMarkup()
    newsletter_panel_reply_markup.add(make_newsletter_button)
    newsletter_panel_reply_markup.add(recall_newsletter_button)
    newsletter_panel_reply_markup.add(get_delete_button())

    return newsletter_panel_reply_markup


def get_confirm_recall_reply_markup():
    confirm_recall_button = types.InlineKeyboardButton(text=CONFIRM_RECALL_BUTTON,
                                                       callback_data=RECALL_CONFIRMED_CALLBACK_DATA)
    confirm_recall_reply_markup = types.InlineKeyboardMarkup()
    confirm_recall_reply_markup.add(confirm_recall_button)
    confirm_recall_reply_markup.add(get_delete_button())

    return confirm_recall_reply_markup