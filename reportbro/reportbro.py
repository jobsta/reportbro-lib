#
# Copyright (C) 2017-2022 jobsta
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

import base64
import fpdf
import importlib.resources
import re
import os
import xlsxwriter
from io import BufferedReader, IOBase

from .containers import ReportBand
from .elements import *
from .enums import *
from .errors import Error, ReportBroError, ReportBroInternalError
from .structs import Parameter, TextStyle
from .utils import get_int_value, parse_datetime_string


regex_valid_identifier = re.compile(r'^[^\d\W]\w*$', re.U)


class DocumentPDFRenderer:
    def __init__(self, header_band, content_band, footer_band, report, context,
                 additional_fonts, filename, add_watermark, page_limit, encode_error_handling, core_fonts_encoding):
        self.header_band = header_band
        self.content_band = content_band
        self.footer_band = footer_band
        self.document_properties = report.document_properties
        self.pdf_doc = FPDFRB(
            report.document_properties, additional_fonts=additional_fonts,
            encode_error_handling=encode_error_handling, core_fonts_encoding=core_fonts_encoding)
        self.pdf_doc.set_margins(0, 0)
        self.pdf_doc.c_margin = 0  # interior cell margin
        self.context = context
        self.filename = filename
        self.add_watermark = add_watermark
        self.page_limit = page_limit

    def add_page(self):
        self.pdf_doc.add_page()
        self.context.inc_page_number()

    def is_finished(self):
        return self.content_band.is_finished()

    def render(self):
        watermark_width = watermark_height = 0
        watermark_filename = None
        if self.add_watermark:
            with importlib.resources.path('reportbro.data', 'logo_watermark.png') as p:
                watermark_filename = p
                if watermark_filename.exists():
                    watermark_width = self.document_properties.page_width / 3
                    watermark_height = watermark_width * (115 / 460)
                else:
                    self.add_watermark = False

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
            complete = self.content_band.create_render_elements(0, height, self.context, self.pdf_doc)
            if complete:
                break
            page_count += 1
            if self.page_limit and page_count > self.page_limit:
                raise ReportBroInternalError('Too many pages (probably an endless loop)', log_error=False)
        self.context.set_page_count(page_count)

        footer_offset_y = self.document_properties.page_height -\
            self.document_properties.footer_size - self.document_properties.margin_bottom
        # render at least one page to show header/footer even if content is empty
        while not self.content_band.is_finished() or self.context.get_page_number() == 0:
            self.add_page()
            if self.add_watermark:
                if watermark_height < self.document_properties.page_height:
                    self.pdf_doc.image(
                        watermark_filename,
                        self.document_properties.page_width / 2 - watermark_width / 2,
                        self.document_properties.page_height - watermark_height,
                        watermark_width, watermark_height)

            content_offset_y = self.document_properties.margin_top
            page_number = self.context.get_page_number()
            if self.document_properties.header_display == BandDisplay.always or\
                    (self.document_properties.header_display == BandDisplay.not_on_first_page and page_number != 1):
                content_offset_y += self.document_properties.header_size
                self.header_band.prepare(self.context, self.pdf_doc)
                self.header_band.create_render_elements(
                    0, self.document_properties.header_size, self.context, self.pdf_doc)
                self.header_band.render_pdf(
                    self.document_properties.margin_left, self.document_properties.margin_top, self.pdf_doc)
                self.header_band.reset()
            if self.document_properties.footer_display == BandDisplay.always or\
                    (self.document_properties.footer_display == BandDisplay.not_on_first_page and page_number != 1):
                self.footer_band.prepare(self.context, self.pdf_doc)
                self.footer_band.create_render_elements(
                    0, self.document_properties.footer_size, self.context, self.pdf_doc)
                self.footer_band.render_pdf(self.document_properties.margin_left, footer_offset_y, self.pdf_doc)
                self.footer_band.reset()

            self.content_band.render_pdf(
                self.document_properties.margin_left, content_offset_y, self.pdf_doc, cleanup=True)

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

    def write(self, row, col, colspan, text, cell_format, width, url=None):
        if colspan > 1:
            self.worksheet.merge_range(row, col, row, col + colspan - 1, text, cell_format)
        elif not url:
            self.worksheet.write(row, col, text, cell_format)
            self.update_column_width(col, width)
        # url also works combined with colspan, the first cell of the range is simply overwritten
        if url:
            self.worksheet.write_url(row, col, url, cell_format, text)

    def insert_image(self, row, col, image_filename, image_data, width, url=None):
        options = dict()
        if image_data:
            options['image_data'] = image_data
        if url:
            options['url'] = url
        self.worksheet.insert_image(row, col, image_filename, options)
        self.update_column_width(col, width)

    def add_format(self, format_props):
        return self.workbook.add_format(format_props)

    def set_row(self, row, cell_format):
        self.worksheet.set_row(row, cell_format=cell_format)


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
                if self.page_width < 30 or self.page_width >= 100000:
                    self.report.errors.append(Error('errorMsgInvalidPageSize', object_id=self.id, field='page'))
                elif self.page_height < 30 or self.page_height >= 100000:
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
            raise ReportBroInternalError('invalid pattern_locale', log_error=False)

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


