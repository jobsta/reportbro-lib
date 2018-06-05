from enum import Enum


class Border(Enum):
    grid = 1
    frame_row = 2
    frame = 3
    row = 4
    none = 5


class RenderElementType(Enum):
    none = 0
    complete = 1
    between = 2
    first = 3
    last = 4


class DocElementType(Enum):
    text = 1
    image = 2
    line = 3
    page_break = 4
    table_band = 5
    table = 6
    table_text = 7
    bar_code = 8
    frame = 9
    section = 10
    section_band = 11


class ParameterType(Enum):
    none = 0
    string = 1
    number = 2
    boolean = 3
    date = 4
    array = 5
    simple_array = 6
    map = 7
    sum = 8
    average = 9
    image = 10


class BandType(Enum):
    header = 1
    content = 2
    footer = 3


class PageFormat(Enum):
    a4 = 1
    a5 = 2
    letter = 3
    user_defined = 4


class Unit(Enum):
    pt = 1
    mm = 2
    inch = 3


class Orientation(Enum):
    portrait = 1
    landscape = 2


class BandDisplay(Enum):
    never = 1
    always = 2
    not_on_first_page = 3


class HorizontalAlignment(Enum):
    left = 1
    center = 2
    right = 3
    justify = 4


class VerticalAlignment(Enum):
    top = 1
    middle = 2
    bottom = 3
