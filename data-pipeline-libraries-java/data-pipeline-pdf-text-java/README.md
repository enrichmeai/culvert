# data-pipeline-pdf-text (Java)

PDF-to-text extraction on Apache PDFBox 3, for an application and a pipeline that must
extract text the same way. Issue #275.

```xml
<dependency>
    <groupId>com.enrichmeai.culvert</groupId>
    <artifactId>data-pipeline-pdf-text</artifactId>
    <version>0.6.2</version>
</dependency>
```

```java
String text = PdfTextExtract.extract(pdfBytes);   // null means "no text"
```

## Contract

`PdfTextExtract.extract(byte[])` calls `Loader.loadPDF(bytes)`, then PDFBox's
`PDFTextStripper` with one change to its overprint check (below). It:

- returns the text of a PDF that has a text layer;
- returns `null` when that text is blank, as from a scanned, image-only PDF;
- returns `null` for input PDFBox cannot open or read: corrupt, truncated, not a PDF, empty,
  `null`, protected by a non-empty user password, or protected by public-key (certificate)
  encryption;
- never throws an exception. It catches `RuntimeException` as well as `IOException`, because
  PDFBox throws unchecked exceptions on corrupt input. A caller working through millions of
  documents can then record "no text" and move on, instead of re-queueing a document that will
  fail on every pass.

A PDF that uses **public-key encryption** makes PDFBox reach for BouncyCastle, an optional
dependency this module does not add, and that raises `NoClassDefFoundError`. It is the one `Error`
caught, so such a PDF returns `null` (since 0.6.1, #279; 0.6.0 let it escape). Other `Error`s, such as
`StackOverflowError` or `OutOfMemoryError` on pathological input, still escape.

PDFBox repairs a PDF that lost only its last bytes, so it returns its text.

**Overprinted text (since 0.6.2, #288).** Some PDFs print a glyph two or three times a fraction of
a point apart, to fake bold type. PDFBox drops such a copy when the same character already sits
within a third of the glyph's declared width. A font that declares every glyph one em wide (seen in
Bombay High Court judgments of 2019 to 2024) then loses real doubles: "offence" reads "ofence",
"allegations" reads "alegations". This module caps that reach at a fifth of an em. Across 2,600
court PDFs, overprint copies sat under 0.05 em and real doubles at 0.25 em or more. The change
affected 27 of the 2,600: 16 Bombay judgments regain their doubled letters, and 11 others gain one
to five characters (`%`, an em dash, a space, or a `क` in text that was already garbled).

## Not in this module

OCR, detecting garbled text, time limits and byte caps, and a Beam `DoFn`. The caller owns
those.

## Dependencies

`org.apache.pdfbox:pdfbox:3.0.7` (with its own `pdfbox-io`, `fontbox` and `commons-logging`) and
`org.slf4j:slf4j-api`. Nothing else: no Culvert module, no cloud SDK, no Beam.

## Tests

```bash
mvn -B -pl data-pipeline-pdf-text-java -am test
```

`PdfTextExtractTest` pins each case above on real PDFs. Where each fixture comes from, and its
licence, is in `src/test/resources/com/enrichmeai/culvert/pdftext/README.md`.
