from __future__ import division
import sys


try:
    basestring  # For Python 2, str and unicode
except NameError:
    basestring = str

PY2 = sys.version_info.major == 2
PY3 = sys.version_info >= (3, 0)


def get_int_value(data, key):
    value = data.get(key)
    return int(value) if value else 0


def get_float_value(data, key):
    value = data.get(key)
    if value:
        if isinstance(value, (float, int)):
            return float(value)
        if isinstance(value, basestring):
            return float(value.replace(',', '.'))
    return 0.0


def to_string(val):
    if PY2:
        if isinstance(val, str):
            return val.decode('utf-8')
        elif not isinstance(val, unicode):
            return unicode(val)
    else:
        if not isinstance(val, str):
            return str(val)
    return val


# return image size so image fits into configured width/height and keep aspect ratio
def get_image_display_size(width, height, image_width, image_height):
    if image_width <= width and image_height <= height:
        image_display_width, image_display_height = image_width, image_height
    else:
        size_ratio = image_width / image_height
        tmp = width / size_ratio
        if tmp <= height:
            image_display_width = width
            image_display_height = tmp
        else:
            image_display_width = height * size_ratio
            image_display_height = height
    return image_display_width, image_display_height
