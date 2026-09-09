package com.enrichmeai.culvert.aws.dynamodb;

import software.amazon.awssdk.services.dynamodb.DynamoDbClient;
import software.amazon.awssdk.services.dynamodb.model.AttributeValue;
import software.amazon.awssdk.services.dynamodb.model.ConditionalCheckFailedException;
import software.amazon.awssdk.services.dynamodb.model.PutItemRequest;
import software.amazon.awssdk.services.dynamodb.model.PutItemResponse;
import software.amazon.awssdk.services.dynamodb.model.QueryRequest;
import software.amazon.awssdk.services.dynamodb.model.QueryResponse;
import software.amazon.awssdk.services.dynamodb.model.ScanRequest;
import software.amazon.awssdk.services.dynamodb.model.ScanResponse;

import java.util.ArrayList;
import java.util.HashMap;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.TreeMap;

/**
 * An in-memory stand-in for {@link DynamoDbClient}, modelling a single table
 * keyed exactly as {@link DynamoDbJobControlRepository} expects: partition key
 * {@code run_id}, sort key {@code event_seq}.
 *
 * <p><b>Why a hand-written fake rather than Mockito.</b> A mock returns
 * whatever it was told to return, so it can prove the <em>shape</em> of a
 * request (that is {@link DynamoDbJobControlRepositoryTest}'s job) but never
 * that a projection is correct — the assertion and the stub would be the same
 * statement written twice. This fake stores what the repository writes and
 * hands back what a real table would, so
 * {@link DynamoDbJobControlContractTest} and
 * {@link DynamoDbJobControlProjectionTest} assert against a ledger the
 * repository actually built.
 *
 * <p>Four DynamoDB behaviours are modelled because the repository depends on
 * each of them:
 *
 * <ul>
 *   <li><b>Composite-key overwrite.</b> A {@code PutItem} at an existing
 *       {@code (run_id, event_seq)} replaces that item. Append-only holds
 *       because every append mints a new sort key, and this fake would silently
 *       lose an item if that ever stopped being true.
 *   <li><b>{@code attribute_not_exists(run_id)}</b> evaluated against the item
 *       at the request's exact key — which is what makes {@code createJob}'s
 *       sentinel sort key an atomic INSERT.
 *   <li><b>Sort-key ordering.</b> A {@code Query} returns a partition's items
 *       ascending by {@code event_seq}; a {@code Scan} deliberately does
 *       <em>not</em> promise order, so this fake returns scanned items in an
 *       order the repository must not rely on.
 *   <li><b>Pagination.</b> Both reads return at most {@link #PAGE_SIZE} items
 *       per call with a {@code LastEvaluatedKey}, so an unpaginated caller
 *       reads a truncated history. A final page carries an <em>empty</em>
 *       {@code LastEvaluatedKey} map, not null, exactly as the SDK does.
 * </ul>
 *
 * <p>Anything else — {@code UpdateItem}, {@code DeleteItem},
 * {@code BatchWriteItem}, an unrecognised condition or filter expression —
 * is left to the interface's default methods, which throw
 * {@link UnsupportedOperationException}. That is deliberate: an adapter that
 * starts mutating, or filters a scan on a mutable attribute, meets an explicit
 * refusal rather than a guess.
 */
final class InMemoryDynamoDb implements DynamoDbClient {

    /** Small enough that every contract-test read spans several pages. */
    static final int PAGE_SIZE = 2;

    /** table name -> composite key -> item. Sorted: pk, then sk. */
    private final Map<String, TreeMap<String, Map<String, AttributeValue>>> tables =
            new LinkedHashMap<>();

    /** Distinguishes repeated {@link #injectLate} calls. */
    private int lateCounter;

    @Override
    public String serviceName() {
        return "dynamodb-in-memory";
    }

    @Override
    public void close() {
        // Nothing to release.
    }

    // --- writes ------------------------------------------------------------

    @Override
    public PutItemResponse putItem(PutItemRequest request) {
        Map<String, AttributeValue> item = request.item();
        String key = compositeKey(item);
        TreeMap<String, Map<String, AttributeValue>> table = table(request.tableName());

        String condition = request.conditionExpression();
        if (condition != null) {
            if (!condition.equals("attribute_not_exists("
                    + DynamoDbJobControlRepository.ATTR_RUN_ID + ")")) {
                throw new UnsupportedOperationException(
                        "InMemoryDynamoDb models only attribute_not_exists(run_id); got: " + condition);
            }
            if (table.containsKey(key)) {
                throw ConditionalCheckFailedException.builder()
                        .message("The conditional request failed").build();
            }
        }

        table.put(key, new HashMap<>(item));
        return PutItemResponse.builder().build();
    }

