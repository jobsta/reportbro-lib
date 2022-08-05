from .enums import *
from .errors import Error, ReportBroInternalError
from .utils import get_float_value, get_int_value


class Color:
    def __init__(self, color):
        self.color_code = ''
        if color:
            valid = False
            if isinstance(color, str) and len(color) == 7 and color[0] == '#':
                try:
                    self.r = int(color[1:3], 16)
                    self.g = int(color[3:5], 16)
                    self.b = int(color[5:7], 16)
                    self.transparent = False
                    self.color_code = color
                    valid = True
                except ValueError:
                    pass

            if not valid:
                raise ReportBroInternalError(f'Invalid color value {color}', log_error=False)
        else:
            self.r = 0
            self.g = 0
            self.b = 0
            self.transparent = True
            self.color_code = ''

    def __eq__(self, other):
        if isinstance(other, Color):
            return self.color_code == other.color_code
        return False

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
        self.is_internal = self.name in ('page_count', 'page_number', 'row_number')
        self.range_stack = []
        self.children = []
        self.fields = dict()
        if self.type == ParameterType.array or self.type == ParameterType.map:
            for item in data.get('children'):
                parameter = Parameter(self.report, item)
                if parameter.name in self.fields:
                    self.report.errors.append(
                        Error('errorMsgDuplicateParameterField', object_id=parameter.id, field='name'))
                else:
                    self.children.append(parameter)
                    self.fields[parameter.name] = parameter

    def is_evaluated(self):
        """Return True if parameter data must be evaluated initially."""
        return self.eval or self.is_range_function()

    def is_range_function(self):
        """Return True if parameter is a function with range input."""
        return self.type in (ParameterType.average, ParameterType.sum)

    def set_range(self, row_start, row_end):
        """
        Set row range which is used for parameter functions (e.g. sum/avg), if a range is set then
        only these rows will be used for the function, otherwise all rows are used.

        :param row_start: first row of group
        :param row_end: index after last row of group
        """
        self.range_stack.append((row_start, row_end))

    def clear_range(self):
        """Clear previously set row range."""
        self.range_stack.pop()

    def get_range(self):
        if self.range_stack:
            return self.range_stack[-1]
        return None, None

    def has_range(self):
        return bool(self.range_stack)


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
        self.key_prefix = key_prefix
        self.id = str(get_int_value(data, 'id'))
        self.bold = bool(data.get(key_prefix + 'bold'))
        self.italic = bool(data.get(key_prefix + 'italic'))
        self.underline = bool(data.get(key_prefix + 'underline'))
        self.strikethrough = bool(data.get(key_prefix + 'strikethrough'))
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

    def set_bold(self, bold):
        self.bold = bold
        self.font_style = self.get_font_style(ignore_underline=True)

    def set_italic(self, italic):
        self.italic = italic
        self.font_style = self.get_font_style(ignore_underline=True)

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
