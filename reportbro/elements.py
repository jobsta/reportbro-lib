from babel.numbers import format_decimal
from babel.dates import format_datetime
from io import BytesIO
import copy
import datetime
import decimal
import PIL
import qrcode
import tempfile
import urllib

from .barcode128 import code128_image
from .context import Context
from .docelement import DocElementBase, DocElement
from .enums import *
from .errors import Error, ReportBroError, ReportBroInternalError
from .rendering import ImageRenderElement, BarCodeRenderElement, TableRenderElement,\
    FrameRenderElement, SectionRenderElement
from .structs import Color, BorderStyle, TextStyle
from .utils import get_float_value, get_int_value, get_str_value, to_string, get_image_display_size


class ImageElement(DocElement):
    def __init__(self, report, data):
        DocElement.__init__(self, report, data)
        self.source = get_str_value(data, 'source')
        self.image = get_str_value(data, 'image')
        self.image_filename = get_str_value(data, 'imageFilename')
        self.horizontal_alignment = HorizontalAlignment[data.get('horizontalAlignment')]
        self.vertical_alignment = VerticalAlignment[data.get('verticalAlignment')]
        self.background_color = Color(data.get('backgroundColor'))
        self.print_if = get_str_value(data, 'printIf')
        self.remove_empty_element = bool(data.get('removeEmptyElement'))
        self.link = get_str_value(data, 'link')
        self.spreadsheet_hide = bool(data.get('spreadsheet_hide'))
        self.spreadsheet_column = get_int_value(data, 'spreadsheet_column')
        self.spreadsheet_add_empty_row = bool(data.get('spreadsheet_addEmptyRow'))
        self.image_key = None
        self.prepared_link = None

    def prepare(self, ctx, pdf_doc, only_verify):
        self.image_key = None
        # set image_key which is used to fetch cached images
        if self.source:
            if Context.is_parameter_name(self.source):
                # use current parameter value as image key
                param_ref = ctx.get_parameter(Context.strip_parameter_name(self.source))
                if param_ref:
                    source_parameter = param_ref.parameter
                    if source_parameter.type == ParameterType.string:
                        self.image_key, _ = ctx.get_parameter_data(param_ref)
                    elif source_parameter.type == ParameterType.image:
                        self.image_key = self.source + '_' +\
                                         str(Context.get_parameter_context_id(param_ref))
            else:
                # static url
                self.image_key = self.source
        else:
            # static image
            if self.image_filename:
                self.image_key = self.image_filename
            else:
                self.image_key = 'image_' + str(self.id)
        self.report.load_image(self.image_key, ctx, self.id, self.source, self.image)
        if self.link:
            self.prepared_link = ctx.fill_parameters(self.link, self.id, field='link')
            if not (self.prepared_link.startswith('http://') or self.prepared_link.startswith('https://')):
                raise ReportBroError(
                    Error('errorMsgInvalidLink', object_id=self.id, field='link'))

    def get_next_render_element(self, offset_y, container_top, container_height, ctx, pdf_doc):
        _, rv = DocElement.get_next_render_element(
            self, offset_y, container_top, container_height, ctx, pdf_doc)
        if not rv:
            return None, False
        return ImageRenderElement(self.report, offset_y, self), True

    def render_spreadsheet(self, row, col, ctx, renderer):
        if self.image_key:
            image = self.report.get_image(self.image_key)
            if self.spreadsheet_column:
                col = self.spreadsheet_column - 1

            try:
                raw_image = PIL.Image.open(image.image_data)
            except Exception as ex:
                raise ReportBroError(
                    Error('errorMsgLoadingImageFailed', object_id=self.id,
                          field='source' if self.source else 'image', info=str(ex)))

            image_display_width, image_display_height = get_image_display_size(
                self.width, self.height, raw_image.width, raw_image.height)
            if image_display_width != raw_image.width or image_display_height != raw_image.height:
                raw_image = raw_image.resize(
                    (int(image_display_width), int(image_display_height)), PIL.Image.BILINEAR)
                image.image_data = BytesIO()
                raw_image.save(image.image_data, format='PNG' if image.image_type.upper() == 'PNG' else 'JPEG')

            renderer.insert_image(row, col, image_filename=self.image_filename, image_data=image.image_data,
                                  width=self.width, url=self.prepared_link)
            row += 2 if self.spreadsheet_add_empty_row else 1
            col += 1
        return row, col


class BarCodeElement(DocElement):
    def __init__(self, report, data):
        DocElement.__init__(self, report, data)
        self.content = get_str_value(data, 'content')
        self.format = get_str_value(data, 'format').lower()
        assert self.format in ('code128', 'qrcode')
        self.display_value = bool(data.get('displayValue')) if self.format == 'code128' else False
        self.bar_width = get_float_value(data, 'barWidth')
        error_correction_level = get_str_value(data, 'errorCorrectionLevel')
        self.error_correction_level = qrcode.ERROR_CORRECT_M
        if error_correction_level == 'L':
            self.error_correction_level = qrcode.ERROR_CORRECT_L
        elif error_correction_level == 'H':
            self.error_correction_level = qrcode.ERROR_CORRECT_H
        elif error_correction_level == 'Q':
            self.error_correction_level = qrcode.ERROR_CORRECT_Q
        self.print_if = data.get('printIf', '')
        self.remove_empty_element = bool(data.get('removeEmptyElement'))
        self.spreadsheet_hide = bool(data.get('spreadsheet_hide'))
        self.spreadsheet_column = get_int_value(data, 'spreadsheet_column')
        self.spreadsheet_colspan = get_int_value(data, 'spreadsheet_colspan')
        self.spreadsheet_add_empty_row = bool(data.get('spreadsheet_addEmptyRow'))
        self.image_key = None
        self.image_height = self.height - 22 if (self.display_value and self.format == 'code128') else self.height
        self.prepared_content = None

    def is_printed(self, ctx):
        if not self.content:
            return False
        return DocElementBase.is_printed(self, ctx)

    def prepare(self, ctx, pdf_doc, only_verify):
        self.image_key = None
        self.prepared_content = ctx.fill_parameters(self.content, self.id, field='content')
        if self.prepared_content:
            try:
                if self.format == 'qrcode':
                    img = qrcode.make(self.prepared_content, border=0, error_correction=self.error_correction_level)
                elif self.format == 'code128':
                    img = code128_image(
                        self.prepared_content, height=self.image_height, thickness=self.bar_width, quiet_zone=False)
            except:
                raise ReportBroError(
                    Error('errorMsgInvalidBarCode', object_id=self.id, field='content'))
            if not only_verify:
                with tempfile.NamedTemporaryFile(delete=False, suffix='.png') as f:
                    img.save(f.name)
                    self.image_key = f.name
                    if self.format == 'qrcode':
                        # QR Code is always quadratic and only height can be set -> use same value for width
                        self.width = self.height
                    else:
                        # for Code128 the width is defined by the image width of the bar code
                        self.width = img.width

    def get_next_render_element(self, offset_y, container_top, container_height, ctx, pdf_doc):
        _, rv = DocElement.get_next_render_element(
            self, offset_y, container_top, container_height, ctx, pdf_doc)
        if not rv:
            return None, False
        return BarCodeRenderElement(self.report, offset_y, self), True

    def render_spreadsheet(self, row, col, ctx, renderer):
        if self.content:
            cell_format = dict()
            if self.spreadsheet_column:
                col = self.spreadsheet_column - 1
            renderer.write(row, col, self.spreadsheet_colspan, self.prepared_content, cell_format, self.width)
            row += 2 if self.spreadsheet_add_empty_row else 1
            col += 1
        return row, col


class LineElement(DocElement):
    def __init__(self, report, data):
        DocElement.__init__(self, report, data)
        self.color = Color(data.get('color'))
        self.print_if = get_str_value(data, 'printIf')

    def render_pdf(self, container_offset_x, container_offset_y, pdf_doc):
        pdf_doc.set_draw_color(self.color.r, self.color.g, self.color.b)
        pdf_doc.set_line_width(self.height)
        x = self.x + container_offset_x
        y = self.render_y + container_offset_y + (self.height / 2)
        pdf_doc.line(x, y, x + self.width, y)


