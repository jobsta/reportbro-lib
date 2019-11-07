from __future__ import unicode_literals
from __future__ import division
from babel.numbers import format_decimal
from babel.dates import format_datetime
from io import BytesIO
from typing import List
import copy
import datetime
import decimal
import PIL
import tempfile

from .barcode128 import code128_image
from .context import Context
from .docelement import DocElementBase, DocElement
from .enums import *
from .errors import Error, ReportBroError
from .rendering import ImageRenderElement, BarCodeRenderElement, TableRenderElement, FrameRenderElement, SectionRenderElement
from .structs import Color, BorderStyle, TextStyle
from .utils import get_float_value, get_int_value, to_string, PY2, get_image_display_size

try:
    from urllib.request import urlopen  # For Python 3.0 and later
except ImportError:
    from urllib2 import urlopen  # Fall back to Python 2's urllib2

try:
    basestring  # For Python 2, str and unicode
except NameError:
    basestring = str


class ImageElement(DocElement):
    def __init__(self, report, data):
        DocElement.__init__(self, report, data)
        self.source = data.get('source', '')
        self.image = data.get('image', '')
        self.image_filename = data.get('imageFilename', '')
        self.horizontal_alignment = HorizontalAlignment[data.get('horizontalAlignment')]
        self.vertical_alignment = VerticalAlignment[data.get('verticalAlignment')]
        self.background_color = Color(data.get('backgroundColor'))
        self.print_if = data.get('printIf', '')
        self.remove_empty_element = bool(data.get('removeEmptyElement'))
        self.link = data.get('link', '')
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
                source_parameter = ctx.get_parameter(Context.strip_parameter_name(self.source))
                if source_parameter:
                    if source_parameter.type == ParameterType.string:
                        self.image_key, _ = ctx.get_data(source_parameter.name)
                    elif source_parameter.type == ParameterType.image:
                        self.image_key = self.source + '_' + str(ctx.get_context_id(source_parameter.name))
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

    def get_next_render_element(self, offset_y, container_height, ctx, pdf_doc):
        _, rv = DocElement.get_next_render_element(self, offset_y, container_height, ctx, pdf_doc)
        if not rv:
            return None, False
        return ImageRenderElement(self.report, offset_y, self), True

    def render_spreadsheet(self, row, col, ctx, renderer):
        if self.image_key:
            image = self.report.get_image(self.image_key)
            if self.spreadsheet_column:
                col = self.spreadsheet_column - 1

            try:
                raw_image = PIL.Image.open(image.image_fp)
            except Exception as ex:
                raise ReportBroError(
                    Error('errorMsgLoadingImageFailed', object_id=self.id,
                          field='source' if self.source else 'image', info=str(ex)))

            image_display_width, image_display_height = get_image_display_size(
                self.width, self.height, raw_image.width, raw_image.height)
            if image_display_width != raw_image.width or image_display_height != raw_image.height:
                raw_image = raw_image.resize(
                    (int(image_display_width), int(image_display_height)), PIL.Image.BILINEAR)
                image.image_fp = BytesIO()
                raw_image.save(image.image_fp, format='PNG' if image.image_type.upper() == 'PNG' else 'JPEG')

            renderer.insert_image(row, col, image_filename=self.image_filename, image_data=image.image_fp,
                                  width=self.width, url=self.prepared_link)
            row += 2 if self.spreadsheet_add_empty_row else 1
            col += 1
        return row, col


class BarCodeElement(DocElement):
    def __init__(self, report, data):
        DocElement.__init__(self, report, data)
        self.content = data.get('content', '')
        self.format = data.get('format', '').lower()
        assert self.format == 'code128'
        self.display_value = bool(data.get('displayValue'))
        self.print_if = data.get('printIf', '')
        self.remove_empty_element = bool(data.get('removeEmptyElement'))
        self.spreadsheet_hide = bool(data.get('spreadsheet_hide'))
        self.spreadsheet_column = get_int_value(data, 'spreadsheet_column')
        self.spreadsheet_colspan = get_int_value(data, 'spreadsheet_colspan')
        self.spreadsheet_add_empty_row = bool(data.get('spreadsheet_addEmptyRow'))
        self.image_key = None
        self.image_height = self.height - 22 if self.display_value else self.height
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
                img = code128_image(self.prepared_content, height=self.image_height, thickness=2, quiet_zone=False)
            except:
                raise ReportBroError(
                    Error('errorMsgInvalidBarCode', object_id=self.id, field='content'))
            if not only_verify:
                with tempfile.NamedTemporaryFile(delete=False, suffix='.png') as f:
                    img.save(f.name)
                    self.image_key = f.name
                    self.width = img.width

    def get_next_render_element(self, offset_y, container_height, ctx, pdf_doc):
        _, rv = DocElement.get_next_render_element(self, offset_y, container_height, ctx, pdf_doc)
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
        self.print_if = data.get('printIf', '')

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
        self.x = 0
        self.width = 0
        self.sort_order = 0  # sort order for elements with same 'y'-value, render page break before other elements