    // --- reads -------------------------------------------------------------

    @Override
    public QueryResponse query(QueryRequest request) {
        if (!"#run_id = :run_id".equals(request.keyConditionExpression())) {
            throw new UnsupportedOperationException(
                    "InMemoryDynamoDb models only a single-partition query; got: "
                            + request.keyConditionExpression());
        }
        if (Boolean.FALSE.equals(request.scanIndexForward())) {
            throw new UnsupportedOperationException(
                    "InMemoryDynamoDb returns a partition ascending only");
        }
        String runId = request.expressionAttributeValues().get(":run_id").s();

        List<Map.Entry<String, Map<String, AttributeValue>>> partition = new ArrayList<>();
        for (Map.Entry<String, Map<String, AttributeValue>> entry
                : table(request.tableName()).entrySet()) {
            if (runId.equals(entry.getValue()
                    .getOrDefault(DynamoDbJobControlRepository.ATTR_RUN_ID,
                            AttributeValue.fromS("")).s())) {
                partition.add(entry);
            }
        }

        Page page = pageOf(partition, request.exclusiveStartKey());
        return QueryResponse.builder()
                .items(page.items)
                .lastEvaluatedKey(page.lastEvaluatedKey)
                .count(page.items.size())
                .build();
    }

    @Override
    public ScanResponse scan(ScanRequest request) {
        List<Map.Entry<String, Map<String, AttributeValue>>> matched = new ArrayList<>();
        // Descending on purpose: a real Scan promises no order, so a repository
        // that assumed key order here would pass its tests and mis-project in
        // production. DynamoDbJobControlRepository.projectEach sorts for itself.
        for (Map.Entry<String, Map<String, AttributeValue>> entry
                : table(request.tableName()).descendingMap().entrySet()) {
            if (matches(entry.getValue(), request)) {
                matched.add(entry);
            }
        }

        Page page = pageOf(matched, request.exclusiveStartKey());
        return ScanResponse.builder()
                .items(page.items)
                .lastEvaluatedKey(page.lastEvaluatedKey)
                .count(page.items.size())
                .build();
    }

    /**
     * Evaluates a {@code FilterExpression} of the one shape the repository
     * builds: a conjunction of {@code #name = :value} equality tests. Anything
     * else is refused rather than approximated.
     */
    private static boolean matches(Map<String, AttributeValue> item, ScanRequest request) {
        String filter = request.filterExpression();
        if (filter == null) {
            return true;
        }
        for (String term : filter.split(" AND ")) {
            String[] sides = term.trim().split(" = ");
            if (sides.length != 2 || !sides[0].startsWith("#") || !sides[1].startsWith(":")) {
                throw new UnsupportedOperationException(
                        "InMemoryDynamoDb models only '#name = :value' conjunctions; got: " + filter);
            }
            String attribute = request.expressionAttributeNames().get(sides[0]);
            AttributeValue expected = request.expressionAttributeValues().get(sides[1]);
            if (attribute == null || expected == null) {
                throw new IllegalArgumentException("unbound name or value in filter: " + term);
            }
            if (!expected.equals(item.get(attribute))) {
                return false;
            }
        }
        return true;
    }

    /** One page of results plus the key that continues it (empty when done). */
    private static final class Page {
        private final List<Map<String, AttributeValue>> items = new ArrayList<>();
        private Map<String, AttributeValue> lastEvaluatedKey = Map.of();
    }