class PageBreakElement(DocElementBase):
    def __init__(self, report, data):
        DocElementBase.__init__(self, report, data)
        self.id = get_int_value(data, 'id')
        self.print_if = get_str_value(data, 'printIf')
        self.x = 0
        self.width = 0
        self.sort_order = 0  # sort order for elements with same 'y'-value, render page break before other elements


class TextElement(DocElement):
    def __init__(self, report, data):
        DocElement.__init__(self, report, data)
        self.content = get_str_value(data, 'content')
        self.rich_text = bool(data.get('richText'))
        self.rich_text_content = data.get('richTextContent') or {}
        if self.rich_text and not isinstance(self.rich_text_content, dict):
            raise ReportBroInternalError(f'Invalid richTextContent for text element {self.id}')
        self.eval = bool(data.get('eval'))
        if data.get('styleId'):
            style = report.styles.get(get_int_value(data, 'styleId'))
            if style is None:
                raise ReportBroInternalError(f'Style for text element {self.id} not found')
            # shallow copy is sufficient in our case
            self.style = copy.copy(style)
        else:
            self.style = TextStyle(data)
        self.print_if = get_str_value(data, 'printIf')
        self.pattern = get_str_value(data, 'pattern')
        self.link = get_str_value(data, 'link')
        self.cs_condition = get_str_value(data, 'cs_condition')
        if self.cs_condition:
            if data.get('cs_styleId'):
                style = report.styles.get(int(data.get('cs_styleId')))
                if style is None:
                    raise ReportBroInternalError(f'Conditional style for text element {self.id} not found')
                # shallow copy is sufficient in our case
                self.conditional_style = copy.copy(style)
            else:
                self.conditional_style = TextStyle(data, key_prefix='cs_')
        else:
            self.conditional_style = None
        # additional styles are used when text is rendered inside table row and
        # the row has a background color -> a new style is created based on the
        # existing style
        self.additional_styles = dict()
        if isinstance(self, TableTextElement):
            self.remove_empty_element = False
            self.always_print_on_same_page = False
        else:
            self.remove_empty_element = bool(data.get('removeEmptyElement'))
            self.always_print_on_same_page = bool(data.get('alwaysPrintOnSamePage'))
        self.height = get_int_value(data, 'height')
        self.spreadsheet_hide = bool(data.get('spreadsheet_hide'))
        self.spreadsheet_column = get_int_value(data, 'spreadsheet_column')
        self.spreadsheet_colspan = get_int_value(data, 'spreadsheet_colspan')
        self.spreadsheet_add_empty_row = bool(data.get('spreadsheet_addEmptyRow'))
        self.spreadsheet_text_wrap = bool(data.get('spreadsheet_textWrap'))
        self.spreadsheet_formats = dict()  # caching of formats for rendering spreadsheet
        self.text_height = 0
        self.line_index = -1
        self.lines_count = 0
        self.text_lines = None
        self.used_style = None
        self.prepared_link = None
        self.space_top = 0
        self.space_bottom = 0
        self.total_height = 0
        self.spreadsheet_cell_format = None
        self.spreadsheet_cell_format_initialized = False

    def fill_parameters(self, ctx):
        return ctx.fill_parameters(self.content, self.id, field='content', pattern=self.pattern)

    def is_printed(self, ctx):
        if self.remove_empty_element and len(self.text_lines) == 0:
            return False
        return DocElementBase.is_printed(self, ctx)

    def prepare(self, ctx, pdf_doc, only_verify):
        if not self.rich_text:
            if self.eval:
                content = ctx.evaluate_expression(self.content, self.id, field='content')
                if self.pattern:
                    if isinstance(content, (int, float, decimal.Decimal)):
                        try:
                            content = format_decimal(content, self.pattern, locale=ctx.pattern_locale)
                            if self.pattern.find('$') != -1:
                                content = content.replace('$', ctx.pattern_currency_symbol)
                        except ValueError:
                            raise ReportBroError(
                                Error('errorMsgInvalidPattern', object_id=self.id, field='pattern', context=self.content))
                    elif isinstance(content, datetime.date):
                        try:
                            content = format_datetime(content, self.pattern, locale=ctx.pattern_locale)
                        except ValueError:
                            raise ReportBroError(
                                Error('errorMsgInvalidPattern', object_id=self.id, field='pattern', context=self.content))
                content = to_string(content)
            else:
                content = self.fill_parameters(ctx)

            if self.link:
                self.prepared_link = ctx.fill_parameters(self.link, self.id, field='link')
                if not (self.prepared_link.startswith('http://') or self.prepared_link.startswith('https://')):
                    raise ReportBroError(
                        Error('errorMsgInvalidLink', object_id=self.id, field='link'))
        else:
            content = None

        if self.cs_condition:
            if ctx.evaluate_expression(self.cs_condition, self.id, field='cs_condition'):
                self.used_style = self.conditional_style
            else:
                self.used_style = self.style
        else:
            self.used_style = self.style
        if self.used_style.vertical_alignment != VerticalAlignment.top and not self.always_print_on_same_page and\
                not isinstance(self, TableTextElement):
            self.always_print_on_same_page = True
        available_width = self.width - self.used_style.padding_left - self.used_style.padding_right

        self.text_lines = []
        if pdf_doc:
            self.split_text_lines(content, available_width=available_width, ctx=ctx, pdf_doc=pdf_doc)
            self.line_index = 0

            if isinstance(self, TableTextElement):
                self.total_height = max(
                    self.text_height + self.used_style.padding_top +
                    self.used_style.padding_bottom, self.height)
            else:
                self.set_height(self.height)
        else:
            # set text_lines so is_printed can check for empty element when rendering spreadsheet
            self.text_lines = [content] if content else []

    def get_style(self, style_id, background_color, base_style):
        if style_id in self.additional_styles:
            return self.additional_styles[style_id]
        # shallow copy is sufficient in our case
        style = copy.copy(base_style)
        style.id = style_id
        style.background_color = background_color
        self.additional_styles[style_id] = style
        return style

    def set_height(self, height):
        self.space_top = 0
        self.space_bottom = 0
        if self.text_height > 0:
            total_height = self.text_height + self.used_style.padding_top + self.used_style.padding_bottom
        else:
            total_height = 0
        if total_height < height:
            remaining_space = height - total_height
            if self.used_style.vertical_alignment == VerticalAlignment.top:
                self.space_bottom = remaining_space
            elif self.used_style.vertical_alignment == VerticalAlignment.middle:
                self.space_top = remaining_space / 2
                self.space_bottom = remaining_space / 2
            elif self.used_style.vertical_alignment == VerticalAlignment.bottom:
                self.space_top = remaining_space
        self.total_height = total_height + self.space_top + self.space_bottom

    def get_next_render_element(self, offset_y, container_top, container_height, ctx, pdf_doc):
        available_height = container_height - offset_y
        if self.always_print_on_same_page and self.first_render_element and\
                self.total_height > available_height and (offset_y != 0 or container_top != 0):
            return None, False

        lines = []
        remaining_height = available_height
        block_height = 0
        text_height = 0
        text_offset_y = 0
        if self.space_top > 0:
            space_top = min(self.space_top, remaining_height)
            self.space_top -= space_top
            block_height += space_top
            remaining_height -= space_top
            text_offset_y = space_top
        if self.space_top == 0:
            while self.line_index < self.lines_count:
                last_line = (self.line_index >= self.lines_count - 1)
                line_height = self.text_lines[self.line_index].height
                tmp_height = line_height
                if self.line_index == 0:
                    tmp_height += self.used_style.padding_top
                if  last_line:
                    tmp_height += self.used_style.padding_bottom
                if tmp_height > remaining_height:
                    break
                lines.append(self.text_lines[self.line_index])
                remaining_height -= tmp_height
                block_height += tmp_height
                text_height += line_height
                self.line_index += 1

        if self.line_index >= self.lines_count and self.space_bottom > 0:
            space_bottom = min(self.space_bottom, remaining_height)
            self.space_bottom -= space_bottom
            block_height += space_bottom
            remaining_height -= space_bottom

        if self.space_top == 0 and self.line_index == 0 and self.lines_count > 0:
            # even first line does not fit
            if offset_y != 0 or container_top != 0:
                # either container is not at top of page or element is not at top inside container
                # -> try on next page
                return None, False
            else:
                # already on top of container -> raise error
                raise ReportBroError(
                    Error('errorMsgInvalidSize', object_id=self.id, field='height'))

        rendering_complete = self.line_index >= self.lines_count and self.space_top == 0 and self.space_bottom == 0
        if not rendering_complete and remaining_height > 0:
            # draw text block until end of container
            block_height += remaining_height
            remaining_height = 0

        if self.first_render_element and rendering_complete:
            render_element_type = RenderElementType.complete
        else:
            if self.first_render_element:
                render_element_type = RenderElementType.first
            elif rendering_complete:
                render_element_type = RenderElementType.last
                if self.used_style.vertical_alignment == VerticalAlignment.bottom:
                    # make sure text is exactly aligned to bottom
                    tmp_offset_y = block_height - self.used_style.padding_bottom - text_height
                    if tmp_offset_y > 0:
                        text_offset_y = tmp_offset_y
            else:
                render_element_type = RenderElementType.between

        text_block_elem = TextBlockElement(
            self.report, x=self.x, y=self.y, render_y=offset_y,
            width=self.width, height=block_height, text_offset_y=text_offset_y,
            lines=lines, render_element_type=render_element_type, style=self.used_style)
        self.first_render_element = False
        self.render_bottom = text_block_elem.render_bottom
        self.rendering_complete = rendering_complete
        return text_block_elem, rendering_complete

    def is_first_render_element(self):
        return self.first_render_element

    def render_spreadsheet(self, row, col, ctx, renderer):
        cell_format = None
        if self.used_style.id not in self.spreadsheet_formats:
            format_props = dict()
            if self.used_style.bold:
                format_props['bold'] = True
            if self.used_style.italic:
                format_props['italic'] = True
            if self.used_style.underline:
                format_props['underline'] = True
            if self.used_style.strikethrough:
                format_props['font_strikeout'] = True
            if self.used_style.horizontal_alignment != HorizontalAlignment.left:
                format_props['align'] = self.used_style.horizontal_alignment.name
            if self.used_style.vertical_alignment != VerticalAlignment.top:
                if self.used_style.vertical_alignment == VerticalAlignment.middle:
                    format_props['valign'] = 'vcenter'
                else:
                    format_props['valign'] = self.used_style.vertical_alignment.name
            if not self.used_style.text_color.is_black():
                format_props['font_color'] = self.used_style.text_color.color_code
            if not self.used_style.background_color.transparent:
                format_props['bg_color'] = self.used_style.background_color.color_code
            if self.used_style.border_left or self.used_style.border_top or\
                    self.used_style.border_right or self.used_style.border_bottom:
                if not self.used_style.border_color.is_black():
                    format_props['border_color'] = self.used_style.border_color.color_code
                if self.used_style.border_left:
                    format_props['left'] = 1
                if self.used_style.border_top:
                    format_props['top'] = 1
                if self.used_style.border_right:
                    format_props['right'] = 1
                if self.used_style.border_bottom:
                    format_props['bottom'] = 1
            if self.spreadsheet_text_wrap:
                format_props['text_wrap'] = True
            if format_props:
                cell_format = renderer.add_format(format_props)
                self.spreadsheet_formats[self.used_style.id] = cell_format
        else:
            # use cached cell format which is already added to renderer
            cell_format = self.spreadsheet_formats[self.used_style.id]
        if self.spreadsheet_column:
            col = self.spreadsheet_column - 1
        content = self.get_spreadsheet_content()
        renderer.write(row, col, self.spreadsheet_colspan, content, cell_format,
                       self.width, url=self.prepared_link)
        if self.spreadsheet_add_empty_row:
            row += 1
        return row + 1, col + (self.spreadsheet_colspan if self.spreadsheet_colspan else 1)

    def get_spreadsheet_content(self):
        return self.text_lines[0] if self.text_lines else ''

    def set_font_by_style(self, style, pdf_doc):
        if not pdf_doc.set_font(
                style.font, style.font_style, style.font_size, underline=style.underline):
            error_field = style.key_prefix + 'font'
            raise ReportBroError(
                Error('errorMsgFontNotAvailable', object_id=self.id, field=error_field))

    def split_text_lines(self, content, available_width, ctx, pdf_doc):
        if content is not None:
            self.set_font_by_style(self.used_style, pdf_doc)
            try:
                lines = pdf_doc.split_text(first_w=available_width, w=available_width, txt=content)
            except UnicodeEncodeError:
                raise ReportBroError(
                    Error('errorMsgUnicodeEncodeError', object_id=self.id, field='content', context=self.content))
            for line in lines:
                text_line = TextLine(width=available_width, style=self.used_style, link=self.prepared_link)
                text, text_width, _ = line
                text_line.add_text(text, text_width, self.used_style)
                self.text_lines.append(text_line)
        else:
            if hasattr(self.__class__, 'split_rich_text_lines'):
                self.split_rich_text_lines(available_width, ctx, pdf_doc)
            else:
                raise ReportBroError(Error('errorMsgPlusVersionRequired', object_id=self.id, field='richText'))

        self.text_height = 0
        self.lines_count = len(self.text_lines)
        if self.lines_count > 0:
            self.text_lines[-1].last_line = True
            for text_line in self.text_lines:
                text_line.setup()
                self.text_height += text_line.height