class TextElement(DocElement):
    def __init__(self, report, data):
        DocElement.__init__(self, report, data)
        self.content = data.get('content', '')
        self.eval = bool(data.get('eval'))
        if data.get('styleId'):
            style = report.styles.get(get_int_value(data, 'styleId'))
            if style is None:
                raise RuntimeError('Style for text element {id} not found'.format(id=self.id))
            # shallow copy is sufficient in our case
            self.style = copy.copy(style)
        else:
            self.style = TextStyle(data)
        self.print_if = data.get('printIf', '')
        self.pattern = data.get('pattern', '')
        self.link = data.get('link', '')
        self.cs_condition = data.get('cs_condition')
        if self.cs_condition:
            if data.get('cs_styleId'):
                style = report.styles.get(int(data.get('cs_styleId')))
                if style is None:
                    raise RuntimeError('Conditional style for text element {id} not found'.format(id=self.id))
                # shallow copy is sufficient in our case
                self.conditional_style = copy.copy(style)
            else:
                self.conditional_style = TextStyle(data, key_prefix='cs_')
        else:
            self.conditional_style = None
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
        self.text_height = 0
        self.line_index = -1
        self.line_height = 0
        self.lines_count = 0
        self.text_lines = None
        self.used_style = None
        self.prepared_link = None
        self.space_top = 0
        self.space_bottom = 0
        self.total_height = 0
        self.spreadsheet_cell_format = None
        self.spreadsheet_cell_format_initialized = False

    def is_printed(self, ctx):
        if self.remove_empty_element and len(self.text_lines) == 0:
            return False
        return DocElementBase.is_printed(self, ctx)

    def prepare(self, ctx, pdf_doc, only_verify):
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
            content = ctx.fill_parameters(self.content, self.id, field='content', pattern=self.pattern)

        if self.link:
            self.prepared_link = ctx.fill_parameters(self.link, self.id, field='link')
            if not (self.prepared_link.startswith('http://') or self.prepared_link.startswith('https://')):
                raise ReportBroError(
                    Error('errorMsgInvalidLink', object_id=self.id, field='link'))

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
            pdf_doc.set_font(self.used_style.font, self.used_style.font_style, self.used_style.font_size,
                    underline=self.used_style.underline)
            if content:
                try:
                    lines = pdf_doc.multi_cell(available_width, 0, content, align=self.used_style.text_align, split_only=True)
                except UnicodeEncodeError:
                    raise ReportBroError(
                        Error('errorMsgUnicodeEncodeError', object_id=self.id, field='content', context=self.content))
            else:
                lines = []
            self.line_height = self.used_style.font_size * self.used_style.line_spacing
            self.lines_count = len(lines)
            if self.lines_count > 0:
                self.text_height = (len(lines) - 1) * self.line_height + self.used_style.font_size
            self.line_index = 0
            for line in lines:
                self.text_lines.append(TextLine(line, width=available_width,
                                                style=self.used_style, link=self.prepared_link))
            if isinstance(self, TableTextElement):
                self.total_height = max(self.text_height +\
                        self.used_style.padding_top + self.used_style.padding_bottom, self.height)
            else:
                self.set_height(self.height)
        else:
            # set text_lines so is_printed can check for empty element when rendering spreadsheet
            self.text_lines = [content] if content else []

    def set_height(self, height):
        self.height = height
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

    def get_next_render_element(self, offset_y, container_height, ctx, pdf_doc):
        available_height = container_height - offset_y
        if self.always_print_on_same_page and self.first_render_element and\
                self.total_height > available_height and offset_y != 0:
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
            first_line = True
            while self.line_index < self.lines_count:
                last_line = (self.line_index >= self.lines_count - 1)
                line_height = self.used_style.font_size if first_line else self.line_height
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
                first_line = False

        if self.line_index >= self.lines_count and self.space_bottom > 0:
            space_bottom = min(self.space_bottom, remaining_height)
            self.space_bottom -= space_bottom
            block_height += space_bottom
            remaining_height -= space_bottom

        if self.space_top == 0 and self.line_index == 0 and self.lines_count > 0:
            # even first line does not fit
            if offset_y != 0:
                # try on next container
                return None, False
            else:
                # already on top of container -> raise error
                raise ReportBroError(
                    Error('errorMsgInvalidSize', object_id=self.id, field='size'))

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

        text_block_elem = TextBlockElement(self.report, x=self.x, y=self.y, render_y=offset_y,
                width=self.width, height=block_height, text_offset_y=text_offset_y,
                lines=lines, line_height=self.line_height,
                render_element_type=render_element_type, style=self.used_style)
        self.first_render_element = False
        self.render_bottom = text_block_elem.render_bottom
        self.rendering_complete = rendering_complete
        return text_block_elem, rendering_complete

    def is_first_render_element(self):
        return self.first_render_element

    def render_spreadsheet(self, row, col, ctx, renderer):
        cell_format = None
        if not self.spreadsheet_cell_format_initialized:
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
            if format_props:
                cell_format = renderer.add_format(format_props)
                if isinstance(self, TableTextElement):
                    # format can be used in following rows
                    self.spreadsheet_cell_format = cell_format
            self.spreadsheet_cell_format_initialized = True
        else:
            cell_format = self.spreadsheet_cell_format
        if self.spreadsheet_column:
            col = self.spreadsheet_column - 1
        content = self.text_lines[0] if self.text_lines else ''
        renderer.write(row, col, self.spreadsheet_colspan, content, cell_format,
                       self.width, url=self.prepared_link)
        if self.spreadsheet_add_empty_row:
            row += 1
        return row + 1, col + 1


