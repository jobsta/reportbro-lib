#
# Copyright (C) 2018 jobsta
#
# This file is part of ReportBro, a library to generate PDF and Excel reports.
# Demos can be found at https://www.reportbro.com
#
# Dual licensed under AGPLv3 and ReportBro commercial license:
# https://www.reportbro.com/license
#
# You should have received a copy of the GNU Affero General Public License
# along with this program. If not, see https://www.gnu.org/licenses/
#
# Details for ReportBro commercial license can be found at
# https://www.reportbro.com/license/agreement
#

from __future__ import unicode_literals
from __future__ import division
import fpdf
import re
import xlsxwriter
import pkg_resources

from .containers import ReportBand
from .elements import *
from .enums import *
from .structs import Parameter, TextStyle
from .utils import get_int_value, PY3


try:
    basestring  # For Python 2, str and unicode
except NameError:
    basestring = str

if PY3:
    long = int

regex_valid_identifier = re.compile(r'^[^\d\W]\w*$', re.U)


class DocumentPDFRenderer:
    def __init__(self, header_band, content_band, footer_band, report, context,
            additional_fonts, filename, add_watermark):
        self.header_band = header_band
        self.content_band = content_band
        self.footer_band = footer_band
        self.document_properties = report.document_properties
        self.pdf_doc = FPDFRB(report.document_properties, additional_fonts=additional_fonts)
        self.pdf_doc.set_margins(0, 0)
        self.pdf_doc.c_margin = 0  # interior cell margin
        self.context = context
        self.filename = filename
        self.add_watermark = add_watermark

    def add_page(self):
        self.pdf_doc.add_page()
        self.context.inc_page_number()

    def is_finished(self):
        return self.content_band.is_finished()

    def render(self):
        watermark_width = watermark_height = 0
        watermark_filename = pkg_resources.resource_filename('reportbro', 'data/logo_watermark.png')
        if self.add_watermark:
            if not os.path.exists(watermark_filename):
                self.add_watermark = False
            else:
                watermark_width = self.document_properties.page_width / 3
                watermark_height = watermark_width * (108 / 461)

        self.content_band.prepare(self.context, self.pdf_doc)
        page_count = 1
        while True:
            height = self.document_properties.page_height -\
                self.document_properties.margin_top - self.document_properties.margin_bottom
            if self.document_properties.header_display == BandDisplay.always or\
                    (self.document_properties.header_display == BandDisplay.not_on_first_page and page_count != 1):
                height -= self.document_properties.header_size
            if self.document_properties.footer_display == BandDisplay.always or\
                    (self.document_properties.footer_display == BandDisplay.not_on_first_page and page_count != 1):
                height -= self.document_properties.footer_size
            complete = self.content_band.create_render_elements(height, self.context, self.pdf_doc)
            if complete:
                break
            page_count += 1
            if page_count >= 10000:
                raise RuntimeError('Too many pages (probably an endless loop)')
        self.context.set_page_count(page_count)

        footer_offset_y = self.document_properties.page_height -\
            self.document_properties.footer_size - self.document_properties.margin_bottom
        # render at least one page to show header/footer even if content is empty
        while not self.content_band.is_finished() or self.context.get_page_number() == 0:
            self.add_page()
            if self.add_watermark:
                if watermark_height < self.document_properties.page_height:
                    self.pdf_doc.image(watermark_filename,
                            self.document_properties.page_width / 2 - watermark_width / 2,
                            self.document_properties.page_height - watermark_height,
                            watermark_width, watermark_height)

            content_offset_y = self.document_properties.margin_top
            page_number = self.context.get_page_number()
            if self.document_properties.header_display == BandDisplay.always or\
                    (self.document_properties.header_display == BandDisplay.not_on_first_page and page_number != 1):
                content_offset_y += self.document_properties.header_size
                self.header_band.prepare(self.context, self.pdf_doc)
                self.header_band.create_render_elements(self.document_properties.header_size,
                        self.context, self.pdf_doc)
                self.header_band.render_pdf(self.document_properties.margin_left,
                    self.document_properties.margin_top, self.pdf_doc)
            if self.document_properties.footer_display == BandDisplay.always or\
                    (self.document_properties.footer_display == BandDisplay.not_on_first_page and page_number != 1):
                self.footer_band.prepare(self.context, self.pdf_doc)
                self.footer_band.create_render_elements(self.document_properties.footer_size,
                        self.context, self.pdf_doc)
                self.footer_band.render_pdf(self.document_properties.margin_left, footer_offset_y, self.pdf_doc)

            self.content_band.render_pdf(self.document_properties.margin_left, content_offset_y, self.pdf_doc, cleanup=True)

        self.header_band.cleanup()
        self.footer_band.cleanup()
        dest = 'F' if self.filename else 'S'
        return self.pdf_doc.output(name=self.filename, dest=dest)


