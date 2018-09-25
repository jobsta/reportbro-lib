# Changelog

## [1.0] - 2018-09-25

### Bug Fixes
* fix rendering of frame element inside section
* fix Python 3 compatability issues
* do not convert decimal values to float when evaluating expressions to avoid rounding issues
* fix handling errors when evaluating parameter expression
* check "Print if" condition before rendering element in spreadsheet

### Changes
* do not modify data parameter which is passed to ReportBro constructor
* add decimal to default functions in expression evaluation (allows to create a decimal.Decimal instance
in an expression)

## [0.12.1] - 2018-06-06

### Features
* section elements to iterate lists
* set column width for xls export
* column range spreadsheet property
* allow decimal values for border width

### Bug Fixes
* fix element rendering position in case height of element above grows and the element is not first one above
* do not set text size in xls export (because row default height is always used)
* fix rendering spreadsheet when table content rows contain group expression

## [0.11.2] - 2018-04-10

### Features
* support for dynamic table column (column containing simple array parameter will be expanded to multiple columns)

### Bug Fixes
* fix calculation of frame height (could lead to wrong positioning of following elements)

## [0.11.1] - 2018-03-21

### Features
* multiple content row definitions for tables
* group expression and print if for table content rows
* boolean parameter type
* simple list parameter type (list items with basic type like string, number, boolean, date)
* nullable setting for parameter to explicitly allow nullable parameters, non-nullable parameters automatically get default value in case there is no data (e.g. 0 for numbers or '' for strings)
* allow file object as data for image parameter

### Bug Fixes
* datetime parameter is not converted to date anymore

## [0.10.1] - 2017-11-02

### Features
* frame elements to group document elements

## [0.9.9] - 2017-08-19

Initial release.
