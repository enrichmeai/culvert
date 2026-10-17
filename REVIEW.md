# Review instructions

Culvert is a data-pipeline framework released on PyPI (`culvert`) and Maven Central
(`com.enrichmeai.culvert:*`), in Java and Python at one version. A silent wrong answer in a pipeline
costs more than a loud failure, so review for correctness first. `CLAUDE.md` holds the project rules;
this file only says what to flag, how severely, and what to skip.

## What Important means here

Reserve 🔴 Important for a finding that would ship a wrong result, lose or double data, or break a user:

- Incorrect logic, a null/None or empty case that crashes or is silently treated as valid, a resource
  that is never closed, a Beam `DoFn` capturing a non-`Serializable` field.
- A failure that is swallowed: a write, publish, load or reconciliation whose error is caught and not
  raised or logged at ERROR, or a run recorded as SUCCEEDED when something it owns failed.
- Anything that loads or writes data and is not idempotent on a re-run, or a retry that can write twice.
- Java/Python drift: a contract (`docs/CONTRACT.md`, the Java interfaces in `data-pipeline-core-java`, the
  Python Protocols in `data-pipeline-core`) changed in one language and not the other, or an implementer or
  test fake of a changed type left on the old shape.
- A change to a public type or a released behaviour with no `CHANGELOG.md` `[Unreleased]` entry, or a
  breaking change with no `MIGRATION.md` section.
- A secret, credential or real project id committed; a `[deploy]` or `[publish:deploy]` marker in a commit
  message; `enable_composer = true`.
- Anything from the book (`enrichmeai/culvert-book`): this repository is public.

Style, naming, refactoring suggestions and missing docstrings are 🟡 Nit at most.

## Cap the nits

Report at most five Nits per review.

## Do not report

- Formatting and import order. Report a flake8 error only when it is a real bug (an undefined name).
- Generated or vendored files: anything under `target/`, `build/`, `dist/`, `*.egg-info/`, `_bmad/`,
  `_bmad-output/`, and any lock file.
- `docs/historical/`: it is deprecated in place on purpose.
- Test-only code that breaks a production rule on purpose (a fake that skips validation).

## Always check

- A behaviour change has a test that fails without it, in each language it touches. A test that was
  weakened, skipped or deleted to get green is Important.
- A type shared by Java and Python changed the same way in both, with the same error messages where the
  other language's tests pin them.
- A fact the change alters (a count, a version, a "not yet" note, a status line) is updated everywhere it is
  stated, including READMEs and `docs/`. A stale statement left beside its replacement is a finding.
- An external API, CLI flag or config key the diff adds is used as that library's docs describe it, at the
  version the build pins.

## Evidence

A finding about behaviour needs a `file:line` citation from the source or a failing case, not an inference
from a name. A claim that two languages match cites both sides.
