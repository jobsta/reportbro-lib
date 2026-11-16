import pytest
import json
import os
from reportbro import Report
from hashlib import sha256
from pathlib import Path

BASEDIR = Path(__file__).parent.resolve().joinpath(Path('data'))

DEMOS = ['invoice', 'contract', 'delivery_slip']
GUIDES = [
    '03_creating-tables', '04_table-column-printing', '05_table-grouping', '07_sections', '08_expressions',
    '12_dynamic-columns', '13_multi-page-layout',
]
MISC_TESTS = [
    'barcode', 'border', 'line', 'hello_world', 'section_text', 'spreadsheet_type', 'style',
    'table_group', 'text_justified', 'thousands_separator',
]
PARAMETER_TESTS = [
    'svg_image',
]


class ReportRenderTest:
    formats = ['pdf', 'xlsx']

    def __init__(self, prefix_dir: str, name: str, encode_error_handling: str = 'strict', parameter_data: dict = None):
        self.name = name
        self.base_dir = BASEDIR.joinpath(prefix_dir).joinpath(name)
        self.encode_error_handling = encode_error_handling
        self.is_test_data = True
        self._test_data = None
        self._report_definition = None
        if parameter_data:
            self.is_test_data = False
            self._test_data = parameter_data

    def _get_report_definition(self) -> dict:
        if not self._report_definition:
            report_file = self.base_dir.joinpath(Path(f'{self.name}.json'))
            with report_file.open('r') as f:
                report_definition = json.loads(f.read())

            self._report_definition = report_definition
        return self._report_definition

    def _get_data(self) -> dict:
        if not self._test_data:
            data_file = self.base_dir.joinpath(Path('data.json'))
            if data_file.exists():
                with data_file.open('r') as f:
                    self._test_data = json.loads(f.read())
            else:
                report_definition = self._get_report_definition()
                parameter_key = 'parameters'
                if parameter_key not in report_definition:
                    pytest.fail('No data for report creation')
                self._test_data = Report.get_test_data(report_definition[parameter_key])
        return self._test_data

    def _get_report(self) -> Report:
        # allow usage of additional font 'tangerine'
        fonts_dir = os.path.join('tests', 'fonts')
        additional_fonts = [
            dict(
                value='tangerine',
                filename=os.path.join(fonts_dir, 'tangerine.ttf'),
                bold_filename=os.path.join(fonts_dir, 'tangerine-bold.ttf')
            )
        ]

        report = Report(
            report_definition=self._get_report_definition(), data=self._get_data(), is_test_data=self.is_test_data,
            additional_fonts=additional_fonts,
            allow_local_image=not self.is_test_data, allow_external_image=not self.is_test_data,
        )
        report.set_creation_date('2023-03-23 10:01:24')
        return report

    def _get_reference_report_file_name(self, format_type: str, overwrite: bool = True) -> Path:
        base_name = 'report' if overwrite else 'report_modified'
        return self.base_dir.joinpath(f'{base_name}.{format_type}')

    def _get_checksum_file_name(self, format_type: str, overwrite: bool = True) -> Path:
        base_name = 'report' if overwrite else 'report_modified'
        return self.base_dir.joinpath(f'{base_name}.{format_type}.checksum')

    def _get_checksum(self, format_type: str) -> str:
        checksum_file = self._get_checksum_file_name(format_type)
        if checksum_file.exists():
            return checksum_file.read_text('utf-8').replace('\n', '').replace('\r', '')

        reference_report = self._get_reference_report_file_name(format_type)
        if not reference_report.exists():
            pytest.fail('No data for comparison found')

        with reference_report.open('rb') as f:
            data = f.read()
            return sha256(data).hexdigest()

    def _run_format(self, format_type: str):
        report_data = self.generate_report_data(format_type)
        calculated_checksum = sha256(report_data).hexdigest()
        test_checksum = self._get_checksum(format_type)
        print(f'checking type {format_type} with checksum {calculated_checksum}')
        assert (test_checksum == calculated_checksum)

    def run(self):
        for format_type in ReportRenderTest.formats:
            self._run_format(format_type)

    def update_report_output(self, update_file: bool = True, update_checksum: bool = False, overwrite: bool = True):
        for format_type in ReportRenderTest.formats:
            update_current_file = update_file
            update_current_checksum = update_checksum
            report = self._get_report()
            assert len(report.errors) == 0
            report_data = self.generate_report_data(format_type)
            if not overwrite:
                # only write modified file in case checksum changed
                calculated_checksum = sha256(report_data).hexdigest()
                test_checksum = self._get_checksum(format_type)
                if test_checksum == calculated_checksum:
                    update_current_file = update_current_checksum = False

            if update_current_checksum:
                self._get_checksum_file_name(format_type, overwrite=overwrite).write_text(
                    sha256(report_data).hexdigest(), 'utf-8')
            if update_current_file:
                self._get_reference_report_file_name(format_type, overwrite=overwrite).write_bytes(report_data)

    def generate_report_data(self, format_type: str):
        report = self._get_report()
        if format_type == 'pdf':
            return report.generate_pdf()
        elif format_type == 'xlsx':
            return report.generate_xlsx()
        assert False


@pytest.mark.parametrize('demo_name', DEMOS)
def test_report_demo_render(demo_name):
    ReportRenderTest('demos', demo_name).run()


@pytest.mark.parametrize('guide_name', GUIDES)
def test_report_guide_render(guide_name):
    ReportRenderTest('guides', guide_name).run()


@pytest.mark.parametrize('misc_name', MISC_TESTS)
def test_report_misc_render(misc_name):
    ReportRenderTest('misc', misc_name).run()


@pytest.mark.parametrize('report_name', PARAMETER_TESTS)
def test_report_parameter_render(report_name):
    ReportRenderTest('parameter', report_name, parameter_data=get_report_parameter_render_data(report_name)).run()


def get_report_parameter_render_data(report_name):
    parameter_data = dict()
    if report_name == 'svg_image':
        parameter_data = dict(signature='file:tests/data/parameter/svg_image/signature.svg')
    return parameter_data
