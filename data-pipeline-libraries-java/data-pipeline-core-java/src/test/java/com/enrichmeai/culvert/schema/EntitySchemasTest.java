package com.enrichmeai.culvert.schema;

import com.enrichmeai.culvert.contracts.BlobMetadata;
import com.enrichmeai.culvert.contracts.BlobStore;
import com.enrichmeai.culvert.dataquality.NumericRange;
import com.enrichmeai.culvert.governance.DataClassification;
import com.enrichmeai.culvert.governance.MaskingPolicy;
import com.enrichmeai.culvert.governance.MaskingStrategy;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.CsvSource;

import java.io.FileNotFoundException;
import java.io.InputStream;
import java.io.OutputStream;
import java.io.UncheckedIOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.Iterator;
import java.util.List;
import java.util.Optional;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

/**
 * {@link EntitySchemas}: the format, and every way a file is refused. The Python
 * {@code test_schema_files.py} runs the same cases and expects the same messages.
 */
class EntitySchemasTest {

    private static final String FULL = """
            entity: customers
            version: 2
            description: Customer records
            headers: [customer_id, ssn, age, score]
            fields:
              - name: customer_id
                type: string
                required: true
              - name: ssn
                type: STRING
                required: true
                description: Social security number
                classification: restricted
                masking: {strategy: partial, replacement: "#"}
              - name: age
                type: INT64
                range: {min: 0, max: 150}
              - name: score
                type: FLOAT64
                classification: INTERNAL
                masking: hash
            primary_key: [customer_id]
            partition_key: age
            envelope:
              system_id: Retail
              csv_header_row: false
            """;

    @Test
    void readsEveryPartOfTheFormat() {
        EntitySchemaFile file = EntitySchemas.parse(FULL, "customers.schema.yaml");

        assertThat(file.headers()).containsExactly("customer_id", "ssn", "age", "score");
        assertThat(file.envelope()).isEqualTo(new EnvelopeSettings(Optional.of("Retail"), Optional.of(false)));
        assertThat(file.schema()).isEqualTo(new EntitySchema("customers", List.of(
                SchemaField.required("customer_id", "STRING"),
                new SchemaField("ssn", "STRING", "REQUIRED", Optional.of("Social security number"),
                        Optional.of(DataClassification.RESTRICTED),
                        Optional.of(new MaskingPolicy(MaskingStrategy.PARTIAL, "#", ""))),
                SchemaField.nullable("age", "INT64").withRange(NumericRange.of(0, 150)),
                new SchemaField("score", "FLOAT64", "NULLABLE", Optional.empty(),
                        Optional.of(DataClassification.INTERNAL), Optional.of(MaskingPolicy.of(MaskingStrategy.HASH)))),
                "2", Optional.of("Customer records"), List.of("customer_id"), Optional.of("age")));
    }

    @Test
    void readsJsonToo() {
        String json = """
                {"entity": "accounts", "headers": ["account_id", "balance"],
                 "fields": [{"name": "account_id", "type": "STRING", "required": true},
                            {"name": "balance", "type": "NUMERIC"}]}
                """;

        EntitySchemaFile file = EntitySchemas.parse(json, "accounts.schema.json");

        assertThat(file.schema()).isEqualTo(EntitySchema.of("accounts", List.of(
                SchemaField.required("account_id", "STRING"), SchemaField.nullable("balance", "NUMERIC"))));
        assertThat(file.envelope()).isEqualTo(EnvelopeSettings.defaults());
    }

    @Test
    void loadsALocalPathAndAFileUri(@TempDir Path dir) throws Exception {
        Path path = dir.resolve("accounts.schema.yaml");
        Files.writeString(path, "entity: accounts\nheaders: [id]\nfields: [{name: id, type: STRING}]\n");

        assertThat(EntitySchemas.load(path).schema().name()).isEqualTo("accounts");
        assertThat(EntitySchemas.load(path.toString(), null).headers()).containsExactly("id");
        assertThat(EntitySchemas.load(path.toUri().toString(), null).headers()).containsExactly("id");
    }

