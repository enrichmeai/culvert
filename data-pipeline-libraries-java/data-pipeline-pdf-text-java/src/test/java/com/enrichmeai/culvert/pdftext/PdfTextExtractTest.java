package com.enrichmeai.culvert.pdftext;

import org.apache.pdfbox.Loader;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.junit.jupiter.api.Test;

import java.io.IOException;
import java.io.InputStream;
import java.util.Arrays;

import static org.assertj.core.api.Assertions.assertThat;

/**
 * Pins the {@link PdfTextExtract} contract on real PDFs. Where each fixture comes from,
 * and its licence, is in {@code src/test/resources/com/enrichmeai/culvert/pdftext/README.md}.
 */
class PdfTextExtractTest {

    private static byte[] fixture(String name) throws IOException {
        try (InputStream in = PdfTextExtractTest.class.getResourceAsStream(name)) {
            assertThat(in).as("fixture %s", name).isNotNull();
            return in.readAllBytes();
        }
    }

    @Test
    void bornDigitalPdfYieldsItsText() throws IOException {
        String text = PdfTextExtract.extract(fixture("born-digital-kerala-hc-2024.pdf"));

        assertThat(text)
                .startsWith("IN THE HIGH COURT OF KERALA AT ERNAKULAM")
                .contains("THE HONOURABLE MR.JUSTICE MURALI PURUSHOTHAMAN")
                .contains("WP(C) NO. 18565 OF 2013")
                .contains("The  writ  petition  is,  accordingly,  dismissed  as\ninfructuous.");
        // An earlier measurement of this file with the same PDFBox 3.0.7 call recorded
        // 1271 chars (String.length()).
        assertThat(text).hasSize(1271);
    }

    @Test
    void imageOnlyScannedPdfYieldsNull() throws IOException {
        // Eight pages of scanned images: PDFBox returns one line break per page, which is blank.
        assertThat(PdfTextExtract.extract(fixture("image-only-sc-2018.pdf"))).isNull();
    }

    @Test
    void unparseableInputYieldsNullWithoutThrowing() throws IOException {
        // A real corpus object: a Word (.docx) file stored under a .pdf name.
        assertThat(PdfTextExtract.extract(fixture("docx-saved-as-pdf-sc-2012.pdf"))).isNull();
    }

    @Test
    void truncatedPdfYieldsNullWithoutThrowing() throws IOException {
        byte[] whole = fixture("born-digital-kerala-hc-2024.pdf");

        assertThat(PdfTextExtract.extract(Arrays.copyOf(whole, whole.length / 2))).isNull();
        assertThat(PdfTextExtract.extract(Arrays.copyOf(whole, 1000))).isNull();
        assertThat(PdfTextExtract.extract(Arrays.copyOf(whole, 10))).isNull();
    }

    @Test
    void pdfMissingOnlyItsLastBytesStillYieldsItsText() throws IOException {
        // PDFBox rebuilds a lost cross-reference table, so a cut through the trailer is repaired.
        byte[] whole = fixture("born-digital-kerala-hc-2024.pdf");

        assertThat(PdfTextExtract.extract(Arrays.copyOf(whole, whole.length - 200)))
                .isEqualTo(PdfTextExtract.extract(whole));
    }

    @Test
    void pdfNeedingAUserPasswordYieldsNullWithoutThrowing() throws IOException {
        byte[] encrypted = fixture("PasswordSample-128bit.pdf");
        // The fixture is a readable PDF with a user password, not a broken file.
        try (PDDocument document = Loader.loadPDF(encrypted, "user")) {
            assertThat(document.isEncrypted()).isTrue();
        }

        assertThat(PdfTextExtract.extract(encrypted)).isNull();
    }

    @Test
    void emptyAndNullInputYieldNull() {
        assertThat(PdfTextExtract.extract(new byte[0])).isNull();
        assertThat(PdfTextExtract.extract(null)).isNull();
    }

    @Test
    void publicKeyEncryptedPdfYieldsNullWithoutThrowing() throws IOException {
        // PDFBox's BouncyCastle dependency is optional and this module does not add it, so
        // opening a PDF that uses public-key encryption raises NoClassDefFoundError inside
        // PDFBox (#279). extract() returns null for it, as for every other unreadable PDF.
        byte[] publicKeyEncrypted = fixture("AESkeylength128.pdf");

        assertThat(PdfTextExtract.extract(publicKeyEncrypted)).isNull();
        // A second call in the same JVM hits the already-failed class resolution.
        assertThat(PdfTextExtract.extract(publicKeyEncrypted)).isNull();
    }

    @Test
    void doubledLettersSurviveWhenTheFontDeclaresEveryGlyphOneEmWide() throws IOException {
        // #288. This court template's font declares every glyph 1000 units (one em) wide, so
        // PDFBox's overprint check, which allows a third of the glyph width, takes the second
        // of two close letters (3.6 to 4.2 points apart at 13 points: "ff", "ll") for a copy
        // and drops it. Before the fix this file read "ofence", "alegations" and so on.
        String text = PdfTextExtract.extract(fixture("close-doubles-bombay-hc-2020.pdf"));

        assertThat(text).contains(
                "offence", "Collector", "official", "allegations", "allowed", "sufficient",
                "illegally", "affairs", "Officer", "effect");
        assertThat(text).doesNotContain(
                "ofence", "Colector", "oficial", "alegations", "alowed", "suficient",
                "ilegaly", "afairs", "Oficer", "efect");
        // Doubles PDFBox already kept are unchanged.
        assertThat(count(text, "applications")).isEqualTo(6);
        assertThat(count(text, "oppose")).isEqualTo(2);
        // 0.6.1 gave 3211 chars. 3235 is every glyph on the page with no overprint
        // check at all: the 24 restored letters, and nothing else.
        assertThat(text).hasSize(3235);
    }

    @Test
    void overprintedBoldTextIsStillReadOnce() throws IOException {
        // The other side of #288: this template prints its bold headings three times, a
        // fraction of a point apart. Those copies must still be dropped.
        String text = PdfTextExtract.extract(fixture("overprinted-bold-bombay-hc-2005.pdf"));

        assertThat(count(text, "IN  THE HIGH COURT OF JUDICATURE AT BOMBAY")).isEqualTo(1);
        assertThat(count(text, "ORDINARY ORIGINAL CIVIL JURISDICTION")).isEqualTo(1);
        // PDFBox 3.0.7's own duplicate suppression gives 889 chars for this file.
        assertThat(text).hasSize(889);
    }

    private static int count(String text, String word) {
        return text.split(java.util.regex.Pattern.quote(word), -1).length - 1;
    }
}
