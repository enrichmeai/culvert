package com.enrichmeai.culvert.tester;

import com.enrichmeai.culvert.contracts.Warehouse;
import org.junit.jupiter.api.Test;

import java.util.Iterator;
import java.util.List;
import java.util.Map;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.anyMap;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.Mockito.when;

class WarehouseFixturesTest {

    @Test
    void emptyWarehouseReturnsEmptyResultsAndFalseTableExists() {
        Warehouse w = WarehouseFixtures.emptyWarehouse();

        assertThat(w.query("SELECT 1", Map.of()).hasNext()).isFalse();
        assertThat(w.tableExists("p.d.t")).isFalse();
        assertThat(w.loadFromUri("gs://b/o", "p.d.t", null)).isZero();
        assertThat(w.merge("src", "dst", List.of("id"))).isZero();
        assertThat(w.copy("src", "dst")).isZero();
    }

    @Test
    void warehouseWithTablesReturnsTrueOnlyForListedFqtns() {
        Warehouse w = WarehouseFixtures.warehouseWithTables("proj.ds.users", "proj.ds.orders");

        assertThat(w.tableExists("proj.ds.users")).isTrue();
        assertThat(w.tableExists("proj.ds.orders")).isTrue();
        assertThat(w.tableExists("proj.ds.missing")).isFalse();
    }

    @Test
    void failingWarehouseThrowsFromEveryMethod() {
        RuntimeException boom = new RuntimeException("outage");
        Warehouse w = WarehouseFixtures.failingWarehouse(boom);

        assertThatThrownBy(() -> w.query("SELECT 1", Map.of())).isSameAs(boom);
        assertThatThrownBy(() -> w.execute("DROP TABLE t", Map.of())).isSameAs(boom);
        assertThatThrownBy(() -> w.tableExists("p.d.t")).isSameAs(boom);
    }

    @Test
    void rowsHelperWiresQueryResultsForConsumers() {
        Warehouse w = WarehouseFixtures.emptyWarehouse();
        when(w.query(anyString(), anyMap()))
                .thenReturn(WarehouseFixtures.rows(Map.of("id", 1), Map.of("id", 2)));

        Iterator<Map<String, Object>> it = w.query("SELECT id FROM t", Map.of());
        assertThat(it.next()).containsEntry("id", 1);
        assertThat(it.next()).containsEntry("id", 2);
        assertThat(it.hasNext()).isFalse();
    }
}
