package com.enrichmeai.culvert.schema;

/**
 * An entity schema file that cannot be read or does not describe a valid layout. The message
 * names the file and the offending entry, e.g.
 * {@code customers.schema.yaml: fields[3].type: unknown type 'STRNG'}.
 */
public class SchemaFileException extends IllegalArgumentException {

    private static final long serialVersionUID = 1L;

    public SchemaFileException(String message) {
        super(message);
    }

    public SchemaFileException(String message, Throwable cause) {
        super(message, cause);
    }
}
