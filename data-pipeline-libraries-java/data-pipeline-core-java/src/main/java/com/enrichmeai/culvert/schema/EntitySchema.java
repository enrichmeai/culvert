package com.enrichmeai.culvert.schema;

import java.util.List;
import java.util.Objects;
import java.util.Optional;

/**
 * A named schema for an entity (a logical table or file structure).
 *
 * <p>{@code version} enables schema evolution: two {@link EntitySchema}
 * instances with the same name and different versions can coexist, and the
 * framework picks the right one based on the record being processed.
 *
 * <p>Mirrors the Python {@code EntitySchema} dataclass.
 *
 * @param name         Schema name (e.g. {@code "customer"}).
 * @param fields       The field definitions, in order.
 * @param version      Schema version (defaults to {@code "1"}).
 * @param description  Optional human description.
 * @param primaryKey   The fields that form the primary key (may be empty).
 * @param partitionKey Optional partition key for partitioned tables.
 */
public record EntitySchema(
        String name,
        List<SchemaField> fields,
        String version,
        Optional<String> description,
        List<String> primaryKey,
        Optional<String> partitionKey) {

    public EntitySchema {
        Objects.requireNonNull(name, "name");
        Objects.requireNonNull(fields, "fields");
        if (version == null) version = "1";
        if (description == null) description = Optional.empty();
        if (primaryKey == null) primaryKey = List.of();
        if (partitionKey == null) partitionKey = Optional.empty();
        fields = List.copyOf(fields);
        primaryKey = List.copyOf(primaryKey);
    }

    public static EntitySchema of(String name, List<SchemaField> fields) {
        return new EntitySchema(name, fields, "1",
                Optional.empty(), List.of(), Optional.empty());
    }
}
