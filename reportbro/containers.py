from typing import List
from .elements import DocElementBase, PageBreakElement
from .enums import BandType


class Container(object):
    def __init__(self, container_id, containers, report):
        self.id = container_id
        self.report = report
        self.doc_elements = []  # type: List[DocElementBase]
        self.width = 0
        self.height = 0
        if containers is not None:
            containers[self.id] = self

        self.allow_page_break = True
        self.container_offset_y = 0
        self.sorted_elements = None  # type: List[DocElementBase]
        self.render_elements = None  # type: List[DocElementBase]
        self.render_elements_created = False
        self.manual_page_break = False
        self.first_element_offset_y = 0
        # maximum bottom value (from element layout coordinates) of currently rendered elements,
        # this is used to determine if the minimum height of a container
        # (e.g. table or section band) is reached
        self.max_bottom = 0
        # maximum bottom render value of currently rendered elements, this is the actual container
        # height on the current page
        self.render_bottom = 0

    def add(self, doc_element):
        self.doc_elements.append(doc_element)

    def is_visible(self):
        return True

    def prepare(self, ctx, pdf_doc=None, only_verify=False):
        self.sorted_elements = []
        for elem in self.doc_elements:
            if pdf_doc or not elem.spreadsheet_hide or only_verify:
                elem.prepare(ctx, pdf_doc=pdf_doc, only_verify=only_verify)
                if not self.allow_page_break:
                    # make sure element can be rendered multiple times (for header/footer)
                    elem.first_render_element = True
                    elem.rendering_complete = False
                # if page break is not printed we have to skip it during prepare because
                # offset calculations between elements are affected
                if not isinstance(elem, PageBreakElement) or elem.is_printed(ctx):
                    self.sorted_elements.append(elem)

        if pdf_doc:
            self.sorted_elements = sorted(self.sorted_elements, key=lambda item: (item.y, item.sort_order))
            # predecessors are only needed for rendering pdf document
            for i, elem in enumerate(self.sorted_elements):
                for j in range(i-1, -1, -1):
                    elem2 = self.sorted_elements[j]
                    if isinstance(elem2, PageBreakElement):
                        # new page so all elements before are not direct predecessors
                        break
                    if elem.is_predecessor(elem2):
                        elem.add_predecessor(elem2)
            self.render_elements = []
            self.render_bottom = 0
            self.first_element_offset_y = 0
        else:
            self.sorted_elements = sorted(self.sorted_elements, key=lambda item: (item.y, item.x))

    def clear_rendered_elements(self):
        self.render_elements = []
        self.render_bottom = 0

    def get_offset_y(self, doc_element):
        """
        Return y offset for given element on page. The offset is relative to the predecessor elements
        on the page, i.e. if a predecessor element is expanded the element is moved down relative to the
        predecessor.
        """
        if doc_element.predecessors:
            # element is on same page as predecessor element(s) so offset is relative to predecessors
            offset_y = doc_element.get_offset_y()
        else:
            if doc_element.first_render_element:
                offset_y = doc_element.y - self.first_element_offset_y
                if offset_y < 0:
                    offset_y = 0
            else:
                offset_y = 0
        return offset_y

    def create_render_elements(self, container_top, container_height, ctx, pdf_doc):
        i = 0
        new_page = False
        processed_elements = []
        completed_elements = dict()

        self.render_elements_created = False
        self.manual_page_break = False
        next_offset_y = None
        while not new_page and i < len(self.sorted_elements):
            elem = self.sorted_elements[i]
            if elem.has_uncompleted_predecessor(completed_elements):
                # a predecessor is not completed yet -> start new page
                new_page = True
            else:
                elem_deleted = False
                if isinstance(elem, PageBreakElement):
                    if self.allow_page_break:
                        del self.sorted_elements[i]
                        elem_deleted = True
                        new_page = True
                        self.manual_page_break = True
                        next_offset_y = elem.y
                    else:
                        self.sorted_elements = []
                        return True
                else:
                    complete = False
                    offset_y = self.get_offset_y(elem)

                    if elem.is_printed(ctx):
                        if offset_y >= container_height:
                            new_page = True
                        if not new_page:
                            render_elem, complete = elem.get_next_render_element(
                                offset_y, container_top=container_top,
                                container_width=self.width, container_height=container_height,
                                ctx=ctx, pdf_doc=pdf_doc)
                            if complete:
                                processed_elements.append(elem)
                            if render_elem:
                                self.render_elements.append(render_elem)
                                self.render_elements_created = True
                                if elem.bottom > self.max_bottom:
                                    self.max_bottom = elem.bottom
                                if render_elem.render_bottom > self.render_bottom:
                                    self.render_bottom = render_elem.render_bottom
                    else:
                        processed_elements.append(elem)
                        elem.finish_empty_element(offset_y)
                        complete = True

                    if not complete and next_offset_y is None:
                        # in case we continue rendering on the next page the first element which is not complete
                        # will define the offset-y for the next page
                        next_offset_y = elem.y

                    if complete:
                        completed_elements[elem.id] = True
                        del self.sorted_elements[i]
                        elem_deleted = True
                if not elem_deleted:
                    i += 1

        self.first_element_offset_y = next_offset_y if next_offset_y else 0

        if len(self.sorted_elements) > 0:
            if self.allow_page_break:
                self.render_elements.append(PageBreakElement(self.report, dict(y=-1)))
            for processed_element in processed_elements:
                # remove dependency to predecessors because successor element is either already added
                # to render_elements or on new page
                for successor in processed_element.successors:
                    successor.clear_predecessor(processed_element)
        return len(self.sorted_elements) == 0

    def render_pdf(self, container_offset_x, container_offset_y, pdf_doc, cleanup=False):
        counter = 0
        for render_elem in self.render_elements:
            counter += 1
            if isinstance(render_elem, PageBreakElement):
                break
            render_elem.render_pdf(container_offset_x, container_offset_y, pdf_doc)
            if cleanup:
                render_elem.cleanup()
        self.render_elements = self.render_elements[counter:]

    def render_spreadsheet(self, row, col, ctx, renderer):
        max_col = col
        i = 0
        count = len(self.sorted_elements)
        while i < count:
            elem = self.sorted_elements[i]
            if elem.is_printed(ctx):
                j = i + 1
                # render elements with same y-coordinate in same spreadsheet row
                row_elements = [elem]
                while j < count:
                    elem2 = self.sorted_elements[j]
                    if elem2.y == elem.y:
                        if elem2.is_printed(ctx):
                            row_elements.append(elem2)
                    else:
                        break
                    j += 1
                i = j
                current_row = row
                current_col = col
                for row_element in row_elements:
                    tmp_row, current_col = row_element.render_spreadsheet(
                        current_row, current_col, ctx, renderer)
                    row = max(row, tmp_row)
                    if current_col > max_col:
                        max_col = current_col
            else:
                i += 1
        return row, max_col

    def is_finished(self):
        return len(self.render_elements) == 0

    def reset(self):
        """Reset container when used multiple times.

        Must be called when the same container is used for rendering, e.g. for
        different rows in a section content band or a repeated header/footer.
        """
        self.manual_page_break = False
        self.first_element_offset_y = 0
        self.max_bottom = 0
        self.render_bottom = 0
        for elem in self.doc_elements:
            elem.first_render_element = True
            elem.rendering_complete = False

    def cleanup(self):
        for elem in self.doc_elements:
            elem.cleanup()


class Frame(Container):
    def __init__(self, width, height, container_id, containers, report):
        Container.__init__(self, container_id, containers, report)
        self.width = width
        self.height = height
        self.allow_page_break = False


class ReportBand(Container):
    def __init__(self, band, container_id, containers, report):
        Container.__init__(self, container_id, containers, report)
        self.band = band
        self.width = report.document_properties.page_width -\
            report.document_properties.margin_left - report.document_properties.margin_right
        if band == BandType.content:
            self.height = report.document_properties.content_height
        elif band == BandType.header:
            self.allow_page_break = False
            self.height = report.document_properties.header_size
        elif band == BandType.footer:
            self.allow_page_break = False
            self.height = report.document_properties.footer_size

    def is_visible(self):
        if self.band == BandType.header:
            return self.report.document_properties.header
        elif self.band == BandType.footer:
            return self.report.document_properties.footer
        return True