class TextBlockElement(DocElementBase):
    def __init__(self, report, x, y, render_y, width, height, text_offset_y,
                 lines, render_element_type, style):
        DocElementBase.__init__(self, report, dict(y=y))
        self.x = x
        self.render_y = render_y
        self.render_bottom = render_y + height
        self.width = width
        self.height = height
        self.text_offset_y = text_offset_y
        self.lines = lines
        self.render_element_type = render_element_type
        self.style = style

    def render_pdf(self, container_offset_x, container_offset_y, pdf_doc):
        y = container_offset_y + self.render_y
        if not self.style.background_color.transparent:
            pdf_doc.set_fill_color(
                self.style.background_color.r, self.style.background_color.g, self.style.background_color.b)
            pdf_doc.rect(self.x + container_offset_x, y, self.width, self.height, style='F')
        if (self.style.border_left or self.style.border_top or
                self.style.border_right or self.style.border_bottom):
            DocElement.draw_border(
                x=self.x+container_offset_x, y=y, width=self.width, height=self.height,
                render_element_type=self.render_element_type, border_style=self.style, pdf_doc=pdf_doc)

        if self.render_element_type in (RenderElementType.complete, RenderElementType.first):
            y += self.style.padding_top
        y += self.text_offset_y

        if self.lines:
            self.lines[-1].last_line = True
            for line in self.lines:
                line.render_pdf(self.x + container_offset_x + self.style.padding_left, y, pdf_doc=pdf_doc)
                y += line.height