    @Test
    void loadsARemoteUriThroughTheStore() {
        BlobStore store = new OneObjectStore("gs://schemas/accounts.schema.yaml",
                "entity: accounts\nheaders: [id]\nfields: [{name: id, type: STRING}]\n");

        assertThat(EntitySchemas.load("gs://schemas/accounts.schema.yaml", store).schema().name())
                .isEqualTo("accounts");
        assertThatThrownBy(() -> EntitySchemas.load("gs://schemas/missing.schema.yaml", store))
                .isInstanceOf(SchemaFileException.class)
                .hasMessageStartingWith("gs://schemas/missing.schema.yaml: cannot read the schema file");
        assertThatThrownBy(() -> EntitySchemas.load("gs://schemas/accounts.schema.yaml", null))
                .isInstanceOf(SchemaFileException.class)
                .hasMessageContaining("no store to read a remote schema file from");
    }

    /** Each invalid file and the start of its message, after "s.yaml: ". */
    @ParameterizedTest(name = "{0}")
    @CsvSource(delimiter = '|', textBlock = """
            unknown type                | entity: e\\nheaders: [a]\\nfields: [{name: a, type: STRNG}]                         | fields[0].type: unknown type 'STRNG'
            duplicate field             | entity: e\\nheaders: [a]\\nfields: [{name: a, type: STRING}, {name: a, type: INT64}] | fields[1].name: duplicate field 'a'
            header naming no field      | entity: e\\nheaders: [a, b]\\nfields: [{name: a, type: STRING}]                     | headers[1]: header 'b' names no field
            field with no header        | entity: e\\nheaders: [a]\\nfields: [{name: a, type: STRING}, {name: b, type: STRING}] | fields[1]: field 'b' has no header
            duplicate header            | entity: e\\nheaders: [a, a]\\nfields: [{name: a, type: STRING}]                     | headers[1]: duplicate header 'a'
            missing entity              | headers: [a]\\nfields: [{name: a, type: STRING}]                                  | entity: is required
            blank entity                | entity: ' '\\nheaders: [a]\\nfields: [{name: a, type: STRING}]                     | entity: must not be blank
            missing headers             | entity: e\\nfields: [{name: a, type: STRING}]                                     | headers: is required
            empty headers               | entity: e\\nheaders: []\\nfields: [{name: a, type: STRING}]                        | headers: must list at least one header
            missing fields              | entity: e\\nheaders: [a]                                                         | fields: is required
            empty fields                | entity: e\\nheaders: [a]\\nfields: []                                              | fields: must be a non-empty list of fields
            missing field name          | entity: e\\nheaders: [a]\\nfields: [{type: STRING}]                                | fields[0].name: is required
            missing field type          | entity: e\\nheaders: [a]\\nfields: [{name: a}]                                     | fields[0].type: is required
            misspelt key                | entity: e\\nheaders: [a]\\nfields: [{name: a, type: STRING, requried: true}]       | fields[0]: unknown key 'requried'
            unknown top-level key       | entity: e\\nheader: [a]\\nfields: [{name: a, type: STRING}]                        | the file: unknown key 'header'
            required not a boolean      | entity: e\\nheaders: [a]\\nfields: [{name: a, type: STRING, required: maybe}]      | fields[0].required: must be true or false
            unknown classification      | entity: e\\nheaders: [a]\\nfields: [{name: a, type: STRING, classification: secret}] | fields[0].classification: unknown classification 'secret'
            unknown masking strategy    | entity: e\\nheaders: [a]\\nfields: [{name: a, type: STRING, masking: shred}]       | fields[0].masking: unknown masking strategy 'shred'
            masking without a strategy  | entity: e\\nheaders: [a]\\nfields: [{name: a, type: STRING, masking: {salt: x}}]   | fields[0].masking.strategy: is required
            range missing max           | entity: e\\nheaders: [a]\\nfields: [{name: a, type: INT64, range: {min: 1}}]       | fields[0].range.max: is required
            range upside down           | entity: e\\nheaders: [a]\\nfields: [{name: a, type: INT64, range: {min: 5, max: 1}}] | fields[0].range: max (1.0) must be >= min (5.0)
            primary key naming no field | entity: e\\nheaders: [a]\\nfields: [{name: a, type: STRING}]\\nprimary_key: [b]     | primary_key[0]: 'b' names no field
            header YAML reads as a bool | entity: e\\nheaders: [on]\\nfields: [{name: a, type: STRING}]                      | headers[0]: must be a non-blank string
            not a mapping               | - just a list                                                                  | the file: must be a mapping
            """)
    void refuses(String name, String yaml, String message) {
        assertThatThrownBy(() -> EntitySchemas.parse(yaml.replace("\\n", "\n"), "s.yaml"))
                .isInstanceOf(SchemaFileException.class)
                .hasMessageStartingWith("s.yaml: " + message);
    }

