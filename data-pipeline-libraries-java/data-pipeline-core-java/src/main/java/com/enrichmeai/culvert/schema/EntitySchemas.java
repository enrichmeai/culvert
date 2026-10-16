package com.enrichmeai.culvert.schema;

import com.enrichmeai.culvert.contracts.BlobStore;
import com.enrichmeai.culvert.dataquality.NumericRange;
import com.enrichmeai.culvert.governance.DataClassification;
import com.enrichmeai.culvert.governance.MaskingPolicy;
import com.enrichmeai.culvert.governance.MaskingStrategy;
import org.yaml.snakeyaml.LoaderOptions;
import org.yaml.snakeyaml.Yaml;
import org.yaml.snakeyaml.constructor.SafeConstructor;
import org.yaml.snakeyaml.error.YAMLException;

import java.io.IOException;
import java.nio.ByteBuffer;
import java.nio.charset.CharacterCodingException;
import java.net.URI;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Optional;
import java.util.Set;

/**
 * Reads an entity schema file: one entity's layout as YAML (JSON is accepted too), so a product
 * supplies its layout as configuration rather than as code.
 *
 * <pre>
 * entity: customers                # required
 * version: "1"                     # optional, default "1"
 * description: Customer records    # optional
 * headers: [customer_id, ssn, dob] # required: the file's columns, in order
 * fields:                          # required: one entry per field
 *   - name: customer_id            #   required
 *     type: STRING                 #   required, see TYPES
 *     required: true               #   optional, default false
 *     description: ...             #   optional
 *     classification: restricted   #   optional: public | internal | confidential | restricted
 *     masking: hash                #   optional: a strategy, or {strategy, replacement, salt}
 *     range: {min: 0, max: 150}    #   optional: closed numeric bounds
 *     allowed: [A, I, C]           #   optional, STRING fields only: the values it may hold
 * primary_key: [customer_id]       # optional: field names
 * partition_key: dob               # optional: a field name
 * envelope:                        # optional HDR/TRL overrides
 *   system_id: Generic
 *   csv_header_row: true
 * </pre>
 *
 * <p>The file is refused, with a {@link SchemaFileException} naming the file and the entry, when
 * it is not a mapping, has a key this format does not define (a misspelt {@code requried} is an
 * error, not a field that silently stays optional), lacks a required entry, names an unknown type,
 * repeats a field or a header, has a header that names no field or a field no header supplies, or
 * has an invalid classification, masking strategy, range or list of allowed values.
 *
 * <p>Mirrors the Python {@code data_pipeline_core.schema.files}: the same format, rules and
 * messages.
 */
public final class EntitySchemas {

    /** The field types a schema file may use: the warehouse-neutral wire types Culvert maps. */
    public static final Set<String> TYPES = Set.of(
            "STRING", "INT64", "FLOAT64", "BOOL", "NUMERIC", "BIGNUMERIC",
            "DATE", "DATETIME", "TIMESTAMP", "BYTES", "JSON");

    private static final Set<String> TOP_KEYS = Set.of(
            "entity", "version", "description", "headers", "fields", "primary_key", "partition_key", "envelope");
    private static final Set<String> FIELD_KEYS = Set.of(
            "name", "type", "required", "description", "classification", "masking", "range", "allowed");
    private static final Set<String> MASKING_KEYS = Set.of("strategy", "replacement", "salt");
    private static final Set<String> RANGE_KEYS = Set.of("min", "max");
    private static final Set<String> ENVELOPE_KEYS = Set.of("system_id", "csv_header_row");

    private EntitySchemas() {
    }

    /**
     * Load a schema file from a local path, a {@code file:} URI, or any URI {@code store} reads
     * ({@code gs://}, {@code s3://}, ...).
     *
     * @param uriOrPath Where the file is.
     * @param store     The store for remote URIs; may be null when {@code uriOrPath} is local.
     */
    public static EntitySchemaFile load(String uriOrPath, BlobStore store) {
        return parse(read(uriOrPath, store), uriOrPath);
    }

    /** Load a schema file from the local file system. */
    public static EntitySchemaFile load(Path path) {
        return parse(readLocal(path, path.toString()), path.toString());
    }

