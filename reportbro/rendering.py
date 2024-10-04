from barcode.writer import SVGWriter, create_svg_object, pt2mm

from .docelement import DocElementBase, DocElement
from .enums import *
from .errors import Error, ReportBroError
from .utils import get_image_display_size


class ImageRenderElement(DocElementBase):
    def __init__(self, report, render_y, image):
        DocElementBase.__init__(self, report, dict(y=0))
        self.report = report
        self.x = image.x
        self.width = image.width
        self.height = image.height
        self.render_y = render_y
        self.render_bottom = render_y + self.height
        self.horizontal_alignment = image.style.horizontal_alignment
        self.vertical_alignment = image.style.vertical_alignment
        self.background_color = image.style.background_color
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
            if image and image.image_data:
                halign = {
                    HorizontalAlignment.left: 'L', HorizontalAlignment.center: 'C',
                    HorizontalAlignment.right: 'R'}.get(self.horizontal_alignment)
                valign = {
                    VerticalAlignment.top: 'T', VerticalAlignment.middle: 'C',
                    VerticalAlignment.bottom: 'B'}.get(self.vertical_alignment)
                try:
                    image_info = pdf_doc.image(
                        image.image_data, x, y, self.width, self.height, halign=halign, valign=valign)
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


class BarcodeSVGWriter(SVGWriter):
    """
    SVGWriter class adapted for ReportBro needs. Units are specified in pt (instead of mm) so we
    do not have to convert our ReportBro unit values.
    Some minor adaptations are made for size and position for exact layout.
    """

    @staticmethod
    def get_unit_value(size):
        """
        Return value with pt unit type.
        """
        return f'{size}pt'

    @staticmethod
    def set_attributes(element, **attributes):
        """
        Same as barcode.writer._set_attributes

        Because it is "private" we do not import it and define it as static method here.
        """
        for key, value in attributes.items():
            element.setAttribute(key, value)

    def __init__(self):
        SVGWriter.__init__(self)
        # width of generated barcode, available after barcode was created
        self._barcode_width = None

    @property
    def barcode_width(self):
        # make sure barcode was generated before accessing property
        assert self._barcode_width is not None
        return self._barcode_width

    def calculate_size(self, modules_per_line, number_of_lines):
        """Calculates the size of the barcode in pixel.

        :parameters:
            modules_per_line : Integer
                Number of modules in one line.
            number_of_lines : Integer
                Number of lines of the barcode.

        :return: Width and height of the barcode in pixel.
        :rtype: Tuple
        """
        width = 2 * self.quiet_zone + modules_per_line * self.module_width
        # we do not add 2.0 to height (as is done in BaseWriter.calculate_size) to get
        # barcode height as defined in report layout
        height = self.module_height * number_of_lines
        number_of_text_lines = len(self.text.splitlines())
        if self.font_size and self.text:
            height += (
                pt2mm(self.font_size) / 2 * number_of_text_lines + self.text_distance
            )
            height += self.text_line_distance * (number_of_text_lines - 1)
        return width, height

    def _init(self, code):
        width, height = self.calculate_size(len(code[0]), len(code))
        # save width of generated barcode
        self._barcode_width = width
        self._document = create_svg_object(self.with_doctype)
        self._root = self._document.documentElement
        attributes = {
            "width": self.get_unit_value(width),
            "height": self.get_unit_value(height),
            # add viewBox attribute so fpdf does not output warning about missing viewBox
            # when width and height are set
            "viewBox": f"0 0 {width} {height}",
        }
        self.set_attributes(self._root, **attributes)
        # create group for easier handling in 3rd party software
        # like corel draw, inkscape, ...
        group = self._document.createElement("g")
        attributes = {"id": "barcode_group"}
        self.set_attributes(group, **attributes)
        self._group = self._root.appendChild(group)
        background = self._document.createElement("rect")
        # use exact size instead of "100%" because fpdf cannot handle percent values
        attributes = {
            "width": self.get_unit_value(width),
            "height": self.get_unit_value(height),
            "style": f"fill:{self.background}",
        }
        self.set_attributes(background, **attributes)
        self._group.appendChild(background)

    def _create_module(self, xpos, ypos, width, color):
        # Background rect has been provided already, so skipping "spaces"
        if color != self.background:
            element = self._document.createElement("rect")
            attributes = {
                "x": self.get_unit_value(xpos),
                # ypos starts with 1.0 instead of 0.0 in BaseWriter.render of barcode lib,
                # to have exact position we remove the offset
                "y": self.get_unit_value(ypos - 1.0),
                "width": self.get_unit_value(width),
                "height": self.get_unit_value(self.module_height),
                "style": f"fill:{color};",
            }
            self.set_attributes(element, **attributes)
            self._group.appendChild(element)

    def _create_text(self, xpos, ypos):
        # check option to override self.text with self.human (barcode as
        # human readable data, can be used to print own formats)
        if self.human != "":
            barcodetext = self.human
        else:
            barcodetext = self.text
        for subtext in barcodetext.split("\n"):
            element = self._document.createElement("text")
            attributes = {
                "x": self.get_unit_value(xpos),
                "y": self.get_unit_value(ypos),
                "style": "fill:{};font-size:{}pt;text-anchor:middle;".format(
                    self.foreground,
                    self.font_size,
                ),
            }
            self.set_attributes(element, **attributes)
            text_element = self._document.createTextNode(subtext)
            element.appendChild(text_element)
            self._group.appendChild(element)
            ypos += pt2mm(self.font_size) + self.text_line_distance


