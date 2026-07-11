package com.enrichmeai.culvert.aws.s3;

import org.junit.jupiter.api.Test;

import static org.assertj.core.api.Assertions.assertThatThrownBy;

/** CULVERT_CLOUD gate on the worker-side no-arg constructor (see AthenaWorkerAutoConfigTest). */
class S3WorkerAutoConfigTest {

    @Test
    void noArgConstructionIsGatedToAwsSelector() {
        System.clearProperty("culvert.cloud");
        assertThatThrownBy(S3BlobStore::new)
                .isInstanceOf(IllegalStateException.class)
                .hasMessageContaining("CULVERT_CLOUD");
    }
}