class DocumentXLSXRenderer:
    def __init__(self, header_band, content_band, footer_band, report, context, filename):
        self.header_band = header_band
        self.content_band = content_band
        self.footer_band = footer_band
        self.document_properties = report.document_properties
        self.workbook_mem = BytesIO()
        self.workbook = xlsxwriter.Workbook(filename if filename else self.workbook_mem)
        self.worksheet = self.workbook.add_worksheet()
        self.context = context
        self.filename = filename
        self.row = 0
        self.column_widths = []

    def render(self):
        if self.document_properties.header_display != BandDisplay.never:
            self.render_band(self.header_band)
        self.render_band(self.content_band)
        if self.document_properties.header_display != BandDisplay.never:
            self.render_band(self.footer_band)

        for i, column_width in enumerate(self.column_widths):
            if column_width > 0:
                # setting the column width is just an approximation, in Excel the width
                # is the number of characters in the default font
                self.worksheet.set_column(i, i, column_width / 7)

        self.workbook.close()
        if not self.filename:
            # if no filename is given the spreadsheet data will be returned
            self.workbook_mem.seek(0)
            return self.workbook_mem.read()
        return None

    def render_band(self, band):
        band.prepare(self.context)
        self.row, _ = band.render_spreadsheet(self.row, 0, self.context, self)

    def update_column_width(self, col, width):
        if col >= len(self.column_widths):
            # make sure column_width list contains entries for each column
            self.column_widths.extend([-1] * (col + 1 - len(self.column_widths)))
        if width > self.column_widths[col]:
            self.column_widths[col] = width

    def write(self, row, col, colspan, text, cell_format, width):
        if colspan > 1:
            self.worksheet.merge_range(row, col, row, col + colspan - 1, text, cell_format)
        else:
            self.worksheet.write(row, col, text, cell_format)
            self.update_column_width(col, width)

    def insert_image(self, row, col, image_filename, width):
        self.worksheet.insert_image(row, col, image_filename)
        self.update_column_width(col, width)

    def add_format(self, format_props):
        return self.workbook.add_format(format_props)


class DocumentProperties:
    def __init__(self, report, data):
        self.id = '0_document_properties'
        self.page_format = PageFormat[data.get('pageFormat').lower()]
        self.orientation = Orientation[data.get('orientation')]
        self.report = report

        if self.page_format == PageFormat.a4:
            if self.orientation == Orientation.portrait:
                self.page_width = 210
                self.page_height = 297
            else:
                self.page_width = 297
                self.page_height = 210
            unit = Unit.mm
        elif self.page_format == PageFormat.a5:
            if self.orientation == Orientation.portrait:
                self.page_width = 148
                self.page_height = 210
            else:
                self.page_width = 210
                self.page_height = 148
            unit = Unit.mm
        elif self.page_format == PageFormat.letter:
            if self.orientation == Orientation.portrait:
                self.page_width = 8.5
                self.page_height = 11
            else:
                self.page_width = 11
                self.page_height = 8.5
            unit = Unit.inch
        else:
            self.page_width = get_int_value(data, 'pageWidth')
            self.page_height = get_int_value(data, 'pageHeight')
            unit = Unit[data.get('unit')]
            if unit == Unit.mm:
                if self.page_width < 100 or self.page_width >= 100000:
                    self.report.errors.append(Error('errorMsgInvalidPageSize', object_id=self.id, field='page'))
                elif self.page_height < 100 or self.page_height >= 100000:
                    self.report.errors.append(Error('errorMsgInvalidPageSize', object_id=self.id, field='page'))
            elif unit == Unit.inch:
                if self.page_width < 1 or self.page_width >= 1000:
                    self.report.errors.append(Error('errorMsgInvalidPageSize', object_id=self.id, field='page'))
                elif self.page_height < 1 or self.page_height >= 1000:
                    self.report.errors.append(Error('errorMsgInvalidPageSize', object_id=self.id, field='page'))
        dpi = 72
        if unit == Unit.mm:
            self.page_width = round((dpi * self.page_width) / 25.4)
            self.page_height = round((dpi * self.page_height) / 25.4)
        else:
            self.page_width = round(dpi * self.page_width)
            self.page_height = round(dpi * self.page_height)

        self.content_height = get_int_value(data, 'contentHeight')
        self.margin_left = get_int_value(data, 'marginLeft')
        self.margin_top = get_int_value(data, 'marginTop')
        self.margin_right = get_int_value(data, 'marginRight')
        self.margin_bottom = get_int_value(data, 'marginBottom')
        self.pattern_locale = data.get('patternLocale', '')
        self.pattern_currency_symbol = data.get('patternCurrencySymbol', '')
        if self.pattern_locale not in ('de', 'en', 'es', 'fr', 'it'):
            raise RuntimeError('invalid pattern_locale')

        self.header = bool(data.get('header'))
        if self.header:
            self.header_display = BandDisplay[data.get('headerDisplay')]
            self.header_size = get_int_value(data, 'headerSize')
        else:
            self.header_display = BandDisplay.never
            self.header_size = 0
        self.footer = bool(data.get('footer'))
        if self.footer:
            self.footer_display = BandDisplay[data.get('footerDisplay')]
            self.footer_size = get_int_value(data, 'footerSize')
        else:
            self.footer_display = BandDisplay.never
            self.footer_size = 0
        if self.content_height == 0:
            self.content_height = self.page_height - self.header_size - self.footer_size -\
                self.margin_top - self.margin_bottom


