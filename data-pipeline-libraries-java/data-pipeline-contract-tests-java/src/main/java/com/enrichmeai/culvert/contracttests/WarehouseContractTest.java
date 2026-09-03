package com.enrichmeai.culvert.contracttests;

import com.enrichmeai.culvert.contracts.LoadOptions;
import com.enrichmeai.culvert.contracts.Warehouse;
import com.enrichmeai.culvert.schema.EntitySchema;
import com.enrichmeai.culvert.schema.SchemaField;
import org.junit.jupiter.api.Test;

import java.util.Iterator;
import java.util.List;
import java.util.Map;
import java.util.Set;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatNullPointerException;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

/**
 * Contract tests every {@link Warehouse} implementation must pass.
 *
 * <p>Subclasses provide a Warehouse configured so that:
 * <ul>
 *   <li>Querying {@code "SELECT id FROM " + knownTable()} yields at least one row
 *       containing an {@code "id"} key</li>
 *   <li>{@code tableExists(knownTable())} returns true</li>
 *   <li>{@code tableExists(missingTable())} returns false (no throw)</li>
 * </ul>
 *
 * <p>Default table name tokens are plain identifiers. Cloud warehouses that
 * require fully-qualified names (e.g. {@code dataset.table} for BigQuery)
 * should override {@link #knownTable()} and {@link #missingTable()} to supply
 * the appropriate qualified name.
 *
 * <p>Sprint-5 deliverable. Sprint-15 (T15.4): added {@link #knownTable()} /
 * {@link #missingTable()} hooks so BigQuery subclasses can supply
 * {@code dataset.table} qualified names (BigQuery rejects bare unqualified
 * names at parse time).
 */
public abstract class WarehouseContractTest {

    protected abstract Warehouse warehouse();

    /**
     * The table name that the Warehouse is pre-configured to recognise as
     * existing. Defaults to {@code "contract_test_table"}.
     *
     * <p>Subclasses for cloud warehouses that require qualified names (e.g.
     * BigQuery's {@code dataset.table}) should override this method.
     */
    protected String knownTable() {
        return "contract_test_table";
    }

    /**
     * The table name that the Warehouse is pre-configured to treat as absent.
     * Defaults to {@code "contract_missing_table"}.
     *
     * <p>Must use the same qualification level as {@link #knownTable()}.
     */
    protected String missingTable() {
        return "contract_missing_table";
    }

    /**
     * Write dispositions this backend genuinely cannot express.
     *
     * <p>Defaults to none. Athena overrides it: its load idiom is
     * {@code INSERT INTO}, and it has no DML on non-Iceberg tables, so it can
     * only append.
     *
     * <p>Declaring a disposition here is a promise that
     * {@link Warehouse#loadFromUri} <strong>throws</strong> for it. The one
     * thing an implementation must never do is quietly fall back to
     * {@code APPEND} — a caller who asked for replace and silently got append
     * ends up with duplicated data and no signal, which is the exact failure
     * {@link LoadOptions} was introduced to eliminate.
     */
    protected Set<LoadOptions.WriteDisposition> unsupportedDispositions() {
        return Set.of();
    }

    /** A URI in this backend's scheme, used only for argument-validation tests. */
    protected String loadUri() {
        return "gs://contract-bucket/contract.ndjson";
    }

    private static EntitySchema contractSchema() {
        return EntitySchema.of("contract", List.of(SchemaField.required("id", "STRING")));
    }

    @Test
    void loadFromUriRejectsNullOptions() {
        // There is no defaulted disposition anywhere in the contract: a caller
        // must decide what a re-run means. Enforced before any backend call,
        // so this holds for every implementation without stubbing.
        assertThatNullPointerException().isThrownBy(() ->
                warehouse().loadFromUri(loadUri(), knownTable(), contractSchema(), null));
    }

    @Test
    void unsupportedDispositionsThrowRatherThanSilentlyAppending() {
        for (LoadOptions.WriteDisposition disposition : unsupportedDispositions()) {
            LoadOptions options = new LoadOptions(disposition, java.util.Optional.empty());

            assertThatThrownBy(() ->
                    warehouse().loadFromUri(loadUri(), knownTable(), contractSchema(), options))
                    .as("disposition %s must be refused, not downgraded to APPEND", disposition)
                    .isInstanceOf(UnsupportedOperationException.class)
                    // Naming the disposition is part of the contract: "not
                    // supported" without saying what leaves the caller guessing.
                    .hasMessageContaining(disposition.name());
        }
    }

    @Test
    void queryStreamsRows() {
        Iterator<Map<String, Object>> rows = warehouse().query(
                "SELECT id FROM " + knownTable(), Map.of());
        assertThat(rows.hasNext()).isTrue();
        Map<String, Object> first = rows.next();
        assertThat(first).containsKey("id");
    }

    @Test
    void tableExistsTrueForKnown() {
        assertThat(warehouse().tableExists(knownTable())).isTrue();
    }

    @Test
    void tableExistsFalseForMissing() {
        assertThat(warehouse().tableExists(missingTable())).isFalse();
    }

    @Test
    void nullSqlRejected() {
        assertThatThrownBy(() -> warehouse().query(null, Map.of()))
                .isInstanceOfAny(NullPointerException.class, IllegalArgumentException.class);
    }
}
