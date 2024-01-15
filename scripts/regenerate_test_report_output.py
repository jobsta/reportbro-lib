#!/usr/bin/env python3
import sys
from tests.test_report_render import ReportRenderTest, DEMOS, GUIDES, MISC_TESTS

if __name__ == "__main__":
    group_name = None
    report_name = None
    if len(sys.argv) >= 2:
        group_name = sys.argv[1]
        if len(sys.argv) >= 3:
            report_name = sys.argv[2]

    if not group_name or group_name == 'demos':
        for test in DEMOS:
            if not report_name or test == report_name:
                ReportRenderTest('demos', test).update_report_output(update_file=True, update_checksum=False)
    if not group_name or group_name == 'guides':
        for test in GUIDES:
            if not report_name or test == report_name:
                ReportRenderTest('guides', test).update_report_output(update_file=True, update_checksum=False)
    if not group_name or group_name == 'misc':
        for test in MISC_TESTS:
            if not report_name or test == report_name:
                ReportRenderTest('misc', test).update_report_output(update_file=True, update_checksum=False)