class ImageData:
    def __init__(self, ctx, image_id, source, image_file, is_test_data, headers):
        self.image_data = None
        self.image_type = None
        image_uri = None  # can be either url or file path
        image_url = None
        image_path = None
        img_data_b64 = None
        if source:
            if Context.is_parameter_name(source):
                param_ref = ctx.get_parameter(Context.strip_parameter_name(source))
                if param_ref:
                    source_parameter = param_ref.parameter
                    if source_parameter.type == ParameterType.string:
                        image_uri, _ = ctx.get_parameter_data(param_ref)
                    elif source_parameter.type == ParameterType.image:
                        # image is available as base64 encoded or
                        # file object (only possible if report data is passed directly from python code
                        # and not via web request)
                        img_data, _ = ctx.get_parameter_data(param_ref)
                        if isinstance(img_data, BufferedReader):
                            self.image_data = img_data
                            pos = img_data.name.rfind('.')
                            self.image_type = img_data.name[pos+1:].lower() if pos != -1 else ''
                        elif isinstance(img_data, str):
                            img_data_b64 = img_data
                    else:
                        raise ReportBroError(
                            Error('errorMsgInvalidImageSourceParameter', object_id=image_id, field='source'))
                else:
                    raise ReportBroError(
                        Error('errorMsgMissingParameter', object_id=image_id, field='source'))
            else:
                image_uri = source

        if img_data_b64 is None and not image_uri and self.image_data is None and image_file:
            # static image base64 encoded within image element
            img_data_b64 = image_file

        if img_data_b64:
            m = re.match('^data:image/(.+);base64,', img_data_b64)
            if not m:
                raise ReportBroError(
                    Error('errorMsgInvalidImage', object_id=image_id, field='source'))
            self.image_type = m.group(1).lower()
            img_data = base64.b64decode(re.sub('^data:image/.+;base64,', '', img_data_b64))
            self.image_data = BytesIO(img_data)
        elif image_uri:
            if image_uri.startswith("http://") or image_uri.startswith("https://"):
                image_url = image_uri
                try:
                    parse_result = urllib.parse.urlparse(image_url)
                    pos = parse_result.path.rfind('.')
                    self.image_type = parse_result.path[pos+1:].lower() if pos != -1 else ''
                except ValueError as ex:
                    raise ReportBroError(
                        Error('errorMsgInvalidImageSource', object_id=image_id, field='source'))
            elif not is_test_data and image_uri.startswith("file:"):
                # only allow image path (referencing file on server) when data is passed directly
                # and not from Reportbro Designer
                image_path = image_uri[5:]
                pos = image_uri.rfind('.')
                self.image_type = image_uri[pos+1:].lower() if pos != -1 else ''
            else:
                raise ReportBroError(
                    Error('errorMsgInvalidImageSource', object_id=image_id, field='source'))

        if self.image_type is not None:
            if self.image_type not in ('png', 'jpg', 'jpeg'):
                raise ReportBroError(
                    Error('errorMsgUnsupportedImageType', object_id=image_id, field='source'))

        if image_url:
            try:
                req = urllib.request.Request(image_url, headers=headers)
                self.image_data = BytesIO(urllib.request.urlopen(req).read())
            except Exception as ex:
                raise ReportBroError(
                    Error('errorMsgLoadingImageFailed', object_id=image_id, field='source', info=str(ex)))
        elif image_path:
            try:
                cwd = os.getcwd()
                image_path = os.path.abspath(image_path)
                # make sure image file access is restricted to application
                if os.path.commonprefix([cwd, image_path]) != cwd:
                    raise Exception('Accessing file outside of application path not allowed')
                self.image_data = open(image_path, 'rb')
            except Exception as ex:
                raise ReportBroError(
                    Error('errorMsgLoadingImageFailed', object_id=image_id, field='source', info=str(ex)))


