package com.enrichmeai.culvert.pdftext;

import org.apache.pdfbox.Loader;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.junit.jupiter.api.Test;

import java.io.IOException;
import java.io.InputStream;
import java.util.Arrays;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

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
    void publicKeyEncryptedPdfEscapesAsAnError() throws IOException {
        // Known gap, pinned so that a change to it is deliberate: PDFBox's BouncyCastle
        // dependency is optional, and an Error is not caught, so a PDF that uses public-key
        // encryption escapes extract() instead of returning null.
        byte[] publicKeyEncrypted = fixture("AESkeylength128.pdf");

        assertThatThrownBy(() -> PdfTextExtract.extract(publicKeyEncrypted))
                .isInstanceOf(NoClassDefFoundError.class)
                .hasMessageContaining("org/bouncycastle");
    }
}
