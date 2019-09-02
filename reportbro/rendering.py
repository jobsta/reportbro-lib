from __future__ import division
from .docelement import DocElementBase, DocElement
from .enums import *
from .errors import Error, ReportBroError
from .utils import get_image_display_size
import os


class ImageRenderElement(DocElementBase):
    def __init__(self, report, render_y, image):
        DocElementBase.__init__(self, report, dict(y=0))
        self.report = report
        self.x = image.x
        self.width = image.width
        self.height = image.height
        self.render_y = render_y
        self.render_bottom = render_y
        self.background_color = image.background_color
        self.horizontal_alignment = image.horizontal_alignment
        self.vertical_alignment = image.vertical_alignment
        self.prepared_link = image.prepared_link
        self.source = image.source
        self.image_filename = image.image_filename
        self.image_key = image.image_key

    def render_pdf(self, container_offset_x, container_offset_y, pdf_doc):
        x = self.x + container_offset_x
        y = self.render_y + container_offset_y
        if not self.background_color.transparent:
            pdf_doc.set_fill_color(self.background_color.r, self.background_color.g, self.background_color.b)
            pdf_doc.rect(x, y, self.width, self.height, 'F')
        if self.image_key:
            image = self.report.get_image(self.image_key)
            if image and image.image_fp:
                halign = {HorizontalAlignment.left: 'L', HorizontalAlignment.center: 'C',
                        HorizontalAlignment.right: 'R'}.get(self.horizontal_alignment)
                valign = {VerticalAlignment.top: 'T', VerticalAlignment.middle: 'C',
                        VerticalAlignment.bottom: 'B'}.get(self.vertical_alignment)
                try:
                    image_info = pdf_doc.image(
                        self.image_key, x, y, self.width, self.height, type=image.image_type,
                        image_fp=image.image_fp, halign=halign, valign=valign)
                except Exception as ex:
                    raise ReportBroError(
                        Error('errorMsgLoadingImageFailed', object_id=self.id,
                              field='source' if self.source else 'image', info=str(ex)))

                if self.prepared_link:
                    # horizontal and vertical alignment of image within given width and height
                    # by keeping original image aspect ratio
                    offset_x = offset_y = 0
                    image_display_width, image_display_height = get_image_display_size(
                        self.width, self.height, image_info['w'], image_info['h'])
                    if self.horizontal_alignment == HorizontalAlignment.center:
                        offset_x = (self.width - image_display_width) / 2
                    elif self.horizontal_alignment == HorizontalAlignment.right:
                        offset_x = self.width - image_display_width
                    if self.vertical_alignment == VerticalAlignment.middle:
                        offset_y = (self.height - image_display_height) / 2
                    elif self.vertical_alignment == VerticalAlignment.bottom:
                        offset_y = self.height - image_display_height

                    pdf_doc.link(x + offset_x, y + offset_y,
                                 image_display_width, image_display_height, self.prepared_link)


class BarCodeRenderElement(DocElementBase):
    def __init__(self, report, render_y, barcode):
        DocElementBase.__init__(self, report, dict(y=0))
        self.report = report
        self.x = barcode.x
        self.width = barcode.width
        self.height = barcode.height
        self.render_y = render_y
        self.render_bottom = render_y
        self.content = barcode.prepared_content
        self.display_value = barcode.display_value
        self.image_key = barcode.image_key
        self.image_height = barcode.image_height

    def render_pdf(self, container_offset_x, container_offset_y, pdf_doc):
        x = self.x + container_offset_x
        y = self.render_y + container_offset_y
        if self.image_key:
            pdf_doc.image(self.image_key, x, y, self.width, self.image_height)
            if self.display_value:
                pdf_doc.set_font('courier', 'B', 18)
                pdf_doc.set_text_color(0, 0, 0)
                content_width = pdf_doc.get_string_width(self.content)
                offset_x = (self.width - content_width) / 2
                pdf_doc.text(x + offset_x, y + self.image_height + 20, self.content)

    def cleanup(self):
        if self.image_key:
            os.unlink(self.image_key)
            self.image_key = None


