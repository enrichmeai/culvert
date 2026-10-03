package com.enrichmeai.culvert.itsupport;

import org.junit.jupiter.api.Test;
import org.testcontainers.junit.jupiter.Container;
import org.testcontainers.junit.jupiter.Testcontainers;

import javax.sql.DataSource;
import java.sql.Connection;
import java.sql.SQLException;
import java.sql.Statement;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

/**
 * Proves the fixture gives two independent sessions: distinct backends, and a row lock held on
 * one is contended from the other. Needs Docker; runs under the {@code it} profile.
 */
@Testcontainers
class PostgresContainerIT {

    @Container
    static final PostgresContainer PG = new PostgresContainer();

    @Test
    void twoConnectionsAreTwoSessions() throws SQLException {
        try (Connection a = PG.newConnection(); Connection b = PG.newConnection()) {
            assertThat(PostgresContainer.backendPid(a)).isNotEqualTo(PostgresContainer.backendPid(b));
        }
        DataSource ds = PG.newDataSource();
        try (Connection a = ds.getConnection(); Connection b = ds.getConnection()) {
            assertThat(PostgresContainer.backendPid(a)).isNotEqualTo(PostgresContainer.backendPid(b));
        }
    }

    @Test
    void aRowLockedOnOneConnectionIsContendedFromTheOther() throws SQLException {
        PG.execute("DROP TABLE IF EXISTS claim; CREATE TABLE claim (k text PRIMARY KEY); "
                + "INSERT INTO claim VALUES ('unit-1')");
        try (Connection holder = PG.newConnection(); Connection contender = PG.newConnection()) {
            holder.setAutoCommit(false);
            try (Statement s = holder.createStatement()) {
                s.execute("SELECT k FROM claim WHERE k = 'unit-1' FOR UPDATE");
            }

            contender.setAutoCommit(false);
            try (Statement s = contender.createStatement()) {
                s.execute("SET LOCAL lock_timeout = '200ms'");
                assertThatThrownBy(() -> s.execute("SELECT k FROM claim WHERE k = 'unit-1' FOR UPDATE"))
                        .isInstanceOf(SQLException.class)
                        .satisfies(e -> assertThat(((SQLException) e).getSQLState())
                                .as("55P03 lock_not_available").isEqualTo("55P03"));
            }
            contender.rollback();

            holder.commit(); // releasing the lock lets the contender take it
            try (Statement s = contender.createStatement()) {
                s.execute("SELECT k FROM claim WHERE k = 'unit-1' FOR UPDATE NOWAIT");
            }
            contender.commit();
        }
    }
}
