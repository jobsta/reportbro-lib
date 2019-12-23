# Changelog

## [1.3.4] - 2019-12-23

### Bug Fixes
* fix rendering issue when previous element is removed and use correct space to last predecessor

## [1.3.3] - 2019-11-08

### Changes
* show error details when returning string representation of ReportBro exception

### Bug Fixes
* fix rendering element with multiple predecessor elements (elements with same bottom y-coord)
* fix rendering table cell with selected style when style contains transparent background color

## [1.3.1] - 2019-09-02

### Bug Fixes
* fix rendering of images inside section
* fix rendering of barcodes inside section
* fix rendering of links (for texts and images) inside section
* fix rendering sections in spreadsheet

## [1.3.0] - 2019-08-26

### Features
* support column span field for table text element
* support internal parameter row_number for tables and sections

## [1.2.0] - 2019-07-05
### Changes
* reduce minimum page width/height (minimum is now 30)

### Bug Fixes
* include images and links in xls export

## [1.1.0] - 2019-01-10

### Feature
* external links for text and image element with link property
* strikethrough text style

### Changes
* allow static tables (table without data source)
* support removeEmptyElement field for table
* make datetime module available for expressions
* show error message if loading image failed

### Bug Fixes
* set correct line color when justified text is underlined
* fix rendering of table element inside frame
* no page break after rendering table where no rows are printed because of print condition
* define True/False for expression evaluation

## [1.0.0] - 2018-09-25

### Bug Fixes
* fix rendering of frame element inside section
* fix Python 3 compatibility issues
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
