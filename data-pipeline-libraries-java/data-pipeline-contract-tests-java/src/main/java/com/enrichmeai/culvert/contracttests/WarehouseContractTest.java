package com.enrichmeai.culvert.contracttests;

import com.enrichmeai.culvert.contracts.Warehouse;
import org.junit.jupiter.api.Test;

import java.util.Iterator;
import java.util.Map;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

/**
 * Contract tests every {@link Warehouse} implementation must pass.
 *
 * <p>Subclasses provide a Warehouse configured so that:
 * <ul>
 *   <li>Querying {@code "SELECT id FROM contract_test_table"} yields rows
 *       {@code {{"id": 1}, {"id": 2}}}</li>
 *   <li>{@code tableExists("contract_test_table")} returns true</li>
 *   <li>{@code tableExists("contract_missing_table")} returns false (no throw)</li>
 * </ul>
 *
 * <p>Sprint-5 deliverable.
 */
public abstract class WarehouseContractTest {

    protected abstract Warehouse warehouse();

    @Test
    void queryStreamsRows() {
        Iterator<Map<String, Object>> rows = warehouse().query(
                "SELECT id FROM contract_test_table", Map.of());
        assertThat(rows.hasNext()).isTrue();
        Map<String, Object> first = rows.next();
        assertThat(first).containsKey("id");
    }

    @Test
    void tableExistsTrueForKnown() {
        assertThat(warehouse().tableExists("contract_test_table")).isTrue();
    }

    @Test
    void tableExistsFalseForMissing() {
        assertThat(warehouse().tableExists("contract_missing_table")).isFalse();
    }

    @Test
    void nullSqlRejected() {
        assertThatThrownBy(() -> warehouse().query(null, Map.of()))
                .isInstanceOfAny(NullPointerException.class, IllegalArgumentException.class);
    }
}