class TextLine(object):
    def __init__(self, width, style, link=None):
        self.available_width = width
        self.width = 0
        self.height = 0
        self.style = style
        self.link = link
        self.text = None
        self.last_line = False
        self.baseline_offset_y = 0

    def add_text(self, text, text_width, style, link=None):
        self.text = TextLinePart(text, text_width, style, link)

    def setup(self):
        self.width = self.text.width
        max_font_size = self.style.font_size
        self.baseline_offset_y = max_font_size * 0.8
        self.height = max_font_size if self.last_line else (max_font_size * self.style.line_spacing)

    def render_pdf(self, x, y, pdf_doc):
        offset_x = 0
        # last line of justified text is aligned left
        if self.style.horizontal_alignment != HorizontalAlignment.justify or self.last_line:
            if self.style.horizontal_alignment == HorizontalAlignment.center:
                offset_x = ((self.available_width - self.width) / 2)
            elif self.style.horizontal_alignment == HorizontalAlignment.right:
                offset_x = self.available_width - self.width
            render_x = x + offset_x
            render_y = y + self.baseline_offset_y

            pdf_doc.set_font(family=self.style.font, style=self.style.font_style,
                             size=self.style.font_size, underline=self.style.underline)
            pdf_doc.set_text_color(self.style.text_color.r, self.style.text_color.g, self.style.text_color.b)
            pdf_doc.text(render_x, render_y, self.text.text)
            if self.style.strikethrough:
                # use underline thickness
                strikethrough_thickness = pdf_doc.current_font['ut']
                render_line_y = render_y - self.style.font_size * 0.3
                strikethrough_width = strikethrough_thickness / 1000.0 * self.style.font_size
                pdf_doc.set_line_width(strikethrough_width)
                pdf_doc.set_draw_color(self.style.text_color.r, self.style.text_color.g, self.style.text_color.b)
                pdf_doc.line(render_x, render_line_y, render_x + self.text.width, render_line_y)
            if self.text.link:
                pdf_doc.link(render_x, y, self.text.width, self.style.font_size, self.text.link)
            render_x += self.text.width
        else:
            # justify text -> split text into words and use equal space between words
            words = []
            total_word_width = 0
            font_size = self.style.font_size

            pdf_doc.set_font(family=self.style.font, style=self.style.font_style,
                             size=font_size, underline=self.style.underline)
            pwords = self.text.text.split()
            for pword in pwords:
                tmp_width = pdf_doc.get_string_width(pword)
                total_word_width += tmp_width
                words.append((pword, tmp_width))

            word_count = len(words)
            spaces_count = word_count - 1
            word_spacing = ((self.available_width - total_word_width) / spaces_count) if spaces_count > 0 else 0
            render_y = y + self.baseline_offset_y

            # draw words with equal space between words
            pdf_doc.set_text_color(self.style.text_color.r, self.style.text_color.g, self.style.text_color.b)
            word_x = x
            for text, word_width in words:
                pdf_doc.text(word_x, render_y, text)
                word_x += word_width + word_spacing

            if self.style.strikethrough:
                line_position = pdf_doc.current_font['up']
                line_thickness = pdf_doc.current_font['ut']
                # strikethrough with an offset from baseline
                render_y = y + self.baseline_offset_y - font_size * 0.3
                line_width = line_thickness / 1000.0 * font_size
                pdf_doc.set_line_width(line_width)
                pdf_doc.set_draw_color(self.style.text_color.r, self.style.text_color.g, self.style.text_color.b)
                pdf_doc.line(x, render_y, x + self.available_width, render_y)

            if self.style.underline:
                line_position = pdf_doc.current_font['up']
                line_thickness = pdf_doc.current_font['ut']
                # underline needs offset for line position
                render_y = y + self.baseline_offset_y - (line_position / 1000.0 * font_size)
                line_width = line_thickness / 1000.0 * font_size
                pdf_doc.set_line_width(line_width)
                pdf_doc.set_draw_color(self.style.text_color.r, self.style.text_color.g, self.style.text_color.b)
                pdf_doc.line(x, render_y, x + self.available_width, render_y)

        if self.link:
            pdf_doc.link(x + offset_x, y, self.width, self.style.font_size, self.link)


class TextLinePart:
    def __init__(self, text, width, style, link):
        self.text = text
        self.width = width
        self.style = style
        self.link = link


class TableTextElement(TextElement):
    def __init__(self, report, data, simple_array_param=None, simple_array_item_index=-1):
        TextElement.__init__(self, report, data)
        self.colspan = get_int_value(data, 'colspan') if data.get('colspan') else 1
        # overwrite spreadsheet colspan with table cell colspan (spreadsheet colspan
        # cannot be set separately in a table cell)
        self.spreadsheet_colspan = self.colspan
        self.initial_width = self.width
        self.grow_weight = get_int_value(data, 'growWeight')
        # column can be hidden in case print_if condition is set in header and evaluates to False
        self.column_visible = True
        # a previous cell can have a colspan which includes this cell -> this cell is not shown
        self.inside_colspan = False
        self.simple_array_param = simple_array_param
        self.simple_array_item_index = simple_array_item_index
        self.data = data  # needed in case cell is expanded by simple_array parameter

    def expand_simple_array(self, printed_cells, ctx):
        if self.content and not self.eval and Context.is_parameter_name(self.content):
            param_ref = ctx.get_parameter(Context.strip_parameter_name(self.content))
            if param_ref:
                column_data_parameter = param_ref.parameter
                if column_data_parameter.type == ParameterType.simple_array:
                    cell_values, value_exists = ctx.get_parameter_data(param_ref)
                    if value_exists and cell_values and len(cell_values) > 0:
                        self.simple_array_param = column_data_parameter
                        self.simple_array_item_index = 0
                        for i in range(1, len(cell_values)):
                            expanded_cell = TableTextElement(
                                self.report, self.data,
                                simple_array_param=column_data_parameter, simple_array_item_index=i)
                            printed_cells.append(expanded_cell)

    def fill_parameters(self, ctx):
        if self.simple_array_param is not None:
            param_ref = ctx.get_parameter(self.simple_array_param.name)
            if param_ref:
                cell_values, value_exists = ctx.get_parameter_data(param_ref)
                if value_exists and self.simple_array_item_index < len(cell_values):
                    simple_array_item_value = cell_values[self.simple_array_item_index]
                    return ctx.get_formatted_value(
                        simple_array_item_value, self.simple_array_param, object_id=self.id, is_array_item=True)
        return TextElement.fill_parameters(self, ctx)

    def is_printed(self, ctx):
        return self.column_visible and not self.inside_colspan