class BarCodeRenderElement(DocElementBase):
    def __init__(self, report, render_y, content_width, barcode):
        DocElementBase.__init__(self, report, dict(y=0))
        self.report = report
        self.x = barcode.x
        self.render_y = render_y
        self.format = barcode.format
        self.content = barcode.prepared_content
        self.display_value = barcode.display_value
        self.guardbar = barcode.guardbar
        self.rotate = barcode.rotate
        if barcode.rotate:
            self.width = barcode.barcode_height
            self.height = barcode.barcode_width
            render_height = barcode.barcode_width if barcode.barcode_width > content_width else content_width
        else:
            self.width = barcode.barcode_width
            self.height = barcode.barcode_height
            render_height = barcode.height
        self.svg_data = barcode.svg_data
        self.object_id = barcode.id
        self.content_width = content_width  # width of content text when barcode value is displayed
        self.render_bottom = render_y + render_height

    def render_pdf(self, container_offset_x, container_offset_y, pdf_doc):
        x = self.x + container_offset_x
        y = self.render_y + container_offset_y

        if self.format == 'qrcode':
            pdf_doc.image(self.svg_data, x, y, self.width, self.height)
        else:
            rotate_angle = 0
            if self.rotate:
                rotate_angle = 270  # rotate 270 degrees counter clockwise
                offset_x = self.width
                if self.display_value:
                    # move by 20 pixel to leave space for barcode value as text
                    offset_x += 20
                with pdf_doc.rotation(angle=rotate_angle, x=x, y=y):
                    # because we rotate by 270 degrees ccw we have to adapt the x offset on the y coordinate
                    pdf_doc.image(self.svg_data, x, y - offset_x)
            else:
                pdf_doc.image(self.svg_data, x, y)

            if self.display_value:
                # because svg text elements are not supported in fpdf we display the value
                # ourself with a normal text item
                pdf_doc.set_font('courier', 'B', 18)
                pdf_doc.set_text_color(0, 0, 0)
                # show barcode value centered and below barcode,
                # in case text is larger than barcode we show the text at same position as barcode
                if rotate_angle:
                    offset_y = (self.height - self.content_width) / 2
                    if offset_y < 0:
                        offset_y = 0
                    with pdf_doc.rotation(angle=rotate_angle, x=x, y=y):
                        # because we rotate by 270 degrees ccw we have to adapt the y offset on the x coordinate
                        pdf_doc.print_text(x + offset_y, y, self.content, object_id=self.object_id, field='content')
                else:
                    offset_x = (self.width - self.content_width) / 2
                    if offset_x < 0:
                        offset_x = 0
                    pdf_doc.print_text(
                        x + offset_x, y + self.height + 20, self.content, object_id=self.object_id, field='content')

    def cleanup(self):
        if self.svg_data:
            self.svg_data.close()
            self.svg_data = None


class LineRenderElement(DocElementBase):
    def __init__(self, report, render_y, line):
        DocElementBase.__init__(self, report, dict())
        self.report = report
        self.x = line.x
        self.render_y = render_y
        self.width = line.width
        self.height = line.height
        self.color = line.style.color

    def render_pdf(self, container_offset_x, container_offset_y, pdf_doc):
        pdf_doc.set_draw_color(self.color.r, self.color.g, self.color.b)
        pdf_doc.set_line_width(self.height)
        x = self.x + container_offset_x
        y = self.render_y + container_offset_y + (self.height / 2)
        pdf_doc.line(x, y, x + self.width, y)


