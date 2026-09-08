package com.enrichmeai.culvert.deployments.ingestion;

import org.apache.beam.runners.dataflow.options.DataflowPipelineOptions;
import org.junit.jupiter.api.Test;

import java.util.HashMap;
import java.util.Map;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatCode;

/**
 * Regression tests for the Dataflow options pass-through.
 *
 * <p>The defect: {@code main} built options with
 * {@code PipelineOptionsFactory.as(DataflowPipelineOptions.class)}, which reads
 * no command line at all, and then set only three fields by hand. Every other
 * Beam flag was accepted on the command line and silently discarded — no
 * effect, no error.
 *
 * <p>Found running this against real GCP on 2026-09-08: Dataflow placed workers
 * in a zone returning {@code ZONE_RESOURCE_POOL_EXHAUSTED} and
 * {@code --workerZone} could not move them, because it never reached the
 * runner. Nothing in the existing suite could catch that — the option building
 * was inline in {@code main}, and {@code main} submits a real job.
 *
 * <p>These tests assert on the built options, so a regression to {@code .as(…)}
 * fails here rather than in production.
 */
class IngestionMainDataflowOptionsTest {

    private static Map<String, String> argMap(String... pairs) {
        Map<String, String> m = new HashMap<>();
        for (int i = 0; i < pairs.length; i += 2) {
            m.put(pairs[i], pairs[i + 1]);
        }
        return m;
    }

    @Test
    void workerZoneReachesTheRunner() {
        // The flag that would have unblocked the stockout. Under the old
        // .as(...) construction this was silently dropped.
        String[] args = {
            "--entity=customers", "--project=p", "--region=europe-west2",
            "--workerZone=europe-west2-a",
        };

        DataflowPipelineOptions options = IngestionMain.buildDataflowOptions(
                args, argMap("region", "europe-west2"), "p");

        assertThat(options.getWorkerZone()).isEqualTo("europe-west2-a");
    }

    @Test
    void tempLocationReachesTheRunner() {
        // A run that passed --tempLocation still warned "No tempLocation
        // specified" and staged itself to a us-central1 bucket.
        String[] args = {"--project=p", "--tempLocation=gs://bucket/temp"};

        DataflowPipelineOptions options =
                IngestionMain.buildDataflowOptions(args, argMap(), "p");

        assertThat(options.getTempLocation()).isEqualTo("gs://bucket/temp");
    }

    @Test
    void enterpriseNetworkAndIdentityFlagsReachTheRunner() {
        // Most estates mandate these; neither could be supplied before.
        String[] args = {
            "--project=p",
            "--subnetwork=regions/europe-west2/subnetworks/private",
            "--serviceAccount=worker@p.iam.gserviceaccount.com",
            "--usePublicIps=false",
        };

        DataflowPipelineOptions options =
                IngestionMain.buildDataflowOptions(args, argMap(), "p");

        assertThat(options.getSubnetwork()).isEqualTo("regions/europe-west2/subnetworks/private");
        assertThat(options.getServiceAccount()).isEqualTo("worker@p.iam.gserviceaccount.com");
        assertThat(options.getUsePublicIps()).isFalse();
    }

    @Test
    void workerSizingFlagsReachTheRunner() {
        String[] args = {
            "--project=p", "--numWorkers=3", "--maxNumWorkers=7",
            "--workerMachineType=n2-standard-2",
        };

        DataflowPipelineOptions options =
                IngestionMain.buildDataflowOptions(args, argMap(), "p");

        assertThat(options.getNumWorkers()).isEqualTo(3);
        assertThat(options.getMaxNumWorkers()).isEqualTo(7);
        assertThat(options.getWorkerMachineType()).isEqualTo("n2-standard-2");
    }

    @Test
    void applicationFlagsDoNotBreakBeamParsing() {
        // withoutStrictParsing() is load-bearing: Beam does not know this
        // class's own flags, and strict parsing would refuse to start the job.
        String[] args = {
            "--entity=customers",
            "--sourceUri=gs://bucket/generic_customers_20260908.csv",
            "--extractDate=20260908", "--project=p",
            "--targetTable=p.odp_generic.customers",
            "--stagingPathPrefix=gs://bucket/staging",
            "--errorPathPrefix=gs://bucket/errors",
            "--cloud=gcp", "--runner=DataflowRunner",
        };

        assertThatCode(() -> IngestionMain.buildDataflowOptions(args, argMap(), "p"))
                .doesNotThrowAnyException();
    }

    @Test
    void theApplicationsOwnValuesRemainAuthoritative() {
        // project/region/stagingLocation are re-applied after parsing so the
        // app's required-argument validation stays the source of truth.
        String[] args = {"--project=ignored", "--region=ignored"};

        DataflowPipelineOptions options = IngestionMain.buildDataflowOptions(
                args,
                argMap("region", "europe-west2", "stagingLocation", "gs://bucket/dfstaging"),
                "real-project");

        assertThat(options.getProject()).isEqualTo("real-project");
        assertThat(options.getRegion()).isEqualTo("europe-west2");
        assertThat(options.getStagingLocation()).isEqualTo("gs://bucket/dfstaging");
    }

    @Test
    void absentOptionalValuesAreNotOverwrittenWithNull() {
        // region/stagingLocation absent from argMap must leave whatever Beam
        // parsed intact, rather than blanking it.
        String[] args = {"--project=p", "--region=asia-south1"};

        DataflowPipelineOptions options =
                IngestionMain.buildDataflowOptions(args, argMap(), "p");

        assertThat(options.getRegion()).isEqualTo("asia-south1");
    }
}