class FPDFRB(fpdf.FPDF):
    def __init__(self, document_properties, additional_fonts, encode_error_handling, core_fonts_encoding):
        if document_properties.orientation == Orientation.portrait:
            orientation = 'P'
            dimension = (document_properties.page_width, document_properties.page_height)
        else:
            orientation = 'L'
            dimension = (document_properties.page_height, document_properties.page_width)
        fpdf.FPDF.__init__(self, orientation=orientation, unit='pt', format=dimension)
        self.x = 0
        self.y = 0
        self.core_fonts_encoding = core_fonts_encoding
        self.encode_error_handling = encode_error_handling
        self.loaded_images = dict()
        self.available_fonts = dict(
            courier=dict(standard_font=True),
            helvetica=dict(standard_font=True),
            times=dict(standard_font=True))
        if additional_fonts:
            for additional_font in additional_fonts:
                filename = additional_font.get('filename', '')
                font = dict(
                    standard_font=False, uni=additional_font.get('uni', True))

                regular_style = dict(
                    font_filename=filename, style='', font_added=False)
                bold_style = dict(
                    font_filename=additional_font.get('bold_filename', filename),
                    style='B', font_added=False)
                italic_style = dict(
                    font_filename=additional_font.get('italic_filename', filename),
                    style='I', font_added=False)
                bold_italic_style = dict(
                    font_filename=additional_font.get('bold_italic_filename', filename),
                    style='BI', font_added=False)

                # map styles in case there are no separate font-files for bold, italic or bold italic
                # to avoid adding the same font multiple times to the pdf document
                if bold_style['font_filename'] == regular_style['font_filename']:
                    bold_style = regular_style
                if italic_style['font_filename'] == regular_style['font_filename']:
                    italic_style = regular_style
                if bold_italic_style['font_filename'] == italic_style['font_filename']:
                    bold_italic_style = italic_style
                elif bold_italic_style['font_filename'] == bold_style['font_filename']:
                    bold_italic_style = bold_style
                elif bold_italic_style['font_filename'] == regular_style['font_filename']:
                    bold_italic_style = regular_style
                font['style'] = regular_style
                font['styleB'] = bold_style
                font['styleI'] = italic_style
                font['styleBI'] = bold_italic_style

                self.available_fonts[additional_font.get('value', '')] = font

    def add_image(self, img, image_key):
        self.loaded_images[image_key] = img

    def get_image(self, image_key):
        return self.loaded_images.get(image_key)

    def set_font(self, family, style='', size=0, underline=False):
        """Set font in underlying pdf renderer.

        This font is used for all following text rendering calls until changed again.

        :param family: name of the font which must either be one of the standard
        fonts (courier, helvetica, times) or added to ReportBro instance with the
        additional_fonts setting.
        :param size: font size, if not set then the standard font size is used.
        :param underline: True if text should be rendered with underlined style.
        :return: True if font exists, False otherwise.
        """
        font = self.available_fonts.get(family)
        if font:
            if not font['standard_font']:
                # get font for specific style
                if style:
                    # replace of 'U' is needed because it is set for underlined text
                    # when called from FPDF.add_page
                    style_font = font['style' + style.replace('U', '')]
                    # style could be different in case styles are mapped,
                    # e.g. if bold style has same font file as regular style
                    style = style_font['style']
                else:
                    style_font = font['style']

                if not style_font['font_added']:
                    self.add_font(
                        family, style=style, fname=style_font['font_filename'], uni=font['uni'])
                    style_font['font_added'] = True

            if underline:
                style += 'U'
            fpdf.FPDF.set_font(self, family, style, size)
            return True
        else:
            return False