class TableRenderElement(DocElementBase):
    def __init__(self, report, table, render_y):
        DocElementBase.__init__(self, report, dict(y=0))
        self.report = report
        self.table = table
        self.x = table.x
        self.width = table.width
        self.render_y = render_y
        self.render_bottom = render_y
        self.height = 0
        self.bands = []
        self.complete = False

    def is_empty(self):
        return len(self.bands) == 0

    def add_band(self, band, row_index=-1):
        if band.rendering_complete or not band.always_print_on_same_page:
            band_height = band.get_render_bottom()
            background_color = band.style.background_color
            if band.band_type == BandType.content and not band.style.alternate_background_color.transparent and\
                    row_index % 2 == 1:
                background_color = band.style.alternate_background_color

            self.bands.append(dict(
                height=band_height, background_color=background_color,
                elements=list(band.get_render_elements()), cells=band.printed_cells))
            self.height += band_height
            self.render_bottom += band_height

    def render_pdf(self, container_offset_x, container_offset_y, pdf_doc):
        x = self.x + container_offset_x
        x1 = x
        x2 = x1 + self.width
        y = self.render_y + container_offset_y
        row_y = y
        for band in self.bands:
            background_color = band['background_color']
            if not background_color.transparent:
                pdf_doc.set_fill_color(
                    background_color.r, background_color.g, background_color.b)
                pdf_doc.rect(x, row_y, self.width, band['height'], style='F')

            for element in band['elements']:
                element.render_pdf(container_offset_x=x, container_offset_y=row_y, pdf_doc=pdf_doc)
            row_y += band['height']

        if not self.is_empty() and self.table.style.border != Border.none:
            pdf_doc.set_draw_color(
                self.table.style.border_color.r, self.table.style.border_color.g, self.table.style.border_color.b)
            pdf_doc.set_line_width(self.table.style.border_width)
            half_border_width = self.table.style.border_width / 2
            x1 += half_border_width
            x2 -= half_border_width
            y1 = y
            y2 = row_y
            if self.table.style.border in (Border.grid, Border.frame_row, Border.frame):
                # draw left and right table borders
                pdf_doc.line(x1, y1, x1, y2)
                pdf_doc.line(x2, y1, x2, y2)
            y = y1
            pdf_doc.line(x1, y1, x2, y1)
            if self.table.style.border != Border.frame:
                # draw lines between table rows
                for band in self.bands[:-1]:
                    y += band['height']
                    pdf_doc.line(x1, y, x2, y)
            pdf_doc.line(x1, y2, x2, y2)
            if self.table.style.border == Border.grid:
                # draw lines between table columns
                cells = self.bands[0]['cells']
                # add half border_width so border is drawn inside right cell and
                # can be aligned with borders of other elements outside the table
                x = x1
                y2 = y1 + self.bands[0]['height']

                # rows can have different cells (colspan) than other rows so
                # we draw cell borders separately if necessary
                for band in self.bands[1:]:
                    current_cells = band['cells']
                    same_borders = True
                    if len(cells) == len(current_cells):
                        for (col1, col2) in zip(cells, current_cells):
                            if col1.width != col2.width:
                                same_borders = False
                                break
                    else:
                        same_borders = False
                    if not same_borders:
                        x = x1
                        for cell in cells[:-1]:
                            x += cell.width
                            pdf_doc.line(x, y1, x, y2)
                        y1 = y2
                        x = x1
                        cells = current_cells
                    y2 += band['height']

                for cell in cells[:-1]:
                    x += cell.width
                    pdf_doc.line(x, y1, x, y2)

    def cleanup(self):
        for band in self.bands:
            for element in band['elements']:
                element.cleanup()


class FrameRenderElement(DocElementBase):
    def __init__(self, report, frame, render_y):
        DocElementBase.__init__(self, report, dict(y=0))
        self.report = report
        self.x = frame.x
        self.width = frame.width
        self.border_style = frame.style
        self.background_color = frame.style.background_color
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

    def add_section_band(self, section_band, background_color):
        if section_band.rendering_complete or not section_band.always_print_on_same_page:
            band_height = section_band.get_render_bottom()
            self.bands.append(dict(
                width=section_band.width,
                height=band_height,
                background_color=background_color,
                elements=list(section_band.get_render_elements())
            ))
            self.height += band_height
            self.render_bottom += band_height

    def render_pdf(self, container_offset_x, container_offset_y, pdf_doc):
        y = self.render_y + container_offset_y
        for band in self.bands:
            if not band['background_color'].transparent:
                pdf_doc.set_fill_color(
                    band['background_color'].r, band['background_color'].g, band['background_color'].b)
                pdf_doc.rect(container_offset_x, y, band['width'], band['height'], 'F')

            for element in band['elements']:
                element.render_pdf(container_offset_x=container_offset_x, container_offset_y=y, pdf_doc=pdf_doc)
            y += band['height']

    def cleanup(self):
        for band in self.bands:
            for element in band['elements']:
                element.cleanup()