class TableElement(DocElement):
    def __init__(self, report, data):
        DocElement.__init__(self, report, data)
        self.data_source = get_str_value(data, 'dataSource')
        self.columns = get_int_value(data, 'columns')
        self.header = None
        self.content_rows = []
        self.row_index_after_main_content = -1
        self.has_table_band_group = False
        self.footer = None
        self.data_source_parameter = None

        column_count = None
        if bool(data.get('header')):
            self.header = TableBandElement(report, data.get('headerData'), BandType.header)
            column_count = len(self.header.cells)
        content_data_rows = data.get('contentDataRows')
        assert isinstance(content_data_rows, list)
        main_content_created = False
        for idx, content_data_row in enumerate(content_data_rows):
            band_element = TableBandElement(
                report, content_data_row, BandType.content, before_group=not main_content_created)

            if band_element.group_expression:
                self.has_table_band_group = True
            if main_content_created:
                if self.row_index_after_main_content == -1 and band_element.group_expression:
                    self.row_index_after_main_content = idx
            else:
                if not band_element.group_expression:
                    main_content_created = True

            self.content_rows.append(band_element)
            if column_count is None:
                column_count = len(band_element.cells)
            else:
                assert column_count == len(band_element.cells)
        if bool(data.get('footer')):
            self.footer = TableBandElement(report, data.get('footerData'), BandType.footer)
            if column_count is not None:
                assert column_count == len(self.footer.cells)

        self.print_header = False
        self.print_footer = False
        self.border = Border[data.get('border')]
        self.border_color = Color(data.get('borderColor'))
        self.border_width = get_float_value(data, 'borderWidth')
        self.print_if = get_str_value(data, 'printIf')
        self.remove_empty_element = bool(data.get('removeEmptyElement'))
        self.spreadsheet_hide = bool(data.get('spreadsheet_hide'))
        self.spreadsheet_column = get_int_value(data, 'spreadsheet_column')
        self.spreadsheet_add_empty_row = bool(data.get('spreadsheet_addEmptyRow'))
        self.row_parameters = dict()
        self.rows = []
        self.row_count = 0
        self.row_index = -1
        self.content_row_index = -1
        self.width = 0  # width will be set in prepare method
        if self.header:
            self.height += self.header.height
        if self.footer:
            self.height += self.footer.height
        if len(self.content_rows) > 0:
            for content_row in self.content_rows:
                self.height += content_row.height
        self.bottom = self.y + self.height

    def prepare(self, ctx, pdf_doc, only_verify):
        if self.header:
            self.print_header = True
            free_space = 0  # space freed up by hidden columns
            total_weight = 0
            for column_idx, cell in enumerate(self.header.cells):
                if not cell.inside_colspan and cell.print_if:
                    cell.column_visible = ctx.evaluate_expression(
                        cell.print_if, cell.id, field='printIf')
                    if not cell.column_visible:
                        free_space += cell.width
                    for content_row in self.content_rows:
                        content_row.cells[column_idx].column_visible = cell.column_visible
                    if self.footer:
                        self.footer.cells[column_idx].column_visible = cell.column_visible
                if cell.column_visible:
                    total_weight += cell.grow_weight

            # there is free space (because of hidden columns) and growable columns exist
            # -> the free space is shared among the growable columns depending on
            # their grow weight
            if free_space > 0 and total_weight > 0:
                for column_idx, cell in enumerate(self.header.cells):
                    if cell.grow_weight > 0:
                        added_width = int((free_space / total_weight) * cell.grow_weight + 0.5)
                        cell.width = cell.initial_width + added_width
                        for content_row in self.content_rows:
                            content_row.cells[column_idx].width = cell.width
                        if self.footer:
                            self.footer.cells[column_idx].width = cell.width

        if self.footer:
            self.print_footer = True

        parameter_name = Context.strip_parameter_name(self.data_source)
        if parameter_name:
            param_ref = ctx.get_parameter(parameter_name)
            if param_ref is None:
                raise ReportBroError(
                    Error('errorMsgMissingParameter', object_id=self.id, field='dataSource'))
            self.data_source_parameter = param_ref.parameter
            if self.data_source_parameter.type != ParameterType.array:
                raise ReportBroError(
                    Error('errorMsgInvalidDataSourceParameter', object_id=self.id, field='dataSource'))
            for row_parameter in self.data_source_parameter.children:
                self.row_parameters[row_parameter.name] = row_parameter
            self.rows, parameter_exists = ctx.get_parameter_data(param_ref)
            if not parameter_exists:
                raise ReportBroError(
                    Error('errorMsgMissingData', object_id=self.id, field='dataSource'))
            if not isinstance(self.rows, list):
                raise ReportBroError(
                    Error('errorMsgInvalidDataSource', object_id=self.id, field='dataSource'))
        else:
            # there is no data source parameter so we create a static table (faked by one empty data row)
            self.rows = [dict()]
            self.data_source_parameter = None

        self.row_count = len(self.rows)
        self.row_index = 0
        self.content_row_index = 0

        self.width = 0
        table_width_initialized = False
        # expand cells if necessary (a cell with a simple_array parameter
        # will be expanded to multiple cells) for all table bands and set table width
        if self.header:
            self.header.set_printed_cells(ctx)
            self.header.prepare(ctx)
            for cell in self.header.printed_cells:
                self.width += cell.width
            table_width_initialized = True

        if self.row_index < self.row_count:
            ctx.push_context(self.row_parameters, self.rows[self.row_index])
            for content_row in self.content_rows:
                content_row.set_printed_cells(ctx)
                if not table_width_initialized and not content_row.group_expression:
                    for cell in content_row.printed_cells:
                        self.width += cell.width
                    table_width_initialized = True
            ctx.pop_context()

        self.init_group_rows(ctx=ctx)

        if only_verify:
            # call prepare for each content band in each row to verify
            # group and print-if expressions
            self.row_index = 0
            while self.row_index < self.row_count:
                # push data context of current row so values of current row can be accessed
                ctx.push_context(self.row_parameters, self.rows[self.row_index])
                for content_row in self.content_rows:
                    content_row.prepare(ctx=ctx, row_index=self.row_index)
                ctx.pop_context()
                self.row_index += 1

        if self.footer:
            self.footer.set_printed_cells(ctx)
            self.footer.prepare(ctx)

    def get_next_render_element(self, offset_y, container_top, container_height, ctx, pdf_doc):
        self.render_y = offset_y
        self.render_bottom = self.render_y
        if self.is_rendering_complete():
            self.rendering_complete = True
            return None, True
        render_element = TableRenderElement(self.report, table=self, render_y=offset_y)

        if self.print_header:
            if not self.header.rendering_complete:
                self.header.create_render_elements(offset_y, container_top, container_height, ctx, pdf_doc)
            render_element.add_band(self.header)
            if not self.header.rendering_complete:
                return render_element, False
            if not self.header.repeat_header:
                self.print_header = False

        first_render_row_index = self.row_index
        first_content_row_index = self.content_row_index
        first_row_on_page = True
        while self.row_index < self.row_count:
            # push data context of current row so values of current row can be accessed
            ctx.push_context(self.row_parameters, self.rows[self.row_index])
            self.content_row_index = 0
            for content_row in self.content_rows:
                # in case we are on the first row of the page we have to check if the content row
                # is visible (and not already displayed on previous page) or if it is a group content
                # row which is repeated on every page
                if not first_row_on_page or self.content_row_index >= first_content_row_index or\
                        content_row.repeat_group_header:
                    content_row.prepare(ctx=ctx, row_index=self.row_index)
                    if content_row.repeat_group_header and first_row_on_page:
                        # group content row is repeated on every page
                        content_row.group_changed = True

                    if content_row.is_printed(ctx=ctx):
                        # only perform page break before content if there is at least
                        # one rendered row
                        if content_row.page_break and content_row.before_group and\
                                self.row_index != first_render_row_index:
                            ctx.pop_context()
                            return render_element, False

                        content_row.set_parameter_range(parameter=self.data_source_parameter, ctx=ctx)

                        content_row.create_render_elements(
                            offset_y + render_element.height, container_top, container_height, ctx, pdf_doc)

                        content_row.set_parameter_range(parameter=self.data_source_parameter, ctx=ctx, clear=True)

                        render_element.add_band(content_row, row_index=self.row_index)
                        if not content_row.rendering_complete:
                            ctx.pop_context()
                            return render_element, False

                        # only perform page break after content if this is not the last row
                        if content_row.page_break and not content_row.before_group and\
                                self.row_index < (self.row_count - 1):
                            self.content_row_index += 1
                            ctx.pop_context()
                            return render_element, False
                    else:
                        content_row.rendering_complete = True

                content_row.update_group_changed_row_indices()

                self.content_row_index += 1
            ctx.pop_context()

            self.row_index += 1
            first_row_on_page = False

        if self.row_index >= self.row_count and self.print_footer:
            self.footer.create_render_elements(
                offset_y + render_element.height, container_top, container_height, ctx, pdf_doc)
            render_element.add_band(self.footer)
            if not self.footer.rendering_complete:
                return render_element, False
            self.print_footer = False

        if self.is_rendering_complete():
            self.rendering_complete = True

        if render_element.is_empty():
            return None, self.rendering_complete

        self.render_bottom = render_element.render_bottom
        return render_element, self.rendering_complete

    def init_group_rows(self, ctx):
        """
        Initialize table group bands (e.g. to show header or sums for grouped rows) and
        set row index when a group band is printed.

        :param ctx: current context
        """
        if self.has_table_band_group and self.row_count > 0:
            row_index = 0
            content_group_rows = []
            for content_row in self.content_rows:
                if content_row.group_expression:
                    content_row.group_changed_row_indices = []
                    content_group_rows.append(content_row)

            # set next group expr which is used for group expr of first row
            ctx.push_context(self.row_parameters, self.rows[row_index])
            for content_group_row in content_group_rows:
                content_group_row.set_next_group_expression(ctx)
            ctx.pop_context()

            while row_index < self.row_count:
                has_next = (row_index + 1) < self.row_count
                # set context for next row (if available) so group expr of next row can be evaluated
                if has_next:
                    ctx.push_context(self.row_parameters, self.rows[row_index + 1])
                for content_group_row in content_group_rows:
                    # set group expression for next row so the group expressions for previous, next and current
                    # row are available
                    content_group_row.set_next_group_expression(ctx, has_next=has_next)
                    # now test if the group expression (prev <-> current for group before content or
                    # current <-> next for group after content has changed)
                    content_group_row.test_group_changed(row_index)
                if has_next:
                    ctx.pop_context()
                row_index += 1

    def is_rendering_complete(self):
        # test if footer and all content rows are completely rendered
        if self.row_index >= self.row_count and not self.print_footer:
            # only test rendering_complete of bands if at least one row was processed
            # because otherwise the flag was not set
            if self.row_index > 0:
                for content_row in self.content_rows:
                    if not content_row.rendering_complete:
                        return False
            return True
        else:
            return False

    def render_spreadsheet(self, row, col, ctx, renderer):
        if self.spreadsheet_column:
            col = self.spreadsheet_column - 1
        columns = 0

        if self.header:
            columns = len(self.header.printed_cells)
            row, _ = self.header.render_spreadsheet(row, col, ctx, renderer)

        while self.row_index < self.row_count:
            # push data context of current row so values of current row can be accessed
            ctx.push_context(self.row_parameters, self.rows[self.row_index])
            for i, content_row in enumerate(self.content_rows):
                content_row.prepare(ctx=ctx, row_index=self.row_index)
                if content_row.is_printed(ctx=ctx):
                    if columns == 0:
                        # get column count from first printed content row if there is no header
                        columns = len(content_row.printed_cells)
                    row, _ = content_row.render_spreadsheet(
                        row, col, ctx, renderer, row_index=self.row_index)
            ctx.pop_context()
            self.row_index += 1

        if self.footer:
            row, _ = self.footer.render_spreadsheet(row, col, ctx, renderer)

        if self.spreadsheet_add_empty_row:
            row += 1
        return row, col + columns


