# Changelog

## [3.9.2] - 2024-10-07

### Changes
* Support setting to show watermark in foreground (PLUS version)
* Use attributes from linked style instead of attributes set on element (allows changing style data
independent of Designer)

### Bug Fixes
* Fix calculating y-offset for watermark elements (use absolute position on page)

## [3.9.0] - 2024-08-27

### Features
* Support watermark texts and images with rotation and transparency (PLUS version)

### Changes
* Store fonts with lowercase name to allow case independent font access

## [3.8.0] - 2024-05-23

### Features
* Support background color for section bands
* Support custom functions for evaluating expressions
* Support options to set spreadsheet cell type and pattern

### Changes
* Add "abs", "floor" and "ceil" to available functions for evaluating expressions
* encode_error_handling setting is now also used for TrueType fonts (custom fonts)

## [3.7.1] - 2024-04-09

### Changes
* Update dependencies
* Use simpleeval instead of reportbro-simpleeval

### Bug Fixes
* Removed deprecation warning with python 3.11

## [3.7.0] - 2024-02-09

### Features
* Support rich text parameters (PLUS version)

### Changes
* Drop support for Python 3.7 (EOL June 2023)

### Bug Fixes
* Fix error using custom thousands separator
* Fix xlsx output for report with webp image

## [3.6.2] - 2024-01-22

### Bug Fixes
* Fix rendering line

## [3.6.1] - 2024-01-16

### Bug Fixes
* Fix rendering of justified text with underline or strikethrough formatting

## [3.6.0] - 2024-01-15

### Features
* Support rich text in table cells (PLUS version)
* Support text shaping (PLUS version)

### Changes
* Handle error when printing characters that are not contained in ttf font

### Bug Fixes
* Fix rendering of line inside section
* Fix printing table groups when there are hidden group rows due to "Print If" condition
 
## [3.5.1] - 2023-11-20

### Changes
* Improve retrieving test data from parameters - set default value for test data if data is missing
* Evaluate parameter expressions for nested parameters

## [3.5.0] - 2023-11-16

### Changes
* Support ':' prefix for parameter to access root parameter
* Add functions "format_datetime" and "format_decimal" to format value in expressions

### Bug Fixes
* Initialize map parameter with default values if parameter is not nullable and no data is available
* Fix error field for invalid test data

## [3.4.0] - 2023-10-23

### Changes
* Add spreadsheet options parameter to change default conversion of string content 
* Add static method to extract test data from parameters
* Support webp image format
* Add report instance settings "allow_local_image" and "allow_external_image" to define
if local images (from filesystem) and external images (referenced with link) are allowed

### Bug Fixes
* Fix error when rendering spreadsheet with empty image

## [3.3.1] - 2023-09-26

### Bug Fixes
* Avoid error if barcode parameter data is empty

## [3.3.0] - 2023-09-12

### Features
* Support multiple conditional styles

### Changes
* Support data source prefix for parameter to access parameter from outer scope

### Bug Fixes
* Always remove section (clear space for following elements) if not printed due to "Print If" condition
* Fix showing error in case of duplicate parameter name
* Fix error when formatting decimal by using an invalid bool value
* Do not return error if evaluated parameter expression is None for "Nullable" parameter

## [3.2.1] - 2023-05-17

### Changes
* Check if barcode width/height is valid

## [3.2.0] - 2023-05-12

### Features
* Support additional barcodes CODE39, EAN-8, EAN-13 and UPC
* Support option to rotate barcode

### Changes
* Create barcodes as SVG to allow arbitrary barcode sizes and losless scaling
* Raise error when there is not enough space to render CODE128 barcode

### Bug Fixes
* Fix rendering of barcode and image inside section
* Fix conditional style of text in xls export when style is directly set in text element
* Fix removing empty image element

## [3.1.0] - 2023-04-19

### Features
* Support option to align frame to bottom of page
* Support setting "Thousands separator" for number formatting

### Bug Fixes
* Fix processing of table rows with group expression

## [3.0.5] - 2022-12-30

### Bug Fixes
* Fix error when accessing map parameter with None value

## [3.0.4] - 2022-11-02

### Bug Fixes
* Fix rendering table content band with group expression when a previous group row is not printed

## [3.0.3] - 2022-10-27

### Bug Fixes
* Fix rendering frame which does not fit on one page

## [3.0.2] - 2022-10-11

### Bug Fixes
* Do not throw error for image parameter without image data

## [3.0.1] - 2022-10-11

### Bug Fixes
* Add data directory init file needed for importlib.resources module

## [3.0.0] - 2022-10-10

### Features
* Support processing of nested parameters and rendering nested sections (PLUS version)
* Support option to set bar width for code128 barcode

### Changes
* Drop support for old Python versions 2.x and < 3.7
* Switch to maintained fpdf2 lib for pdf rendering

## [2.1.1] - 2022-06-13

### Bug Fixes
* Fix rendering table group band on page break
* Fix error when rendering empty table with table group band

## [2.1.0] - 2022-04-22

### Changes
* Support "Print if" condition for page break
* Support Average and Sum Parameter Type for table groups
* Use poetry instead of setup.py

### Bug Fixes
* Fix rendering table inside section with same data source

## [2.0.1] - 2022-01-28

### Bug Fixes
* Use own simpleeval lib to fix compatibility issue with setuptools (>= 58)
* Avoid error for rich text without content

## [2.0.0] - 2021-08-06

### Features
* rendering of Rich Text (PLUS version)
* QR Code
* support option to repeat table group on each page

### Changes
* add option to set encoding for core fonts

### Bug Fixes
* fix endless loop when rendering empty table
    
## [1.6.0] - 2021-03-19

### Changes
* allow manual page break inside section content

### Bug Fixes
* fix returned exception for 'always on same page' setting so error can be displayed in ReportBro Designer

## [1.5.2] - 2020-10-06

### Changes
* image type is compared case insensitive
* throw error if used font is not available

### Bug Fixes
* fix referencing image data inside collection

## [1.5.1] - 2020-07-27

### Bug Fixes
* fix rendering issues of text elements inside table or section

## [1.5.0] - 2020-07-15

### Features
* support option to expand column width
* support option to force page break for each new group in a table
* support text wrap in spreadsheet cell

### Changes
* evaluate parameters inside list
* add encode_error_handling setting to define behavior when a character cannot be
encoded with the core fonts encoding

### Bug Fixes
* parameter for image source can now also be part of a collection parameter
* fix usage of additional font when multiple font files are set for different styles

## [1.4.0] - 2020-04-20

### Changes
* add page_limit parameter to ReportBro constructor to define custom page limit
* adapt field values of Error object to changes in latest reportbro-designer release
* allow file path in text parameter for image source
* use default request headers for loading image with urlopen when image is specified by url
(some sites check for existance of 'user-agent' request header and do not return image otherwise)
* allow to override request headers used when fetching images in ReportBro constructor
* allow query parameters in url for image source

### Bug Fixes
* fix bug with ReportBroError instance when trying to format a number parameter with an invalid pattern

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