class TextBlockElement(DocElementBase):
    def __init__(self, report, x, y, render_y, width, height, text_offset_y,
                lines, line_height, render_element_type, style):
        DocElementBase.__init__(self, report, dict(y=y))
        self.x = x
        self.render_y = render_y
        self.render_bottom = render_y + height
        self.width = width
        self.height = height
        self.text_offset_y = text_offset_y
        self.lines = lines
        self.line_height = line_height
        self.render_element_type = render_element_type
        self.style = style

    def render_pdf(self, container_offset_x, container_offset_y, pdf_doc):
        y = container_offset_y + self.render_y
        if not self.style.background_color.transparent:
            pdf_doc.set_fill_color(self.style.background_color.r, self.style.background_color.g,
                    self.style.background_color.b)
            pdf_doc.rect(self.x + container_offset_x, y, self.width, self.height, style='F')
        if (self.style.border_left or self.style.border_top or
                self.style.border_right or self.style.border_bottom):
            DocElement.draw_border(
                x=self.x+container_offset_x, y=y, width=self.width, height=self.height,
                render_element_type=self.render_element_type, border_style=self.style, pdf_doc=pdf_doc)

        if self.render_element_type in (RenderElementType.complete, RenderElementType.first):
            y += self.style.padding_top
        y += self.text_offset_y

        underline = self.style.underline
        last_line_index = len(self.lines) - 1
        # underline for justified text is drawn manually to have a single line for the
        # whole text. each word is rendered individually,
        # therefor we can't use the underline style of the rendered text
        if self.style.horizontal_alignment == HorizontalAlignment.justify and last_line_index > 0:
            underline = False
            pdf_doc.set_draw_color(self.style.text_color.r, self.style.text_color.g, self.style.text_color.b)
        pdf_doc.set_font(self.style.font, self.style.font_style, self.style.font_size, underline=underline)
        pdf_doc.set_text_color(self.style.text_color.r, self.style.text_color.g, self.style.text_color.b)

        for i, line in enumerate(self.lines):
            last_line = (i == last_line_index)
            line.render_pdf(self.x + container_offset_x + self.style.padding_left, y,
                            last_line=last_line, pdf_doc=pdf_doc)
            y += self.line_height


class TextLine(object):
    def __init__(self, text, width, style, link):
        self.text = text
        self.width = width
        self.style = style
        self.link = link

    def render_pdf(self, x, y, last_line, pdf_doc):
        render_y = y + self.style.font_size * 0.8
        line_width = None
        offset_x = 0
        if self.style.horizontal_alignment == HorizontalAlignment.justify:
            if last_line:
                pdf_doc.set_font(
                    self.style.font, self.style.font_style, self.style.font_size, underline=self.style.underline)
                pdf_doc.text(x, render_y, self.text)
            else:
                words = self.text.split()
                word_width = []
                total_word_width = 0
                for word in words:
                    tmp_width = pdf_doc.get_string_width(word)
                    word_width.append(tmp_width)
                    total_word_width += tmp_width
                count_spaces = len(words) - 1
                word_spacing = ((self.width - total_word_width) / count_spaces) if count_spaces > 0 else 0
                word_x = x
                pdf_doc.set_font(self.style.font, self.style.font_style, self.style.font_size, underline=False)
                for i, word in enumerate(words):
                    pdf_doc.text(word_x, render_y, word)
                    word_x += word_width[i] + word_spacing

                if self.style.underline:
                    if len(words) == 1:
                        text_width = word_width[0]
                    else:
                        text_width = self.width
                    underline_position = pdf_doc.current_font['up']
                    underline_thickness = pdf_doc.current_font['ut']
                    render_y += -underline_position / 1000.0 * self.style.font_size
                    underline_width = underline_thickness / 1000.0 * self.style.font_size
                    pdf_doc.set_line_width(underline_width)
                    pdf_doc.line(x, render_y, x + text_width, render_y)

                if len(words) > 1:
                    line_width = self.width
                elif len(words) > 0:
                    line_width = word_width[0]
        else:
            if self.style.horizontal_alignment != HorizontalAlignment.left:
                line_width = pdf_doc.get_string_width(self.text)
                space = self.width - line_width
                if self.style.horizontal_alignment == HorizontalAlignment.center:
                    offset_x = (space / 2)
                elif self.style.horizontal_alignment == HorizontalAlignment.right:
                    offset_x = space
            pdf_doc.text(x + offset_x, render_y, self.text)

        if self.style.strikethrough:
            if line_width is None:
                line_width = pdf_doc.get_string_width(self.text)
            # use underline thickness
            strikethrough_thickness = pdf_doc.current_font['ut']
            render_y = y + self.style.font_size * 0.5
            strikethrough_width = strikethrough_thickness / 1000.0 * self.style.font_size
            pdf_doc.set_line_width(strikethrough_width)
            pdf_doc.line(x + offset_x, render_y, x + offset_x + line_width, render_y)

        if self.link:
            if line_width is None:
                line_width = pdf_doc.get_string_width(self.text)
            pdf_doc.link(x + offset_x, y, line_width, self.style.font_size, self.link)


