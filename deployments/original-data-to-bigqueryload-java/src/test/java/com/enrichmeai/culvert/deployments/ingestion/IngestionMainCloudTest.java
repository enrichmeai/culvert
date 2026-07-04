package com.enrichmeai.culvert.deployments.ingestion;

import org.junit.jupiter.api.Test;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatIllegalArgumentException;

/**
 * The {@code --cloud} switch: gcp (default) and aws are supported; azure is
 * rejected with the honest roadmap message (skeleton adapter family only);
 * anything else is rejected as unknown. The adapter families selected per
 * cloud are exercised end-to-end in {@code CrossCloudIngestionLocalStackIT}
 * (AWS, real LocalStack S3 + DynamoDB) and the existing runner tests (GCP
 * shape via in-memory adapters).
 */
class IngestionMainCloudTest {

    @Test
    void gcpAndAwsAreSupportedCaseInsensitively() {
        assertThat(IngestionMain.normalizeCloud("gcp")).isEqualTo("gcp");
        assertThat(IngestionMain.normalizeCloud("AWS")).isEqualTo("aws");
        assertThat(IngestionMain.normalizeCloud("  Aws ")).isEqualTo("aws");
        assertThat(IngestionMain.normalizeCloud(null)).isEqualTo("gcp");
    }

    @Test
    void azureIsRejectedWithRoadmapMessage() {
        assertThatIllegalArgumentException()
                .isThrownBy(() -> IngestionMain.normalizeCloud("azure"))
                .withMessageContaining("skeleton")
                .withMessageContaining("roadmap");
    }

    @Test
    void unknownCloudIsRejected() {
        assertThatIllegalArgumentException()
                .isThrownBy(() -> IngestionMain.normalizeCloud("onprem"))
                .withMessageContaining("gcp")
                .withMessageContaining("aws");
    }
}
