import datetime
import decimal

current_datetime_str = datetime.datetime.now().strftime('%Y-%m-%d %H:%M')


def get_int_value(data, key):
    value = data.get(key)
    return int(value) if value else 0


def get_float_value(data, key):
    value = data.get(key)
    if value:
        if isinstance(value, (float, int)):
            return float(value)
        if isinstance(value, str):
            return float(value.replace(',', '.'))
    return 0.0


def get_str_value(data, key):
    value = data.get(key)
    if isinstance(value, str):
        return value
    return ''


def to_string(val):
    if not isinstance(val, str):
        return str(val)
    return val


def parse_datetime_string(val):
    date_format = '%Y-%m-%d'
    colon_count = val.count(':')
    if colon_count == 1:
        date_format = '%Y-%m-%d %H:%M'
    elif colon_count == 2:
        date_format = '%Y-%m-%d %H:%M:%S'
    return datetime.datetime.strptime(val, date_format)


def parse_number_string(val):
    return decimal.Decimal(val.replace(',', '.'))


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
