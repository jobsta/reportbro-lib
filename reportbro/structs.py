from __future__ import unicode_literals
from __future__ import division
from .enums import *
from .errors import Error
from .utils import get_float_value, get_int_value


class Color:
    def __init__(self, color):
        self.color_code = ''
        if color:
            assert len(color) == 7 and color[0] == '#'
            self.r = int(color[1:3], 16)
            self.g = int(color[3:5], 16)
            self.b = int(color[5:7], 16)
            self.transparent = False
            self.color_code = color
        else:
            self.transparent = True

    def is_black(self):
        return self.r == 0 and self.g == 0 and self.b == 0 and not self.transparent


class Parameter:
    def __init__(self, report, data):
        self.report = report
        self.id = int(data.get('id'))
        self.name = data.get('name', '<unnamed>')
        self.type = ParameterType[data.get('type')]
        if self.type == ParameterType.simple_array:
            self.array_item_type = ParameterType[data.get('arrayItemType')]
        else:
            self.array_item_type = ParameterType.none
        self.eval = bool(data.get('eval'))
        self.nullable = bool(data.get('nullable'))
        self.expression = data.get('expression', '')
        self.pattern = data.get('pattern', '')
        self.pattern_has_currency = (self.pattern.find('$') != -1)
        self.test_data = data.get('test_data', '') if not self.eval else None
        self.is_internal = self.name in ('page_count', 'page_number')
        self.children = []
        self.fields = dict()
        if self.type == ParameterType.array or self.type == ParameterType.map:
            for item in data.get('children'):
                parameter = Parameter(self.report, item)
                if parameter.name in self.fields:
                    self.report.errors.append(Error('errorMsgDuplicateParameterField',
                            object_id=parameter.id, field='name'))
                else:
                    self.children.append(parameter)
                    self.fields[parameter.name] = parameter


class BorderStyle:
    def __init__(self, data, key_prefix=''):
        self.border_color = Color(data.get(key_prefix + 'borderColor'))
        self.border_width = get_float_value(data, key_prefix + 'borderWidth')
        self.border_all = bool(data.get(key_prefix + 'borderAll'))
        self.border_left = self.border_all or bool(data.get(key_prefix + 'borderLeft'))
        self.border_top = self.border_all or bool(data.get(key_prefix + 'borderTop'))
        self.border_right = self.border_all or bool(data.get(key_prefix + 'borderRight'))
        self.border_bottom = self.border_all or bool(data.get(key_prefix + 'borderBottom'))


class TextStyle(BorderStyle):
    def __init__(self, data, key_prefix=''):
        BorderStyle.__init__(self, data, key_prefix)
        self.bold = bool(data.get(key_prefix + 'bold'))
        self.italic = bool(data.get(key_prefix + 'italic'))
        self.underline = bool(data.get(key_prefix + 'underline'))
        self.horizontal_alignment = HorizontalAlignment[data.get(key_prefix + 'horizontalAlignment')]
        self.vertical_alignment = VerticalAlignment[data.get(key_prefix + 'verticalAlignment')]
        self.text_color = Color(data.get(key_prefix + 'textColor'))
        self.background_color = Color(data.get(key_prefix + 'backgroundColor'))
        self.font = data.get(key_prefix + 'font')
        self.font_size = get_int_value(data, key_prefix + 'fontSize')
        self.line_spacing = get_float_value(data, key_prefix + 'lineSpacing')
        self.padding_left = get_int_value(data, key_prefix + 'paddingLeft')
        self.padding_top = get_int_value(data, key_prefix + 'paddingTop')
        self.padding_right = get_int_value(data, key_prefix + 'paddingRight')
        self.padding_bottom = get_int_value(data, key_prefix + 'paddingBottom')
        self.font_style = ''
        if self.bold:
            self.font_style += 'B'
        if self.italic:
            self.font_style += 'I'
        self.text_align = ''
        if self.horizontal_alignment == HorizontalAlignment.left:
            self.text_align = 'L'
        elif self.horizontal_alignment == HorizontalAlignment.center:
            self.text_align = 'C'
        elif self.horizontal_alignment == HorizontalAlignment.right:
            self.text_align = 'R'
        elif self.horizontal_alignment == HorizontalAlignment.justify:
            self.text_align = 'J'
        self.add_border_padding()

    def get_font_style(self, ignore_underline=False):
        font_style = ''
        if self.bold:
            font_style += 'B'
        if self.italic:
            font_style += 'I'
        if self.underline and not ignore_underline:
            font_style += 'U'
        return font_style

    def add_border_padding(self):
        if self.border_left:
            self.padding_left += self.border_width
        if self.border_top:
            self.padding_top += self.border_width
        if self.border_right:
            self.padding_right += self.border_width
        if self.border_bottom:
            self.padding_bottom += self.border_width
