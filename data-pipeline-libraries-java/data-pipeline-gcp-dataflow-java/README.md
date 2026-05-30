# data-pipeline-gcp-dataflow (Java)

Google Cloud Dataflow adapter for the Culvert framework. Provides `DataflowPipeline`, the GCP implementation of the cloud-neutral [`Pipeline`](../data-pipeline-core-java/src/main/java/com/enrichmeai/culvert/contracts/Pipeline.java) contract — plus Beam-bridging utility methods (`buildBeam` / `runOnDataflow`).

## Status

**Version 0.1.0 — Sprint 2 deliverable** (issue [#25](https://github.com/enrichmeai/culvert/issues/25)).

## Install (Maven)

```xml
<dependency>
    <groupId>com.enrichmeai.culvert</groupId>
    <artifactId>data-pipeline-gcp-dataflow</artifactId>
    <version>0.1.0</version>
</dependency>
```

Pulls in `data-pipeline-core` plus Apache Beam SDK + Dataflow runner (pinned at `beam.version` = 2.55.0 to match the existing `mainframe-segment-transform-java` deployment).

## Contract satisfied

[`com.enrichmeai.culvert.contracts.Pipeline`](../data-pipeline-core-java/src/main/java/com/enrichmeai/culvert/contracts/Pipeline.java):

```java
public interface Pipeline {
    String name();
    List<PipelineStage> stages();
    void validate();
}
```

`DataflowPipeline` is a thin Pipeline implementation: it holds the stage list, exposes its name, and validates the graph (unique stage names, every input references an upstream output, no cycles, no self-loops, no duplicate outputs).

## Beam bridging (utility methods, beyond the contract)

```java
DataflowPipeline p = new DataflowPipeline("ingest-customers", List.of(
        readStage, transformStage, writeStage));

// Build a Beam pipeline with default options (no runner set).
org.apache.beam.sdk.Pipeline beam = p.buildBeam();

// Or with caller-supplied options (e.g. for the DirectRunner in tests).
PipelineOptions opts = PipelineOptionsFactory.create();
opts.setRunner(DirectRunner.class);
org.apache.beam.sdk.Pipeline localBeam = p.buildBeam(opts);
localBeam.run().waitUntilFinish();

// Or submit to Cloud Dataflow.
DataflowPipelineOptions dfOpts = PipelineOptionsFactory.as(DataflowPipelineOptions.class);
dfOpts.setProject("my-project");
dfOpts.setRegion("europe-west2");
dfOpts.setTempLocation("gs://my-bucket/temp");
PipelineResult result = p.runOnDataflow(dfOpts);
// result is typically a DataflowPipelineJob; .waitUntilFinish() blocks.
```

## Construction

One public constructor: `(String name, List<PipelineStage> stages)`. Throws `IllegalArgumentException` if name is blank or stages is empty; throws `NullPointerException` if either is null.

## Sprint-4 follow-up

The current `buildBeam()` returns a Beam Pipeline with NO transforms applied. Each Culvert `PipelineStage` carries an `execute(RuntimeContext)` method, but translating that into a Beam `PTransform` requires a runtime-context factory that doesn't exist yet. Sprint-4's auto-config layer will provide it; for sprint-2, the bridging method establishes the API surface and the validation logic.

## ServiceLoader registration

`src/main/resources/META-INF/services/com.enrichmeai.culvert.contracts.Pipeline` lists the impl. Same sprint-4 caveat as the other GCP adapters — the constructor takes name + stages, which can't be ServiceLoader-instantiated without a config layer.

## Errors

| Cause | Thrown |
|---|---|
| Null name or stages | `NullPointerException` |
| Blank name, empty stages | `IllegalArgumentException` |
| Duplicate stage name, orphan input, duplicate output, self-loop, cycle | `IllegalStateException` (from `validate()`) |
| Dataflow submission failure | Beam's exception (`DataflowJobException` or similar) |

## Testing

```bash
cd data-pipeline-libraries-java && mvn -pl data-pipeline-gcp-dataflow-java -am clean test
```

12/12 tests pass. Beam DirectRunner is the test driver — no real Dataflow needed.
