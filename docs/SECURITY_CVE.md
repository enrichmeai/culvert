# Culvert — Dependency CVE Scan Notes

T16.2 (sprint-16, issue #106). IAM notes are in [`SECURITY_IAM.md`](SECURITY_IAM.md).

---

## 1. Scan Status — Deferred

The OWASP `dependency-check-maven` plugin is **not in the local Maven cache**
(the project uses `-o` / offline mode for CI). An online attempt was made:

```
mvn org.owasp:dependency-check-maven:check \
    -pl data-pipeline-gcp-secrets-java \
    --no-transfer-progress
```

Result: the plugin downloaded successfully but then began pulling the full NVD
dataset (~358 000 CVE records). Without an NVD API key this takes 30+ minutes and
is rate-limited. The run was stopped.

### How to run when online and unthrottled

```bash
# Recommended: obtain a free NVD API key first
# https://nvd.nist.gov/developers/request-an-api-key

export NVD_API_KEY=<your-key>

cd data-pipeline-libraries-java
mvn org.owasp:dependency-check-maven:check \
    -Dodc.nvdApiKey=${NVD_API_KEY} \
    -Dodc.formats=HTML,JSON \
    --no-transfer-progress
```

Reports will appear at:

```
<module>/target/dependency-check-report.html
<module>/target/dependency-check-report.json
```

To add the plugin permanently (so it runs in CI on the `check` lifecycle):

```xml
<!-- Add to data-pipeline-libraries-java/pom.xml <build><plugins> -->
<plugin>
  <groupId>org.owasp</groupId>
  <artifactId>dependency-check-maven</artifactId>
  <version>9.2.0</version>   <!-- latest stable as of mid-2024 -->
  <configuration>
    <nvdApiKey>${env.NVD_API_KEY}</nvdApiKey>
    <formats>
      <format>HTML</format>
      <format>JSON</format>
    </formats>
    <failBuildOnCVSS>7</failBuildOnCVSS>  <!-- fail on HIGH+ -->
  </configuration>
  <executions>
    <execution>
      <goals><goal>check</goal></goals>
    </execution>
  </executions>
</plugin>
```

---

## 2. Pinned Dependency Versions (as of T16.2)

These are the versions that need to be checked when the scan runs.
Flag any CVE hits against these GAVs for immediate triage.

| Module(s) | Dependency (GAV) | Pinned version | Risk notes |
|---|---|---|---|
| All GCP adapter modules | `com.google.cloud:libraries-bom` | **26.39.0** | GCP Java BOM. Manages `google-cloud-secretmanager`, `google-cloud-bigquery`, `google-cloud-storage`, `google-cloud-pubsub`, `google-cloud-monitoring`, `google-cloud-datacatalog`. Verify the component versions it resolves via `mvn dependency:tree`. |
| `gcp-dataflow` | `org.apache.beam:beam-sdks-java-core`, `beam-runners-google-cloud-dataflow-java`, `beam-runners-direct-java` | **2.55.0** | Apache Beam. Beam itself pulls a large transitive graph (Guava, Jackson, gRPC, Netty, etc.). Historically higher CVE density than the GCP client libs. **Prioritise scanning this module.** |
| `gcp-observability` | `io.opentelemetry:opentelemetry-bom` | **1.38.0** | OpenTelemetry Java BOM. Manages API + SDK. Relatively new library family; check for deserialization issues in the OTLP export path. |
| `gcp-observability` | `com.google.cloud.opentelemetry:exporter-trace` | **0.30.0** | GCP OTel trace exporter. Not under `libraries-bom`; pinned explicitly. |
| `gcp-observability` | `com.fasterxml.jackson:jackson-bom` → `jackson-databind` | **2.13.5** | Jackson 2.13.x series. Earlier 2.13.x patches carried deserialization CVEs (e.g. CVE-2022-42003, CVE-2022-42004 fixed in 2.13.4; 2.13.5 should be clean for the known chain). Confirm latest 2.13.x or upgrade to 2.16.x when the BOM allows. **Second priority after Beam.** |
| `gcp-observability` | `ch.qos.logback:logback-classic`, `logback-core` | **1.4.14** | Logback 1.4.x. CVE-2023-6378 (denial-of-service via serialisation, CVSS 7.5, patched in 1.4.14 itself) should be resolved. Verify 1.4.14 is the latest 1.4.x patch and that no newer issues affect it. |
| `gcp-observability` | `net.logstash.logback:logstash-logback-encoder` | **7.2** | Logstash Logback encoder. Depends on Jackson; keep in sync with jackson-bom. |
| All test modules | `org.testcontainers:testcontainers-bom` | **1.19.8** | Test-scope only. Docker-in-Docker surface; less critical for production. |
| `core`, all modules | `org.junit:junit-bom` | **5.10.2** | Test-scope only. |
| All | `org.mockito:mockito-core`, `mockito-junit-jupiter` | **5.11.0** | Test-scope only. |
| All | `org.assertj:assertj-core` | **3.25.3** | Test-scope only. |
| All | `org.slf4j:slf4j-api` | **2.0.13** | Logging API only; CVE exposure is low (no implementation bundled). |

### Priority order for triage when scan runs

1. **Beam 2.55.0 transitive graph** — largest surface, historically most hits.
2. **jackson-databind 2.13.5** — confirm no open deserialization CVEs remain.
3. **logback-classic 1.4.14** — confirm CVE-2023-6378 is resolved.
4. **libraries-bom 26.39.0 component versions** — run `mvn dependency:tree` to see resolved versions and check against NVD.
5. Test-scope dependencies (Testcontainers, Mockito, JUnit) — lowest urgency.

---

## 3. Known-Clean Observations (without scan confirmation)

These observations are **not CVE assertions** — they are context notes based on
known public disclosures as of June 2026. Always prefer the scan output.

- **logback 1.4.14**: CVE-2023-6378 (JNDI/serialisation DoS) was patched in 1.4.12.
  1.4.14 should be clean for that CVE; confirm no newer reports affect 1.4.x.
- **jackson-databind 2.13.5**: The polymorphic deserialization chain CVEs (CVE-2022-42003,
  CVE-2022-42004) were fixed in 2.13.4; 2.13.5 added further patches. The 2.13.x line
  is in maintenance mode — upgrading the jackson-bom pin to `2.16.x` is advisable once
  downstream Beam/OTel compatibility is confirmed.
- **Beam 2.55.0**: No specific CVEs known at time of writing for this exact version, but
  Beam's transitive graph (Netty, gRPC, Guava) is historically the highest-risk surface.
  Run the scan against the `gcp-dataflow` module first.

---

*Last updated: T16.2 (sprint-16, issue #106). Re-run scan before each production release.*