class TableTextElement(TextElement):
    def __init__(self, report, data):
        TextElement.__init__(self, report, data)
        self.colspan = get_int_value(data, 'colspan') if data.get('colspan') else 1
        # overwrite spreadsheet colspan with table cell colspan (spreadsheet colspan
        # cannot be set separately in a table cell)
        self.spreadsheet_colspan = self.colspan


class TableRow(object):
    def __init__(self, report, table_band, columns, ctx, prev_row=None):
        assert len(columns) <= len(table_band.column_data)
        self.column_data = []
        colspan_end_idx = 0
        colspan_element = None
        for idx, column in enumerate(columns):
            column_element = TableTextElement(report, table_band.column_data[column])
            if idx < colspan_end_idx:
                colspan_element.width += column_element.width
                continue

            self.column_data.append(column_element)
            if column_element.colspan > 1:
                colspan_element = column_element
                colspan_end_idx = idx + column_element.colspan

            if table_band.column_data[column].get('simple_array') != False:
                # in case value of column is a simple array parameter we create multiple columns,
                # one for each array entry of parameter data
                is_simple_array = False
                if column_element.content and not column_element.eval and\
                        Context.is_parameter_name(column_element.content):
                    column_data_parameter = ctx.get_parameter(Context.strip_parameter_name(column_element.content))
                    if column_data_parameter and column_data_parameter.type == ParameterType.simple_array:
                        is_simple_array = True
                        column_values, parameter_exists = ctx.get_data(column_data_parameter.name)
                        for idx, column_value in enumerate(column_values):
                            formatted_val = ctx.get_formatted_value(column_value, column_data_parameter,
                                                                    object_id=None, is_array_item=True)
                            if idx == 0:
                                column_element.content = formatted_val
                            else:
                                column_element = TableTextElement(report, table_band.column_data[column])
                                column_element.content = formatted_val
                                self.column_data.append(column_element)
                # store info if column content is a simple array parameter to
                # avoid checks for the next rows
                table_band.column_data[column]['simple_array'] = is_simple_array

        self.height = 0
        self.always_print_on_same_page = True
        self.table_band = table_band
        self.render_elements = []
        self.background_color = table_band.background_color
        self.alternate_background_color = table_band.background_color
        if table_band.band_type == BandType.content and not table_band.alternate_background_color.transparent:
            self.alternate_background_color = table_band.alternate_background_color
        self.group_expression = ''
        self.print_if_result = True
        self.prev_row = prev_row
        self.next_row = None
        if prev_row is not None:
            prev_row.next_row = self

    def is_printed(self, ctx):
        printed = self.print_if_result
        if printed and self.table_band.group_expression:
            if self.table_band.before_group:
                printed = self.prev_row is None or self.group_expression != self.prev_row.group_expression
            else:
                printed = self.next_row is None or self.group_expression != self.next_row.group_expression
        return printed

    def prepare(self, ctx, pdf_doc, row_index=-1, only_verify=False):
        if only_verify:
            for column_element in self.column_data:
                column_element.prepare(ctx, pdf_doc, only_verify=True)
        else:
            if self.table_band.group_expression:
                self.group_expression = ctx.evaluate_expression(
                    self.table_band.group_expression, self.table_band.id, field='group_expression')
            if self.table_band.print_if:
                self.print_if_result = ctx.evaluate_expression(
                    self.table_band.print_if, self.table_band.id, field='print_if')
            heights = [self.table_band.height]
            for column_element in self.column_data:
                column_element.prepare(ctx, pdf_doc, only_verify=False)
                heights.append(column_element.total_height)
                if row_index != -1 and row_index % 2 == 1:
                    background_color = self.alternate_background_color
                else:
                    background_color = self.background_color
                if not background_color.transparent and column_element.used_style.background_color.transparent:
                    column_element.used_style.background_color = background_color
            self.height = max(heights)
            for column_element in self.column_data:
                column_element.set_height(self.height)

    def create_render_elements(self, offset_y, container_height, ctx, pdf_doc):
        for column_element in self.column_data:
            render_element, _ = column_element.get_next_render_element(
                offset_y=offset_y, container_height=container_height, ctx=ctx, pdf_doc=pdf_doc)
            if render_element is None:
                raise RuntimeError('TableRow.create_render_elements failed - failed to create column render_element')
            self.render_elements.append(render_element)

    def render_pdf(self, container_offset_x, container_offset_y, pdf_doc):
        x = container_offset_x
        for render_element in self.render_elements:
            render_element.render_pdf(container_offset_x=x, container_offset_y=container_offset_y, pdf_doc=pdf_doc)
            x += render_element.width

    def render_spreadsheet(self, row, col, ctx, renderer):
        for column_element in self.column_data:
            column_element.render_spreadsheet(row, col, ctx, renderer)
            col += column_element.colspan
        return row + 1

    def verify(self, ctx):
        for column_element in self.column_data:
            column_element.verify(ctx)

    def get_width(self):
        width = 0
        for column_element in self.column_data:
            width += column_element.width
        return width

    def get_render_y(self):
        if self.render_elements:
            return self.render_elements[0].render_y
        return 0


