package com.enrichmeai.culvert.pdftext;

import org.apache.pdfbox.cos.COSDictionary;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.pdmodel.PDPage;
import org.apache.pdfbox.pdmodel.documentinterchange.markedcontent.PDMarkedContent;
import org.apache.pdfbox.pdmodel.font.PDType3Font;
import org.apache.pdfbox.text.PDFTextStripper;
import org.apache.pdfbox.text.TextPosition;

import java.io.IOException;
import java.util.ArrayDeque;
import java.util.Deque;
import java.util.HashMap;
import java.util.Map;
import java.util.SortedMap;
import java.util.TreeMap;
import java.util.TreeSet;

/**
 * A {@link PDFTextStripper} whose overprint check never reaches further than a fifth of
 * an em (#288).
 *
 * <p>Some PDFs print a glyph two or three times a fraction of a point apart to fake bold
 * type. PDFBox drops such a copy when the same character already sits within a third of
 * the glyph's width. It takes that width from the font's {@code /Widths}. A font that
 * declares every glyph one em wide therefore makes PDFBox drop real doubles: an "ff" or
 * "ll" a quarter of an em apart reads as one letter ("ofence", "alegations").
 *
 * <p>This class turns PDFBox's own check off and runs the same check, with one change:
 * the tolerance is the smaller of PDFBox's and {@value #MAX_OVERPRINT_EM} of an em, the
 * em taken from the text rendering matrix rather than from {@code /Widths}. Across 2,600
 * court PDFs, overprint copies sat under 0.05 em and real doubles at 0.25 em or more.
 * A Type 3 font or a glyph with no Unicode keeps PDFBox's tolerance. Text inside an
 * {@code /ActualText} span is never checked, as in PDFBox.
 *
 * <p>Mirrors {@code PDFTextStripper.processTextPosition} in PDFBox 3.0.7: when PDFBox is
 * upgraded, compare this class with that method again. Not thread-safe: one instance per
 * document.
 */
final class OverprintTextStripper extends PDFTextStripper {

    /** The furthest apart, in ems, two identical glyphs may be and still count as one. */
    static final float MAX_OVERPRINT_EM = 0.2f;

    private final Map<String, TreeMap<Float, TreeSet<Float>>> seen = new HashMap<>();
    private final Deque<PDMarkedContent> markedContents = new ArrayDeque<>();
    private String actualText;

    OverprintTextStripper() {
        setSuppressDuplicateOverlappingText(false);
    }

    @Override
    protected void startPage(PDPage page) throws IOException {
        seen.clear();
        super.startPage(page);
    }

    @Override
    public void beginMarkedContentSequence(COSName tag, COSDictionary properties) {
        PDMarkedContent markedContent = PDMarkedContent.create(tag, properties);
        markedContents.push(markedContent);
        actualText = markedContent.getActualText();
        super.beginMarkedContentSequence(tag, properties);
    }

    @Override
    public void endMarkedContentSequence() {
        PDMarkedContent markedContent = markedContents.peek();
        if (markedContent != null) {
            if (markedContent.getActualText() != null) {
                actualText = null;
            }
            markedContents.pop();
        }
        super.endMarkedContentSequence();
    }

    @Override
    protected void processTextPosition(TextPosition text) {
        if (actualText == null && isOverprint(text)) {
            return;
        }
        super.processTextPosition(text);
    }

    private boolean isOverprint(TextPosition text) {
        String character = text.getUnicode();
        float x = text.getX();
        float y = text.getY();
        float tolerance = text.getWidth() / character.length() / 3.0f;
        float em = text.getXScale();
        if (!character.isEmpty() && em > 0 && !(text.getFont() instanceof PDType3Font)) {
            tolerance = Math.min(tolerance, MAX_OVERPRINT_EM * em);
        }

        TreeMap<Float, TreeSet<Float>> sameCharacter =
                seen.computeIfAbsent(character, k -> new TreeMap<>());
        SortedMap<Float, TreeSet<Float>> xMatches =
                sameCharacter.subMap(x - tolerance, x + tolerance);
        for (TreeSet<Float> xMatch : xMatches.values()) {
            if (!xMatch.subSet(y - tolerance, y + tolerance).isEmpty()) {
                return true;
            }
        }
        sameCharacter.computeIfAbsent(x, k -> new TreeSet<>()).add(y);
        return false;
    }
}
