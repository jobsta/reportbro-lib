import json
from typing import Optional, Union

from .enums import *
from .errors import Error, ReportBroInternalError
from .utils import current_datetime_str, get_float_value, get_int_value, get_str_value


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
    def __init__(self, report, data, init_test_data=False):
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
        self.pattern_has_currency = '$' in self.pattern
        self.is_internal = self.name in ('page_count', 'page_number', 'row_number')
        self.needs_evaluation = self.is_evaluated()
        self.test_data = None
        self.test_data_boolean = None
        self.test_data_image = None
        self.test_data_rich_text = None
        if init_test_data:
            self.test_data = data.get('testData')
            self.test_data_boolean = data.get('testDataBoolean')
            self.test_data_image = data.get('testDataImage')
            self.test_data_rich_text = data.get('testDataRichText')
        self.range_stack = []
        self.children = []
        self.show_only_name_type = bool(data.get('showOnlyNameType'))
        self.fields = dict()
        if self.type == ParameterType.array or self.type == ParameterType.map:
            for item in data.get('children'):
                parameter = Parameter(self.report, item)
                if parameter.name in self.fields:
                    # report instance can be null when test data is retrieved from parameters
                    if self.report:
                        self.report.errors.append(
                            Error('errorMsgDuplicateParameterField', object_id=parameter.id, field='name'))
                else:
                    self.children.append(parameter)
                    self.fields[parameter.name] = parameter
                    if parameter.needs_evaluation:
                        self.needs_evaluation = True

    def is_evaluated(self):
        """Return True if parameter data must be evaluated initially."""
        return not self.is_internal and (self.eval or self.is_range_function())

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

    def get_test_data(self, include_image_data=True) -> Optional[Union[dict, list]]:
        """
        Extract test data from test data value of parameters.

        Supports test data saved in ReportBro Designer version >= 3.0.
        The method is ported from the ReportBro Designer method ReportBro.getTestData

        This is used for ReportBro tests where data is extracted from parameter test data
        saved within the report template.

        :param include_image_data: if False then image test data will not be set (set to None value)
        """
        test_data = None
        try:
            test_data = json.loads(self.test_data)
        except json.JSONDecodeError:
            pass
        if self.type in (ParameterType.array, ParameterType.simple_array, ParameterType.map):
            if test_data:
                return self.get_parameter_test_data(self, test_data, include_image_data=include_image_data)
            elif self.type == ParameterType.map:
                # return map with default values for all map fields
                return self.get_parameter_test_data(self, {}, include_image_data=include_image_data)
            else:
                # array or simple_array
                return []
        return None

    @staticmethod
    def get_parameter_test_data(parameter, test_data, include_image_data):
        """
        Get test data from parameter.

        The method is ported from the ReportBro Designer method Parameter.getSanitizedTestData

        :param parameter: parameter must be of type map, simple_array or array.
        :param test_data: test data for parameter, must be a dict for parameter type map and a list otherwise.
        :param include_image_data: if False then image test data will not be set (set to None value)
        :return: test data in a dict for parameter type map and list otherwise.
        """
        if parameter.type == ParameterType.map:
            if not isinstance(test_data, dict):
                test_data = {}
            rv = Parameter.get_parameter_test_data_map(parameter, test_data, include_image_data=include_image_data)
        elif parameter.type == ParameterType.simple_array:
            rv = Parameter.get_parameter_test_data_simple_array(test_data)
        elif parameter.type == ParameterType.array:
            if not isinstance(test_data, list):
                test_data = []
            rv = []
            for test_data_row in test_data:
                if parameter.type == ParameterType.array:
                    if not isinstance(test_data_row, dict):
                        test_data_row = {}
                    rv.append(Parameter.get_parameter_test_data_map(
                        parameter, test_data_row, include_image_data=include_image_data))
        else:
            assert False
        return rv

    @staticmethod
    def get_parameter_test_data_map(parameter, test_data, include_image_data):
        """
        The method is ported from the ReportBro Designer method Parameter.getSanitizedTestDataMap
        """
        rv = {}
        for field in parameter.children:
            if field.show_only_name_type:
                continue
            value = test_data[field.name] if (field.name in test_data) else None
            if field.type == ParameterType.array or field.type == ParameterType.map:
                rv[field.name] = Parameter.get_parameter_test_data(field, value, include_image_data=include_image_data)
            elif field.type == ParameterType.simple_array:
                rv[field.name] = Parameter.get_parameter_test_data_simple_array(value)
            elif field.type == ParameterType.image:
                if include_image_data and isinstance(value, dict) and 'data' in value:
                    rv[field.name] = value['data']
                else:
                    rv[field.name] = ''
            else:
                if value:
                    rv[field.name] = value
                else:
                    # set default value when value is missing
                    rv[field.name] = {
                        ParameterType.string: '',
                        ParameterType.number: '0',
                        ParameterType.boolean: False,
                        ParameterType.date: current_datetime_str,
                        ParameterType.rich_text: '',
                    }.get(field.type)
        return rv

    @staticmethod
    def get_parameter_test_data_simple_array(test_data):
        """
        The method is ported from the ReportBro Designer method Parameter.getSanitizedTestDataSimpleArray
        """
        test_data_rows = test_data
        if not isinstance(test_data_rows, list):
            test_data_rows = []
        array_values = []
        for test_data_row in test_data_rows:
            if isinstance(test_data_row, dict) and 'data' in test_data_row:
                array_values.append(test_data_row['data'])
        return array_values


