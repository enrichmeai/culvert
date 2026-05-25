# Publishing Playbook — GCP Pipeline Framework Book & Medium Series

This is your go-to-market plan. Ship in this order; each step supports the next.

---

## Publishing entity

The book is published through your UK private limited company, not personally. This section explains the rationale and what you need to set up before anything goes live.

### Why the company route?

- **Tax.** Book income taxed at the Corporation Tax rate (currently 19–25%), not personal marginal Income Tax (up to 45% at higher rate). Legitimate expenses — design, software, hosting, ISBN fees — are deductible before the tax calculation.
- **IP chain.** The copyright, the Gumroad/KDP/Play Books accounts, and the payment flows all sit inside the company, keeping your personal and business IP cleanly separated. This matters if you ever license excerpts, hire a co-author, or sell the IP.
- **Brand.** Trading under an imprint (e.g. `<PUBLISHER> Press`) looks more credible to bookshops, libraries, and enterprise buyers than a personal name on the publisher line.

### Tax forms

US-routed platforms (Gumroad, Google Play Books, Amazon KDP) require a W-8 form to claim treaty relief on US withholding tax:

- **Company route → W-8BEN-E** (entity form). Do **not** file the individual W-8BEN.
- The UK–US tax treaty reduces withholding to 0% on royalties for UK companies. You will need your company's Unique Taxpayer Reference (UTR) and registered address.

### Author identity vs. publisher

- **Author:** Joseph Aruja — this appears on the cover, on Medium, in bios, everywhere.
- **Publisher:** `<PUBLISHER> Press` — fill in your chosen imprint name. This appears on the copyright page, the spine (if print), the KDP publisher field, and the back-cover ISBN block.

### Pre-launch checklist for company-route

Work through this before Week 0:

- [ ] Confirm your company UTR is active (check via HMRC online or your accountant).
- [ ] Open a **business bank account** linked to the company. Wise Business, Mettle, and Starling Business all support digital-product sellers and integrate cleanly with Gumroad payouts (GBP or USD). Monzo Business also works.
- [ ] **Buy an ISBN block** from Nielsen (the UK ISBN Agency). A block of 10 costs £149; individual ISBNs are £89 each. URL: [https://www.nielsenisbnstore.com](https://www.nielsenisbnstore.com). You need one ISBN per format (PDF/ebook, EPUB, paperback). Register them to your imprint name, not your personal name.
- [ ] **Pick your imprint name.** Conventional format: `<Company> Press` or `<Company> Publishing`. This goes on the copyright page in the book and in the KDP publisher field.
- [ ] **VAT position.** Book sales (physical and ebooks) are zero-rated for UK VAT — you do not charge VAT on them. You may still reclaim VAT on business expenses (design, software). Flag this with your accountant so it flows correctly through the accounts.

### Account setup — company vs. personal

| Platform | Account type | Notes |
|---|---|---|
| Gumroad | **Company name** | Use your company email and business bank for payouts. File W-8BEN-E. |
| Google Play Books Partner Center | **Company name** | Publisher name = imprint. File W-8BEN-E. |
| Amazon KDP | **Company name** | Publisher name = imprint. File W-8BEN-E. EIN not required — UTR suffices for treaty relief. |
| Medium Partner Program | **Personal** | Medium pays individuals only. Your Joseph Aruja Medium account is correct. Do **not** use a company account here. |

---

## Replacing placeholders

The Medium articles contain `[link — add before publishing]` placeholders — 11 instances across 8 files. Once your Gumroad listing (and optionally Play Books / Amazon) is live, run:

```bash
# Gumroad only (minimum viable)
./scripts/publish/insert-product-urls.sh \
    --gumroad https://yourname.gumroad.com/l/gcp-pipeline-book

# All three platforms
./scripts/publish/insert-product-urls.sh \
    --gumroad     https://yourname.gumroad.com/l/gcp-pipeline-book \
    --play-books  https://play.google.com/store/books/details?id=YOUR_ID \
    --amazon      https://www.amazon.co.uk/dp/YOUR_ASIN \
    --dry-run    # remove --dry-run to write changes
```

The script is idempotent: running it twice causes no harm. It reports a per-file count of replacements and exits 0 if nothing remains to substitute.

---

## Week 0 — Prep

- [ ] Read through `gcp-pipeline-book.md` end to end. Make notes on anything you want to soften, sharpen, or rephrase.
- [ ] Work through the "Pre-launch checklist for company-route" section above.
- [ ] Replace every `[link — add before publishing]` placeholder using `scripts/publish/insert-product-urls.sh` (see "Replacing placeholders" above).
- [ ] Replace every `![Image placeholder: ...]` in the Medium files with a real image. Options:
  - Generate diagrams with Excalidraw (free) or Whimsical.
  - Use Unsplash / Pexels for hero images (free, commercial use OK).
  - Ask a designer for a 3-piece cover set (cover, series banner, diagram).
- [ ] Confirm your PyPI package names match what's in the text. If any differ, do a find-and-replace.
- [ ] Set up a simple landing page (even a Notion doc works) that links all the channels. Include a buy link and a free-chapter sample.
- [ ] Turn on the Medium Partner Program in your **personal** Medium account settings (not a company account).

---

## Week 1 — Medium launch: Post 1

**Publish:** `medium/01-i-built-a-gcp-pipeline-framework.md`

Format notes:
- Paste the Markdown directly into Medium's editor — it handles `#`/`##`/`###`, code fences, and bold/italic.
- Title goes in the H1 slot. Subtitle goes in the kicker.
- Add 5 tags: `Google Cloud`, `Data Engineering`, `Python`, `Data Pipeline`, `Apache Beam`.
- Submit to **Better Programming**, **ILLUMINATION**, or a data-engineering publication for cross-posting reach. Some accept instantly; some take a day.
- Publish **Tuesday morning, 9am US Eastern**. Historically Medium's best slot for tech.
- Cross-post to LinkedIn (full text) and X (thread of key points, links back to Medium).
- Email it to anyone who's asked about the framework.

**Day-1 goal:** 500 views, 20 followers.

---

## Week 2 — Medium launch: Post 2

**Publish:** `medium/02-the-gcp-pipeline-gap.md`

Same ritual. Reference Post 1 explicitly ("In my last post I said..."). Cross-link.

**Day-1 goal:** 1,000 views (compounding).

---

## Week 3 — Gumroad launch

Open a Gumroad product at **$19**. Register the Gumroad **account in the company name** (see "Account setup — company vs. personal" in the Publishing entity section). File the W-8BEN-E before your first payout to avoid withholding.

- Upload the generated PDF.
- Set "pay what you want" with $19 minimum if you want to leave room for fans to pay more.
- Write the product page using the book's Preface as your description.
- Publisher field: use your imprint name (`<PUBLISHER> Press`).
- Medium post 3 goes live that week and includes the Gumroad link in the CTA.
- Post the Gumroad link to r/dataengineering, Hacker News Show HN, and relevant LinkedIn groups.

**Month-1 revenue expectation:** $200–$1,500 depending on Medium traction.

---

## Week 4 — Medium post 3

**Publish:** `medium/03-gcp-pipelines-zero-to-hero.md`

This post attracts more beginner readers. They're less likely to buy the book but very likely to follow you. Growth is the goal this week.

---

## Weeks 5–8 — Medium posts 4–8

One per week. The pattern:

- Tuesday publish.
- Tuesday–Thursday cross-post to LinkedIn + X.
- Thursday post a discussion starter ("what pattern does your team use?") on LinkedIn.

The posts in order:
- Week 5: `04-three-unit-deployment-model.md`
- Week 6: `05-mainframe-to-bigquery-beam.md`
- Week 7: `06-join-vs-map.md`
- Week 8: `07-composer-and-local-airflow.md`
- Week 9: `08-shipping-to-pypi.md`

Each one links back to the full book on Gumroad.

---

## Week 10 — Google Play Books

Register the **Google Play Books Partner Center account in the company name**. File W-8BEN-E. Upload the PDF (and an EPUB if you can generate one — pandoc can help).

- Price: **$9.99**.
- Publisher name: your imprint (`<PUBLISHER> Press`).
- Category: "Computers / Data Processing" and "Computers / Programming Languages / Python".
- Add at least 100 words of description; include the Table of Contents.
- Enable territories: start with US, UK, CA, AU, IN.
- Takes 24–72 hours to go live.

**Royalty:** 70% in standard list-price band — about $6.99 per sale.

---

## Week 11 — Amazon KDP

Register Amazon KDP **in the company name** and file W-8BEN-E. Kindle Direct Publishing. Upload the EPUB or .docx; they auto-convert.

- Publisher name: your imprint (`<PUBLISHER> Press`).
- ISBN: assign an ISBN from your Nielsen block (KDP will assign a free ASIN for the ebook; use your ISBN for the paperback).
- Enrol in **KDP Select** for 90 days (gives you free-days promotion + Kindle Unlimited royalties).
- Price: **$9.99** Kindle, **$24.99** paperback via KDP Print.
- Keywords: `GCP data pipeline`, `Apache Beam`, `dbt BigQuery`, `mainframe BigQuery`, `data engineering book`.
- BISAC codes: `COM021030` (Data Modeling), `COM051360` (Python), `COM051230` (Cloud Computing).

---

## Month 4 onwards — Sustain

- Write one deeper post per month (new patterns, reader questions, updates).
- Respond to every Medium comment within 24 hours; it's the strongest signal for Medium's algorithm.
- Update the framework; push v1.1.0. Write a "what's new" post.
- Collect an email list via Gumroad / Substack to own your audience.
- Consider a paid workshop or consulting slot at around 1,000 followers.

---

## Realistic revenue projection (first six months)

These are conservative.

- **Medium Partner Program:** $200–$2,000 cumulative.
- **Gumroad (PDF):** 50–300 sales × $19 = $950–$5,700 (minus ~10% fees).
- **Google Play Books:** 20–200 sales × $6.99 royalty = $140–$1,400.
- **Amazon KDP (ebook + paperback):** 30–300 sales × ~$5 average royalty = $150–$1,500.

**Total six-month:** $1,440–$10,600 if everything clicks. Upside is substantially higher if one of the posts hits Hacker News or gets picked up by a big newsletter.

None of those numbers are guarantees. Writing technical books is a slow compounding business, not a get-rich-quick one. But the framework is the real asset: every reader becomes a potential user, and every user potentially becomes a hire, a consulting lead, or an advocate.

---

## Tags to use on every Medium post

Use 5 tags per post (max allowed). Rotate to reach different slices:

Core tags (on every post): `Data Engineering`, `Google Cloud`.
Rotate: `Apache Beam`, `Airflow`, `dbt`, `Python`, `PyPI`, `Mainframe`, `BigQuery`, `Cloud Composer`, `Infrastructure as Code`, `FinOps`, `Data Governance`.

---

## Checklist before publishing anything

- [ ] Replace all placeholder links.
- [ ] Add at least one image per post.
- [ ] Run the Markdown through a spell-check.
- [ ] Have one trusted reader skim each post first.
- [ ] Double-check code samples copy-paste cleanly.
- [ ] Add your bio and a CTA at the bottom.

---

*Good luck. Build an audience by being useful. The money follows.*