class FPDFRB(fpdf.FPDF):
    def __init__(self, document_properties, additional_fonts):
        if document_properties.orientation == Orientation.portrait:
            orientation = 'P'
            dimension = (document_properties.page_width, document_properties.page_height)
        else:
            orientation = 'L'
            dimension = (document_properties.page_height, document_properties.page_width)
        fpdf.FPDF.__init__(self, orientation=orientation, unit='pt', format=dimension)
        self.x = 0
        self.y = 0
        self.set_doc_option('core_fonts_encoding', 'windows-1252')
        self.loaded_images = dict()
        self.available_fonts = dict(
            courier=dict(standard_font=True),
            helvetica=dict(standard_font=True),
            times=dict(standard_font=True))
        if additional_fonts:
            for additional_font in additional_fonts:
                filename = additional_font.get('filename', '')
                style_map = {'': '', 'B': 'B', 'I': 'I', 'BI': 'BI'}
                font = dict(standard_font=False, added=False, regular_filename=filename,
                        bold_filename=additional_font.get('bold_filename', filename),
                        italic_filename=additional_font.get('italic_filename', filename),
                        bold_italic_filename=additional_font.get('bold_italic_filename', filename),
                        style_map=style_map, uni=additional_font.get('uni', True))
                # map styles in case there are no separate font-files for bold, italic or bold italic
                # to avoid adding the same font multiple times to the pdf document
                if font['bold_filename'] == font['regular_filename']:
                    style_map['B'] = ''
                if font['italic_filename'] == font['bold_filename']:
                    style_map['I'] = style_map['B']
                elif font['italic_filename'] == font['regular_filename']:
                    style_map['I'] = ''
                if font['bold_italic_filename'] == font['italic_filename']:
                    style_map['BI'] = style_map['I']
                elif font['bold_italic_filename'] == font['bold_filename']:
                    style_map['BI'] = style_map['B']
                elif font['bold_italic_filename'] == font['regular_filename']:
                    style_map['BI'] = ''
                font['style2filename'] = {'': filename, 'B': font['bold_filename'],
                        'I': font['italic_filename'], 'BI': font['bold_italic_filename']}
                self.available_fonts[additional_font.get('value', '')] = font

    def add_image(self, img, image_key):
        self.loaded_images[image_key] = img

    def get_image(self, image_key):
        return self.loaded_images.get(image_key)

    def set_font(self, family, style='', size=0, underline=False):
        font = self.available_fonts.get(family)
        if font:
            if not font['standard_font']:
                if style:
                    # replace of 'U' is needed because it is set for underlined text
                    # when called from FPDF.add_page
                    style = font['style_map'].get(style.replace('U', ''))
                if not font['added']:
                    filename = font['style2filename'].get(style)
                    self.add_font(family, style=style, fname=filename, uni=font['uni'])
                    font['added'] = True
            if underline:
                style += 'U'
            fpdf.FPDF.set_font(self, family, style, size)

        
