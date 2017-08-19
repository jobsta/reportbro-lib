from __future__ import unicode_literals
from __future__ import division
from babel.numbers import format_decimal
from babel.dates import format_datetime
from simpleeval import simple_eval, NameNotDefined, FunctionNotDefined
from simpleeval import DEFAULT_NAMES as EVAL_DEFAULT_NAMES
from simpleeval import DEFAULT_FUNCTIONS as EVAL_DEFAULT_FUNCTIONS
import decimal

from .enums import *
from .errors import Error, ReportBroError


class Context:
    def __init__(self, report, parameters, data):
        self.report = report
        self.pattern_locale = report.document_properties.pattern_locale
        self.pattern_currency_symbol = report.document_properties.pattern_currency_symbol
        self.parameters = parameters
        self.data = data
        self.data.update(EVAL_DEFAULT_NAMES)
        self.eval_functions = EVAL_DEFAULT_FUNCTIONS.copy()
        self.eval_functions.update(
            len=len,
            float=float
        )
        self.root_data = data
        self.root_data['page_number'] = 0
        self.root_data['page_count'] = 0

    def get_parameter(self, name, parameters=None):
        if parameters is None:
            parameters = self.parameters
        if name in parameters:
            return parameters[name]
        elif parameters.get('__parent'):
            return self.get_parameter(name, parameters.get('__parent'))
        return None

    def get_data(self, name, data=None):
        if data is None:
            data = self.data
        if name in data:
            return data[name]
        elif data.get('__parent'):
            return self.get_data(name, data.get('__parent'))
        return None

    def push_context(self, parameters, data):
        parameters['__parent'] = self.parameters
        self.parameters = parameters
        data['__parent'] = self.data
        self.data = data

    def pop_context(self):
        parameters = self.parameters.get('__parent')
        if parameters is None:
            raise RuntimeError('Context.pop_context failed - no parent available')
        del self.parameters['__parent']
        self.parameters = parameters
        data = self.data.get('__parent')
        if data is None:
            raise RuntimeError('Context.pop_context failed - no parent available')
        del self.data['__parent']
        self.data = data

    def fill_parameters(self, expr, object_id, field, pattern=None):
        if expr.find('${') == -1:
            return expr
        ret = ''
        prev_c = None
        parameter_index = -1
        for i, c in enumerate(expr):
            if parameter_index == -1:
                if prev_c == '$' and c == '{':
                    parameter_index = i + 1
                    ret = ret[:-1]
                else:
                    ret += c
            else:
                if c == '}':
                    parameter_name = expr[parameter_index:i]
                    collection_name = None
                    field_name = None
                    if parameter_name.find('.') != -1:
                        name_parts = parameter_name.split('.')
                        collection_name = name_parts[0]
                        field_name = name_parts[1]
                        parameter = self.get_parameter(collection_name)
                        if parameter is None:
                            self.report.errors.append(Error('errorMsgInvalidExpressionNameNotDefined',
                                    object_id=object_id, field=field, info=collection_name))
                            raise ReportBroError()
                    else:
                        parameter = self.get_parameter(parameter_name)
                        if parameter is None:
                            self.report.errors.append(Error('errorMsgInvalidExpressionNameNotDefined',
                                    object_id=object_id, field=field, info=parameter_name))
                            raise ReportBroError()
                    value = None
                    if parameter.type == ParameterType.map:
                        parameter = self.get_parameter(field_name, parameters=parameter.fields)
                        if parameter is None:
                            self.report.errors.append(Error('errorMsgInvalidExpressionNameNotDefined',
                                    object_id=object_id, field=field, info=parameter_name))
                            raise ReportBroError()
                        map_value = self.get_data(collection_name)
                        if parameter and isinstance(map_value, dict):
                            value = map_value.get(field_name)
                    else:
                        value = self.get_data(parameter_name)
                    if value is not None:
                        if parameter.type == ParameterType.string:
                            ret += value
                        elif parameter.type in (ParameterType.number, ParameterType.average, ParameterType.sum):
                            if pattern:
                                used_pattern = pattern
                                pattern_has_currency = (pattern.find('$') != -1)
                            else:
                                used_pattern = parameter.pattern
                                pattern_has_currency = parameter.pattern_has_currency
                            if used_pattern:
                                try:
                                    value = format_decimal(value, used_pattern, locale=self.pattern_locale)
                                    if pattern_has_currency:
                                        value = value.replace('$', self.pattern_currency_symbol)
                                    ret += value
                                except ValueError:
                                    error_object_id = object_id if pattern else parameter.id
                                    self.report.errors.append(Error('errorMsgInvalidPattern',
                                            object_id=error_object_id, field='pattern'))
                                    raise ReportBroError()
                            else:
                                ret += str(value)
                        elif parameter.type == ParameterType.date:
                            used_pattern = pattern if pattern else parameter.pattern
                            if used_pattern:
                                try:
                                    ret += format_datetime(value, used_pattern, locale=self.pattern_locale)
                                except ValueError:
                                    error_object_id = object_id if pattern else parameter.id
                                    self.report.errors.append(Error('errorMsgInvalidPattern',
                                            object_id=error_object_id, field='pattern'))
                                    raise ReportBroError()
                            else:
                                ret += str(value)
                    else:
                        self.report.errors.append(Error('errorMsgMissingParameterData',
                                object_id=object_id, field=field, info=parameter_name))
                        raise ReportBroError()
                    parameter_index = -1
            prev_c = c
        return ret

    def evaluate_expression(self, expr, object_id, field):
        if expr:
            try:
                data = dict()
                expr = self.replace_parameters(expr, data=data)
                return simple_eval(expr, names=data, functions=self.eval_functions)
            except NameNotDefined as ex:
                self.report.errors.append(Error('errorMsgInvalidExpressionNameNotDefined',
                        object_id=object_id, field=field, info=ex.name))
                raise ReportBroError()
            except FunctionNotDefined as ex:
                self.report.errors.append(Error('errorMsgInvalidExpressionFuncNotDefined',
                        object_id=object_id, field=field, info=ex.func_name))
                raise ReportBroError()
            except SyntaxError as ex:
                self.report.errors.append(Error('errorMsgInvalidExpression',
                        object_id=object_id, field=field, info=ex.msg))
                raise ReportBroError()
            except Exception as ex:
                self.report.errors.append(Error('errorMsgInvalidExpression',
                        object_id=object_id, field=field, info=ex.message))
                raise ReportBroError()
        return True

    @staticmethod
    def strip_parameter_name(expr):
        if expr:
            return expr.strip().lstrip('${').rstrip('}')
        return expr

    def replace_parameters(self, expr, data=None):
        pos = expr.find('${')
        if pos == -1:
            return expr
        ret = ''
        pos2 = 0
        while pos != -1:
            if pos != 0:
                ret += expr[pos2:pos]
            pos2 = expr.find('}', pos)
            if pos2 != -1:
                parameter_name = expr[pos+2:pos2]
                if data is not None:
                    if parameter_name.find('.') != -1:
                        name_parts = parameter_name.split('.')
                        collection_name = name_parts[0]
                        field_name = name_parts[1]
                        value = self.get_data(collection_name)
                        if isinstance(value, dict):
                            value = value.get(field_name)
                        else:
                            value = None
                        # use valid python identifier for parameter name
                        parameter_name = collection_name + '_' + field_name
                    else:
                        value = self.get_data(parameter_name)
                    if isinstance(value, decimal.Decimal):
                        value = float(value)
                    data[parameter_name] = value
                ret += parameter_name
                pos2 += 1
                pos = expr.find('${', pos2)
            else:
                pos2 = pos
                pos = -1
        ret += expr[pos2:]
        return ret

    def inc_page_number(self):
        self.root_data['page_number'] += 1

    def get_page_number(self):
        return self.root_data['page_number']

    def set_page_count(self, page_count):
        self.root_data['page_count'] = page_count