    /**
     * The text of a schema file, read as {@link #load(String, BlobStore)} reads it. For a caller
     * that ships the text on, for example to workers that cannot read the original location.
     */
    public static String read(String uriOrPath, BlobStore store) {
        if (uriOrPath == null || uriOrPath.isBlank()) {
            throw new SchemaFileException("schema file location must not be blank");
        }
        if (uriOrPath.startsWith("file:")) {
            Path path;
            try {
                path = Path.of(URI.create(uriOrPath));
            } catch (IllegalArgumentException e) {   // e.g. file:relative.yaml, which has no path
                throw new SchemaFileException(uriOrPath + ": cannot read the schema file: " + e.getMessage(), e);
            }
            return readLocal(path, uriOrPath);
        }
        if (!uriOrPath.contains("://")) {
            return readLocal(Path.of(uriOrPath), uriOrPath);
        }
        if (store == null) {
            throw new SchemaFileException(uriOrPath + ": no store to read a remote schema file from");
        }
        byte[] bytes;
        try {
            bytes = store.get(uriOrPath);
        } catch (RuntimeException e) {
            // A missing object (UncheckedIOException, per the BlobStore contract), a denied read,
            // a bad bucket: whatever the store throws, the message names the schema file.
            throw new SchemaFileException(uriOrPath + ": cannot read the schema file: " + e.getMessage(), e);
        }
        try {
            // Strict, as Files.readString is for a local file: bad bytes are an error, not U+FFFD.
            return StandardCharsets.UTF_8.newDecoder().decode(ByteBuffer.wrap(bytes)).toString();
        } catch (CharacterCodingException e) {
            throw new SchemaFileException(uriOrPath + ": cannot read the schema file: not UTF-8 (" + e + ")", e);
        }
    }

    /**
     * Parse and validate the text of a schema file.
     *
     * @param text   The YAML or JSON text.
     * @param source Where it came from, for the messages.
     */
    public static EntitySchemaFile parse(String text, String source) {
        Object root;
        try {
            LoaderOptions options = new LoaderOptions();
            options.setAllowDuplicateKeys(false);
            root = new Yaml(new SafeConstructor(options)).load(text);
        } catch (YAMLException e) {
            throw new SchemaFileException(source + ": not valid YAML or JSON: " + e.getMessage(), e);
        }
        return new Reader(source).file(root);
    }

    private static String readLocal(Path path, String source) {
        try {
            return Files.readString(path, StandardCharsets.UTF_8);
        } catch (IOException e) {
            throw new SchemaFileException(source + ": cannot read the schema file: " + e, e);
        }
    }

    /** Walks the parsed document, naming each entry it rejects by its path in the file. */
    private static final class Reader {
        private final String source;

        Reader(String source) {
            this.source = source;
        }

        EntitySchemaFile file(Object root) {
            Map<String, Object> top = mapping(root, "the file");
            onlyKeys(top, TOP_KEYS, "the file");

            String entity = requiredString(top, "entity", "entity");
            String version = top.containsKey("version") ? scalarString(top.get("version"), "version") : "1";
            Optional<String> description = optionalString(top, "description", "description");

            List<String> headers = stringList(require(top, "headers", "headers"), "headers");
            if (headers.isEmpty()) {
                throw error("headers", "must list at least one header");
            }
            List<SchemaField> fields = fields(require(top, "fields", "fields"));

            Set<String> fieldNames = new LinkedHashSet<>();
            fields.forEach(f -> fieldNames.add(f.name()));
            Set<String> seenHeaders = new LinkedHashSet<>();
            for (int i = 0; i < headers.size(); i++) {
                String header = headers.get(i);
                if (!seenHeaders.add(header)) {
                    throw error("headers[" + i + "]", "duplicate header '" + header + "'");
                }
                if (!fieldNames.contains(header)) {
                    throw error("headers[" + i + "]", "header '" + header + "' names no field");
                }
            }
            for (int i = 0; i < fields.size(); i++) {
                if (!seenHeaders.contains(fields.get(i).name())) {
                    throw error("fields[" + i + "]", "field '" + fields.get(i).name() + "' has no header");
                }
            }

            List<String> primaryKey = top.containsKey("primary_key")
                    ? stringList(top.get("primary_key"), "primary_key") : List.of();
            for (int i = 0; i < primaryKey.size(); i++) {
                if (!fieldNames.contains(primaryKey.get(i))) {
                    throw error("primary_key[" + i + "]", "'" + primaryKey.get(i) + "' names no field");
                }
            }
            Optional<String> partitionKey = optionalString(top, "partition_key", "partition_key");
            if (partitionKey.isPresent() && !fieldNames.contains(partitionKey.get())) {
                throw error("partition_key", "'" + partitionKey.get() + "' names no field");
            }

            EntitySchema schema = new EntitySchema(entity, fields, version, description, primaryKey, partitionKey);
            return new EntitySchemaFile(schema, headers, envelope(top.get("envelope")));
        }

