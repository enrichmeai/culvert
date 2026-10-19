# data-pipeline-pdf-text (Java)

PDF-to-text extraction on Apache PDFBox 3, for an application and a pipeline that must
extract text the same way. Issue #275.

```xml
<dependency>
    <groupId>com.enrichmeai.culvert</groupId>
    <artifactId>data-pipeline-pdf-text</artifactId>
    <version><!-- the first Culvert release that ships it --></version>
</dependency>
```

```java
String text = PdfTextExtract.extract(pdfBytes);   // null means "no text"
```

## Contract

`PdfTextExtract.extract(byte[])` calls `Loader.loadPDF(bytes)`, then
`new PDFTextStripper().getText(document)`. It:

- returns the text of a PDF that has a text layer;
- returns `null` when that text is blank, as from a scanned, image-only PDF;
- returns `null` for input PDFBox cannot open or read: corrupt, truncated, not a PDF, empty,
  `null`, or protected by a non-empty user password;
- never throws an exception. It catches `RuntimeException` as well as `IOException`, because
  PDFBox throws unchecked exceptions on corrupt input. A caller working through millions of
  documents can then record "no text" and move on, instead of re-queueing a document that will
  fail on every pass.

It does not catch `Error`s. The one to know about: a PDF that uses **public-key encryption**
escapes as `NoClassDefFoundError`, because PDFBox's BouncyCastle dependency is optional and this
module does not add it. A caller that must never fail on such a PDF can catch it, or add
`org.bouncycastle:bcprov-jdk18on` and `bcpkix-jdk18on` itself.

Two more cases:
- An encrypted PDF with an empty user password, as when only an owner password is set, opens,
  so its text is returned.
- A PDF that lost only its last bytes is repaired by PDFBox, so it returns its text.

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
