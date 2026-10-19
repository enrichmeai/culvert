package com.enrichmeai.culvert.pdftext;

import org.apache.pdfbox.Loader;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.text.PDFTextStripper;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.io.IOException;

/**
 * Plain PDFBox 3 text extraction: {@link Loader#loadPDF(byte[])}, then
 * {@link PDFTextStripper#getText(PDDocument)}.
 *
 * <p>The contract of {@link #extract(byte[])}:
 * <ul>
 *   <li>it returns the stripped text of a PDF that has a text layer;</li>
 *   <li>it returns {@code null} when the stripped text is blank, as from a scanned,
 *       image-only PDF;</li>
 *   <li>it returns {@code null} for input PDFBox cannot open or read: corrupt or
 *       truncated beyond repair, not a PDF at all, empty or {@code null}, or protected
 *       by a non-empty user password;</li>
 *   <li>it never throws an exception.</li>
 * </ul>
 *
 * <p>Two cases a caller might not expect:
 * <ul>
 *   <li>{@code Loader.loadPDF(byte[])} opens an encrypted PDF whose user password is
 *       empty, as when only an owner password is set, so its text is returned.</li>
 *   <li>PDFBox rebuilds a damaged cross-reference table where it can, so a PDF that
 *       lost only its last bytes still returns its text.</li>
 * </ul>
 *
 * <p>{@link Error}s are not caught, so they escape: {@code NoClassDefFoundError} on a
 * PDF that uses public-key encryption (PDFBox's BouncyCastle dependency is optional,
 * and this module does not add it), and {@code StackOverflowError} or
 * {@code OutOfMemoryError} on pathological input.
 *
 * <p>No OCR, no detection of garbled text, no time or size limit. A caller that
 * needs a time or byte cap applies it around this call.
 */
public final class PdfTextExtract {

    private static final Logger log = LoggerFactory.getLogger(PdfTextExtract.class);

    private PdfTextExtract() {
    }

    /**
     * Extracts the text of a PDF.
     *
     * @param pdfBytes the whole PDF file
     * @return the text, or {@code null} if the PDF yields no text or cannot be read
     */
    public static String extract(byte[] pdfBytes) {
        try (PDDocument document = Loader.loadPDF(pdfBytes)) {
            String text = new PDFTextStripper().getText(document);
            return (text == null || text.isBlank()) ? null : text;
        } catch (IOException | RuntimeException e) {
            // RuntimeException as well as IOException, deliberately: PDFBox throws unchecked
            // exceptions on structurally corrupt input, and to a caller the distinction is
            // meaningless — both mean "this document yields no text". It matters at corpus
            // scale: a caller that records an unreadable PDF as having no text moves on,
            // whereas an escaping exception marks the document failed, leaving it in the work
            // queue to be fetched and to fail again on every future pass, forever.
            log.warn("PDF text extraction failed: {}", e.toString());
            return null;
        }
    }
}
