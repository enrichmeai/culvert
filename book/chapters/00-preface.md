# Preface

I wrote my first line of professional Java in February 2001 — a Java EE point-of-sale system on EJB 2.0 and JSP for a chain of retail discount stores. Eight years in, by 2009, I was at Wm Morrison Supermarkets, building Message-Driven Beans and BPEL processes on Oracle SOA Suite that pushed prices and promotions out of Oracle Retail Price Management, through the Oracle Retail Integration Bus, into a mainframe-backed merchandising system. We monitored it with custom HP OpenView alerts and ran reconciliation against Oracle AQ queues.

Nobody had a word for what we were doing yet. The phrase *data pipeline* hadn't escaped Silicon Valley. We called it *integration*, and it was the kind of work that ate weekends and produced incident reports written in passive voice.

I've been doing some version of that work ever since. Twenty-five years now. Different decade, different stack, same underlying job: get business-critical data out of the system that owns it, into somewhere it can be analysed — without losing rows, leaking PII, or blowing the budget.

The customers move around. **Banking** — HSBC, First Direct, M&S Bank, Allstate Insurance. **Government** — Home Office, GOV.UK, DWP, UKBA, and NHS Spine, where I was technical lead on Release 7A and built the SAML single-sign-on framework reused across every Spine module. **Retail** — Morrison's, twice (the Evolve mainframe-integration programme in 2009, then the Ocado Direct Delivery and Store Pick projects in 2016–2017). **Transport** — Smart Ticketing on Greater Manchester Metrolink with Worldline; ITSO smart cards and contactless EMV under PCI-DSS. **Automotive** — Jaguar Land Rover, also twice; the VCS event-framework migration to GCP, and now the Subscription Control Platform. **Travel** — migrating Booking.com's booking engine to AWS EKS; Thomas Cook's iTour Connect. **Betting** — Caesars Digital and William Hill (UK and US), terminal estates and back-office. **Most recently**, a financial-services client where I'm currently Senior Lead Engineer on a mainframe-to-cloud migration.

Along the way I contributed to the Java standards as a member of the JSR 255\index{JSR 255} (JMX) specification group — a long way of saying I've spent a lot of years thinking about what makes a *good interface* hold up under production load.

The platforms keep changing. Oracle SOA Suite. JBoss EAP. WebLogic. Spring. Dropwizard. AWS EKS. GCP. Kubernetes. The hard parts never do. Audit trails. Cost tracking. Error classification. Schema drift. Reconciliation. The stuff that makes a pipeline trustworthy rather than merely functional.

Around year fifteen I noticed something embarrassing: every team I joined was rebuilding the same scaffolding. Different language, different cloud, same scaffolding. By year twenty I was tired enough of writing it from scratch that I sat down and built a proper framework. I started with GCP — a single real cloud, a concrete target, no hand-waving. Then something interesting happened: when I looked hard at what I'd built, most of the code was already cloud-neutral. The contracts — the language-neutral interfaces that every adapter implements — were the seam. Extract those, and the GCP implementation becomes the *first* implementation rather than the only one. That extraction became **Culvert**. The repo this book is a tour of is `culvert`, built at 0.1.0 and held; the GCP-only first iteration is retired, its lessons now the origin arc of what you are reading.

The design language was deliberate. I had spent a decade on Spring projects and watched what Spring Framework had done for the JVM: a small framework-agnostic core, opinionated modules clipped on around it, conventions over configuration, escape hatches when you needed them. The result was an industry. Culvert borrows that DNA without apology. There is a Spring-shaped framework hiding underneath the dbt models and the Beam jobs, and I think it deserves to be called that.

This book is the long-form version of the conversation I've been having for the last decade with senior engineers, architects, and CFOs at banks and government departments. It's the answer to the question they always end up asking: *"How do we do this in a way we can defend to a regulator and afford to operate?"*

**Who I wrote this for.** Three kinds of reader:

- You're newish to GCP and you want to learn how pipelines actually work in the real world. Start at Chapter 1 and go in order. Chapters 2 and 3 give you the landscape and the basics before we touch any framework code.
- You're an experienced engineer and you just want the patterns. Skip to Chapters 4 through 12. That's where the meat is.
- You're an architect trying to decide whether to adopt this thing or build your own. Read Chapters 2, 19 (the honest code review) and Appendix C (the cost model). That'll tell you most of what you need.

**What this book isn't.** It's not a certification cram. It's not a GUI walkthrough. I assume you've clicked around the Google Cloud Console before and you know what BigQuery is, even if you've never written a Dataflow job.

**What you'll be able to do by the end.** Take an unfamiliar mainframe extract and design an ingestion pipeline for it in an afternoon. Add a new entity to a running Culvert deployment in less than a working day. Diagnose a failed run end-to-end using only an audit trail and a run ID. Justify, with real numbers, whether your team should be paying for Cloud Composer. Read a deployment workflow and tell what it actually does. Argue convincingly with your security team about IAM, KMS, and lifecycle policies.

**A note on opinions.** When I tell you that audit-trail propagation matters, or that Composer is overkill below a certain scale, that's not theory. That's two decades of post-incident reviews talking. The opinions in this book are *empirically* what survives in production, calibrated across eight industries and the regulatory regimes that go with them — FCA\index{FCA}, PCI-DSS\index{PCI-DSS}, GOV-grade, NHS data, ITSO\index{ITSO} transport, US gaming.

**A note on honesty.** Chapter 19 is a code review of my own framework. I've tried to make it useful rather than flattering. Culvert has real strengths and real weaknesses, and I'd rather you understood both before adopting it. If this book helps you build something better, that's a win I'll happily take.

Where I could use a story instead of a bullet list, I did. Where I could cut a paragraph, I cut it. If something's still clunky, tell me and I'll fix it in the next edition.

Right. Coffee in hand? Let's go.

Joseph Aruja, Leeds, 2026

\newpage