class Report:
    def __init__(self, report_definition, data, is_test_data=False, additional_fonts=None,
                 page_limit=10000, request_headers=None, encode_error_handling='strict',
                 core_fonts_encoding='windows-1252'):
        """Create Report instance which can then be used to generate pdf and xlsx reports.

        :param report_definition: The report object containg report elements, parameters,
        styles and document properties. This object can be obtained in
        ReportBro Designer by using getReport method.
        :param data: Dictionary containing all data for the report.
        This structure must correspond with the defined parameters
        in the report_definition (parameter name and type).
        :param is_test_data: set to True in case the given data contains test data which
        is specified within the parameters in ReportBro Designer. Set to False if
        the data comes from your web application. This setting influences the
        error messages in case report generation fails due to invalid data.
        :param additional_fonts: In case additional (non-standard) fonts are used they
        must be made available so they can be embedded into the pdf file.
        :param page_limit: maximum number of pages for pdf reports. This can
        be used to avoid reports getting too big or taking too long for generation.
        If set to 0 or None then no page limit is used.
        :param request_headers: request headers used when images are fetched by url
        :param encode_error_handling: defines behaviour when a character cannot
        be encoded with the encoding used for the core fonts. The following options exist:
        - 'strict': raise a UnicodeDecodeError exception
        - 'ignore': just leave the character out of the result
        - 'replace': use U+FFFD replacement character
        :param core_fonts_encoding: defines the encoding when using the core fonts.
        Default is 'windows-1252' which is usually the best choice for English and many European
        languages including Spanish, French, and German.
        """
        assert isinstance(report_definition, dict)
        assert isinstance(data, dict)
        assert encode_error_handling in ('strict', 'ignore', 'replace')

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
        self.page_limit = page_limit
        self.encode_error_handling = encode_error_handling
        self.core_fonts_encoding = core_fonts_encoding
        # request headers used when fetching images by url (some sites check for existance
        # of user-agent header and do not return image otherwise)
        self.request_headers = {'User-Agent': 'Mozilla/5.0'}
        if request_headers is not None:
            self.request_headers = request_headers

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
                        self.errors.append(Error('errorMsgInvalidPosition', object_id=elem.id, field='x'))
                    elif elem.x + elem.width > container.width:
                        self.errors.append(Error('errorMsgInvalidSize', object_id=elem.id, field='width'))
                    if elem.y < 0:
                        self.errors.append(Error('errorMsgInvalidPosition', object_id=elem.id, field='y'))
                    elif elem.y + elem.height > container.height:
                        self.errors.append(Error('errorMsgInvalidSize', object_id=elem.id, field='height'))
                container.add(elem)

        self.context = Context(self, self.parameters, self.data)

        self.images = dict()  # cached image data

        self.process_data(dest_data=self.data, src_data=data, parameters=parameter_list,
                          is_test_data=is_test_data, parents=[])
        try:
            if not self.errors:
                self.evaluate_parameters(parameter_list, self.data)
        except ReportBroError as err:
            self.errors.append(err.error)

    def load_image(self, image_key, ctx, image_id, source, image_file):
        # test if image is not already loaded into image cache
        if image_key not in self.images:
            image = ImageData(ctx, image_id, source, image_file, self.is_test_data, headers=self.request_headers)
            self.images[image_key] = image

    def get_image(self, image_key):
        return self.images.get(image_key)

    def generate_pdf(self, filename='', add_watermark=False):
        renderer = DocumentPDFRenderer(
            header_band=self.header, content_band=self.content, footer_band=self.footer,
            report=self, context=self.context, additional_fonts=self.additional_fonts,
            filename=filename, add_watermark=add_watermark, page_limit=self.page_limit,
            encode_error_handling=self.encode_error_handling, core_fonts_encoding=self.core_fonts_encoding)
        return renderer.render()

    def generate_xlsx(self, filename=''):
        renderer = DocumentXLSXRenderer(
            header_band=self.header, content_band=self.content, footer_band=self.footer,
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
                if not isinstance(value, str):
                    raise ReportBroInternalError(
                        f'value of parameter {parameter.name} must be str type', log_error=False)
            elif not parameter.nullable:
                value = ''

        elif parameter_type == ParameterType.number:
            if value:
                if isinstance(value, str):
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
                if isinstance(value, (int, float)):
                    value = decimal.Decimal(0)
                elif is_test_data and isinstance(value, str):
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
            if isinstance(value, str):
                if is_test_data and not value:
                    value = None if parameter.nullable else datetime.datetime.now()
                else:
                    try:
                        value = parse_datetime_string(value)
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

    def process_data(self, dest_data, src_data, parameters, is_test_data, parents):
        field = 'test_data' if is_test_data else 'type'
        parent_id = parents[-1].id if parents else None
        for parameter in parameters:
            if parameter.is_internal:
                continue
            if regex_valid_identifier.match(parameter.name) is None:
                self.errors.append(Error('errorMsgInvalidParameterName',
                                         object_id=parameter.id, field='name', info=parameter.name))
            parameter_type = parameter.type
            if not parameter.is_evaluated():
                value = src_data.get(parameter.name)
                if parameter_type in (ParameterType.string, ParameterType.number,
                                      ParameterType.boolean, ParameterType.date):
                    value = self.parse_parameter_value(parameter, parent_id, is_test_data, parameter_type, value)
                    dest_data[parameter.name] = value
                elif parameter_type == ParameterType.image:
                    if value:
                        if isinstance(value, str):
                            # base64 encoded image data
                            if not value.startswith('data:image'):
                                raise ReportBroInternalError(
                                    f'value of parameter {parameter.name} must be base64 encoded image data '
                                    'and start with "data:image"', log_error=False)
                        elif isinstance(value, IOBase):
                            # image passed as file object
                            pass
                        else:
                            raise ReportBroInternalError(
                                f'value of image parameter {parameter.name} must be string with base64 encoded '
                                'image data or a file object of the image', log_error=False)
                        dest_data[parameter.name] = value
                elif parameter_type == ParameterType.simple_array:
                    if isinstance(value, list):
                        list_values = []
                        for list_value in value:
                            parsed_value = self.parse_parameter_value(
                                parameter, parent_id, is_test_data, parameter.array_item_type, list_value)
                            list_values.append(parsed_value)
                        dest_data[parameter.name] = list_values
                    elif value is None:
                        if not parameter.nullable:
                            value = []
                        dest_data[parameter.name] = value
                    else:
                        self.errors.append(Error(
                            'errorMsgInvalidArray',
                            object_id=parameter.id, field=field, context=parameter.name))
                elif not parents:
                    if parameter_type == ParameterType.array:
                        if isinstance(value, list):
                            parents.append(parameter)
                            parameter_list = list(parameter.fields.values())
                            # create new list which will be assigned to dest_data to keep src_data unmodified
                            dest_array = []

                            for row_number, row in enumerate(value, start=1):
                                dest_array_item = dict()
                                self.process_data(
                                    dest_data=dest_array_item, src_data=row, parameters=parameter_list,
                                    is_test_data=is_test_data, parents=parents)
                                # set value for internal parameter 'row_number'
                                dest_array_item['row_number'] = row_number
                                dest_array.append(dest_array_item)
                            parents = parents[:-1]
                            dest_data[parameter.name] = dest_array
                        elif value is None:
                            if not parameter.nullable:
                                value = []
                            dest_data[parameter.name] = value
                        else:
                            self.errors.append(Error(
                                'errorMsgInvalidArray',
                                object_id=parameter.id, field=field, context=parameter.name))
                    elif parameter_type == ParameterType.map:
                        if isinstance(value, dict):
                            if isinstance(parameter.children, list):
                                parents.append(parameter)
                                # create new dict which will be assigned to dest_data to keep src_data unmodified
                                dest_map = dict()

                                self.process_data(
                                    dest_data=dest_map, src_data=value, parameters=parameter.children,
                                    is_test_data=is_test_data, parents=parents)
                                parents = parents[:-1]
                                dest_data[parameter.name] = dest_map
                            else:
                                self.errors.append(Error(
                                    'errorMsgInvalidMap',
                                    object_id=parameter.id, field='type', context=parameter.name))
                        elif value is None:
                            if not parameter.nullable:
                                value = dict()
                            dest_data[parameter.name] = value
                        else:
                            self.errors.append(Error(
                                'errorMsgInvalidMap',
                                object_id=parameter.id, field='type', context=parameter.name))
                else:
                    # nested parameters (array / map inside other array / map parameter) are only
                    # supported in PLUS version
                    self.errors.append(Error(
                        'errorMsgPlusVersionRequired', object_id=parameter.id, field='type', context=parameter.name))

    def evaluate_parameters(self, parameters, data):
        for parameter in parameters:
            if not parameter.is_internal:
                if parameter.is_evaluated():
                    self.evaluate_parameter_expr(parameter, data)
                elif parameter.type == ParameterType.map:
                    for field in parameter.children:
                        if field.is_evaluated():
                            # set dest_data so evaluated expression is set in map
                            self.evaluate_parameter_expr(field, data, dest_data=data[parameter.name])
                elif parameter.type == ParameterType.array:
                    eval_fields = []
                    for field in parameter.children:
                        if field.eval:
                            eval_fields.append(field)
                    if eval_fields:
                        param_ref = self.context.get_parameter(parameter.name)
                        if param_ref is not None:
                            rows, data_exists = self.context.get_parameter_data(param_ref)
                            if data_exists:
                                row_parameters = dict()
                                for row_parameter in parameter.children:
                                    row_parameters[row_parameter.name] = row_parameter

                                for row in rows:
                                    self.context.push_context(row_parameters, row)
                                    for field in eval_fields:
                                        self.evaluate_parameter_expr(field, row)
                                    self.context.pop_context()

    def evaluate_parameter_expr(self, parameter, data, dest_data=None):
        if not parameter.expression:
            self.errors.append(Error(
                'errorMsgMissingExpression',
                object_id=parameter.id, field='expression', context=parameter.name))
            return

        parameter_type = parameter.type
        if parameter_type in (ParameterType.average, ParameterType.sum):
            value, valid_value = self.context.evaluate_parameter_func(parameter)
        else:
            value = self.context.evaluate_expression(
                parameter.expression, parameter.id, field='expression')
            valid_value = False
            if parameter_type == ParameterType.string:
                if isinstance(value, str):
                    valid_value = True
            elif parameter_type == ParameterType.number:
                if isinstance(value, decimal.Decimal):
                    valid_value = True
                elif isinstance(value, (int, float)):
                    value = decimal.Decimal(value)
                    valid_value = True
            elif parameter_type == ParameterType.boolean:
                if isinstance(value, bool):
                    valid_value = True
            elif parameter_type == ParameterType.date:
                if isinstance(value, str):
                    try:
                        value = parse_datetime_string(value)
                    except (ValueError, TypeError):
                        self.errors.append(Error(
                            'errorMsgInvalidExpressionType',
                            object_id=parameter.id, field='expression', context=parameter.name))
                    valid_value = True
                elif isinstance(value, datetime.date):
                    valid_value = True
                    if not isinstance(value, datetime.datetime):
                        value = datetime.datetime(value.year, value.month, value.day)

            if not valid_value:
                self.errors.append(Error(
                    'errorMsgInvalidExpressionType',
                    object_id=parameter.id, field='expression', context=parameter.name))

        if valid_value:
            if dest_data is not None:
                dest_data[parameter.name] = value
            else:
                data[parameter.name] = value