    private static Page pageOf(List<Map.Entry<String, Map<String, AttributeValue>>> entries,
                               Map<String, AttributeValue> exclusiveStartKey) {
        // Resume by position in this read's own order rather than by key
        // comparison: a Scan's order is not the key order, and paging must
        // still visit every item exactly once.
        int from = 0;
        if (exclusiveStartKey != null && !exclusiveStartKey.isEmpty()) {
            String after = compositeKey(exclusiveStartKey);
            for (int i = 0; i < entries.size(); i++) {
                if (entries.get(i).getKey().equals(after)) {
                    from = i + 1;
                    break;
                }
            }
        }

        Page page = new Page();
        for (Map.Entry<String, Map<String, AttributeValue>> entry
                : entries.subList(from, entries.size())) {
            if (page.items.size() == PAGE_SIZE) {
                // More to come: hand back the key of the last item returned,
                // as DynamoDB does.
                Map<String, AttributeValue> last = page.items.get(page.items.size() - 1);
                page.lastEvaluatedKey = Map.of(
                        DynamoDbJobControlRepository.ATTR_RUN_ID,
                        last.get(DynamoDbJobControlRepository.ATTR_RUN_ID),
                        DynamoDbJobControlRepository.ATTR_EVENT_SEQ,
                        last.get(DynamoDbJobControlRepository.ATTR_EVENT_SEQ));
                break;
            }
            page.items.add(entry.getValue());
        }
        return page;
    }

    // --- test-only inspection / seeding ------------------------------------

    /**
     * Writes an item with no condition and no repository involvement — the way
     * a racing writer, a replayed event or a second process would land one.
     * {@link DynamoDbJobControlProjectionTest} uses it to put a contradicting
     * state into the ledger behind the repository's back.
     */
    void inject(String tableName, Map<String, AttributeValue> item) {
        table(tableName).put(compositeKey(item), new HashMap<>(item));
    }

    /**
     * The fake side of {@code JobControlRepositoryContractTest.appendRaw}, and
     * the same idea as {@code InMemoryBigQueryLedger.appendRaw} /
     * {@code InMemoryAthenaLedger.appendRaw} — it takes the table name too,
     * because this fake models more than one table, and an optional error code.
     *
     * <p>Copies a run's newest item back into the ledger under a sort key that
     * follows every generated one, with a different status: what a writer that
     * raced the repository's read-then-append guard, or a redelivered event,
     * leaves behind. The suffix counter keeps repeated calls from overwriting
     * one another, which would be the one thing an append-only ledger must not
     * do.
     *
     * <p>Spelled out rather than taken from the clock on purpose: generated
     * keys are microsecond-resolution, and a tie would make a projection test a
     * coin flip.
     *
     * @param errorCode optional error_code to stamp on the injected item, or
     *                  {@code null} to leave the copied one alone.
     */
    void appendRaw(String tableName, String runId, String statusValue, String errorCode) {
        List<Map<String, AttributeValue>> existing = itemsFor(tableName, runId);
        if (existing.isEmpty()) {
            throw new IllegalStateException("inject after the run has some history: " + runId);
        }
        Map<String, AttributeValue> late = new HashMap<>(existing.get(existing.size() - 1));
        late.put(DynamoDbJobControlRepository.ATTR_EVENT_SEQ,
                AttributeValue.fromS(String.format("99999999999999999999-late-%04d",
                        lateCounter++)));
        late.put(DynamoDbJobControlRepository.ATTR_STATUS, AttributeValue.fromS(statusValue));
        if (errorCode != null) {
            late.put(DynamoDbJobControlRepository.ATTR_ERROR_CODE, AttributeValue.fromS(errorCode));
        }
        inject(tableName, late);
    }

    /** Every stored item for one run, oldest first. */
    List<Map<String, AttributeValue>> itemsFor(String tableName, String runId) {
        List<Map<String, AttributeValue>> out = new ArrayList<>();
        for (Map<String, AttributeValue> item : table(tableName).values()) {
            if (runId.equals(item.getOrDefault(DynamoDbJobControlRepository.ATTR_RUN_ID,
                    AttributeValue.fromS("")).s())) {
                out.add(item);
            }
        }
        return out;
    }

    // --- internals ---------------------------------------------------------

    private TreeMap<String, Map<String, AttributeValue>> table(String tableName) {
        return tables.computeIfAbsent(tableName, k -> new TreeMap<>());
    }

    /**
     * The stored key: partition key then sort key, so the {@code TreeMap}'s
     * natural order is DynamoDB's.
     */
    private static String compositeKey(Map<String, AttributeValue> item) {
        AttributeValue runId = item.get(DynamoDbJobControlRepository.ATTR_RUN_ID);
        AttributeValue eventSeq = item.get(DynamoDbJobControlRepository.ATTR_EVENT_SEQ);
        if (runId == null || runId.s() == null || eventSeq == null || eventSeq.s() == null) {
            throw new IllegalArgumentException(
                    "item is missing the run_id/event_seq key pair: " + item.keySet());
        }
        return runId.s() + '\0' + eventSeq.s();
    }
}
