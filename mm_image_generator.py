# -*- coding: utf-8 -*-

from PIL import Image, ImageFont, ImageDraw, ImageFilter

from botconfig import *

MAIN_FONT_FILE_PATH = PROJECT_DIRECTORY + '/fonts/helios_cond_bold_cyr.otf'


def generate_image(heading, image, blackout, blur):
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

    image = image.filter(ImageFilter.GaussianBlur(blur - 1))

    blackout = int(255 * blackout)
    grey_img = Image.new(mode='RGBA', size=(1920, 1080), color='black')
    grey_img.putalpha(blackout)
    mask = Image.new('RGBA', (1920, 1080), (0, 0, 0, blackout))

    image.paste(grey_img, mask)

    draw = ImageDraw.Draw(image)

    draw.line((0, 980) + (1920, 980), fill='white', width=200)

    bottom_image_dir = PROJECT_DIRECTORY + '/images/bottom.png'
    bottom_image = Image.open(bottom_image_dir)

    image.paste(bottom_image, (0, 0), bottom_image)

    font = ImageFont.truetype(MAIN_FONT_FILE_PATH, 147)
    text_lines = heading.upper().split('\n')
    chapter_line_length = 550

    white_line_x1 = (1920 - chapter_line_length) / 2
    white_line_x2 = (1920 + chapter_line_length) / 2

    w = []
    h = []
    text_y = []

    first_text_y = 400 - (len(text_lines) - 1) * 97

    for i in range(0, len(text_lines)):
        size = draw.textsize(text_lines[i], font)
        w.append(size[0])
        h.append(size[1])

        text_y.append(first_text_y + 156 * i)
        draw.multiline_text(((1920 - w[i]) / 2, text_y[i]), text_lines[i], 'white', font)

    white_line_y_coord = text_y[len(text_y) - 1] + 182

    if heading != '':
        draw.line(
            (white_line_x1, white_line_y_coord) + (white_line_x2, white_line_y_coord),
            fill='white', width=4
        )

    return image
