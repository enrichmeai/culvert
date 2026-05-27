package com.enrichmeai.culvert.tester;

import com.enrichmeai.culvert.contracts.Warehouse;
import org.mockito.Mockito;

import java.util.Arrays;
import java.util.Collections;
import java.util.HashSet;
import java.util.Iterator;
import java.util.Map;
import java.util.Objects;
import java.util.Set;

/**
 * Mockito-mock fixture builders for {@link Warehouse}.
 *
 * <p>Returned mocks satisfy the documented {@link Warehouse} contract for
 * the configured state — empty result sets for queries, false for
 * {@code tableExists} on unlisted tables, etc. {@code execute},
 * {@code loadFromUri}, {@code merge}, {@code copy} default to no-op
 * returns (zero rows) unless the consumer adds further stubbing on top.
 *
 * <p>This class is non-instantiable.
 */
public final class WarehouseFixtures {

    private WarehouseFixtures() {
        throw new AssertionError("no instances");
    }

    /**
     * Mock {@link Warehouse} where everything is empty:
     * <ul>
     *     <li>{@code query(...)} returns an empty iterator.</li>
     *     <li>{@code tableExists(...)} returns false for every FQTN.</li>
     *     <li>{@code execute(...)} is a no-op.</li>
     *     <li>{@code loadFromUri / merge / copy} all return 0.</li>
     * </ul>
     */
    @SuppressWarnings("unchecked")
    public static Warehouse emptyWarehouse() {
        Warehouse mock = Mockito.mock(Warehouse.class);
        Mockito.when(mock.query(Mockito.anyString(), Mockito.anyMap()))
                .thenAnswer(invocation -> Collections.emptyIterator());
        Mockito.when(mock.tableExists(Mockito.anyString())).thenReturn(false);
        Mockito.when(mock.loadFromUri(Mockito.anyString(), Mockito.anyString(), Mockito.any()))
                .thenReturn(0L);
        Mockito.when(mock.merge(Mockito.anyString(), Mockito.anyString(), Mockito.anyList()))
                .thenReturn(0L);
        Mockito.when(mock.copy(Mockito.anyString(), Mockito.anyString())).thenReturn(0L);
        return mock;
    }

    /**
     * Mock {@link Warehouse} where the named fully-qualified tables exist
     * ({@code tableExists} returns true) and every other table is missing.
     * Queries still return empty iterators — for stubbing query results,
     * the consumer adds {@code when(mock.query(...)).thenReturn(...)} on
     * top of the returned mock.
     *
     * @param fqtns Fully-qualified table names that {@code tableExists}
     *              should return true for.
     */
    public static Warehouse warehouseWithTables(String... fqtns) {
        Objects.requireNonNull(fqtns, "fqtns must not be null");
        Set<String> known = new HashSet<>(Arrays.asList(fqtns));
        Warehouse mock = emptyWarehouse();
        // Re-stub tableExists with a name-aware answer.
        Mockito.when(mock.tableExists(Mockito.anyString())).thenAnswer(invocation -> {
            String fqtn = invocation.getArgument(0);
            return known.contains(fqtn);
        });
        return mock;
    }

    /**
     * Mock {@link Warehouse} whose every method throws {@code error}.
     * Use to simulate a warehouse outage or auth failure.
     *
     * @param error The exception to throw. Must not be null.
     */
    @SuppressWarnings("unchecked")
    public static Warehouse failingWarehouse(RuntimeException error) {
        Objects.requireNonNull(error, "error must not be null");
        Warehouse mock = Mockito.mock(Warehouse.class);
        Mockito.when(mock.query(Mockito.anyString(), Mockito.anyMap())).thenThrow(error);
        Mockito.doThrow(error).when(mock).execute(Mockito.anyString(), Mockito.anyMap());
        Mockito.when(mock.loadFromUri(Mockito.anyString(), Mockito.anyString(), Mockito.any()))
                .thenThrow(error);
        Mockito.when(mock.merge(Mockito.anyString(), Mockito.anyString(), Mockito.anyList()))
                .thenThrow(error);
        Mockito.when(mock.copy(Mockito.anyString(), Mockito.anyString())).thenThrow(error);
        Mockito.when(mock.tableExists(Mockito.anyString())).thenThrow(error);
        return mock;
    }

    /**
     * Helper: build an iterator over a list of row maps. Convenience for
     * consumers who want to stub {@code query} with concrete results:
     *
     * <pre>{@code
     * Warehouse w = WarehouseFixtures.emptyWarehouse();
     * when(w.query(anyString(), anyMap()))
     *     .thenReturn(WarehouseFixtures.rows(Map.of("id", 1), Map.of("id", 2)));
     * }</pre>
     */
    @SafeVarargs
    @SuppressWarnings("varargs")
    public static Iterator<Map<String, Object>> rows(Map<String, Object>... rows) {
        return Arrays.asList(rows).iterator();
    }
}
