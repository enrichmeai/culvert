# Chapter 17 — CI/CD and the Coordinated Release

\index{CI/CD}\index{coordinated release}\index{Maven Central}\index{PyPI}

Culvert's first internal iteration had a pleasantly simple
publishing model: tag, push, watch the GitHub Actions `publish-libraries.yml`
fire, and ten minutes later six new packages appeared on PyPI. I will not pretend
that wasn't convenient. But it came with a sting I only properly felt after the
third time a tag fired on a Tuesday morning before I had finished the
corresponding migration note. The publish was automatic, irreversible, and the
version number was gone.

Culvert does not do that. The publish is gated. Nothing goes to Maven Central or
PyPI without a deliberate, Joseph-triggered action. That isn't timidity — it is
the direct consequence of having two ecosystems that must land *together*. A Java
release without its Python counterpart, or the reverse, would leave the framework
in a state where half its surface is published and the other half is not. That is
not a state I want `com.enrichmeai.culvert` or `culvert` on PyPI to ever be in.

## The CI workflow

The gate is a single workflow file: `.github/workflows/ci.yml`\index{ci.yml},
written in Sprint 15 (T15.1 / #77) and extended by T15.2 (#79) and T15.3 (#83).
It covers a polyglot reactor: thirteen Java modules, three Python GCP adapter
modules, a Testcontainers emulator integration tier, and an E2E structural gate.

The file opens with an honest comment that is worth quoting directly
(`.github/workflows/ci.yml`:14--16):

```
# NOTE — workflow is intentionally NOT enabled at the GitHub level.
# Re-enabling (gh workflow enable / UI toggle) is an ENGINEER trigger once
# the team is ready to resume Actions minutes.
```

I wanted that in writing. The workflow is correct and tested; it is simply not
consuming Actions minutes on a project that has not yet published. When the
coordinated release is ready, one command re-enables it. Until then, it exists as
a contract with our future selves.

### Job 1 — verify-module-list

The first job does something I wish I had done years earlier
(`.github/workflows/ci.yml`:79--125). It diffs the workflow's explicit Java
module matrix against the `<modules>` block in
`data-pipeline-libraries-java/pom.xml`. If a new module is added to the reactor
but its name is missing from the CI matrix, the job fails loudly. A module gap in
a matrix is the worst kind of CI blind spot — everything passes, nothing is
actually tested, and you discover the omission six months later during a release.
This job makes the omission a visible red build, not a silent pass.

Thirteen modules are enumerated (`.github/workflows/ci.yml`:97--110):

```
data-pipeline-core-java
data-pipeline-gcp-secrets-java
data-pipeline-gcp-bigquery-java
data-pipeline-gcp-gcs-java
data-pipeline-gcp-pubsub-java
data-pipeline-gcp-observability-java
data-pipeline-gcp-dataflow-java
data-pipeline-tester-java
data-pipeline-it-support-java
data-pipeline-contract-tests-java
data-pipeline-aws-s3-java
data-pipeline-azure-blob-java
data-pipeline-orchestration-java
```

The AWS and Azure skeleton modules are in there. They are minimal — a proof that
the contract seam works across cloud targets — but they must compile and their
tests must pass like everyone else. There is no special treatment for "not fully
implemented yet."

### Job 2 — java-build matrix

Job 2 runs the full reactor in a fan-out matrix, one leg per module
(`.github/workflows/ci.yml`:133--182). Each leg uses `-pl <module> -am` so Maven
only builds the specific module and its inter-module dependencies — not the whole
reactor every time. The matrix is set with `fail-fast: false`
(`.github/workflows/ci.yml`:139), which means all thirteen legs report
independently. I find the default `fail-fast: true` maddening in multi-module
builds: one red module aborts the rest, and you go around again. With
`fail-fast: false` you get the complete picture in one run.

The Maven cache key is tied to a hash of all `pom.xml` files in the reactor
(`.github/workflows/ci.yml`:171):

```yaml
key: maven-${{ hashFiles('data-pipeline-libraries-java/**/pom.xml') }}
restore-keys: |
  maven-
```

The restore-key fallback (`maven-`) means a cold runner still benefits from any
prior cache entry. The first run is slow; subsequent runs are fast. The same key
and restore pattern is reused by the IT and E2E jobs so all three tiers share a
warm cache.

Surefire's defaults exclude `*IT.java` — integration tests stay out of this tier.

### Job 3 — python-tests

Three Python GCP adapter modules run in a parallel matrix
(`.github/workflows/ci.yml`:193--238):

- `data-pipeline-gcp-bigquery`
- `data-pipeline-gcp-gcs`
- `data-pipeline-gcp-pubsub`

The install order matters (`.github/workflows/ci.yml`:225--228): `data-pipeline-core`
goes in first as a local editable install, then the adapter. This is deliberate —
`data-pipeline-core` is not on PyPI yet, and we cannot let pip try to fetch it
from the index. Installing it locally in editable mode (`-e`) pins it to the
working tree.

`data-pipeline-orchestration` is excluded pending tech-debt #88: a test file
references an Airflow 3.x import path that does not exist under the pinned
Airflow 2.9.x. A `pytest.skip()` guard is in place, but the module cannot be
collected cleanly on a bare CI runner without Airflow installed. The fix is
tracked; the exclusion is documented at the top of the workflow file
(`.github/workflows/ci.yml`:29--38) rather than left as a silent gap.

### Job 4 — java-it (emulator ITs)

This tier was added in T15.2 (#79) and is the one I find most satisfying
(`.github/workflows/ci.yml`:267--303). It runs `mvn -P it verify` against
Testcontainers-backed emulators for BigQuery, GCS, and Pub/Sub — and it requires
zero GCP credentials. No service-account JSON. No project ID. The ITs use
localhost emulator ports; they never reach a real GCP endpoint. Docker is
available on `ubuntu-latest` runners without any `services:` block; Testcontainers
auto-detects it.

The IT job only runs after `java-build` is green (`.github/workflows/ci.yml`:270:
`needs: java-build`). Unit-test failures abort the IT tier. This is intentional:
there is no value in running emulator tests if the module doesn't compile.

The `it` profile is activated in `data-pipeline-libraries-java/pom.xml`
(lines 239--259) by `maven-failsafe-plugin`, which picks up `*IT.java` suffixed
classes that Surefire's default pattern ignores. The two profiles — `it` for
integration tests, `release` for publishing — are additive and independent:
`mvn -P it verify` and `mvn -P release deploy` are separate commands with
separate concerns.

### Job 5 — e2e-gate (T15.3 / #83)

The E2E gate compiles and runs the standalone reference deployment
`deployments/reference-e2e-gcp` on DirectRunner with in-memory recording hooks
(`.github/workflows/ci.yml`:327--371). No Docker. No live GCP credentials. The
deployment's `pom.xml` has no parent in the reactor — the Culvert library
artefacts at `com.enrichmeai.culvert:0.1.0` are not on Maven Central yet, so the
E2E job installs them into the local `~/.m2` first, then runs the deployment
tests. The step comment spells this out
(`.github/workflows/ci.yml`:351--353):

```yaml
- name: Install Culvert library artifacts into local Maven repo
  # The deployment is standalone (not in the reactor), so its dependencies
  # are not built as a side-effect of the reactor build.
```

One test is intentionally left disabled in the E2E suite — the live GCS
quarantine IT — because enabling it would require Docker inside this job. That is
flagged as the remaining open DoD box for the architect to verify.

### Job 6 — ci-gate

A single status-check job that collects all four required jobs
(`.github/workflows/ci.yml`:378--399):

```yaml
ci-gate:
  needs: [java-build, python-tests, java-it, e2e-gate]
  if: always()
```

The `if: always()` means the gate job runs even when upstream jobs fail — so it
can report exactly which leg caused the problem, rather than showing as "skipped"
on the PR status. Branch protection registers only `ci-gate` as the required
check. Add new jobs, wire them into `needs:` here, and the PR merge contract
updates automatically.

## The release model

The predecessor auto-published on tag push. Culvert does not. The reason is the
coordinated gate.

`docs/framework-evolution/13-python-parity-release.md` (lines 34--48) makes the
model explicit:

```
Java 0.1.0 (built, frozen)  ─┐
                             ├─►  coordinated 0.1.0  ──►  Maven Central + PyPI (culvert), together
Python parity (this epic)  ──┘
```

Java is at `0.1.0` — built, tagged `java-0.1.0`, frozen. It does not publish
on its own. The tag exists to prevent the Java side from silently drifting while
the Python parity work (Waves A through D) catches up. When Python is ready —
contracts reconciled, adapter parity achieved, distributions renamed to `culvert`
— both sides publish together, or neither does. The version number `0.1.0` will
appear on Maven Central and PyPI simultaneously. There will be no window where
`pip install culvert` fails because the Java artefacts are already out but the
Python wheel is not.

### The Maven side

The `release` profile in `data-pipeline-libraries-java/pom.xml` (lines 261--291)
is the mechanism:

```xml
<profile>
    <id>release</id>
    <build>
        <plugins>
            <plugin>
                <groupId>org.apache.maven.plugins</groupId>
                <artifactId>maven-gpg-plugin</artifactId>
                ...
                <!-- signs during the verify phase -->
            </plugin>
            <plugin>
                <groupId>org.sonatype.central</groupId>
                <artifactId>central-publishing-maven-plugin</artifactId>
                <version>0.5.0</version>
                <configuration>
                    <publishingServerId>central</publishingServerId>
                    <autoPublish>false</autoPublish>
                </configuration>
            </plugin>
        </plugins>
    </build>
</profile>
```

`autoPublish>false</autoPublish>` is the operative line. The
`central-publishing-maven-plugin` uploads the staged bundle to Sonatype's
Central Portal but holds it in the portal's review queue — it does not flip the
"publish" switch automatically. A human (me) has to log into
`central.sonatype.com`, inspect the staged bundle, and click Release. That is a
deliberate second gate after the Actions run.

The GPG passphrase, the Sonatype credentials, and the PyPI token are my secrets.
They are not in the repository. Dev-agents do not have them and cannot trigger a
release. This is not a process gap — it is the design.

### The Python side

PyPI trusted publishing (OIDC) is Wave D — the Actions publish job does not exist
yet (`docs/framework-evolution/13-python-parity-release.md`:79). When it lands,
the plan is OIDC / trusted publishing: the Actions job proves it is running on
the correct repository and branch by presenting an OIDC token; PyPI mints a
short-lived upload credential in response. No stored API token. No long-lived
secret to rotate.

The distribution name will be `culvert` (not `data-pipeline-*`), with import
shims from the old names kept for one release. The decision on whether to ship a
single `culvert` mega-package or `culvert` + `culvert-gcp-*` namespace
sub-packages is open — the recommendation is the split to keep install footprint
small and mirror the Maven module story, but Joseph decides before Wave D
(`docs/framework-evolution/13-python-parity-release.md`:148--152).

## Publishing and deploying are different things

The predecessor made this distinction clear, and Culvert inherits it. A library
publish creates a versioned artefact in a registry (Maven Central or PyPI); a
deployment runs infrastructure and pushes a Dataflow template. Conflating them
creates race conditions where a deployment consumes a published version that has
not yet propagated through the registry's CDN, and it creates an asymmetry where
a library fix requires a deploy cycle rather than a version bump.

The workflow file has no deploy steps. When Culvert's reference deployments
(`deployments/reference-e2e-gcp` and any future production deployments) need
their own Actions workflow, it will be a separate file. The `ci.yml` name is not
`ci-and-release.yml` for the same reason.

## Honest status

To be plain: nothing has been published.

`com.enrichmeai.culvert:*` does not exist on Maven Central. `culvert` does not
exist on PyPI. The `gcp-pipeline-*` packages — the predecessor — exist on PyPI
and will be deprecated-in-place when the coordinated release happens. They will
not be yanked in a way that breaks existing pinned installs.

The Java reactor builds and all unit tests pass. The Testcontainers IT tier
passes. The E2E gate passes on DirectRunner. The workflow file is correct. The
release profile in the POM is correct. What remains is Python parity (Waves C and
D), the Actions PyPI publish job, and the coordinated-release runbook in
`RELEASE.md` (Wave E).

The publish, when it happens, will be irreversible. PyPI version numbers cannot
be reused. Maven Central is immutable. That is exactly why the gate is human, not
automatic, and why it is mine to pull.

\begin{takeaways}
\textbf{Key takeaways}
\begin{itemize}
  \item The coordinated release model holds both ecosystems to a shared gate: Java \texttt{0.1.0} is built and frozen; it does not publish to Maven Central until Python parity (Wave D) is complete and both sides ship together.
  \item The CI workflow (\texttt{.github/workflows/ci.yml}) covers four tiers: a reactor module-list guard, a Java unit-test matrix, Python GCP adapter tests, and a Testcontainers emulator IT tier — all gated behind a single \texttt{ci-gate} required-status-check.
  \item The workflow is committed but intentionally disabled at the GitHub level until the team is ready to consume Actions minutes. One engineer command re-enables it.
  \item \texttt{autoPublish=false} in the Maven \texttt{release} profile means the Central Portal upload requires a manual review and release click — there is no automatic flip to production.
  \item PyPI publish will use OIDC trusted publishing (Wave D) — no stored API token, no long-lived secret. The GPG passphrase and all credentials remain Joseph-only.
  \item Publishing is irreversible. That is not a footnote; it is the architectural reason the gate is manual.
\end{itemize}
\end{takeaways}

\newpage