class BorderStyle:
    def __init__(self, data, key_prefix=''):
        self.border_color = Color(data.get(key_prefix + 'borderColor'))
        self.border_width = get_float_value(data, key_prefix + 'borderWidth')
        self.border_all = bool(data.get(key_prefix + 'borderAll'))
        self.border_left = self.border_all or bool(data.get(key_prefix + 'borderLeft'))
        self.border_top = self.border_all or bool(data.get(key_prefix + 'borderTop'))
        self.border_right = self.border_all or bool(data.get(key_prefix + 'borderRight'))
        self.border_bottom = self.border_all or bool(data.get(key_prefix + 'borderBottom'))


class TextLinePart:
    def __init__(self, text, width, style, link):
        self.text = text
        self.width = width
        self.style = style
        self.link = link


class TextStyle(BorderStyle):
    def __init__(self, data, key_prefix='', id_suffix=''):
        """
        :param data: dict containing text style values
        :param key_prefix: optional prefix to access data values. this is used for conditional style
        values where the values are stored within an element. The conditional style value keys contain
        a prefix to distinguish them from the standard style values.
        :param id_suffix: if set then the id_suffix is appended to the id. this is used for
        (conditional) styles stored within an element to avoid id collision with an existing style.
        """
        BorderStyle.__init__(self, data, key_prefix)
        self.key_prefix = key_prefix
        self.id = str(get_int_value(data, 'id'))
        if id_suffix:
            self.id += id_suffix
        self.bold = bool(data.get(key_prefix + 'bold'))
        self.italic = bool(data.get(key_prefix + 'italic'))
        self.underline = bool(data.get(key_prefix + 'underline'))
        self.strikethrough = bool(data.get(key_prefix + 'strikethrough'))
        self.horizontal_alignment = HorizontalAlignment[data.get(key_prefix + 'horizontalAlignment')]
        self.vertical_alignment = VerticalAlignment[data.get(key_prefix + 'verticalAlignment')]
        self.text_color = Color(data.get(key_prefix + 'textColor'))
        self.background_color = Color(data.get(key_prefix + 'backgroundColor'))
        self.font = get_str_value(data, key_prefix + 'font')
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
        """
        Set bold style and update font_style member which is used for pdf rendering.
        Method is used in rich text rendering.
        """
        self.bold = bold
        self.font_style = self.get_font_style(ignore_underline=True)

    def set_italic(self, italic):
        """
        Set italic style and update font_style member which is used for pdf rendering.
        Method is used in rich text rendering.
        """
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


