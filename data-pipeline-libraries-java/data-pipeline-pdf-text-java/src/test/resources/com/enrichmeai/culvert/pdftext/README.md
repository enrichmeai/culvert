# Test fixtures for PdfTextExtractTest

All of these are real PDFs (or a real non-PDF object stored as one), committed unchanged.
None was made for these tests.

| File | Bytes | SHA-256 | Source | Licence |
|---|---|---|---|---|
| `born-digital-kerala-hc-2024.pdf` | 15069 | `738a4622d1bda3e3f31cbcde276487c7a0312606d82da7a6ecde826623e36387` | `s3://indian-high-court-judgments/data/pdf/year=2024/court=32_4/bench=highcourtofkerala/KLHC010617582013_1_2024-03-27.pdf` | CC-BY-4.0, Dattam Labs |
| `image-only-sc-2018.pdf` | 252175 | `78e1c7b05861e8a105878d6c3f0f43039db5de4ad991916e9f56e46d0ccdcfd0` | `s3://indian-supreme-court-judgments/data/pdf/year=2018/regional/2018_3_689_695_HIN.pdf` | CC-BY-4.0, Dattam Labs |
| `docx-saved-as-pdf-sc-2012.pdf` | 32417 | `529a81e4dc523f377853dbad786b093ab0b991fcf9c8f1281074fca69be60e72` | `s3://indian-supreme-court-judgments/data/pdf/year=2012/regional/2012_2_492_511_HIN.pdf` (a Word .docx file under a .pdf key) | CC-BY-4.0, Dattam Labs |
| `close-doubles-bombay-hc-2020.pdf` | 23856 | `710a3105c36f4133b6edc001acdba1312017f2ac4bc2233dba07568775a0b5c9` | `s3://indian-high-court-judgments/data/pdf/year=2020/court=27_1/bench=hcaurdb/HCBM030263422020_1_2020-11-26.pdf` | CC-BY-4.0, Dattam Labs |
| `overprinted-bold-bombay-hc-2005.pdf` | 2507 | `bce982533efa286de998700f73923713bb14961ff9fbf5619a14db9e8ed68f20` | `s3://indian-high-court-judgments/data/pdf/year=2005/court=27_1/bench=newos/HCBM020000151975_1_2005-08-02.pdf` | CC-BY-4.0, Dattam Labs |
| `PasswordSample-128bit.pdf` | 8377 | `1919480aba35617d69a1f9e1dce30bbe6864b3906d5c136fd7a8837826f9f750` | Apache PDFBox 3.0.7, `pdfbox/src/test/resources/org/apache/pdfbox/encryption/` (user password `user`) | Apache-2.0 |
| `AESkeylength128.pdf` | 11591 | `4c9633e68c8a6ece14bc79ae997d44b24868d38d2beea182314807b51d925b7b` | Apache PDFBox 3.0.7, same folder (public-key encryption) | Apache-2.0 |

The five court files come from the Indian High Court Judgments and Indian Supreme Court
Judgments datasets on the AWS Registry of Open Data, managed by
[Dattam Labs](https://dattam.in) and licensed
[CC-BY-4.0](https://creativecommons.org/licenses/by/4.0/). They were picked from
a measurement sample of 2026-10-18 in which the same PDFBox 3.0.7 call recorded, in turn,
1271 characters of text, blank text, and a parse failure. Those are the results the tests
assert.

The two Bombay High Court files pin #288 from both sides. `close-doubles-bombay-hc-2020.pdf`
declares every glyph one em wide, and PDFBox's default overprint check dropped the second letter
of its "ff" and "ll" pairs. `overprinted-bold-bombay-hc-2005.pdf` prints its bold headings three
times a fraction of a point apart, so the check must still drop those copies.
