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
