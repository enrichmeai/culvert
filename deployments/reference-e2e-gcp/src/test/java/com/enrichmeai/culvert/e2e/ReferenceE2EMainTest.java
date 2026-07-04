package com.enrichmeai.culvert.e2e;

import org.junit.jupiter.api.Test;

import java.util.Map;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

/**
 * Unit tests for {@link ReferenceE2EMain}'s argument parsing and run-id
 * format. The launcher's DirectRunner path executes the same pipeline as
 * {@link ReferenceE2EPipelineTest} (which already proves DONE on
 * DirectRunner); the Dataflow path is exercised in the GCP deploy phase.
 */
class ReferenceE2EMainTest {

    @Test
    void parsesKeyValueArgs() {
        Map<String, String> parsed = ReferenceE2EMain.parseArgs(new String[]{
                "--runner=dataflow", "--project=my-proj", "--flag"});

        assertThat(parsed).containsEntry("runner", "dataflow")
                .containsEntry("project", "my-proj")
                .containsEntry("flag", "true");
    }

    @Test
    void rejectsNonFlagArgument() {
        assertThatThrownBy(() -> ReferenceE2EMain.parseArgs(new String[]{"oops"}))
                .isInstanceOf(IllegalArgumentException.class);
    }

    @Test
    void runIdMatchesWireContractFormat() {
        // docs/CONTRACT.md: ^\d{8}T\d{6}Z-[0-9a-f]{4}$
        assertThat(ReferenceE2EMain.generateRunId())
                .matches("^\\d{8}T\\d{6}Z-[0-9a-f]{4}$");
    }
}