class TableElement(DocElement):
    def __init__(self, report, data):
        DocElement.__init__(self, report, data)
        self.data_source = data.get('dataSource', '')
        self.columns = list(range(get_int_value(data, 'columns')))
        header = bool(data.get('header'))
        footer = bool(data.get('footer'))
        self.header = TableBandElement(data.get('headerData'), BandType.header) if header else None
        self.content_rows = []
        content_data_rows = data.get('contentDataRows')
        assert isinstance(content_data_rows, list)
        main_content_created = False
        for content_data_row in content_data_rows:
            band_element = TableBandElement(content_data_row, BandType.content,
                                            before_group=not main_content_created)
            if not main_content_created and not band_element.group_expression:
                main_content_created = True
            self.content_rows.append(band_element)
        self.footer = TableBandElement(data.get('footerData'), BandType.footer) if footer else None
        self.print_header = self.header is not None
        self.print_footer = self.footer is not None
        self.border = Border[data.get('border')]
        self.border_color = Color(data.get('borderColor'))
        self.border_width = get_float_value(data, 'borderWidth')
        self.print_if = data.get('printIf', '')
        self.remove_empty_element = bool(data.get('removeEmptyElement'))
        self.spreadsheet_hide = bool(data.get('spreadsheet_hide'))
        self.spreadsheet_column = get_int_value(data, 'spreadsheet_column')
        self.spreadsheet_add_empty_row = bool(data.get('spreadsheet_addEmptyRow'))
        self.data_source_parameter = None
        self.row_parameters = dict()
        self.rows = []
        self.row_count = 0
        self.row_index = -1
        self.prepared_rows = []  # type: List[TableRow]
        self.prev_content_rows = [None] * len(self.content_rows)  # type: List[TableRow]
        self.width = 0
        if self.header:
            self.height += self.header.height
        if self.footer:
            self.height += self.footer.height
        if len(self.content_rows) > 0:
            for content_row in self.content_rows:
                self.height += content_row.height
            for column in self.content_rows[0].column_data:
                self.width += column.get('width', 0)
        self.bottom = self.y + self.height
        self.first_render_element = True

    def prepare(self, ctx, pdf_doc, only_verify):
        if self.header:
            for column_idx, column in enumerate(self.header.column_data):
                if column.get('printIf'):
                    printed = ctx.evaluate_expression(column.get('printIf'), column.get('id'), field='print_if')
                    if not printed:
                        del self.columns[column_idx]
        parameter_name = Context.strip_parameter_name(self.data_source)
        self.data_source_parameter = None
        if parameter_name:
            self.data_source_parameter = ctx.get_parameter(parameter_name)
            if self.data_source_parameter is None:
                raise ReportBroError(
                    Error('errorMsgMissingParameter', object_id=self.id, field='data_source'))
            if self.data_source_parameter.type != ParameterType.array:
                raise ReportBroError(
                    Error('errorMsgInvalidDataSourceParameter', object_id=self.id, field='data_source'))
            for row_parameter in self.data_source_parameter.children:
                self.row_parameters[row_parameter.name] = row_parameter
            self.rows, parameter_exists = ctx.get_data(self.data_source_parameter.name)
            if not parameter_exists:
                raise ReportBroError(
                    Error('errorMsgMissingData', object_id=self.id, field='data_source'))
            if not isinstance(self.rows, list):
                raise ReportBroError(
                    Error('errorMsgInvalidDataSource', object_id=self.id, field='data_source'))
        else:
            # there is no data source parameter so we create a static table (faked by one empty data row)
            self.rows = [dict()]

        self.row_count = len(self.rows)
        self.row_index = 0
        self.row_number = 0

        if only_verify:
            if self.print_header:
                table_row = TableRow(self.report, self.header, self.columns, ctx=ctx)
                table_row.prepare(ctx, pdf_doc=None, only_verify=True)
            while self.row_index < self.row_count:
                # push data context of current row so values of current row can be accessed
                ctx.push_context(self.row_parameters, self.rows[self.row_index])
                for content_row in self.content_rows:
                    table_row = TableRow(self.report, content_row, self.columns, ctx=ctx)
                    table_row.prepare(ctx, pdf_doc=None, row_index=self.row_index, only_verify=True)
                ctx.pop_context()
                self.row_index += 1
            if self.print_footer:
                table_row = TableRow(self.report, self.footer, self.columns, ctx=ctx)
                table_row.prepare(ctx, pdf_doc=None, only_verify=True)

    def get_next_render_element(self, offset_y, container_height, ctx, pdf_doc):
        self.render_y = offset_y
        self.render_bottom = self.render_y
        if self.is_rendering_complete():
            self.rendering_complete = True
            return None, True
        render_element = TableRenderElement(self.report, self.x, self.width, offset_y, self)

        # batch size can be anything >= 3 because each row needs previous and next row to evaluate
        # group expression (in case it is set), the batch size defines the number of table rows
        # which will be prepared before they are rendered
        batch_size = 10
        remaining_batch_size = batch_size

        # add header in case it is not already available in prepared rows (from previous page)
        if self.print_header and (len(self.prepared_rows) == 0 or
                self.prepared_rows[0].table_band.band_type != BandType.header):
            table_row = TableRow(self.report, self.header, self.columns, ctx=ctx)
            table_row.prepare(ctx, pdf_doc)
            self.prepared_rows.insert(0, table_row)
            if not self.header.repeat_header:
                self.print_header = False

        while self.row_index < self.row_count:
            self.row_number += 1
            self.rows[self.row_index]['row_number'] = self.row_number
            # push data context of current row so values of current row can be accessed
            ctx.push_context(self.row_parameters, self.rows[self.row_index])

            for i, content_row in enumerate(self.content_rows):
                table_row = TableRow(self.report, content_row, self.columns,
                                     ctx=ctx, prev_row=self.prev_content_rows[i])
                table_row.prepare(ctx, pdf_doc, row_index=self.row_index)
                self.prepared_rows.append(table_row)
                self.prev_content_rows[i] = table_row
            ctx.pop_context()
            remaining_batch_size -= 1
            self.row_index += 1
            if remaining_batch_size == 0:
                remaining_batch_size = batch_size
                if self.row_index < self.row_count or not self.print_footer:
                    self.update_render_element(render_element, offset_y, container_height, ctx, pdf_doc)
                    if render_element.complete:
                        break

        if self.row_index >= self.row_count and self.print_footer:
            table_row = TableRow(self.report, self.footer, self.columns, ctx=ctx)
            table_row.prepare(ctx, pdf_doc)
            self.prepared_rows.append(table_row)
            self.print_footer = False

        self.update_render_element(render_element, offset_y, container_height, ctx, pdf_doc)

        if self.is_rendering_complete():
            self.rendering_complete = True

        if render_element.is_empty():
            return None, self.rendering_complete

        self.render_bottom = render_element.render_bottom
        self.first_render_element = False
        return render_element, self.rendering_complete

    def update_render_element(self, render_element, offset_y, container_height, ctx, pdf_doc):
        available_height = container_height - offset_y
        filtered_rows = []
        rows_for_next_update = []
        all_rows_processed = (self.row_index >= self.row_count)
        for prepared_row in self.prepared_rows:
            if prepared_row.table_band.band_type == BandType.content:
                if prepared_row.next_row is not None or all_rows_processed:
                    if prepared_row.is_printed(ctx):
                        filtered_rows.append(prepared_row)
                else:
                    rows_for_next_update.append(prepared_row)
            else:
                filtered_rows.append(prepared_row)

        while not render_element.complete and filtered_rows:
            add_row_count = 1
            if len(filtered_rows) >= 2 and\
                    (filtered_rows[0].table_band.band_type == BandType.header or
                     filtered_rows[-1].table_band.band_type == BandType.footer):
                # make sure header row is not printed alone on a page
                add_row_count = 2
            # allow splitting multiple rows (header + content or footer) in case we are already at top
            # of the container and there is not enough space for both rows
            allow_split = (offset_y == 0)
            height = available_height - render_element.height
            rows_added = render_element.add_rows(
                filtered_rows[:add_row_count], allow_split=allow_split,
                available_height=height, offset_y=offset_y, container_height=container_height,
                ctx=ctx, pdf_doc=pdf_doc)
            if rows_added == 0:
                break
            filtered_rows = filtered_rows[rows_added:]
            self.first_render_element = False

        self.prepared_rows = filtered_rows
        self.prepared_rows.extend(rows_for_next_update)

    def is_rendering_complete(self):
        return (not self.print_header or (self.header and self.header.repeat_header)) and\
               not self.print_footer and self.row_index >= self.row_count and len(self.prepared_rows) == 0

    def render_spreadsheet(self, row, col, ctx, renderer):
        if self.spreadsheet_column:
            col = self.spreadsheet_column - 1

        if self.print_header:
            table_row = TableRow(self.report, self.header, self.columns, ctx=ctx)
            table_row.prepare(ctx, pdf_doc=None)
            if table_row.is_printed(ctx):
                row = table_row.render_spreadsheet(row, col, ctx, renderer)

        data_context_added = False
        while self.row_index < self.row_count:
            # push data context of current row so values of current row can be accessed
            if data_context_added:
                ctx.pop_context()
            else:
                data_context_added = True
            ctx.push_context(self.row_parameters, self.rows[self.row_index])

            for i, content_row in enumerate(self.content_rows):
                table_row = TableRow(
                    self.report, content_row, self.columns, ctx=ctx, prev_row=self.prev_content_rows[i])
                table_row.prepare(ctx, pdf_doc=None, row_index=self.row_index)
                # render rows from previous preparation because we need next row set (used for group_expression)
                if self.prev_content_rows[i] is not None and self.prev_content_rows[i].is_printed(ctx):
                    row = self.prev_content_rows[i].render_spreadsheet(row, col, ctx, renderer)

                self.prev_content_rows[i] = table_row
            self.row_index += 1
        if data_context_added:
            ctx.pop_context()

        for i, prev_content_row in enumerate(self.prev_content_rows):
            if self.prev_content_rows[i] is not None and self.prev_content_rows[i].is_printed(ctx):
                row = self.prev_content_rows[i].render_spreadsheet(row, col, ctx, renderer)

        if self.print_footer:
            table_row = TableRow(self.report, self.footer, self.columns, ctx=ctx)
            table_row.prepare(ctx, pdf_doc=None)
            if table_row.is_printed(ctx):
                row = table_row.render_spreadsheet(row, col, ctx, renderer)

        if self.spreadsheet_add_empty_row:
            row += 1
        return row, col + self.get_column_count()

    def get_column_count(self):
        return len(self.columns)