class LineStyle:
    def __init__(self, data, id_suffix=''):
        """
        :param data: dict containing line style values
        :param id_suffix: if set then the id_suffix is appended to the id. this is used for
        styles stored within an element to avoid id collision with an existing style.
        """
        self.id = str(get_int_value(data, 'id'))
        if id_suffix:
            self.id += id_suffix
        self.color = Color(data.get('color'))


class ImageStyle:
    def __init__(self, data, id_suffix=''):
        """
        :param data: dict containing image style values
        :param id_suffix: if set then the id_suffix is appended to the id. this is used for
        styles stored within an element to avoid id collision with an existing style.
        """
        self.id = str(get_int_value(data, 'id'))
        if id_suffix:
            self.id += id_suffix
        self.horizontal_alignment = HorizontalAlignment[data.get('horizontalAlignment')]
        self.vertical_alignment = VerticalAlignment[data.get('verticalAlignment')]
        self.background_color = Color(data.get('backgroundColor'))


class TableStyle:
    def __init__(self, data, id_suffix=''):
        """
        :param data: dict containing table style values
        :param id_suffix: if set then the id_suffix is appended to the id. this is used for
        styles stored within an element to avoid id collision with an existing style.
        """
        self.id = str(get_int_value(data, 'id'))
        if id_suffix:
            self.id += id_suffix
        self.border = Border[data.get('border')]
        self.border_color = Color(data.get('borderColor'))
        self.border_width = get_float_value(data, 'borderWidth')


class TableBandStyle:
    def __init__(self, data, id_suffix=''):
        """
        :param data: dict containing table band style values
        :param id_suffix: if set then the id_suffix is appended to the id. this is used for
        styles stored within an element to avoid id collision with an existing style.
        """
        self.id = str(get_int_value(data, 'id'))
        if id_suffix:
            self.id += id_suffix
        self.background_color = Color(data.get('backgroundColor'))
        self.alternate_background_color = Color(data.get('alternateBackgroundColor'))


class FrameStyle(BorderStyle):
    def __init__(self, data, id_suffix=''):
        """
        :param data: dict containing frame style values
        :param id_suffix: if set then the id_suffix is appended to the id. this is used for
        styles stored within an element to avoid id collision with an existing style.
        """
        BorderStyle.__init__(self, data)
        self.id = str(get_int_value(data, 'id'))
        if id_suffix:
            self.id += id_suffix
        self.background_color = Color(data.get('backgroundColor'))


class SectionBandStyle:
    def __init__(self, data, id_suffix=''):
        """
        :param data: dict containing section band style values
        :param id_suffix: if set then the id_suffix is appended to the id. this is used for
        styles stored within an element to avoid id collision with an existing style.
        """
        self.id = str(get_int_value(data, 'id'))
        if id_suffix:
            self.id += id_suffix
        self.background_color = Color(data.get('backgroundColor'))
        self.alternate_background_color = Color(data.get('alternateBackgroundColor'))


class ConditionalStyleRule:
    def __init__(self, report, data, object_id, rule_nr):
        self.report = report
        self.condition = data['condition']
        self.style = None
        if not data.get('style_id'):
            self.report.errors.append(
                Error('errorMsgAddtionalRulesNoStyleSelected',
                      object_id=object_id, field='cs_additionalRules', info=str(rule_nr)))
        else:
            self.style = report.styles.get(int(data.get('style_id')))
            if self.style is None:
                raise ReportBroInternalError(f'Conditional style for element {object_id} not found', log_error=False)

    def is_true(self, ctx, object_id):
        return ctx.evaluate_expression(self.condition, object_id, field='cs_additionalRules')
