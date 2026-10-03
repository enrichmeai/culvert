package com.enrichmeai.culvert.itsupport;

import org.junit.jupiter.api.Test;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

/** Unit scope, no Docker: what can be checked before a container exists. */
class PostgresContainerTest {

    @Test
    void defaultsToPostgres16() {
        assertThat(PostgresContainer.DEFAULT_IMAGE.asCanonicalNameString())
                .isEqualTo("postgres:16-alpine");
    }

    @Test
    void connectionsAreRefusedBeforeStartWithASayingMessage() {
        try (PostgresContainer pg = new PostgresContainer()) {
            assertThatThrownBy(pg::newConnection)
                    .isInstanceOf(IllegalStateException.class).hasMessageContaining("not started");
            assertThatThrownBy(pg::newDataSource)
                    .isInstanceOf(IllegalStateException.class).hasMessageContaining("not started");
        }
    }
}
