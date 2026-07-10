package com.enrichmeai.culvert.aws.dynamodb;

import org.junit.jupiter.api.Test;

import static org.assertj.core.api.Assertions.assertThatThrownBy;

/** CULVERT_CLOUD gate on the worker-side no-arg constructor (see AthenaWorkerAutoConfigTest). */
class DynamoDbWorkerAutoConfigTest {

    @Test
    void noArgConstructionIsGatedToAwsSelector() {
        System.clearProperty("culvert.cloud");
        assertThatThrownBy(DynamoDbJobControlRepository::new)
                .isInstanceOf(IllegalStateException.class)
                .hasMessageContaining("CULVERT_CLOUD");
    }
}