class TableBandElement(object):
    def __init__(self, report, data, band_type, before_group=False):
        from .containers import Container
        assert(isinstance(data, dict))
        self.id = get_int_value(data, 'id')
        self.height = get_int_value(data, 'height')
        self.band_type = band_type
        if band_type == BandType.header:
            self.repeat_header = bool(data.get('repeatHeader'))
        else:
            self.repeat_header = None
        self.background_color = Color(data.get('backgroundColor'))
        self.group_expression = get_str_value(data, 'groupExpression')
        self.print_if = get_str_value(data, 'printIf')
        self.before_group = before_group
        self.page_break = False
        self.repeat_group_header = None
        if band_type == BandType.content:
            self.alternate_background_color = Color(data.get('alternateBackgroundColor'))
            self.always_print_on_same_page = bool(data.get('alwaysPrintOnSamePage'))
            if self.group_expression:
                self.page_break = bool(data.get('pageBreak'))
                self.repeat_group_header = bool(data.get('repeatGroupHeader'))
                if self.repeat_group_header and not before_group:
                    report.errors.append(Error(
                        'errorMsgRepeatGroupHeaderAfterContent', object_id=self.id, field='repeatGroupHeader'))
        else:
            self.alternate_background_color = None
            self.always_print_on_same_page = True
        self.cells = []  # cells created from initial data as defined in Designer
        self.print_if_result = True

        self.group_changed = False
        self.group_expr_result = None
        self.prev_group_expr_result = None
        self.next_group_expr_result = None
        self.group_changed_row_indices = []
        self.group_row_index_start = 0
        self.group_row_index_end = 0

        # cells which will be printed, this excludes cells within a colspan of another cells
        # and can include additional cells which get expanded by a cell
        # with a simple_list parameter
        self.printed_cells = []

        colspan_end_idx = 0
        colspan_element = None
        column_data = data.get('columnData')
        assert isinstance(column_data, list)
        for idx, column in enumerate(column_data):
            assert isinstance(column, dict)
            column['height'] = self.height  # set height of cell to band height
            cell = TableTextElement(report, column)
            if idx < colspan_end_idx:
                colspan_element.initial_width += cell.width
                colspan_element.width += cell.width
                cell.inside_colspan = True
            elif cell.colspan > 1:
                colspan_element = cell
                colspan_end_idx = idx + cell.colspan
            self.cells.append(cell)

        # create a virtual container for each table band
        self.container = Container(
            container_id='tablerow_' + str(self.id), containers=None, report=report)
        self.container.height = self.height
        self.container.allow_page_break = False
        self.rendering_complete = False
        self.prepare_container = True

    def set_printed_cells(self, ctx):
        """Initialize the printed cells.

        Cells can be expanded by a simple_list parameter into multiple cells. Cells can also
        be hidden be other cells with colspan set. Must be called exactly once for this band.

        :param ctx: current context
        """
        printed_cells = []
        for cell in self.cells:
            if cell.column_visible and not cell.inside_colspan:
                printed_cells.append(cell)
                cell.expand_simple_array(printed_cells, ctx)
        self.printed_cells = printed_cells
        table_width = 0
        for cell in printed_cells:
            cell.x = table_width
            table_width += cell.width
            self.container.add(cell)
        self.container.width = table_width

    def set_next_group_expression(self, ctx, has_next=True):
        """Evaluate group expression of next row and set group expression of
        previous and current row accordingly.

        :param ctx: context where parameters of next row are pushed.
        :param has_next: True if next row exists.
        """
        self.prev_group_expr_result = self.group_expr_result
        self.group_expr_result = self.next_group_expr_result
        if has_next:
            self.next_group_expr_result = ctx.evaluate_expression(
                self.group_expression, self.id, field='groupExpression')
        else:
            self.next_group_expr_result = None

    def test_group_changed(self, row_index):
        """
        Test if group expression changed and store the row_index if this is the case.

        :param row_index: current row index, group expression for previous, current and next row must
        be set before with :func:`~TableBandElement.set_next_group_expression`
        """
        if self.group_expression:
            if self.before_group:
                if self.group_expr_result != self.prev_group_expr_result:
                    self.group_changed_row_indices.append(row_index)
            else:
                if self.group_expr_result != self.next_group_expr_result:
                    self.group_changed_row_indices.append(row_index)

    def update_group_changed_row_indices(self):
        """
        The internal array of changed row indices for groups is updated in
        case a group row was currently rendered.

        Must be called after the row was processed.
        """
        if self.rendering_complete and self.group_changed:
            self.group_changed_row_indices.pop(0)

    def prepare(self, ctx, row_index=None):
        if self.group_expression:
            self.group_changed = False
            if self.group_changed_row_indices and self.group_changed_row_indices[0] == row_index:
                # the group expression has changed for this row index -> group band will be printed
                self.group_changed = True
                # now set index range which is used for function parameters like sum/avg
                if self.before_group:
                    self.group_row_index_start = self.group_changed_row_indices[0]
                    if len(self.group_changed_row_indices) > 1:
                        self.group_row_index_end = self.group_changed_row_indices[1]
                    else:
                        self.group_row_index_end = -1
                else:
                    self.group_row_index_start = self.group_row_index_end
                    self.group_row_index_end = self.group_changed_row_indices[0] + 1

        if self.print_if:
            self.print_if_result = ctx.evaluate_expression(
                self.print_if, self.id, field='printIf')

    def set_parameter_range(self, parameter, ctx, clear=False):
        """
        Set start and end row index for the given parameter which is used when evaluating a parameter
        function (e.g. sum or avg).

        :param parameter: data source parameter of table
        :param ctx: current context
        :param clear: if True the range will be removed for the parameter
        """
        if self.group_expression:
            if clear:
                parameter.clear_range()
                ctx.dec_range_count()
            else:
                parameter.set_range(self.group_row_index_start, self.group_row_index_end)
                ctx.inc_range_count()

    def is_printed(self, ctx):
        return self.print_if_result and (not self.group_expression or self.group_changed)

    def render_spreadsheet(self, row, col, ctx, renderer, row_index=-1):
        """Render table band in spreadsheet.

        This takes care of the background color and sets it for the row if there is a color.
        The spreadsheet is rendered by calling the method for every element in
        the table band container.
        """

        # elements in container must be prepared for each row before spreadsheet can be rendered
        self.container.prepare(ctx, pdf_doc=None)

        background_color = self.background_color
        if self.band_type == BandType.content and not self.alternate_background_color.transparent and\
                row_index % 2 == 1:
            background_color = self.alternate_background_color
            style_id_suffix = '_alt_table_row'
        else:
            style_id_suffix = '_table_row'

        if not background_color.transparent:
            for cell in self.container.doc_elements:
                if isinstance(cell, TableTextElement):
                    base_style = cell.used_style
                    cell.used_style = cell.get_style(
                        base_style.id + style_id_suffix, background_color, base_style)

        return self.container.render_spreadsheet(row, col, ctx, renderer)

    def create_render_elements(self, offset_y, container_top, container_height, ctx, pdf_doc):
        available_height = container_height - offset_y
        if self.always_print_on_same_page and available_height < self.height:
            # not enough space for whole band
            self.rendering_complete = False
        else:
            if self.prepare_container:
                self.container.prepare(ctx, pdf_doc)

                heights = [self.height]
                # get max height of all cells of this band
                for cell in self.container.doc_elements:
                    if isinstance(cell, TableTextElement):
                        heights.append(cell.total_height)
                # all cells will be set to max cell height
                max_height = max(heights)
                for cell in self.container.doc_elements:
                    if isinstance(cell, TableTextElement):
                        cell.set_height(max_height)
            else:
                # clear render elements from previous page
                self.container.clear_rendered_elements()

            self.rendering_complete = self.container.create_render_elements(
                container_top + offset_y, available_height, ctx=ctx, pdf_doc=pdf_doc)

        if self.rendering_complete:
            remaining_min_height = self.height - self.container.max_bottom
            if remaining_min_height > 0:
                # rendering of band complete, make sure band is at least as large
                # as minimum height (even if it spans over more than 1 page)
                if remaining_min_height <= available_height:
                    self.prepare_container = True
                    self.container.render_bottom += remaining_min_height
                else:
                    # minimum height is larger than available space, continue on next page
                    self.rendering_complete = False
                    self.prepare_container = False
                    self.container.render_bottom += available_height
            else:
                self.prepare_container = True
        else:
            if self.always_print_on_same_page:
                # band must be printed on same page but available space is not enough,
                # try to render it on top of next page
                self.prepare_container = True
                if offset_y == 0:
                    field = 'alwaysPrintOnSamePage' if self.band_type == BandType.content else 'size'
                    raise ReportBroError(
                        Error('errorMsgSectionBandNotOnSamePage', object_id=self.id, field=field))
            else:
                self.prepare_container = False

    def get_render_bottom(self):
        return self.container.render_bottom

    def get_render_elements(self):
        return self.container.render_elements