        private List<SchemaField> fields(Object value) {
            if (!(value instanceof List<?> list) || list.isEmpty()) {
                throw error("fields", "must be a non-empty list of fields");
            }
            List<SchemaField> fields = new ArrayList<>();
            Set<String> names = new LinkedHashSet<>();
            for (int i = 0; i < list.size(); i++) {
                String at = "fields[" + i + "]";
                Map<String, Object> entry = mapping(list.get(i), at);
                onlyKeys(entry, FIELD_KEYS, at);
                String name = requiredString(entry, "name", at + ".name");
                if (!names.add(name)) {
                    throw error(at + ".name", "duplicate field '" + name + "'");
                }
                String type = requiredString(entry, "type", at + ".type").toUpperCase(Locale.ROOT);
                if (!TYPES.contains(type)) {
                    throw error(at + ".type", "unknown type '" + entry.get("type") + "' (expected one of "
                            + String.join(", ", TYPES.stream().sorted().toList()) + ")");
                }
                boolean required = false;
                if (entry.containsKey("required")) {
                    if (!(entry.get("required") instanceof Boolean b)) {
                        throw error(at + ".required", "must be true or false");
                    }
                    required = b;
                }
                fields.add(new SchemaField(name, type, required ? "REQUIRED" : "NULLABLE",
                        optionalString(entry, "description", at + ".description"),
                        classification(entry.get("classification"), at + ".classification"),
                        masking(entry.get("masking"), at + ".masking"),
                        range(entry.get("range"), at + ".range"),
                        allowed(entry.get("allowed"), name, type, at + ".allowed")));
            }
            return fields;
        }

        private Optional<DataClassification> classification(Object value, String at) {
            if (value == null) {
                return Optional.empty();
            }
            String text = scalarString(value, at);
            for (DataClassification c : DataClassification.values()) {
                if (c.getValue().equalsIgnoreCase(text) || c.name().equalsIgnoreCase(text)) {
                    return Optional.of(c);
                }
            }
            throw error(at, "unknown classification '" + text + "' (expected public, internal, confidential"
                    + " or restricted)");
        }

        private Optional<MaskingPolicy> masking(Object value, String at) {
            if (value == null) {
                return Optional.empty();
            }
            if (value instanceof Map<?, ?>) {
                Map<String, Object> entry = mapping(value, at);
                onlyKeys(entry, MASKING_KEYS, at);
                MaskingStrategy strategy = strategy(requiredString(entry, "strategy", at + ".strategy"),
                        at + ".strategy");
                return Optional.of(new MaskingPolicy(strategy,
                        optionalString(entry, "replacement", at + ".replacement").orElse(null),
                        optionalString(entry, "salt", at + ".salt").orElse(null)));
            }
            return Optional.of(MaskingPolicy.of(strategy(scalarString(value, at), at)));
        }

        private MaskingStrategy strategy(String text, String at) {
            for (MaskingStrategy s : MaskingStrategy.values()) {
                if (s.name().equalsIgnoreCase(text)) {
                    return s;
                }
            }
            throw error(at, "unknown masking strategy '" + text + "' (expected full, partial, redacted, hash"
                    + " or none)");
        }

        private Optional<NumericRange> range(Object value, String at) {
            if (value == null) {
                return Optional.empty();
            }
            Map<String, Object> entry = mapping(value, at);
            onlyKeys(entry, RANGE_KEYS, at);
            double min = number(require(entry, "min", at + ".min"), at + ".min");
            double max = number(require(entry, "max", at + ".max"), at + ".max");
            if (max < min) {
                throw error(at, "max (" + max + ") must be >= min (" + min + ")");
            }
            return Optional.of(NumericRange.of(min, max));
        }

