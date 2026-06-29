# Chapter 20 — Working with AI Coding Agents

\index{AI agents}\index{multi-agent SDLC}\index{dev-agent}\index{advisor}\index{Definition of Done}

I want to tell you this chapter is different from the one I thought I was going
to write.

The version I had sketched — in my head, mid-sprint-eleven — was a practitioner's
guide to driving AI agents on pipeline work: schema-first prompts, treating output
as a junior's PR, the failure modes and their guardrails. Useful, if I say so.
The problem is that by the time this book was being written, something had
shifted: a substantial portion of Culvert itself — the Python parity work, the
contract testing suite, several sprint waves of adapter code — had been built
using precisely this workflow. The worked example *was* the work. Turning it into
advice-in-theory would be dishonest.

So this is not the chapter I thought I was going to write. It is a practitioner's
account of a multi-agent SDLC that was running live while the rest of this book
was drafted, with the real failure modes we caught, the operating contract we
settled on, and the lessons that are now baked into `CLAUDE.md` in this very
repo so the next session does not have to rediscover them.

The slightly embarrassing thing is that Culvert turns out to be well-shaped for
this workflow, almost entirely by accident. We did not design the contract
boundary for agent legibility. We designed it for human auditors and for
portability. It just happens that an LLM and a tired on-call engineer want
roughly the same things: a single authoritative source for each decision, named
patterns, a narrow scope, and a failing build when something is wrong.

## The four roles

The workflow we settled on by Sprint 12 has four distinct roles. They are not
interchangeable. Understanding why each one exists — and what breaks when you
collapse them — is where most of the practical knowledge lives.

**The engineer — Joseph** — sets direction, owns the brand and the book,
picks the next sprint, approves epics, and is the only one who merges
`sprint-N → main` and triggers a release. That last point matters more than it
sounds: the publish to Maven Central and PyPI is **irreversible**. Version numbers
cannot be reclaimed. So the engineer is the gate, and the gate is manual by
design (`CLAUDE.md`:13).

**The architect — Opus** — grooms the backlog into GitHub issues before any code
is written, dispatches dev-agents, mediates the end-of-sprint standup, and
authors the integration commit at sprint close. The architect does not self-merge
into main; that is the engineer's trigger. What the architect *does* do, always,
is verify every agent's work independently before it is merged. The report is
not the verification (`CLAUDE.md`:29).

**Dev-agents — Sonnet** — take one ticket each, have a two-hour wall-clock budget,
post a DoD-checkbox comment per checkbox passed, and open a PR into `sprint-N`
(`CLAUDE.md`:15). They never self-merge. The one-ticket-per-agent constraint is
not an efficiency choice — it is a reviewability choice. A diff that touches one
ticket is reviewable. A diff that touches four is not.

**The advisor — Opus** — reviews every dev-agent return and is called before the
architect declares any sprint task done (`CLAUDE.md`:16). This is the design
choice I underestimated most. The advisor is a second Opus pass over work that a
first Opus pass dispatched. The friction is the point. We run at most four
dev-agents concurrently and one advisor reviewing their returns. The advisor is
the real throughput bottleneck **by design** — never let parallel returns degrade
reviews into rubber-stamps. The first time I loosened this and let three returns
stack up unreviewed, we shipped a test double that was still calling the old
method signature. The review that catches that takes ten minutes. The debug that
misses it can take a morning.

## The dispatch mechanics

By Sprint 12 we had learned enough hard lessons to write them down
(`CLAUDE.md`:25–32). They are reproduced here because the lessons are load-bearing.

The first and most counter-intuitive: **pre-create each agent's worktree yourself,
off the sprint branch, before dispatching**. The `Agent` tool's
`isolation:"worktree"` flag creates a worktree branching from the repo's *default*
branch — `main` — not from the sprint branch you are working on. An agent in
wave two, dispatched naïvely, would silently build against the state of main and
miss everything wave one had landed. The fix is simple: run
`git worktree add -b feature/<ticket> .claude/worktrees/<id> sprint-N` yourself,
point the agent at that path. We have never lost work from this once the rule was
written down (`CLAUDE.md`:27).