class TableRenderElement(DocElementBase):
    def __init__(self, report, x, width, render_y, table):
        DocElementBase.__init__(self, report, dict(y=0))
        self.report = report
        self.x = x
        self.width = width
        self.render_y = render_y
        self.render_bottom = render_y
        self.table = table
        self.rows = []
        self.complete = False

    def add_rows(self, rows, allow_split, available_height, offset_y, container_height, ctx, pdf_doc):
        rows_added = 0
        if not self.complete:
            if not allow_split:
                height = 0
                for row in rows:
                    height += row.height
                if height <= available_height:
                    for row in rows:
                        row.create_render_elements(offset_y=offset_y, container_height=container_height,
                                ctx=ctx, pdf_doc=pdf_doc)
                    self.rows.extend(rows)
                    rows_added = len(rows)
                    available_height -= height
                    self.height += height
                    self.render_bottom += height
                else:
                    self.complete = True
            else:
                for row in rows:
                    if row.height <= available_height:
                        row.create_render_elements(offset_y=offset_y, container_height=container_height,
                                ctx=ctx, pdf_doc=pdf_doc)
                        self.rows.append(row)
                        rows_added += 1
                        available_height -= row.height
                        self.height += row.height
                        self.render_bottom += row.height
                    else:
                        self.complete = True
                        break
        return rows_added

    def is_empty(self):
        return len(self.rows) == 0

    def render_pdf(self, container_offset_x, container_offset_y, pdf_doc):
        y = container_offset_y
        for row in self.rows:
            row.render_pdf(container_offset_x=container_offset_x + self.x, container_offset_y=y, pdf_doc=pdf_doc)
            y += row.height

        if self.rows and self.table.border != Border.none:
            pdf_doc.set_draw_color(self.table.border_color.r, self.table.border_color.g, self.table.border_color.b)
            pdf_doc.set_line_width(self.table.border_width)
            half_border_width = self.table.border_width / 2
            x1 = container_offset_x + self.x
            x2 = x1 + self.rows[0].get_width()
            x1 += half_border_width
            x2 -= half_border_width
            y1 = self.rows[0].get_render_y() + container_offset_y
            y2 = y1 + (y - container_offset_y)
            if self.table.border in (Border.grid, Border.frame_row, Border.frame):
                pdf_doc.line(x1, y1, x1, y2)
                pdf_doc.line(x2, y1, x2, y2)
            y = y1
            pdf_doc.line(x1, y1, x2, y1)
            if self.table.border != Border.frame:
                for row in self.rows[:-1]:
                    y += row.height
                    pdf_doc.line(x1, y, x2, y)
            pdf_doc.line(x1, y2, x2, y2)
            if self.table.border == Border.grid:
                columns = self.rows[0].column_data
                # add half border_width so border is drawn inside right column and can be aligned with
                # borders of other elements outside the table
                x = x1
                y2 = y1 + self.rows[0].height

                # rows can have different columns (colspan) than other rows so
                # we draw column borders separately if necessary
                for row in self.rows[1:]:
                    current_columns = row.column_data
                    same_borders = True
                    if len(columns) == len(current_columns):
                        for (col1, col2) in zip(columns, current_columns):
                            if col1.width != col2.width:
                                same_borders = False
                                break
                    else:
                        same_borders = False
                    if not same_borders:
                        x = x1
                        for column in columns[:-1]:
                            x += column.width
                            pdf_doc.line(x, y1, x, y2)
                        y1 = y2
                        x = x1
                        columns = current_columns
                    y2 += row.height

                for column in columns[:-1]:
                    x += column.width
                    pdf_doc.line(x, y1, x, y2)


class FrameRenderElement(DocElementBase):
    def __init__(self, report, frame, render_y):
        DocElementBase.__init__(self, report, dict(y=0))
        self.report = report
        self.x = frame.x
        self.width = frame.width
        self.border_style = frame.border_style
        self.background_color = frame.background_color
        self.render_y = render_y
        self.render_bottom = render_y
        self.height = 0
        self.elements = []
        self.render_element_type = RenderElementType.none
        self.complete = False

    def add_elements(self, container, render_element_type, height):
        self.elements = list(container.render_elements)
        self.render_element_type = render_element_type
        self.render_bottom += height

    def render_pdf(self, container_offset_x, container_offset_y, pdf_doc):
        x = self.x + container_offset_x
        y = self.render_y + container_offset_y
        height = self.render_bottom - self.render_y

        content_x = x
        content_width = self.width
        content_y = y
        content_height = height

        if self.border_style.border_left:
            content_x += self.border_style.border_width
            content_width -= self.border_style.border_width
        if self.border_style.border_right:
            content_width -= self.border_style.border_width
        if self.border_style.border_top and\
                self.render_element_type in (RenderElementType.first, RenderElementType.complete):
            content_y += self.border_style.border_width
            content_height -= self.border_style.border_width
        if self.border_style.border_bottom and\
                self.render_element_type in (RenderElementType.last, RenderElementType.complete):
            content_height -= self.border_style.border_width

        if not self.background_color.transparent:
            pdf_doc.set_fill_color(self.background_color.r, self.background_color.g, self.background_color.b)
            pdf_doc.rect(content_x, content_y, content_width, content_height, style='F')

        render_y = y
        if self.border_style.border_top and\
                self.render_element_type in (RenderElementType.first, RenderElementType.complete):
            render_y += self.border_style.border_width
        for element in self.elements:
            element.render_pdf(container_offset_x=content_x, container_offset_y=content_y, pdf_doc=pdf_doc)

        if (self.border_style.border_left or self.border_style.border_top or
                self.border_style.border_right or self.border_style.border_bottom):
            DocElement.draw_border(
                x=x, y=y, width=self.width, height=height,
                render_element_type=self.render_element_type, border_style=self.border_style, pdf_doc=pdf_doc)

    def cleanup(self):
        for element in self.elements:
            element.cleanup()


class SectionRenderElement(DocElementBase):
    def __init__(self, report, render_y):
        DocElementBase.__init__(self, report, dict(y=0))
        self.report = report
        self.render_y = render_y
        self.render_bottom = render_y
        self.height = 0
        self.bands = []
        self.complete = False

    def is_empty(self):
        return len(self.bands) == 0

    def add_section_band(self, section_band):
        if section_band.rendering_complete or not section_band.always_print_on_same_page:
            band_height = section_band.get_used_band_height()
            self.bands.append(dict(height=band_height, elements=list(section_band.get_render_elements())))
            self.height += band_height
            self.render_bottom += band_height

    def render_pdf(self, container_offset_x, container_offset_y, pdf_doc):
        y = self.render_y + container_offset_y
        for band in self.bands:
            for element in band['elements']:
                element.render_pdf(container_offset_x=container_offset_x, container_offset_y=y, pdf_doc=pdf_doc)
            y += band['height']

    def cleanup(self):
        for band in self.bands:
            for element in band['elements']:
                element.cleanup()