class FrameElement(DocElement):
    def __init__(self, report, data, containers):
        DocElement.__init__(self, report, data)
        from .containers import Frame
        self.background_color = Color(data.get('backgroundColor'))
        self.border_style = BorderStyle(data)
        self.print_if = get_str_value(data, 'printIf')
        self.remove_empty_element = bool(data.get('removeEmptyElement'))
        self.shrink_to_content_height = bool(data.get('shrinkToContentHeight'))
        self.spreadsheet_hide = bool(data.get('spreadsheet_hide'))
        self.spreadsheet_column = get_int_value(data, 'spreadsheet_column')
        self.spreadsheet_add_empty_row = bool(data.get('spreadsheet_addEmptyRow'))

        # rendering_complete status for next page, in case rendering was not started on first page.
        self.next_page_rendering_complete = False
        # container content height of previous page, in case rendering was not started on first page
        self.prev_page_content_height = 0

        self.render_element_type = RenderElementType.none
        self.container = Frame(
            width=self.width, height=self.height,
            container_id=str(data.get('linkedContainerId')), containers=containers, report=report)

    def get_render_bottom(self):
        height = self.container.render_bottom
        if self.border_style.border_top and self.render_element_type == RenderElementType.none:
            height += self.border_style.border_width
        if self.border_style.border_bottom:
            height += self.border_style.border_width
        if self.render_element_type == RenderElementType.none and not self.shrink_to_content_height:
            height = max(self.height, height)
        return height

    def prepare(self, ctx, pdf_doc, only_verify):
        self.container.prepare(ctx, pdf_doc=pdf_doc, only_verify=only_verify)
        self.next_page_rendering_complete = False
        self.prev_page_content_height = 0
        self.render_element_type = RenderElementType.none

    def get_next_render_element(self, offset_y, container_top, container_height, ctx, pdf_doc):
        self.render_y = offset_y
        available_height = container_height - offset_y
        content_height = container_height
        render_element = FrameRenderElement(self.report, self, render_y=offset_y)

        if self.border_style.border_top and self.render_element_type == RenderElementType.none:
            content_height -= self.border_style.border_width
        if self.border_style.border_bottom:
            # this is not 100% correct because bottom border is only applied if frame fits
            # on current page. this should be negligible because the border is usually only a few pixels
            # and most of the time the frame fits on one page.
            # to get the exact height in advance would be quite hard and is probably not worth the effort ...
            content_height -= self.border_style.border_width

        if self.first_render_element:
            self.first_render_element = False
            rendering_complete = self.container.create_render_elements(
                container_top + offset_y, content_height, ctx, pdf_doc)

            needed_height = self.get_render_bottom()

            if rendering_complete and needed_height <= available_height:
                # rendering is complete and all elements of frame fit on current page
                self.rendering_complete = True
                self.render_bottom = offset_y + needed_height
                self.render_element_type = RenderElementType.complete
                render_element.add_elements(self.container, self.render_element_type, needed_height)
                return render_element, True
            else:
                if offset_y == 0:
                    # rendering of frame elements does not fit on current page but
                    # we are already at the top of the page -> start rendering and continue on next page
                    self.render_bottom = offset_y + available_height
                    self.render_element_type = RenderElementType.first
                    render_element.add_elements(self.container, self.render_element_type, available_height)
                    return render_element, False
                else:
                    # rendering of frame elements does not fit on current page -> start rendering on next page
                    self.next_page_rendering_complete = rendering_complete
                    self.prev_page_content_height = content_height
                    return None, False

        if self.render_element_type == RenderElementType.none:
            # render elements were already created on first call to get_next_render_element
            # but elements did not fit on first page

            if content_height == self.prev_page_content_height:
                # we don't have to create any render elements here because we can use
                # the previously created elements

                self.rendering_complete = self.next_page_rendering_complete
            else:
                # we cannot use previously created render elements because container height is different
                # on current page. this should be very unlikely but could happen when the frame should be
                # printed on the first page and header/footer are not shown on first page, i.e. the following
                # pages have a different content band size than the first page.

                self.container.prepare(ctx, pdf_doc=pdf_doc)
                self.rendering_complete = self.container.create_render_elements(
                    container_top, content_height, ctx, pdf_doc)
        else:
            self.container.clear_rendered_elements()
            self.rendering_complete = self.container.create_render_elements(
                container_top, content_height, ctx, pdf_doc)
        self.render_bottom = offset_y + self.get_render_bottom()

        if not self.rendering_complete:
            # use whole size of container if frame is not rendered completely
            self.render_bottom = offset_y + container_height

            if self.render_element_type == RenderElementType.none:
                self.render_element_type = RenderElementType.first
            else:
                self.render_element_type = RenderElementType.between
        else:
            if self.render_element_type == RenderElementType.none:
                self.render_element_type = RenderElementType.complete
            else:
                self.render_element_type = RenderElementType.last
        render_element.add_elements(self.container, self.render_element_type, self.get_render_bottom())
        return render_element, self.rendering_complete

    def render_spreadsheet(self, row, col, ctx, renderer):
        if self.spreadsheet_column:
            col = self.spreadsheet_column - 1
        row, col = self.container.render_spreadsheet(row, col, ctx, renderer)
        if self.spreadsheet_add_empty_row:
            row += 1
        return row, col