class TableBandElement(object):
    def __init__(self, data, band_type, before_group=False):
        self.id = data.get('id', '')
        self.height = get_int_value(data, 'height')
        self.band_type = band_type
        if band_type == BandType.header:
            self.repeat_header = bool(data.get('repeatHeader'))
        else:
            self.repeat_header = None
        self.background_color = Color(data.get('backgroundColor'))
        if band_type == BandType.content:
            self.alternate_background_color = Color(data.get('alternateBackgroundColor'))
        else:
            self.alternate_background_color = None
        self.column_data = data.get('columnData')
        self.group_expression = data.get('groupExpression', '')
        self.print_if = data.get('printIf', '')
        self.before_group = before_group
        assert isinstance(self.column_data, list)


class FrameElement(DocElement):
    def __init__(self, report, data, containers):
        DocElement.__init__(self, report, data)
        from .containers import Frame
        self.background_color = Color(data.get('backgroundColor'))
        self.border_style = BorderStyle(data)
        self.print_if = data.get('printIf', '')
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

    def get_used_height(self):
        height = self.container.get_render_elements_bottom()
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

    def get_next_render_element(self, offset_y, container_height, ctx, pdf_doc):
        self.render_y = offset_y
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
            available_height = container_height - offset_y
            self.first_render_element = False
            rendering_complete = self.container.create_render_elements(
                content_height, ctx, pdf_doc)

            needed_height = self.get_used_height()

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
                self.rendering_complete = self.container.create_render_elements(content_height, ctx, pdf_doc)
        else:
            self.rendering_complete = self.container.create_render_elements(content_height, ctx, pdf_doc)
        self.render_bottom = offset_y + self.get_used_height()

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
        render_element.add_elements(self.container, self.render_element_type, self.get_used_height())
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
        self.id = data.get('id', '')
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
        self.container.allow_page_break = False
        self.rendering_complete = False
        self.prepare_container = True
        self.rendered_band_height = 0

    def prepare(self, ctx, pdf_doc, only_verify):
        pass

    def create_render_elements(self, offset_y, container_height, ctx, pdf_doc):
        available_height = container_height - offset_y
        if self.always_print_on_same_page and not self.shrink_to_content_height and\
                (container_height - offset_y) < self.height:
            # not enough space for whole band
            self.rendering_complete = False
        else:
            if self.prepare_container:
                self.container.prepare(ctx, pdf_doc)
                self.rendered_band_height = 0
            else:
                self.rendered_band_height += self.container.used_band_height
                # clear render elements from previous page
                self.container.clear_rendered_elements()
            self.rendering_complete = self.container.create_render_elements(available_height, ctx=ctx, pdf_doc=pdf_doc)

        if self.rendering_complete:
            remaining_min_height = self.height - self.rendered_band_height
            if not self.shrink_to_content_height and self.container.used_band_height < remaining_min_height:
                # rendering of band complete, make sure band is at least as large
                # as minimum height (even if it spans over more than 1 page)
                if remaining_min_height <= available_height:
                    self.prepare_container = True
                    self.container.used_band_height = remaining_min_height
                else:
                    # minimum height is larger than available space, continue on next page
                    self.rendering_complete = False
                    self.prepare_container = False
                    self.container.used_band_height = available_height
            else:
                self.prepare_container = True
        else:
            if self.always_print_on_same_page:
                # band must be printed on same page but available space is not enough,
                # try to render it on top of next page
                self.prepare_container = True
                if offset_y == 0:
                    field = 'size' if self.band_type == BandType.header else 'always_print_on_same_page'
                    raise ReportBroError(
                        Error('errorMsgSectionBandNotOnSamePage', object_id=self.id, field=field))
            else:
                self.prepare_container = False
                self.container.first_element_offset_y = available_height
                self.container.used_band_height = available_height

    def get_used_band_height(self):
        return self.container.used_band_height

    def get_render_elements(self):
        return self.container.render_elements


