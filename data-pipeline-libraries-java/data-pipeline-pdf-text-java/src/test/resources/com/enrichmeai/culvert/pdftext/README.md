# Test fixtures for PdfTextExtractTest

All of these are real PDFs (or a real non-PDF object stored as one), committed unchanged.
None was made for these tests.

| File | Bytes | SHA-256 | Source | Licence |
|---|---|---|---|---|
| `born-digital-kerala-hc-2024.pdf` | 15069 | `738a4622d1bda3e3f31cbcde276487c7a0312606d82da7a6ecde826623e36387` | `s3://indian-high-court-judgments/data/pdf/year=2024/court=32_4/bench=highcourtofkerala/KLHC010617582013_1_2024-03-27.pdf` | CC-BY-4.0, Dattam Labs |
| `image-only-sc-2018.pdf` | 252175 | `78e1c7b05861e8a105878d6c3f0f43039db5de4ad991916e9f56e46d0ccdcfd0` | `s3://indian-supreme-court-judgments/data/pdf/year=2018/regional/2018_3_689_695_HIN.pdf` | CC-BY-4.0, Dattam Labs |
| `docx-saved-as-pdf-sc-2012.pdf` | 32417 | `529a81e4dc523f377853dbad786b093ab0b991fcf9c8f1281074fca69be60e72` | `s3://indian-supreme-court-judgments/data/pdf/year=2012/regional/2012_2_492_511_HIN.pdf` (a Word .docx file under a .pdf key) | CC-BY-4.0, Dattam Labs |
| `PasswordSample-128bit.pdf` | 8377 | `1919480aba35617d69a1f9e1dce30bbe6864b3906d5c136fd7a8837826f9f750` | Apache PDFBox 3.0.7, `pdfbox/src/test/resources/org/apache/pdfbox/encryption/` (user password `user`) | Apache-2.0 |
| `AESkeylength128.pdf` | 11591 | `4c9633e68c8a6ece14bc79ae997d44b24868d38d2beea182314807b51d925b7b` | Apache PDFBox 3.0.7, same folder (public-key encryption) | Apache-2.0 |

The three court files come from the Indian High Court Judgments and Indian Supreme Court
Judgments datasets on the AWS Registry of Open Data, managed by
[Dattam Labs](https://dattam.in) and licensed
[CC-BY-4.0](https://creativecommons.org/licenses/by/4.0/). They were part of the
valuedocs-data-platform EXTRACT_TEXT Phase 0 sample (2026-10-18), and the statuses that
measurement recorded are the ones the tests assert: EXTRACTED (1271 chars), NO_TEXT_LAYER
and PARSE_FAILED.
