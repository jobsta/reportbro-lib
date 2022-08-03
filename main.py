import json
from reportbro import Report, ReportBroError

if __name__ == "__main__":
    # read report_definition and data from json files in tests dir,
    # generate pdf report and save pdf in test dir
    with open('tests/report_definition.json', 'r') as f:
        report_definition = json.loads(f.read())
    with open('tests/data.json', 'r') as f:
        data = json.loads(f.read())
    try:
        # create report with existing template and dynamic data
        report = Report(report_definition=report_definition, data=data, is_test_data=True)
        report_file = report.generate_pdf()
        with open('tests/report.pdf', 'wb') as f:
            f.write(report_file)
    except ReportBroError as e:
        print('error generating report:')
        print(e)
