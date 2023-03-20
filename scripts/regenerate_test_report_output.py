#!/usr/bin/env python3
from tests.test_report_render import ReportRenderTest, DEMOS

for test in DEMOS:
    ReportRenderTest('demos', test).update_report_output(update_file=True, update_checksum=False)