class SectionBandElement(object):
    def __init__(self, report, data, band_type, containers):
        from .containers import Container
        assert(isinstance(data, dict))
        self.id = get_int_value(data, 'id')
        self.width = report.document_properties.page_width -\
            report.document_properties.margin_left - report.document_properties.margin_right
        self.height = get_int_value(data, 'height')
        self.band_type = band_type
        if band_type == BandType.header:
            self.repeat_header = bool(data.get('repeatHeader'))
            self.always_print_on_same_page = True
        else:
            self.repeat_header = None
            self.always_print_on_same_page = bool(data.get('alwaysPrintOnSamePage'))
        self.shrink_to_content_height = bool(data.get('shrinkToContentHeight'))

        self.container = Container(
            container_id=str(data.get('linkedContainerId')), containers=containers, report=report)
        self.container.width = self.width
        self.container.height = self.height
        if band_type != BandType.content:
            self.container.allow_page_break = False
        self.rendering_complete = False
        self.prepare_container = True

    def prepare(self, ctx, pdf_doc, only_verify):
        pass

    def create_render_elements(self, offset_y, container_top, container_height, ctx, pdf_doc):
        available_height = container_height - offset_y
        if self.always_print_on_same_page and not self.shrink_to_content_height and available_height < self.height:
            # not enough space for whole band
            self.rendering_complete = False
        else:
            if self.prepare_container:
                self.container.prepare(ctx, pdf_doc)
            else:
                # clear render elements from previous page
                self.container.clear_rendered_elements()
            self.rendering_complete = self.container.create_render_elements(
                container_top + offset_y, available_height, ctx=ctx, pdf_doc=pdf_doc)

            if self.container.manual_page_break and self.always_print_on_same_page:
                # a manual page break is not allowed if the whole content should be printed on the same page
                raise ReportBroError(
                    Error('errorMsgSectionBandPageBreakNotAllowed', object_id=self.id, field='alwaysPrintOnSamePage'))

        if self.rendering_complete:
            remaining_min_height = self.height - self.container.max_bottom
            if not self.shrink_to_content_height and remaining_min_height > 0:
                # rendering of band complete, make sure band is at least as large
                # as minimum height (even if it spans over more than 1 page)
                if remaining_min_height <= available_height:
                    self.prepare_container = True
                    self.container.render_bottom += remaining_min_height
                else:
                    # minimum height is larger than available space, continue on next page
                    self.rendering_complete = False
                    self.prepare_container = False
                    self.container.render_bottom += available_height
            else:
                self.prepare_container = True
        else:
            if self.always_print_on_same_page:
                # band must be printed on same page but available space is not enough,
                # try to render it on top of next page
                self.prepare_container = True
                if offset_y == 0:
                    field = 'size' if self.band_type == BandType.header else 'alwaysPrintOnSamePage'
                    raise ReportBroError(
                        Error('errorMsgSectionBandNotOnSamePage', object_id=self.id, field=field))
            else:
                self.prepare_container = False

    def get_render_bottom(self):
        return self.container.render_bottom

    def get_render_elements(self):
        return self.container.render_elements


class SectionElement(DocElement):
    def __init__(self, report, data, containers):
        DocElement.__init__(self, report, data)
        self.data_source = get_str_value(data, 'dataSource')
        self.print_if = get_str_value(data, 'printIf')
        self.spreadsheet_hide = False

        header = bool(data.get('header'))
        footer = bool(data.get('footer'))
        if header:
            self.header = SectionBandElement(report, data.get('headerData'), BandType.header, containers)
        else:
            self.header = None
        self.content = SectionBandElement(report, data.get('contentData'), BandType.content, containers)
        if footer:
            self.footer = SectionBandElement(report, data.get('footerData'), BandType.footer, containers)
        else:
            self.footer = None
        self.print_header = self.header is not None

        self.x = 0
        self.width = 0
        self.height = self.content.height
        if self.header:
            self.height += self.header.height
        if self.footer:
            self.height += self.footer.height
        self.bottom = self.y + self.height

        self.row_parameters = dict()
        self.rows = []
        self.row_count = 0
        self.row_index = -1

    def prepare(self, ctx, pdf_doc, only_verify):
        parameter_name = Context.strip_parameter_name(self.data_source)
        param_ref = ctx.get_parameter(parameter_name)
        if param_ref is None:
            raise ReportBroError(
                Error('errorMsgMissingDataSourceParameter', object_id=self.id, field='dataSource'))
        data_source_parameter = param_ref.parameter
        if data_source_parameter.type != ParameterType.array:
            raise ReportBroError(
                Error('errorMsgInvalidDataSourceParameter', object_id=self.id, field='dataSource'))
        for row_parameter in data_source_parameter.children:
            self.row_parameters[row_parameter.name] = row_parameter
        self.rows, parameter_exists = ctx.get_parameter_data(param_ref)
        if not parameter_exists:
            raise ReportBroError(
                Error('errorMsgMissingData', object_id=self.id, field='dataSource'))
        if not isinstance(self.rows, list):
            raise ReportBroError(
                Error('errorMsgInvalidDataSource', object_id=self.id, field='dataSource'))

        self.row_count = len(self.rows)
        self.row_index = 0

        if only_verify:
            if self.header:
                self.header.prepare(ctx, pdf_doc=None, only_verify=True)
            while self.row_index < self.row_count:
                # push data context of current row so values of current row can be accessed
                ctx.push_context(self.row_parameters, self.rows[self.row_index])
                self.content.prepare(ctx, pdf_doc=None, only_verify=True)
                ctx.pop_context()
                self.row_index += 1
            if self.footer:
                self.footer.prepare(ctx, pdf_doc=None, only_verify=True)

    def get_next_render_element(self, offset_y, container_top, container_height, ctx, pdf_doc):
        self.render_y = offset_y
        self.render_bottom = self.render_y
        render_element = SectionRenderElement(self.report, render_y=offset_y)

        if self.print_header:
            self.header.create_render_elements(offset_y, container_top, container_height, ctx, pdf_doc)
            render_element.add_section_band(self.header)
            if not self.header.rendering_complete:
                return render_element, False
            if not self.header.repeat_header:
                self.print_header = False

        while self.row_index < self.row_count:
            # push data context of current row so values of current row can be accessed
            ctx.push_context(self.row_parameters, self.rows[self.row_index])
            self.content.create_render_elements(
                offset_y + render_element.height, container_top, container_height, ctx, pdf_doc)
            ctx.pop_context()
            render_element.add_section_band(self.content)
            if not self.content.rendering_complete:
                return render_element, False
            self.row_index += 1

            page_break = self.content.container.manual_page_break
            self.content.container.reset()

            # in case of a manual page break inside content band (unless already in last row)
            # we stop rendering and start on new page
            if page_break and self.row_index < self.row_count:
                return render_element, False

        if self.footer:
            self.footer.create_render_elements(
                offset_y + render_element.height, container_top, container_height, ctx, pdf_doc)
            render_element.add_section_band(self.footer)
            if not self.footer.rendering_complete:
                return render_element, False

        # all bands finished
        self.rendering_complete = True
        self.render_bottom += render_element.height
        return render_element, True

    def render_spreadsheet(self, row, col, ctx, renderer):
        if self.header:
            self.header.container.prepare(ctx, pdf_doc=None)
            row, _ = self.header.container.render_spreadsheet(row, col, ctx, renderer)

        while self.row_index < self.row_count:
            # push data context of current row so values of current row can be accessed
            ctx.push_context(self.row_parameters, self.rows[self.row_index])
            self.content.container.prepare(ctx, pdf_doc=None)
            row, _ = self.content.container.render_spreadsheet(row, col, ctx, renderer)
            self.row_index += 1

        if self.footer:
            self.footer.container.prepare(ctx, pdf_doc=None)
            row, _ = self.footer.container.render_spreadsheet(row, col, ctx, renderer)
        return row, col
