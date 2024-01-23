#!/usr/bin/env python3
import argparse
from tests.test_report_render import ReportRenderTest, DEMOS, GUIDES, MISC_TESTS

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '-g', '--group_name', help='Limit tests to specified group. Available groups are *demos*, *guides* or *misc*.')
    parser.add_argument('-r', '--report_name', help='Limit tests to specified report.')
    parser.add_argument('-k', '--keep', help='keep original report output and use different filename instead',
                        action='store_true')
    args = parser.parse_args()
    group_name = args.group_name
    report_name = args.report_name
    overwrite = not args.keep

    if not group_name or group_name == 'demos':
        for test in DEMOS:
            if not report_name or test == report_name:
                ReportRenderTest('demos', test).update_report_output(
                    update_file=True, update_checksum=False, overwrite=overwrite)
    if not group_name or group_name == 'guides':
        for test in GUIDES:
            if not report_name or test == report_name:
                ReportRenderTest('guides', test).update_report_output(
                    update_file=True, update_checksum=False, overwrite=overwrite)
    if not group_name or group_name == 'misc':
        for test in MISC_TESTS:
            if not report_name or test == report_name:
                ReportRenderTest('misc', test).update_report_output(
                    update_file=True, update_checksum=False, overwrite=overwrite)