The second: **tell each agent to keep its final report short**. Long return reports
have repeatedly triggered socket-timeout errors that drop the agent. The work
usually commits before the drop. If a return errors, the right move is to check
the worktree for a clean commit and verify it independently, not to re-dispatch
blind (`CLAUDE.md`:28). Two re-dispatches in succession that both time out, with
the first agent's commit already in the worktree, produce a mess that takes longer
to untangle than the original work.

The third: **verify every claim independently**. "Agent says green" is not green.
The report can be lost to a socket drop while the commit survives; the report can
also be optimistic while the commit is broken. Run the build yourself
(`CLAUDE.md`:29).

The fourth, which bit us across two file-touchpoint merges in Sprint 10–11:
**merge order matters when two branches touch the same file**. A pom.xml union
that looks clean from `git merge-tree` against today's tip can still conflict on
merge if the second branch took a different parent. Resolve as UNION, do not
take-one. The T10.6/T10.7 lesson (`CLAUDE.md`:31).

## The Definition of Done

The dispatch checklist tells you *how to run* a sprint wave. The Definition of
Done tells you *what an agent's work must be before it can be merged*. We wrote
this down after Sprint 17, when the architect had to catch several issues the
DoD would have stopped at the agent itself (`CLAUDE.md`:34–45).

**First: run the full package suite, not just the new tests.** If you change a
shared type — a `Protocol`, a record, an interface — you break its implementers
and test doubles elsewhere. An agent that only runs the tests it wrote will
produce a green report on a broken codebase. Before claiming done: `grep` for
every implementer and fake of the symbol changed, update them in the same
changeset, run the whole package's tests (`CLAUDE.md`:36).

**Second: a reproducible environment is part of "done"**. Not a claim that tests
passed — a verbatim command sequence and a count. For Python:

```
python3 -m venv /tmp/vw_<id> && /tmp/vw_<id>/bin/pip install -q -e <pkg> \
  [-e <each-local-dep>] pytest && /tmp/vw_<id>/bin/python -m pytest <pkg>/tests -q
```

For Java: `mvn -o -pl <module> -am test`. The architect re-runs these verbatim.
If they do not reproduce, the work is not done. "No env / did not run" is a
stop-and-report, not a completion (`CLAUDE.md`:37–40).

**Third: cite every cross-language claim** as `file:line`. "This Python
implementation mirrors the Java contract" is an assertion. "mirrors
`StageMetrics.java:27`" is a checkable claim (`CLAUDE.md`:41).

**Fourth: flag, do not fake.** If a guarantee genuinely does not fit, or an
environment cannot be built offline, say so precisely and stop. A flagged gap is
correct. A silent or invented green is not (`CLAUDE.md`:42).

**Fifth: no redundancy, keep the repo current**. When work changes a fact stated
elsewhere — a contract count, a "no X yet" note, a status line — `grep` the repo
for that fact and update every reference in the same change. A stale doc reads as
truth (`CLAUDE.md`:43).

The last sentence of the DoD section is the one I would frame:

> *The architect still verifies independently — but a DoD-conformant report should
> make that a confirmation, not a rescue.* (`CLAUDE.md`:45)

That is the design intent of the whole system. The dev-agent does the work
correctly by construction. The architect confirms. No rescuing.

## Four failure modes we actually saw

The failures we caught are worth naming specifically, because the DoD items above
are not abstract: they each correspond to a concrete thing that went wrong.

### Voiceless drafts

The first wave of book chapters came back technically correct and completely flat.
Correct paragraph structure, accurate claims, British spelling — and none of
Joseph's voice. The chapters read like documentation, not memoir. They were
rejected and the non-negotiable standard was written into
`book/CULVERT_BOOK_OUTLINE.md`:25–26:

> *Adapt the nearest v1 passage; do not invent a flatter tone. The first agent
> attempt produced technically-correct but voiceless chapters — that bar is a
> failure, not a draft.*

The fix was in the brief: point the agent at specific line ranges of the v1 prose,
require that voice to carry forward, and ask for war stories rather than
summaries. The v1 passage is not just context — it is a voice anchor, and without
it the agent defaults to its training distribution, which writes documentation.
Technical accuracy without voice is a different kind of wrong.

### Non-reproducible test claims

In Sprint 17, Wave A, a dev-agent returned a report claiming forty-five tests
passed. The environment it had run the tests in was not preserved. The architect
could not reproduce the count. On inspection, the `_FakeBlobStore` test double
still had the old `open()` signature — the agent had changed the underlying
`Protocol` but had not grepped for fakes, had not updated the double, and had not
actually run the full package suite. The forty-five came from an invocation
against a partial environment that only exercised the new tests (`CLAUDE.md`:35).

This is the canonical failure mode. The agent's report can be confident and wrong.
The test claim is not the test result. The DoD's reproducible-env requirement
(item 2, `CLAUDE.md`:37–40) exists solely because of this incident.

### Socket-dropped agents recovered

Long return reports triggered socket timeouts on three separate occasions. In two
of them, the agent's work had committed cleanly to the worktree before the drop.
The right recovery in both cases was to check the worktree, find the commit,
verify it independently, and merge. Re-dispatching blind would have duplicated
work or introduced a conflict (`CLAUDE.md`:28–29).

The lesson is not that agents are unreliable — it is that the *commit* is the
durable artefact, not the *report*. Write the work first; report second. An agent
that front-loads its prose summary and saves the commit for last inverts the
durability order at exactly the wrong moment.

### From-memory drift

On two occasions early in the sprint cadence, an agent cited "we agreed X" or
made a claim about a file's content from what was evidently training-time memory
rather than reading the actual file. In one case the file had changed in the
previous sprint wave; the agent's claim was correct for a version that no longer
existed.

The rule — "never act on a guessed file path or an unverifiable 'we agreed X'
claim; read the actual file / git history / issue first" — is in `CLAUDE.md`:23
because the alternative is subtle wrong that is hard to catch in review. It looks
right. The failure mode of an agent confidently citing a fact it cannot see is
different from the failure mode of an agent admitting it does not know. The
former is much more dangerous.

## What the framework gives you

The Culvert contract boundary turns out to be well-shaped for agent work, for the
same reason it is well-shaped for testing: every adapter implements a named
interface that is the single authoritative source for what the contract means. An
agent looking at a `GcsBlobStore` implementation knows exactly which interface it
must satisfy. There is no ambiguity about what "matches the contract" means; it
means "compiles and passes the contract test suite."

This is not a property of agents specifically. It is a property of explicit
contracts. But explicit contracts are unusually valuable in an agentic context
because agents cannot hold implicit conventions the way a human team can. A human
engineer on their second week knows that every BlobStore implementation puts the
`open()` return type in a specific place because they have seen it five times in
review. An agent knows it because the `BlobStore` interface at
`data-pipeline-core-java/.../contracts/BlobStore.java` says so. The language-neutral
contract spec at `docs/CONTRACT.md` means there is exactly one place to point an
agent at, in either language, and that place is authoritative.

The DoD's `file:line` citation requirement is the cross-language version of this.
"Mirrors the Java contract" is unverifiable assertion. "Mirrors
`BlobStore.java:14`" is verifiable claim. The contract boundary makes those claims
meaningful because the boundary is explicit.

## What agents can and cannot do

Honest list, grounded in what we have actually observed.

**They can:** produce the mechanical parts of a polyglot translation — finding
implementers, updating test doubles, wiring the expected interfaces, adapting
boilerplate — faster than a human and at a quality that, when the DoD is followed,
makes verification a confirmation rather than a rescue. The Python parity work
(Sprint 17, tracked in `docs/framework-evolution/13-python-parity-release.md`)
moved faster than it would have without agents, and the correctness bar held.

