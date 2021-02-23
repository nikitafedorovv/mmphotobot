# -*- coding: utf-8 -*-

import os

from PIL import Image, ImageFont, ImageDraw, ImageFilter

CURRENT_DIRECTORY = os.path.dirname(os.path.realpath(__file__))
MM_LOGO_FILE_PATH = CURRENT_DIRECTORY + '/sources/mm-white-logo.png'
MAIN_FONT_FILE_PATH = CURRENT_DIRECTORY + '/sources/OpenSans-Regular.ttf'
DARKENING_LAYER_COLOR = '#1a2535'


# Originally by https://github.com/kuparez at https://github.com/kuparez/studsovet_scripts
def generate_image(heading, subheading, image, blackout, blur):
    width, height = image.size
    if width * 1.0 / height > 1920.0 / 1080:
        new_height = 1080
        new_width = int(new_height * width / height)
    elif width * 1.0 / height < 1920.0 / 1080:
        new_width = 1920
        new_height = int(new_width * height / width)
    else:
        new_width = 1920
        new_height = 1080
    image = image.resize((new_width, new_height), Image.ANTIALIAS).crop((0, 0, 1920, 1080))

    image = image.filter(ImageFilter.GaussianBlur(blur))
    blackout = int(255 * blackout)
    grey_img = Image.new(mode='RGBA', size=(1920, 1080), color=DARKENING_LAYER_COLOR)
    grey_img.putalpha(blackout)
    mask = Image.new('RGBA', (1920, 1080), (0, 0, 0, blackout))
    image.paste(grey_img, mask)
    logo = Image.open(MM_LOGO_FILE_PATH)
    image.paste(logo, (150, 323), logo)
    draw = ImageDraw.Draw(image)
    font = ImageFont.truetype(MAIN_FONT_FILE_PATH, 115)
    draw.multiline_text((120, 650), heading, (255, 255, 255), font=font)
    font = ImageFont.truetype(MAIN_FONT_FILE_PATH, 73)

    if '\n' not in heading:
        draw.multiline_text((120, 800), subheading, (255, 255, 255), font=font)
    else:
        draw.multiline_text((120, 900), subheading, (255, 255, 255), font=font)

    return image
