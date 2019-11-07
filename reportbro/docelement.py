from .enums import *
from .utils import get_int_value


class DocElementBase(object):
    def __init__(self, report, data):
        self.report = report
        self.id = None
        self.y = get_int_value(data, 'y')
        self.render_y = 0
        self.render_bottom = 0
        self.bottom = self.y
        self.height = 0
        self.print_if = None
        self.remove_empty_element = False
        self.spreadsheet_hide = True
        self.spreadsheet_column = None
        self.spreadsheet_add_empty_row = False
        self.first_render_element = True
        self.rendering_complete = False
        self.predecessors = []
        self.successors = []
        self.sort_order = 1  # sort order for elements with same 'y'-value

    def is_predecessor(self, elem):
        # we need to store multiple predecessors if they have the same y-coord because we do not know
        # in advance which one of them is the largest. the current element can only be printed after
        # all predecessors are finished
        return self.y >= elem.bottom and (len(self.predecessors) == 0 or elem.bottom >= self.predecessors[0].y)

    def add_predecessor(self, predecessor):
        self.predecessors.append(predecessor)
        predecessor.successors.append(self)

    # returns True in case there is at least one predecessor which is not completely rendered yet
    def has_uncompleted_predecessor(self, completed_elements):
        for predecessor in self.predecessors:
            if predecessor.id not in completed_elements or not predecessor.rendering_complete:
                return True
        return False

    def get_offset_y(self):
        max_offset_y = 0
        for predecessor in self.predecessors:
            offset_y = predecessor.render_bottom + (self.y - predecessor.bottom)
            if offset_y > max_offset_y:
                max_offset_y = offset_y
        return max_offset_y

    def clear_predecessor(self, elem):
        if elem in self.predecessors:
            self.predecessors.remove(elem)

    def prepare(self, ctx, pdf_doc, only_verify):
        pass

    def is_printed(self, ctx):
        if self.print_if:
            return ctx.evaluate_expression(self.print_if, self.id, field='print_if')
        return True

    def finish_empty_element(self, offset_y):
        if self.remove_empty_element:
            self.render_bottom = offset_y
        else:
            self.render_bottom = offset_y + self.height
        self.rendering_complete = True

    def get_next_render_element(self, offset_y, container_height, ctx, pdf_doc):
        self.rendering_complete = True
        return None, True

    def render_pdf(self, container_offset_x, container_offset_y, pdf_doc):
        pass

    def render_spreadsheet(self, row, col, ctx, renderer):
        return row, col

    def cleanup(self):
        pass


class DocElement(DocElementBase):
    def __init__(self, report, data):
        DocElementBase.__init__(self, report, data)
        self.id = get_int_value(data, 'id')
        self.x = get_int_value(data, 'x')
        self.width = get_int_value(data, 'width')
        self.height = get_int_value(data, 'height')
        self.bottom = self.y + self.height

    def get_next_render_element(self, offset_y, container_height, ctx, pdf_doc):
        if offset_y + self.height <= container_height:
            self.render_y = offset_y
            self.render_bottom = offset_y + self.height
            self.rendering_complete = True
            return self, True
        return None, False

    @staticmethod
    def draw_border(x, y, width, height, render_element_type, border_style, pdf_doc):
        pdf_doc.set_draw_color(
            border_style.border_color.r, border_style.border_color.g, border_style.border_color.b)
        pdf_doc.set_line_width(border_style.border_width)
        border_offset = border_style.border_width / 2
        border_x = x + border_offset
        border_y = y + border_offset
        border_width = width - border_style.border_width
        border_height = height - border_style.border_width
        if border_style.border_all and render_element_type == RenderElementType.complete:
            pdf_doc.rect(border_x, border_y, border_width, border_height, style='D')
        else:
            if border_style.border_left:
                pdf_doc.line(border_x, border_y, border_x, border_y + border_height)
            if border_style.border_top and render_element_type in (
                        RenderElementType.complete, RenderElementType.first):
                pdf_doc.line(border_x, border_y, border_x + border_width, border_y)
            if border_style.border_right:
                pdf_doc.line(border_x + border_width, border_y,
                        border_x + border_width, border_y + border_height)
            if border_style.border_bottom and render_element_type in (
                        RenderElementType.complete, RenderElementType.last):
                pdf_doc.line(border_x, border_y + border_height,
                        border_x + border_width, border_y + border_height)