class Report:
    def __init__(self, report_definition, data, is_test_data=False, additional_fonts=None):
        assert isinstance(report_definition, dict)
        assert isinstance(data, dict)

        self.errors = []

        self.document_properties = DocumentProperties(self, report_definition.get('documentProperties'))

        self.containers = dict()
        self.header = ReportBand(BandType.header, '0_header', self.containers, self)
        self.content = ReportBand(BandType.content, '0_content', self.containers, self)
        self.footer = ReportBand(BandType.footer, '0_footer', self.containers, self)

        self.parameters = dict()
        self.styles = dict()
        self.data = dict()
        self.is_test_data = is_test_data

        self.additional_fonts = additional_fonts

        version = report_definition.get('version')
        if isinstance(version, int):
            # convert old report definitions
            if version < 2:
                for doc_element in report_definition.get('docElements'):
                    if DocElementType[doc_element.get('elementType')] == DocElementType.table:
                        doc_element['contentDataRows'] = [doc_element.get('contentData')]

        # list is needed to compute parameters (parameters with expression) in given order
        parameter_list = []
        for item in report_definition.get('parameters'):
            parameter = Parameter(self, item)
            if parameter.name in self.parameters:
                self.errors.append(Error('errorMsgDuplicateParameter', object_id=parameter.id, field='name'))
            self.parameters[parameter.name] = parameter
            parameter_list.append(parameter)

        for item in report_definition.get('styles'):
            style = TextStyle(item)
            style_id = int(item.get('id'))
            self.styles[style_id] = style

        for doc_element in report_definition.get('docElements'):
            element_type = DocElementType[doc_element.get('elementType')]
            container_id = str(doc_element.get('containerId'))
            container = None
            if container_id:
                container = self.containers.get(container_id)
            elem = None
            if element_type == DocElementType.text:
                elem = TextElement(self, doc_element)
            elif element_type == DocElementType.line:
                elem = LineElement(self, doc_element)
            elif element_type == DocElementType.image:
                elem = ImageElement(self, doc_element)
            elif element_type == DocElementType.bar_code:
                elem = BarCodeElement(self, doc_element)
            elif element_type == DocElementType.table:
                elem = TableElement(self, doc_element)
            elif element_type == DocElementType.page_break:
                elem = PageBreakElement(self, doc_element)
            elif element_type == DocElementType.frame:
                elem = FrameElement(self, doc_element, self.containers)
            elif element_type == DocElementType.section:
                elem = SectionElement(self, doc_element, self.containers)

            if elem and container:
                if container.is_visible():
                    if elem.x < 0:
                        self.errors.append(Error('errorMsgInvalidPosition', object_id=elem.id, field='position'))
                    elif elem.x + elem.width > container.width:
                        self.errors.append(Error('errorMsgInvalidSize', object_id=elem.id, field='position'))
                    if elem.y < 0:
                        self.errors.append(Error('errorMsgInvalidPosition', object_id=elem.id, field='position'))
                    elif elem.y + elem.height > container.height:
                        self.errors.append(Error('errorMsgInvalidSize', object_id=elem.id, field='position'))
                container.add(elem)

        self.context = Context(self, self.parameters, self.data)

        computed_parameters = []
        self.process_data(dest_data=self.data, src_data=data, parameters=parameter_list,
                          is_test_data=is_test_data, computed_parameters=computed_parameters, parents=[])
        try:
            if not self.errors:
                self.compute_parameters(computed_parameters, self.data)
        except ReportBroError as err:
            self.errors.append(err.error)

    def generate_pdf(self, filename='', add_watermark=False):
        renderer = DocumentPDFRenderer(header_band=self.header,
                content_band=self.content, footer_band=self.footer,
                report=self, context=self.context,
                additional_fonts=self.additional_fonts,
                filename=filename, add_watermark=add_watermark)
        return renderer.render()

    def generate_xlsx(self, filename=''):
        renderer = DocumentXLSXRenderer(header_band=self.header, content_band=self.content, footer_band=self.footer,
                report=self, context=self.context, filename=filename)
        return renderer.render()

    # goes through all elements in header, content and footer and throws a ReportBroError in case
    # an element is invalid
    def verify(self):
        if self.document_properties.header_display != BandDisplay.never:
            self.header.prepare(self.context, only_verify=True)
        self.content.prepare(self.context, only_verify=True)
        if self.document_properties.header_display != BandDisplay.never:
            self.footer.prepare(self.context, only_verify=True)

    def parse_parameter_value(self, parameter, parent_id, is_test_data, parameter_type, value):
        error_field = 'test_data' if is_test_data else 'type'
        if parameter_type == ParameterType.string:
            if value is not None:
                if not isinstance(value, basestring):
                    raise RuntimeError('value of parameter {name} must be str type (unicode for Python 2.7.x)'.
                            format(name=parameter.name))
            elif not parameter.nullable:
                value = ''

        elif parameter_type == ParameterType.number:
            if value:
                if isinstance(value, basestring):
                    value = value.replace(',', '.')
                try:
                    value = decimal.Decimal(str(value))
                except (decimal.InvalidOperation, TypeError):
                    if parent_id and is_test_data:
                        self.errors.append(Error('errorMsgInvalidTestData', object_id=parent_id, field='test_data'))
                        self.errors.append(Error('errorMsgInvalidNumber', object_id=parameter.id, field='type'))
                    else:
                        self.errors.append(Error('errorMsgInvalidNumber',
                                                 object_id=parameter.id, field=error_field, context=parameter.name))
            elif value is not None:
                if isinstance(value, (int, long, float)):
                    value = decimal.Decimal(0)
                elif is_test_data and isinstance(value, basestring):
                    value = None if parameter.nullable else decimal.Decimal(0)
                elif not isinstance(value, decimal.Decimal):
                    if parent_id and is_test_data:
                        self.errors.append(Error('errorMsgInvalidTestData', object_id=parent_id, field='test_data'))
                        self.errors.append(Error('errorMsgInvalidNumber', object_id=parameter.id, field='type'))
                    else:
                        self.errors.append(Error('errorMsgInvalidNumber',
                                                 object_id=parameter.id, field=error_field, context=parameter.name))
            elif not parameter.nullable:
                value = decimal.Decimal(0)

        elif parameter_type == ParameterType.boolean:
            if value is not None:
                value = bool(value)
            elif not parameter.nullable:
                value = False

        elif parameter_type == ParameterType.date:
            if isinstance(value, basestring):
                if is_test_data and not value:
                    value = None if parameter.nullable else datetime.datetime.now()
                else:
                    try:
                        format = '%Y-%m-%d'
                        colon_count = value.count(':')
                        if colon_count == 1:
                            format = '%Y-%m-%d %H:%M'
                        elif colon_count == 2:
                            format = '%Y-%m-%d %H:%M:%S'
                        value = datetime.datetime.strptime(value, format)
                    except (ValueError, TypeError):
                        if parent_id and is_test_data:
                            self.errors.append(Error('errorMsgInvalidTestData', object_id=parent_id, field='test_data'))
                            self.errors.append(Error('errorMsgInvalidDate', object_id=parameter.id, field='type'))
                        else:
                            self.errors.append(Error('errorMsgInvalidDate',
                                                     object_id=parameter.id, field=error_field, context=parameter.name))
            elif isinstance(value, datetime.date):
                if not isinstance(value, datetime.datetime):
                    value = datetime.datetime(value.year, value.month, value.day)
            elif value is not None:
                if parent_id and is_test_data:
                    self.errors.append(Error('errorMsgInvalidTestData', object_id=parent_id, field='test_data'))
                    self.errors.append(Error('errorMsgInvalidDate', object_id=parameter.id, field='type'))
                else:
                    self.errors.append(Error('errorMsgInvalidDate',
                                             object_id=parameter.id, field=error_field, context=parameter.name))
            elif not parameter.nullable:
                value = datetime.datetime.now()
        return value

    def process_data(self, dest_data, src_data, parameters, is_test_data, computed_parameters, parents):
        field = 'test_data' if is_test_data else 'type'
        parent_id = parents[-1].id if parents else None
        for parameter in parameters:
            if parameter.is_internal:
                continue
            if regex_valid_identifier.match(parameter.name) is None:
                self.errors.append(Error('errorMsgInvalidParameterName',
                                         object_id=parameter.id, field='name', info=parameter.name))
            parameter_type = parameter.type
            if parameter_type in (ParameterType.average, ParameterType.sum) or parameter.eval:
                if not parameter.expression:
                    self.errors.append(Error('errorMsgMissingExpression',
                                             object_id=parameter.id, field='expression', context=parameter.name))
                else:
                    parent_names = []
                    for parent in parents:
                        parent_names.append(parent.name)
                    computed_parameters.append(dict(parameter=parameter, parent_names=parent_names))
            else:
                value = src_data.get(parameter.name)
                if parameter_type in (ParameterType.string, ParameterType.number,
                                      ParameterType.boolean, ParameterType.date):
                    value = self.parse_parameter_value(parameter, parent_id, is_test_data, parameter_type, value)
                elif not parents:
                    if parameter_type == ParameterType.array:
                        if isinstance(value, list):
                            parents.append(parameter)
                            parameter_list = list(parameter.fields.values())
                            # create new list which will be assigned to dest_data to keep src_data unmodified
                            dest_array = []

                            for row in value:
                                dest_array_item = dict()
                                self.process_data(
                                    dest_data=dest_array_item, src_data=row, parameters=parameter_list,
                                    is_test_data=is_test_data, computed_parameters=computed_parameters,
                                    parents=parents)
                                dest_array.append(dest_array_item)
                            parents = parents[:-1]
                            value = dest_array
                        elif value is None:
                            if not parameter.nullable:
                                value = []
                        else:
                            self.errors.append(Error('errorMsgInvalidArray',
                                                     object_id=parameter.id, field=field, context=parameter.name))
                    elif parameter_type == ParameterType.simple_array:
                        if isinstance(value, list):
                            list_values = []
                            for list_value in value:
                                parsed_value = self.parse_parameter_value(
                                    parameter, parent_id, is_test_data, parameter.array_item_type, list_value)
                                list_values.append(parsed_value)
                            value = list_values
                        elif value is None:
                            if not parameter.nullable:
                                value = []
                        else:
                            self.errors.append(Error('errorMsgInvalidArray',
                                                     object_id=parameter.id, field=field, context=parameter.name))
                    elif parameter_type == ParameterType.map:
                        if value is None and not parameter.nullable:
                            value = dict()
                        if isinstance(value, dict):
                            if isinstance(parameter.children, list):
                                parents.append(parameter)
                                # create new dict which will be assigned to dest_data to keep src_data unmodified
                                dest_map = dict()

                                self.process_data(
                                    dest_data=dest_map, src_data=value, parameters=parameter.children,
                                    is_test_data=is_test_data, computed_parameters=computed_parameters,
                                    parents=parents)
                                parents = parents[:-1]
                                value = dest_map
                            else:
                                self.errors.append(Error('errorMsgInvalidMap',
                                                         object_id=parameter.id, field='type', context=parameter.name))
                        else:
                            self.errors.append(Error('errorMsgMissingData',
                                                     object_id=parameter.id, field='name', context=parameter.name))
                dest_data[parameter.name] = value

    def compute_parameters(self, computed_parameters, data):
        for computed_parameter in computed_parameters:
            parameter = computed_parameter['parameter']
            value = None
            if parameter.type in (ParameterType.average, ParameterType.sum):
                expr = Context.strip_parameter_name(parameter.expression)
                pos = expr.find('.')
                if pos == -1:
                    self.errors.append(Error('errorMsgInvalidAvgSumExpression',
                            object_id=parameter.id, field='expression', context=parameter.name))
                else:
                    parameter_name = expr[:pos]
                    parameter_field = expr[pos+1:]
                    items = data.get(parameter_name)
                    if not isinstance(items, list):
                        self.errors.append(Error('errorMsgInvalidAvgSumExpression',
                                object_id=parameter.id, field='expression', context=parameter.name))
                    else:
                        total = decimal.Decimal(0)
                        for item in items:
                            item_value = item.get(parameter_field)
                            if item_value is None:
                                self.errors.append(Error('errorMsgInvalidAvgSumExpression',
                                        object_id=parameter.id, field='expression', context=parameter.name))
                                break
                            total += item_value
                        if parameter.type == ParameterType.average:
                            value = total / len(items)
                        elif parameter.type == ParameterType.sum:
                            value = total
            else:
                value = self.context.evaluate_expression(parameter.expression, parameter.id, field='expression')

            data_entry = data
            valid = True
            for parent_name in computed_parameter['parent_names']:
                data_entry = data_entry.get(parent_name)
                if not isinstance(data_entry, dict):
                    self.errors.append(Error('errorMsgInvalidParameterData',
                            object_id=parameter.id, field='name', context=parameter.name))
                    valid = False
            if valid:
                data_entry[parameter.name] = value
