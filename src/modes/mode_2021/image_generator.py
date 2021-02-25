# -*- coding: utf-8 -*-

import os

from PIL import Image, ImageFont, ImageDraw

CURRENT_DIRECTORY = os.path.dirname(os.path.realpath(__file__))
FONT_PATH = CURRENT_DIRECTORY + '/sources/Gilroy-SemiBold.ttf'


def generate_image(title="Default title", image_type="main", mmnews=False):
    image = Image.open("%s/sources/%s.png" % (CURRENT_DIRECTORY, image_type)).convert("RGB")
    bottom_image_path = CURRENT_DIRECTORY + '/sources/'
    if mmnews:
        bottom_image_path += "mmnews"
    else:
        bottom_image_path += "mmspbu"
    if image_type == "main":
        bottom_image_path += "_light.png"
        text_color = '#FFFFFF'
    else:
        bottom_image_path += "_dark.png"
        text_color = '#002770'
    bottom_image = Image.open(bottom_image_path)

    draw = ImageDraw.Draw(image)

    image.paste(bottom_image, (153, 1017), bottom_image)

    font = ImageFont.truetype(FONT_PATH, 144)
    text_lines = title.split('\n')

    w = []
    h = []
    text_y = []

    first_text_y = 490 - (len(text_lines) - 1) * 76

    for i in range(0, len(text_lines)):
        size = draw.textsize(text_lines[i], font)
        w.append(size[0])
        h.append(size[1])

        text_y.append(first_text_y + 144 * i)
        draw.multiline_text((148, text_y[i]), text_lines[i], text_color, font)

    return image
