package com.enrichmeai.culvert.deployments.ingestion.schema;

import com.enrichmeai.culvert.schema.EntitySchemas;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.ValueSource;

import java.nio.file.Path;

import static org.assertj.core.api.Assertions.assertThat;

/**
 * The four sample entities written as schema files ({@code schemas/<entity>.schema.yaml}) load to
 * exactly the layout {@link GenericEntities} builds in code: the same schema, field by field, the
 * same headers in the same order, and the default envelope.
 */
class GenericEntitiesSchemaFileParityTest {

    @ParameterizedTest
    @ValueSource(strings = {"customers", "accounts", "decision", "applications"})
    void theSchemaFileDescribesTheBuiltInEntity(String entity) {
        assertThat(EntitySchemas.load(Path.of("schemas", entity + ".schema.yaml")))
                .isEqualTo(GenericEntities.layoutFor(entity));
    }
}