    @Test
    void refusesTextThatIsNotYaml() {
        assertThatThrownBy(() -> EntitySchemas.parse("entity: [unclosed", "s.yaml"))
                .isInstanceOf(SchemaFileException.class)
                .hasMessageStartingWith("s.yaml: not valid YAML or JSON");
    }

    @Test
    void refusesADuplicateKey() {
        assertThatThrownBy(() -> EntitySchemas.parse("entity: a\nentity: b\nheaders: [x]\n"
                + "fields: [{name: x, type: STRING}]\n", "s.yaml"))
                .isInstanceOf(SchemaFileException.class)
                .hasMessageStartingWith("s.yaml: not valid YAML or JSON");
    }

    @Test
    void refusesAComplexKey() {
        assertThatThrownBy(() -> EntitySchemas.parse("? [a]\n: x\n", "s.yaml"))
                .isInstanceOf(SchemaFileException.class)
                .hasMessageStartingWith("s.yaml: ");
    }

    @Test
    void refusesAFileThatIsNotUtf8(@TempDir Path dir) throws Exception {
        Path path = dir.resolve("bad.schema.yaml");
        Files.write(path, new byte[] {'e', 'n', 't', 'i', 't', 'y', ':', ' ', (byte) 0xFF});

        assertThatThrownBy(() -> EntitySchemas.load(path.toString(), null))
                .isInstanceOf(SchemaFileException.class)
                .hasMessageStartingWith(path + ": cannot read the schema file");
    }

    @Test
    void refusesARemoteFileThatIsNotUtf8() {
        BlobStore store = new OneObjectStore("gs://s/bad.schema.yaml", new byte[] {'e', ':', ' ', (byte) 0xFF});

        assertThatThrownBy(() -> EntitySchemas.load("gs://s/bad.schema.yaml", store))
                .isInstanceOf(SchemaFileException.class)
                .hasMessageStartingWith("gs://s/bad.schema.yaml: cannot read the schema file: not UTF-8");
    }

    @Test
    void refusesAFileUriWithNoPath() {
        assertThatThrownBy(() -> EntitySchemas.load("file:relative.schema.yaml", null))
                .isInstanceOf(SchemaFileException.class)
                .hasMessageStartingWith("file:relative.schema.yaml: cannot read the schema file");
    }

    /** A store holding one object; any other URI is missing, as the BlobStore contract says. */
    private record OneObjectStore(String uri, byte[] bytes) implements BlobStore {
        OneObjectStore(String uri, String text) {
            this(uri, text.getBytes(StandardCharsets.UTF_8));
        }

        @Override
        public byte[] get(String u) {
            if (!uri.equals(u)) {
                throw new UncheckedIOException(new FileNotFoundException(u));
            }
            return bytes;
        }

        @Override public InputStream openInput(String u) { throw new UnsupportedOperationException(); }
        @Override public OutputStream openOutput(String u) { throw new UnsupportedOperationException(); }
        @Override public void put(String u, byte[] data) { throw new UnsupportedOperationException(); }
        @Override public Iterator<String> list(String prefix) { throw new UnsupportedOperationException(); }
        @Override public boolean exists(String u) { return uri.equals(u); }
        @Override public BlobMetadata head(String u) { throw new UnsupportedOperationException(); }
        @Override public void delete(String u) { throw new UnsupportedOperationException(); }
        @Override public void copy(String src, String dst) { throw new UnsupportedOperationException(); }
    }

}