        private Optional<List<String>> allowed(Object value, String name, String type, String at) {
            if (value == null) {
                return Optional.empty();
            }
            if (!"STRING".equals(type)) {
                throw error(at, "allowed values are for STRING fields, and '" + name + "' is " + type);
            }
            if (!(value instanceof List<?> list) || list.isEmpty()) {
                throw error(at, "must be a non-empty list of values");
            }
            List<String> values = stringList(value, at);
            for (int i = 0; i < values.size(); i++) {
                if (values.get(i).codePoints().allMatch(c -> Character.isWhitespace(c) || Character.isSpaceChar(c))) {
                    throw error(at + "[" + i + "]", "must be a non-blank string");
                }
                if (values.subList(0, i).contains(values.get(i))) {
                    throw error(at + "[" + i + "]", "duplicate value '" + values.get(i) + "'");
                }
            }
            return Optional.of(values);
        }

        private EnvelopeSettings envelope(Object value) {
            if (value == null) {
                return EnvelopeSettings.defaults();
            }
            Map<String, Object> entry = mapping(value, "envelope");
            onlyKeys(entry, ENVELOPE_KEYS, "envelope");
            Optional<Boolean> csvHeaderRow = Optional.empty();
            if (entry.containsKey("csv_header_row")) {
                if (!(entry.get("csv_header_row") instanceof Boolean b)) {
                    throw error("envelope.csv_header_row", "must be true or false");
                }
                csvHeaderRow = Optional.of(b);
            }
            return new EnvelopeSettings(optionalString(entry, "system_id", "envelope.system_id"), csvHeaderRow);
        }

        // ------------------------------------------------------------------ shapes

        @SuppressWarnings("unchecked")
        private Map<String, Object> mapping(Object value, String at) {
            if (!(value instanceof Map<?, ?> map)) {
                throw error(at, "must be a mapping");
            }
            for (Object key : map.keySet()) {
                if (!(key instanceof String)) {
                    throw error(at, "has a key that is not a string: " + key);
                }
            }
            return (Map<String, Object>) map;
        }

        private void onlyKeys(Map<String, Object> map, Set<String> allowed, String at) {
            for (String key : map.keySet()) {
                if (!allowed.contains(key)) {
                    throw error(at, "unknown key '" + key + "' (expected "
                            + String.join(", ", allowed.stream().sorted().toList()) + ")");
                }
            }
        }

        private Object require(Map<String, Object> map, String key, String at) {
            Object value = map.get(key);
            if (value == null) {
                throw error(at, "is required");
            }
            return value;
        }

        private String requiredString(Map<String, Object> map, String key, String at) {
            String text = scalarString(require(map, key, at), at);
            if (text.isBlank()) {
                throw error(at, "must not be blank");
            }
            return text;
        }

        private Optional<String> optionalString(Map<String, Object> map, String key, String at) {
            return map.get(key) == null ? Optional.empty() : Optional.of(scalarString(map.get(key), at));
        }

        /** A string; a number is accepted and written as YAML wrote it (version: 1 is "1"). */
        private String scalarString(Object value, String at) {
            if (value instanceof String s) {
                return s;
            }
            if (value instanceof Integer || value instanceof Long || value instanceof java.math.BigInteger) {
                return value.toString();
            }
            throw error(at, "must be a string (quote it if YAML reads it as another type, e.g. 1.0)");
        }

        private List<String> stringList(Object value, String at) {
            if (!(value instanceof List<?> list)) {
                throw error(at, "must be a list");
            }
            List<String> out = new ArrayList<>();
            for (int i = 0; i < list.size(); i++) {
                if (!(list.get(i) instanceof String s) || s.isBlank()) {
                    throw error(at + "[" + i + "]", "must be a non-blank string (quote it if YAML reads it as"
                            + " another type, e.g. 'on' or 'no')");
                }
                out.add(s);
            }
            return out;
        }

        private double number(Object value, String at) {
            if (value instanceof Number n && !(value instanceof Boolean)) {
                return n.doubleValue();
            }
            throw error(at, "must be a number");
        }

        private SchemaFileException error(String at, String message) {
            return new SchemaFileException(source + ": " + at + ": " + message);
        }
    }
}