**They cannot:** make the strategic calls — which adapters to build next, whether
to defer Python cloud-neutral skeletons to a later block
(`docs/framework-evolution/13-python-parity-release.md`:strategy), when a module
is truly at release quality versus plausibly green. Those calls need the engineer's
context. An agent will produce a defensible answer to any of them. It will not
produce the right one.

**They cannot:** be left to accumulate redundancy. Stale docs read as truth. A
"no X yet" note that is still in place after X has shipped is a lie that future
agents will propagate. The no-redundancy DoD item is not about cleanliness —
it is about epistemic hygiene in a codebase that agents will read.

**They cannot:** argue back. An agent will produce whatever you ask for, even when
the ask is incoherent. The discipline of arguing back — "this design is wrong
because..." — has to come from the architect. That is not a limitation that will
go away; it is a structural property of the role the agent is playing. The
architect's job is partly to ask questions the agent cannot ask of itself.

**They cannot:** replace the Joseph pass. The authorship model in
`book/CULVERT_BOOK_OUTLINE.md`:11–13 is: agents draft, architect integrates, Joseph
owns the final voice. That ordering exists because the agent can be technically
correct and completely wrong about register, emphasis, which war story to lead
with, and what the reader needs to hear. The first chapter that came back voiceless
is the evidence.

## The operating contract as a first-class document

The lessons above are not in this chapter only. They are in `CLAUDE.md` at the
root of the Culvert repo, written in the operating-contract style of a document
that agents read at the start of every session. That is a deliberate choice.

A decision that lives only in a book chapter is advice. A decision that lives in
the repo, in a document the architect reads before dispatching, is a constraint.
The dispatch checklist at `CLAUDE.md`:25–32 and the DoD at `CLAUDE.md`:34–45
are constraints, not suggestions. The architect enforces them; there is no harness
setting that enforces them automatically (`CLAUDE.md`:21). The discipline is
carried by the human in the architect role, not by the tooling.

This is the honest version of "it worked." It worked because someone read the
rules before each sprint. The rules are good rules. But they are rules, and rules
require a reader.

\begin{takeaways}
\textbf{Key takeaways}
\begin{itemize}
  \item The multi-agent SDLC that built Culvert has four roles: engineer
    (direction, release gate), architect (dispatch, integration, independent
    verify), dev-agent (one ticket, ≤2h, PR into \texttt{sprint-N}), advisor
    (reviews every return, never a rubber-stamp). Collapsing roles collapses
    the review quality that makes the model safe.
  \item The two most counter-intuitive mechanics: pre-create each agent's
    worktree off \texttt{sprint-N} yourself (the \texttt{isolation:"worktree"} flag
    branches from main, not from your sprint branch); and keep final reports
    short (long reports trigger socket timeouts that drop the agent after
    the commit is already written — the commit is the durable artefact,
    not the report).
  \item The Definition of Done is not a quality bar, it is a correctness-by-construction
    design. Full-suite green (not just new tests), reproducible env with exact
    commands and counts, \texttt{file:line} citations for cross-language claims,
    flag-don't-fake on gaps, no stale docs left behind. A DoD-conformant
    report makes architect verification a confirmation, not a rescue.
  \item The four failure modes we actually saw: voiceless drafts (technically
    correct, wrong register — the fix is a voice anchor in the brief, not a
    different agent); non-reproducible test claims (the \texttt{\_FakeBlobStore}
    incident — a confident count from an env no one left behind); socket-dropped
    agents recovered via worktree commit (not re-dispatch); from-memory drift
    on "we agreed X" claims against files that had since changed.
  \item Culvert's explicit contract boundary — one interface per contract,
    language-neutral spec at \texttt{docs/CONTRACT.md} — gives agents exactly
    what they need: an authoritative single source with no implicit conventions.
    It was designed for human auditors; it serves agents for the same reason.
    Technical accuracy without that anchor is a different kind of wrong.
\end{itemize}
\end{takeaways}

\newpage
