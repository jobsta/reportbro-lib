#!/usr/bin/env python3
import sys
from tests.test_report_render import ReportRenderTest

if __name__ == "__main__":
    if len(sys.argv) < 2:
        raise Exception('parameter for report_name is missing')
    report_name = sys.argv[1]
    ReportRenderTest('local', report_name).update_report_output(update_file=True, update_checksum=False)