class SectionElement(DocElement):
    def __init__(self, report, data, containers):
        DocElement.__init__(self, report, data)
        self.data_source = data.get('dataSource', '')
        self.print_if = data.get('printIf', '')
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

        self.data_source_parameter = None
        self.row_parameters = dict()
        self.rows = []
        self.row_count = 0
        self.row_index = -1
        self.row_number = 0

    def prepare(self, ctx, pdf_doc, only_verify):
        parameter_name = Context.strip_parameter_name(self.data_source)
        self.data_source_parameter = ctx.get_parameter(parameter_name)
        if not self.data_source_parameter:
            raise ReportBroError(
                Error('errorMsgMissingDataSourceParameter', object_id=self.id, field='data_source'))
        if self.data_source_parameter.type != ParameterType.array:
            raise ReportBroError(
                Error('errorMsgInvalidDataSourceParameter', object_id=self.id, field='data_source'))
        for row_parameter in self.data_source_parameter.children:
            self.row_parameters[row_parameter.name] = row_parameter
        self.rows, parameter_exists = ctx.get_data(self.data_source_parameter.name)
        if not parameter_exists:
            raise ReportBroError(
                Error('errorMsgMissingData', object_id=self.id, field='data_source'))
        if not isinstance(self.rows, list):
            raise ReportBroError(
                Error('errorMsgInvalidDataSource', object_id=self.id, field='data_source'))

        self.row_count = len(self.rows)
        self.row_index = 0

        if only_verify:
            if self.header:
                self.header.prepare(ctx, pdf_doc=None, only_verify=True)
            while self.row_index < self.row_count:
                self.row_number += 1
                self.rows[self.row_index]['row_number'] = self.row_number
                # push data context of current row so values of current row can be accessed
                ctx.push_context(self.row_parameters, self.rows[self.row_index])
                self.content.prepare(ctx, pdf_doc=None, only_verify=True)
                ctx.pop_context()
                self.row_index += 1
            if self.footer:
                self.footer.prepare(ctx, pdf_doc=None, only_verify=True)

    def get_next_render_element(self, offset_y, container_height, ctx, pdf_doc):
        self.render_y = offset_y
        self.render_bottom = self.render_y
        render_element = SectionRenderElement(self.report, render_y=offset_y)

        if self.print_header:
            self.header.create_render_elements(offset_y, container_height, ctx, pdf_doc)
            render_element.add_section_band(self.header)
            if not self.header.rendering_complete:
                return render_element, False
            if not self.header.repeat_header:
                self.print_header = False

        while self.row_index < self.row_count:
            self.row_number += 1
            self.rows[self.row_index]['row_number'] = self.row_number
            # push data context of current row so values of current row can be accessed
            ctx.push_context(self.row_parameters, self.rows[self.row_index])
            self.content.create_render_elements(offset_y + render_element.height, container_height, ctx, pdf_doc)
            ctx.pop_context()
            render_element.add_section_band(self.content)
            if not self.content.rendering_complete:
                return render_element, False
            self.row_index += 1

        if self.footer:
            self.footer.create_render_elements(offset_y + render_element.height, container_height, ctx, pdf_doc)
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
            self.row_number += 1
            self.rows[self.row_index]['row_number'] = self.row_number
            # push data context of current row so values of current row can be accessed
            ctx.push_context(self.row_parameters, self.rows[self.row_index])
            self.content.container.prepare(ctx, pdf_doc=None)
            row, _ = self.content.container.render_spreadsheet(row, col, ctx, renderer)
            self.row_index += 1

        if self.footer:
            self.footer.container.prepare(ctx, pdf_doc=None)
            row, _ = self.footer.container.render_spreadsheet(row, col, ctx, renderer)
        return row, col
