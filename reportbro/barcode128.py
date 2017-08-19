#!/usr/bin/env python
# Copyright (c) 2010 Erik Karulf (erik@karulf.com)
#
# Permission to use, copy, modify, and/or distribute this software for any
# purpose with or without fee is hereby granted, provided that the above
# copyright notice and this permission notice appear in all copies.
#
# THE SOFTWARE IS PROVIDED "AS IS" AND THE AUTHOR DISCLAIMS ALL WARRANTIES
# WITH REGARD TO THIS SOFTWARE INCLUDING ALL IMPLIED WARRANTIES OF
# MERCHANTABILITY AND FITNESS. IN NO EVENT SHALL THE AUTHOR BE LIABLE FOR
# ANY SPECIAL, DIRECT, INDIRECT, OR CONSEQUENTIAL DAMAGES OR ANY DAMAGES
# WHATSOEVER RESULTING FROM LOSS OF USE, DATA OR PROFITS, WHETHER IN AN
# ACTION OF CONTRACT, NEGLIGENCE OR OTHER TORTIOUS ACTION, ARISING OUT OF
# OR IN CONNECTION WITH THE USE OR PERFORMANCE OF THIS SOFTWARE

from PIL import Image
from PIL import ImageDraw

# Copied from http://en.wikipedia.org/wiki/Code_128
# Value Weights 128A    128B    128C
CODE128_CHART = """
0       212222  space   space   00
1       222122  !       !       01
2       222221  "       "       02
3       121223  #       #       03
4       121322  $       $       04
5       131222  %       %       05
6       122213  &       &       06
7       122312  '       '       07
8       132212  (       (       08
9       221213  )       )       09
10      221312  *       *       10
11      231212  +       +       11
12      112232  ,       ,       12
13      122132  -       -       13
14      122231  .       .       14
15      113222  /       /       15
16      123122  0       0       16
17      123221  1       1       17
18      223211  2       2       18
19      221132  3       3       19
20      221231  4       4       20
21      213212  5       5       21
22      223112  6       6       22
23      312131  7       7       23
24      311222  8       8       24
25      321122  9       9       25
26      321221  :       :       26
27      312212  ;       ;       27
28      322112  <       <       28
29      322211  =       =       29
30      212123  >       >       30
31      212321  ?       ?       31
32      232121  @       @       32
33      111323  A       A       33
34      131123  B       B       34
35      131321  C       C       35
36      112313  D       D       36
37      132113  E       E       37
38      132311  F       F       38
39      211313  G       G       39
40      231113  H       H       40
41      231311  I       I       41
42      112133  J       J       42
43      112331  K       K       43
44      132131  L       L       44
45      113123  M       M       45
46      113321  N       N       46
47      133121  O       O       47
48      313121  P       P       48
49      211331  Q       Q       49
50      231131  R       R       50
51      213113  S       S       51
52      213311  T       T       52
53      213131  U       U       53
54      311123  V       V       54
55      311321  W       W       55
56      331121  X       X       56
57      312113  Y       Y       57
58      312311  Z       Z       58
59      332111  [       [       59
60      314111  \       \       60
61      221411  ]       ]       61
62      431111  ^       ^       62
63      111224  _       _       63
64      111422  NUL     `       64
65      121124  SOH     a       65
66      121421  STX     b       66
67      141122  ETX     c       67
68      141221  EOT     d       68
69      112214  ENQ     e       69
70      112412  ACK     f       70
71      122114  BEL     g       71
72      122411  BS      h       72
73      142112  HT      i       73
74      142211  LF      j       74
75      241211  VT      k       75
76      221114  FF      l       76
77      413111  CR      m       77
78      241112  SO      n       78
79      134111  SI      o       79
80      111242  DLE     p       80
81      121142  DC1     q       81
82      121241  DC2     r       82
83      114212  DC3     s       83
84      124112  DC4     t       84
85      124211  NAK     u       85
86      411212  SYN     v       86
87      421112  ETB     w       87
88      421211  CAN     x       88
89      212141  EM      y       89
90      214121  SUB     z       90
91      412121  ESC     {       91
92      111143  FS      |       92
93      111341  GS      }       93
94      131141  RS      ~       94
95      114113  US      DEL     95
96      114311  FNC3    FNC3    96
97      411113  FNC2    FNC2    97
98      411311  ShiftB  ShiftA  98
99      113141  CodeC   CodeC   99
100     114131  CodeB   FNC4    CodeB
101     311141  FNC4    CodeA   CodeA
102     411131  FNC1    FNC1    FNC1
103     211412  StartA  StartA  StartA
104     211214  StartB  StartB  StartB
105     211232  StartC  StartC  StartC
106     2331112 Stop    Stop    Stop
""".split()

VALUES   = [int(value) for value in CODE128_CHART[0::5]]
WEIGHTS  = dict(zip(VALUES, CODE128_CHART[1::5]))
CODE128A = dict(zip(CODE128_CHART[2::5], VALUES))
CODE128B = dict(zip(CODE128_CHART[3::5], VALUES))
CODE128C = dict(zip(CODE128_CHART[4::5], VALUES))

for charset in (CODE128A, CODE128B):
    charset[' '] = charset.pop('space')


def code128_format(data):
    """
    Generate an optimal barcode from ASCII text
    """
    text     = str(data)
    pos      = 0
    length   = len(text)

    # Start Code
    if text[:2].isdigit() and length > 1:
        charset = CODE128C
        codes   = [charset['StartC']]
    else:
        charset = CODE128B
        codes   = [charset['StartB']]

    # Data
    while pos < length:
        if charset is CODE128C:
            if text[pos:pos+2].isdigit() and length - pos > 1:
                # Encode Code C two characters at a time
                codes.append(int(text[pos:pos+2]))
                pos += 2
            else:
                # Switch to Code B
                codes.append(charset['CodeB'])
                charset = CODE128B
        elif text[pos:pos+4].isdigit() and length - pos >= 4:
            # Switch to Code C
            codes.append(charset['CodeC'])
            charset = CODE128C
        else:
            # Encode Code B one character at a time
            codes.append(charset[text[pos]])
            pos += 1

    # Checksum
    checksum = 0
    for weight, code in enumerate(codes):
        checksum += max(weight, 1) * code
    codes.append(checksum % 103)

    # Stop Code
    codes.append(charset['Stop'])
    return codes


def code128_image(data, height=100, thickness=3, quiet_zone=True):
    if not data[-1] == CODE128B['Stop']:
        data = code128_format(data)

    barcode_widths = []
    for code in data:
        for weight in WEIGHTS[code]:
            barcode_widths.append(int(weight) * thickness)
    width = sum(barcode_widths)
    x = 0

    if quiet_zone:
        width += 20 * thickness
        x = 10 * thickness

    # Monochrome Image
    img  = Image.new('1', (width, height), 1)
    draw = ImageDraw.Draw(img)
    draw_bar = True
    for width in barcode_widths:
        if draw_bar:
            draw.rectangle(((x, 0), (x + width - 1, height)), fill=0)
        draw_bar = not draw_bar
        x += width

    return img