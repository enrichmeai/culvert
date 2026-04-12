# Segment Template Guide

How to create new mainframe segment templates (TRIAD, CDS) without touching Python code.

---

## How It Works

```
  YAML template         Pipeline runner         GCS output
  (you write this)      (runs automatically)    (mainframe consumes)
  +--------------+      +------------------+    +-------------------+
  | segment_id   | ---> | Load template    |    | CUST-00000-of-    |
  | query        |      | Execute query    | -> |   00001.dat       |
  | output.fields|      | Format rows      |    | CUST.manifest     |
  +--------------+      | Write files      |    +-------------------+
                        +------------------+
```

Each segment is defined entirely by a YAML template. The template has three sections:

1. **source** -- which CDP BigQuery table (used for job control metadata and logging)
2. **query** -- the SQL that Dataflow executes against BigQuery (this is what actually runs)
3. **output** -- the fixed-width record layout (fields, widths, types, formatting)

The pipeline reads the template, runs the query via BigQuery DIRECT_READ, and formats each
result row into a fixed-width record. Output is written to GCS as sharded `.dat` files plus
a `.manifest` JSON file.

---

## Step-by-Step: Add a New Segment

### Step 1: Design the record layout

Before writing any YAML, sketch the record layout on paper or in a table. You need:
- The total record length (agreed with the mainframe team)
- Each field's name, position, width, type, and source column
- A filler field at the end to pad the record to the required length

**Rule:** All field widths must sum to exactly `record_length`. The pipeline validates
this at startup and rejects the template if they don't match.

### Step 2: Write the SQL query

The query is standard BigQuery SQL. It runs via Dataflow's `ReadFromBigQuery` with
`DIRECT_READ` (no temporary GCS export). The query must contain three placeholders:

| Placeholder      | Resolved To                                 | Format           |
|------------------|---------------------------------------------|------------------|
| `{project}`      | `--gcp_project` CLI parameter               | `my-gcp-project` |
| `{period_start}` | First day of `--extract_month`              | `2026-03-01`     |
| `{period_end}`   | Last day of `--extract_month`               | `2026-03-31`     |

The column names in your SELECT clause become the `source` values in your field definitions.
They must match exactly (case-sensitive).

**Important:** The `source.dataset` and `source.table` in the YAML are metadata for job
control and logging. The `query` is what Dataflow actually executes. They should reference
the same table, but the query is the authority.

### Step 3: Create the template YAML

Create `config/templates/{segment_id}.yaml`:

```yaml
segment_id: credit_card
segment_name: Credit Card
description: "Credit card account segment for CDS mainframe"
record_length: 250

source:
  dataset: cdp_generic
  table: customer_risk_profile
  partition_column: updated_at

query: |
  SELECT
    customer_id,
    card_number_masked,
    credit_limit,
    current_balance,
    interest_rate,
    status,
    open_date
  FROM `{project}.cdp_generic.credit_card_accounts`
  WHERE status IN ('ACTIVE', 'SUSPENDED')
    AND updated_at BETWEEN '{period_start}' AND '{period_end}'

output:
  file_prefix: "CCRD"
  file_suffix: ".dat"
  shard_template: "-SSSSS-of-NNNNN"
  max_records_per_shard: 1000000

  fields:
    - name: segment_type
      source: _literal
      literal_value: "CCRD"
      width: 4
      type: string
    # ... remaining fields ...
```

### Step 4: Register in system.yaml

Add the segment ID to the `segments` list in `config/system.yaml`:

```yaml
segments:
  - customer
  - credit_card    # <-- add here
```

The pipeline rejects any segment ID not listed here.

### Step 5: Test locally with DirectRunner

```bash
cd deployments/mainframe-segment-transform

PYTHONPATH=src python -m segment_transform.pipeline.runner \
    --segment credit_card \
    --extract_date 20260331 \
    --extract_month 202603 \
    --output_bucket my-project-generic-int-segments \
    --run_id local_test_001 \
    --gcp_project my-project \
    --runner DirectRunner
```

Check the output in GCS:
```
gs://{bucket}/segments/202603/local_test_001/credit_card/
  CCRD-00000-of-00001.dat     <-- data file(s)
  CCRD.manifest               <-- JSON manifest
```

### Step 6: Validate the output

1. Download a data file and check that every line is exactly `record_length` characters
2. Read the manifest to confirm `total_records` matches expectations
3. Spot-check specific field positions against the record layout
4. Verify NULL handling produces the expected fill values (spaces, zeros, etc.)

### Step 7: Run unit tests

Existing template loader tests automatically validate all registered segments:
```bash
PYTHONPATH=src pytest tests/unit/ -v
```

This checks that field widths sum to `record_length`, that the query contains all
three placeholders, and that `source.partition_column` is set.

---

## Field Type Reference

### string

Formats text values with padding and optional truncation.

| Property    | Effect                                                        |
|-------------|---------------------------------------------------------------|
| `align`     | `left` (default): pad right. `right`: pad left                |
| `pad_char`  | Character for padding (default: space)                        |
| Truncation  | Values longer than `width` are silently truncated             |
| NULL        | Treated as empty string, filled with `pad_char`               |
| Non-string  | Coerced via `str()` -- integers, floats become their string form |

```yaml
- name: customer_id
  source: customer_id
  width: 20
  type: string
  align: left
  pad_char: " "
```

Input `"C001"` at width 20 => `"C001                "` (16 spaces of padding)

### integer

Formats whole numbers. Fractional values are truncated (not rounded).

| Property    | Effect                                                        |
|-------------|---------------------------------------------------------------|
| `align`     | `left` or `right` (right with `"0"` pad is most common)      |
| `pad_char`  | `"0"` for zero-fill, `" "` for space-fill                    |
| NULL        | Treated as `0`                                                |
| Non-numeric | Falls back to `0` (logs no error)                             |
| Negative    | The minus sign consumes one character position                |

```yaml
- name: account_count
  source: account_count
  width: 6
  type: integer
  align: right
  pad_char: "0"
```

Input `42` at width 6, right-aligned, pad `"0"` => `"000042"`
Input `-42` at width 6, right-aligned, pad `" "` => `"   -42"` (sign uses 1 position)

### amount

Formats monetary values with fixed decimal places. Always right-aligned.

| Property         | Effect                                                   |
|------------------|----------------------------------------------------------|
| `decimal_places` | Number of decimal digits (default: 2)                    |
| `pad_char`       | Fill character (default: space)                          |
| NULL             | Treated as `0.00` (or `0.0000` etc.)                    |
| Negative         | The minus sign and decimal point both consume positions  |

```yaml
- name: total_balance
  source: total_balance
  width: 15
  type: amount
  decimal_places: 2
  pad_char: " "
```

Input `12345.67` at width 15 => `"       12345.67"` (7 spaces + 8 chars)
Input `-500.00` at width 15 => `"        -500.00"` (8 spaces + 7 chars)
Input `NULL` at width 15 => `"           0.00"` (11 spaces + 4 chars)

**Width planning for amounts:** Account for the decimal point (1 char), decimal digits,
sign (1 char if negative values are possible), and the maximum expected integer digits.
Formula: `width >= max_integer_digits + 1 (decimal point) + decimal_places + 1 (sign)`

### rate

Formats interest rates. Identical behaviour to `amount` -- both use the same code path.
Use `rate` for semantic clarity (rates vs money).

```yaml
- name: interest_rate
  source: interest_rate
  width: 8
  type: rate
  decimal_places: 4
  pad_char: " "
```

Input `5.25` at width 8 => `"  5.2500"` (2 spaces + 6 chars)

### date

Formats date/datetime values using a strftime format string.

| Property      | Effect                                                      |
|---------------|-------------------------------------------------------------|
| `date_format` | Python strftime pattern (default: `%Y%m%d`)                 |
| `null_value`  | Value when source is NULL (e.g. `"00000000"`)               |
| Accepted input| `datetime.date`, `datetime.datetime`, or string in ISO format |

BigQuery DATE columns arrive as `datetime.date`. TIMESTAMP columns arrive as
`datetime.datetime`. Both are handled automatically. String dates are parsed
from three formats: `YYYY-MM-DD`, `YYYYMMDD`, and `YYYY-MM-DD HH:MM:SS`.

Timezone-aware datetimes format correctly -- the date is taken as-is from the
datetime object, not converted to UTC.

```yaml
- name: open_date
  source: open_date
  width: 8
  type: date
  date_format: "%Y%m%d"
  null_value: "00000000"
```

Input `date(2026, 3, 30)` => `"20260330"`
Input `None` with null_value `"00000000"` => `"00000000"`

**Alternative date formats:**

| date_format    | Output for 2026-03-30 | Width needed |
|----------------|-----------------------|--------------|
| `%Y%m%d`       | `20260330`            | 8            |
| `%m%d%Y`       | `03302026`            | 8            |
| `%Y-%m-%d`     | `2026-03-30`          | 10           |
| `%d/%m/%Y`     | `30/03/2026`          | 10           |
| `%Y%m%d%H%M%S` | `20260330120000`      | 14           |

### filler

Fills the field with `pad_char` repeated `width` times. Ignores any input value.

```yaml
- name: filler
  source: _literal
  literal_value: ""
  width: 65
  type: filler
  pad_char: " "
```

Always produces: `" " * width` (or `"0" * width`, etc.)

---

## Special Source Values

### _literal

Uses the `literal_value` property instead of a BigQuery column. Common uses:
- Segment type identifiers: `literal_value: "CUST"`, type `string`
- Record type codes: `literal_value: "D"` (detail record)
- Filler fields: `literal_value: ""`, type `filler`

### _extract_date

Uses the runtime `--extract_date` parameter (format: YYYYMMDD). Typically formatted
as a date field:

```yaml
- name: extract_date
  source: _extract_date
  width: 8
  type: date
  date_format: "%Y%m%d"
  null_value: "00000000"
```

This stamps every record with the extract run date without requiring it in the query.

---

## Query Patterns

### Basic: Single table

```sql
SELECT customer_id, first_name, last_name, status
FROM `{project}.cdp_generic.customer_risk_profile`
WHERE status IN ('ACTIVE', 'DORMANT')
  AND updated_at BETWEEN '{period_start}' AND '{period_end}'
```

### Multi-table JOIN

The query is standard BigQuery SQL. JOINs work exactly as expected. The column
names in the SELECT become the `source` values in your field definitions.

```sql
SELECT
  c.customer_id,
  c.first_name,
  c.last_name,
  a.account_number,
  a.balance,
  a.interest_rate
FROM `{project}.cdp_generic.customer_risk_profile` c
JOIN `{project}.cdp_generic.account_summary` a
  ON c.customer_id = a.customer_id
WHERE c.status = 'ACTIVE'
  AND a.updated_at BETWEEN '{period_start}' AND '{period_end}'
```

**Important:** When using JOINs, the `source.table` in the YAML should reference the
primary/driving table. It is used for logging and job control metadata only.

### Computed columns

Use SQL aliases to create derived fields. The alias name becomes the `source` in your
field definition:

```sql
SELECT
  customer_id,
  CONCAT(last_name, ', ', first_name) AS full_name,
  DATE_DIFF(CURRENT_DATE(), date_of_birth, YEAR) AS age,
  total_balance / account_count AS avg_balance
FROM `{project}.cdp_generic.customer_risk_profile`
WHERE updated_at BETWEEN '{period_start}' AND '{period_end}'
```

Then reference in fields:
```yaml
- name: full_name
  source: full_name      # matches the SQL alias
  width: 40
  type: string
```

### Conditional values with CASE WHEN

```sql
SELECT
  customer_id,
  CASE
    WHEN risk_score >= 80 THEN 'HIGH'
    WHEN risk_score >= 50 THEN 'MEDIUM'
    ELSE 'LOW'
  END AS risk_band,
  CASE
    WHEN total_balance > 0 THEN 'CR'
    ELSE 'DR'
  END AS balance_indicator
FROM `{project}.cdp_generic.customer_risk_profile`
WHERE updated_at BETWEEN '{period_start}' AND '{period_end}'
```

### Aggregation

```sql
SELECT
  customer_id,
  COUNT(*) AS transaction_count,
  SUM(amount) AS total_amount,
  MAX(transaction_date) AS last_transaction_date
FROM `{project}.cdp_generic.transactions`
WHERE transaction_date BETWEEN '{period_start}' AND '{period_end}'
GROUP BY customer_id
```

---

## Output Files and Manifest

### Data files

Each segment run produces one or more sharded data files in GCS:

```
gs://{bucket}/segments/{period}/{run_id}/{segment_id}/
  {file_prefix}-00000-of-00003.dat
  {file_prefix}-00001-of-00003.dat
  {file_prefix}-00002-of-00003.dat
  {file_prefix}.manifest
```

Each line in a data file is exactly `record_length` characters. No delimiters, no
newline at end of record (Beam's `WriteToText` adds newlines between records).

Sharding is controlled by `max_records_per_shard`:
- `1000000` (default): ~1M records per file, ~200 MB per file at 200 chars/record
- `0`: disables sharding -- Beam decides (not recommended for large volumes)

### Manifest file

The manifest is a JSON file written alongside the data files:

```json
{
  "segment": "customer",
  "period": "202603",
  "run_id": "manual_20260330_001",
  "extract_date": "20260330",
  "total_records": 5000000,
  "record_length": 200,
  "num_shards": 5,
  "max_records_per_shard": 1000000,
  "file_pattern": "CUST-*-of-*.dat"
}
```

| Field                   | Description                                           |
|-------------------------|-------------------------------------------------------|
| `segment`               | Segment ID from the template                          |
| `period`                | Extract month (YYYYMM)                                |
| `run_id`                | Unique run identifier                                 |
| `extract_date`          | Extract date (YYYYMMDD)                               |
| `total_records`         | Number of records written across all shards            |
| `record_length`         | Fixed record length in characters                     |
| `num_shards`            | Number of data files produced                         |
| `max_records_per_shard` | Configured shard limit                                |
| `file_pattern`          | Glob pattern to find data files                       |

Mainframe consumers should use `total_records` to verify completeness and
`file_pattern` to discover all data files.

---

## Worked Example: CDS Credit Card Segment

The CDS mainframe application needs a monthly credit card extract: 250-char records
with customer identification, card details, balances, and rates. The source data
comes from two tables joined on customer_id.

### Record layout

```
Position    Width  Field              Type      Source
----------  -----  -----------------  --------  ---------------------------
  0-  3       4    segment_type       string    _literal ("CCRD")
  4- 23      20    customer_id        string    customer_id
 24- 42      19    card_number_masked string    card_number_masked
 43- 57      15    credit_limit       amount    credit_limit (dp=2)
 58- 72      15    current_balance    amount    current_balance (dp=2)
 73- 87      15    available_credit   amount    available_credit (dp=2)
 88- 95       8    interest_rate      rate      interest_rate (dp=4)
 96-103       8    status             string    account_status
104-111       8    open_date          date      open_date
112-119       8    last_payment_date  date      last_payment_date
120-134      15    last_payment_amt   amount    last_payment_amount (dp=2)
135-138       4    risk_band          string    risk_band
139-146       8    extract_date       date      _extract_date
147-249     103    filler             filler    _literal ("")
                                                -----
                                      Total:    250
```

Verify: 4+20+19+15+15+15+8+8+8+8+15+4+8+103 = 250

### Template YAML

`config/templates/cds_credit_card.yaml`:

```yaml
# =============================================================================
# CDS Credit Card Segment Template
# =============================================================================
# Source: customer_risk_profile JOIN credit_card_accounts
# Output: Fixed-width 250-char records for CDS mainframe
# =============================================================================
segment_id: cds_credit_card
segment_name: CDS Credit Card
description: "Credit card account segment for CDS mainframe application"
record_length: 250

source:
  dataset: cdp_generic
  table: credit_card_accounts
  partition_column: updated_at

query: |
  SELECT
    c.customer_id,
    a.card_number_masked,
    a.credit_limit,
    a.current_balance,
    a.credit_limit - a.current_balance AS available_credit,
    a.interest_rate,
    a.status AS account_status,
    a.open_date,
    a.last_payment_date,
    a.last_payment_amount,
    CASE
      WHEN c.risk_score >= 80 THEN 'HIGH'
      WHEN c.risk_score >= 50 THEN 'MED '
      ELSE 'LOW '
    END AS risk_band
  FROM `{project}.cdp_generic.customer_risk_profile` c
  JOIN `{project}.cdp_generic.credit_card_accounts` a
    ON c.customer_id = a.customer_id
  WHERE a.status IN ('ACTIVE', 'SUSPENDED')
    AND a.updated_at BETWEEN '{period_start}' AND '{period_end}'

output:
  file_prefix: "CCRD"
  file_suffix: ".dat"
  shard_template: "-SSSSS-of-NNNNN"
  max_records_per_shard: 1000000

  fields:
    - name: segment_type
      source: _literal
      literal_value: "CCRD"
      width: 4
      type: string
      align: left
      pad_char: " "

    - name: customer_id
      source: customer_id
      width: 20
      type: string
      align: left
      pad_char: " "

    - name: card_number_masked
      source: card_number_masked
      width: 19
      type: string
      align: left
      pad_char: " "

    - name: credit_limit
      source: credit_limit
      width: 15
      type: amount
      decimal_places: 2
      pad_char: " "

    - name: current_balance
      source: current_balance
      width: 15
      type: amount
      decimal_places: 2
      pad_char: " "

    - name: available_credit
      source: available_credit
      width: 15
      type: amount
      decimal_places: 2
      pad_char: " "

    - name: interest_rate
      source: interest_rate
      width: 8
      type: rate
      decimal_places: 4
      pad_char: " "

    - name: account_status
      source: account_status
      width: 8
      type: string
      align: left
      pad_char: " "

    - name: open_date
      source: open_date
      width: 8
      type: date
      date_format: "%Y%m%d"
      null_value: "00000000"

    - name: last_payment_date
      source: last_payment_date
      width: 8
      type: date
      date_format: "%Y%m%d"
      null_value: "00000000"

    - name: last_payment_amount
      source: last_payment_amount
      width: 15
      type: amount
      decimal_places: 2
      pad_char: " "

    - name: risk_band
      source: risk_band
      width: 4
      type: string
      align: left
      pad_char: " "

    - name: extract_date
      source: _extract_date
      width: 8
      type: date
      date_format: "%Y%m%d"
      null_value: "00000000"

    - name: filler
      source: _literal
      literal_value: ""
      width: 103
      type: filler
      pad_char: " "
```

### What this example demonstrates

| Pattern                    | Where in the example                                     |
|----------------------------|----------------------------------------------------------|
| Multi-table JOIN           | `customer_risk_profile JOIN credit_card_accounts`        |
| Computed column            | `credit_limit - current_balance AS available_credit`     |
| CASE WHEN                  | `risk_band` derived from `risk_score`                    |
| Column aliasing            | `a.status AS account_status`                             |
| Multiple amount fields     | `credit_limit`, `current_balance`, `available_credit`    |
| Rate field                 | `interest_rate` with 4 decimal places                    |
| Multiple date fields       | `open_date`, `last_payment_date`                         |
| Filler for padding         | 103-char filler at the end                               |

### Register and run

```bash
# 1. Add to system.yaml
#    segments:
#      - customer
#      - cds_credit_card

# 2. Test locally
cd deployments/mainframe-segment-transform
PYTHONPATH=src python -m segment_transform.pipeline.runner \
    --segment cds_credit_card \
    --extract_date 20260331 \
    --extract_month 202603 \
    --output_bucket my-project-generic-int-segments \
    --run_id cds_test_001 \
    --gcp_project my-project \
    --runner DirectRunner
```

---

## Worked Example: TRIAD Customer Segment

The TRIAD mainframe application needs a simpler customer extract: 150-char records
with customer identification and risk data.

### Record layout

```
Position    Width  Field            Type
----------  -----  ---------------  ------
  0-  4       5    segment_type     string   (_literal: "TRIAD")
  5- 24      20    customer_id      string
 25- 49      25    first_name       string
 50- 74      25    last_name        string
 75- 82       8    date_of_birth    date
 83- 88       6    risk_score       integer  (zero-filled)
 89- 98      10    risk_category    string
 99-106       8    extract_date     date     (_extract_date)
107-149      43    filler           filler
                                    -----
                           Total:   150
```

Verify: 5+20+25+25+8+6+10+8+43 = 150

### Template YAML

`config/templates/triad_customer.yaml`:

```yaml
# =============================================================================
# TRIAD Customer Segment Template
# =============================================================================
segment_id: triad_customer
segment_name: TRIAD Customer
description: "Customer demographic and risk segment for TRIAD mainframe"
record_length: 150

source:
  dataset: cdp_generic
  table: customer_risk_profile
  partition_column: updated_at

query: |
  SELECT
    customer_id,
    first_name,
    last_name,
    date_of_birth,
    risk_score,
    risk_category
  FROM `{project}.cdp_generic.customer_risk_profile`
  WHERE status = 'ACTIVE'
    AND updated_at BETWEEN '{period_start}' AND '{period_end}'

output:
  file_prefix: "TRIAD"
  file_suffix: ".dat"
  shard_template: "-SSSSS-of-NNNNN"
  max_records_per_shard: 1000000

  fields:
    - name: segment_type
      source: _literal
      literal_value: "TRIAD"
      width: 5
      type: string
      align: left
      pad_char: " "

    - name: customer_id
      source: customer_id
      width: 20
      type: string
      align: left
      pad_char: " "

    - name: first_name
      source: first_name
      width: 25
      type: string
      align: left
      pad_char: " "

    - name: last_name
      source: last_name
      width: 25
      type: string
      align: left
      pad_char: " "

    - name: date_of_birth
      source: date_of_birth
      width: 8
      type: date
      date_format: "%Y%m%d"
      null_value: "00000000"

    - name: risk_score
      source: risk_score
      width: 6
      type: integer
      align: right
      pad_char: "0"

    - name: risk_category
      source: risk_category
      width: 10
      type: string
      align: left
      pad_char: " "

    - name: extract_date
      source: _extract_date
      width: 8
      type: date
      date_format: "%Y%m%d"
      null_value: "00000000"

    - name: filler
      source: _literal
      literal_value: ""
      width: 43
      type: filler
      pad_char: " "
```

---

## Field Definition Properties

| Property         | Required | Default    | Description                                       |
|------------------|----------|------------|---------------------------------------------------|
| `name`           | yes      |            | Field name (for documentation, debugging, error messages) |
| `source`         | yes      |            | BigQuery column name, `_literal`, or `_extract_date` |
| `width`          | yes      |            | Fixed width in characters (must be > 0)           |
| `type`           | yes      |            | One of: `string`, `integer`, `amount`, `rate`, `date`, `filler` |
| `align`          | no       | `left`     | `left` or `right`                                 |
| `pad_char`       | no       | `" "`      | Single character for padding (must be exactly 1 char) |
| `decimal_places` | no       | `2`        | Decimal precision for `amount` and `rate` types    |
| `date_format`    | no       | `%Y%m%d`   | Python strftime pattern for `date` type            |
| `null_value`     | no       | `""`       | Fill value when source column is NULL              |
| `literal_value`  | no       | `""`       | Fixed value for `_literal` source fields           |

---

## NULL Handling by Type

Each field type handles NULL values differently. Understanding this is important for
mainframe consumers who may interpret specific fill patterns.

| Type      | NULL becomes                           | Example (width=10)          |
|-----------|----------------------------------------|-----------------------------|
| `string`  | Empty string, filled with `pad_char`   | `"          "` (10 spaces)  |
| `integer` | `0`, then formatted                    | `"0000000000"` (pad `"0"`)  |
| `amount`  | `0.00`, then formatted                 | `"      0.00"` (dp=2)      |
| `rate`    | `0.0000`, then formatted               | `"    0.0000"` (dp=4)      |
| `date`    | `null_value` if set, else `"0"*width`  | `"00000000"` or custom      |
| `filler`  | N/A -- always produces `pad_char*width`| `"          "`              |

**Recommendation:** Always set `null_value: "00000000"` on date fields so mainframe
consumers see a consistent sentinel value rather than relying on default behaviour.

---

## Sharding Strategy

The `max_records_per_shard` setting controls how many records go into each output file.
The right value depends on your mainframe consumer:

| Scenario                             | Recommended setting  | Why                         |
|--------------------------------------|----------------------|-----------------------------|
| Mainframe expects a single file      | `0`                  | Beam decides (usually 1)    |
| Large volume (>1M records)           | `1000000`            | ~200 MB per file at 200 chars/record |
| Very large volume (>10M records)     | `500000`-`1000000`   | Manageable file sizes        |
| Mainframe has file size limit        | Calculate from limit | `limit_bytes / record_length` |

The shard template controls file naming:
- `"-SSSSS-of-NNNNN"` produces: `CUST-00000-of-00003.dat`, `CUST-00001-of-00003.dat`, etc.
- `"-SS-of-NN"` produces: `CUST-00-of-03.dat`, `CUST-01-of-03.dat`, etc.

---

## Limitations

These are current constraints of the pipeline. If your use case requires any of
these, the Python code would need to be extended.

| Limitation                        | Detail                                              |
|-----------------------------------|-----------------------------------------------------|
| No header/trailer records         | Mainframe files often have header (record type "H") and trailer (record type "T" with totals) records. This pipeline only produces detail records. |
| No EBCDIC encoding                | Output is UTF-8 text. If the mainframe requires EBCDIC, a post-processing conversion step is needed (e.g. `iconv` or a GCS Cloud Function). |
| No signed overpunch numerics      | Some mainframe formats encode the sign of the last digit using overpunch characters (e.g. `{` for +0, `}` for -0). Not supported. |
| No sequence numbers               | Some formats require sequence numbers in columns 73-80. Not supported. |
| Fixed set of query placeholders   | Only `{project}`, `{period_start}`, `{period_end}` are resolved. To add more, the Python code in `segment_pipeline.py` would need updating. |
| No cross-segment dependencies     | Each segment runs independently. One segment cannot reference another segment's output. |
| Record length is per-segment      | All records in a segment file have the same length. Variable-length records are not supported. |

---

## Pre-Deployment Checklist

Before registering a new segment template, verify every item:

**Record layout:**
- [ ] All field widths sum to exactly `record_length`
- [ ] `record_length` matches the value agreed with the mainframe team
- [ ] Filler field at the end pads to the exact record length
- [ ] Each field's `width` is large enough for the maximum expected value (including sign for amounts)
- [ ] Segment type literal matches what the mainframe consumer expects

**Query:**
- [ ] Contains all three placeholders: `{project}`, `{period_start}`, `{period_end}`
- [ ] All SELECT column names match `source` values in field definitions (case-sensitive)
- [ ] WHERE clause filters to the correct population (active accounts, correct period, etc.)
- [ ] Query runs successfully in BigQuery console with sample values substituted
- [ ] No curly braces `{}` in the query except the three placeholders (Python's `str.format` will fail)

**Fields:**
- [ ] Every `source` value is either a SELECT column name, `_literal`, or `_extract_date`
- [ ] `pad_char` is exactly one character on every field
- [ ] `null_value` is set on all date fields (typically `"00000000"`)
- [ ] `decimal_places` is set correctly on all `amount` and `rate` fields
- [ ] `date_format` is set on all `date` fields (default `%Y%m%d` if omitted)
- [ ] `type` is one of: `string`, `integer`, `amount`, `rate`, `date`, `filler`

**Testing:**
- [ ] Template validates: `PYTHONPATH=src pytest tests/unit/ -v` passes
- [ ] Local run with DirectRunner produces output files
- [ ] Sample record is exactly `record_length` characters
- [ ] Manifest `total_records` matches expectations
- [ ] Spot-checked field positions against the record layout
- [ ] NULL columns produce the expected fill values

**Registration:**
- [ ] Segment ID added to `config/system.yaml` under `segments`
- [ ] Template YAML file is at `config/templates/{segment_id}.yaml`
- [ ] `source.partition_column` is set (required by existing tests)

---

## Troubleshooting

### Field widths don't sum to record_length

```
ValueError: Segment 'credit_card': field widths sum to 248, expected 250
```

Add up all `width` values in the `fields` list. They must equal `record_length` exactly.
Adjust the filler field width to make up the difference. In this example, increase filler
by 2 (from the current value to current + 2).

### Segment not registered

```
ValueError: Segment 'credit_card' not registered in system.yaml. Available: ['customer']
```

Add the segment ID to the `segments` list in `config/system.yaml`.

### Query placeholder not resolved

```
KeyError: 'period_start'
```

Ensure the query contains all three placeholders: `{project}`, `{period_start}`,
`{period_end}`. They are case-sensitive. Also check for stray `{}` characters in the
query that Python's `str.format()` will try to interpret -- escape them as `{{` and `}}`.

### Column name mismatch

The pipeline runs but output has spaces or zeros where you expected data. This usually
means the `source` value in the field definition doesn't match the column name in the
SELECT clause. Check:
- Case sensitivity: `Customer_ID` is not `customer_id`
- Aliases: if you wrote `a.status AS account_status`, the source must be `account_status`,
  not `status`

### Invalid field type

```
ValueError: Field 'my_field': unknown type 'text', must be one of ['amount', 'date', 'filler', 'integer', 'rate', 'string']
```

Use one of the six supported types. `text` is not valid -- use `string`.

### Invalid pad_char

```
ValueError: Field 'my_field': pad_char must be a single character, got ''
```

`pad_char` must be exactly one character. Common values: `" "` (space), `"0"` (zero).
If you want no padding, you can't -- every field must pad to its full width.

### Invalid width

```
ValueError: Field 'my_field': width must be positive, got 0
```

Every field must have `width` > 0. If you don't need a field, remove it from the list.

### extract_date rejected

```
ValueError: extract_date must be 8-digit YYYYMMDD, got: '2026-03-30'
```

The `--extract_date` CLI parameter must be 8 digits with no separators: `20260330`,
not `2026-03-30`.

### Amount truncated or misaligned

If an amount like `99999999.99` doesn't fit in width 10, it will be truncated from the
left: `999999.99` (9 chars, right-aligned in width 10). Plan the width to accommodate the
largest expected value. See the width planning formula in the `amount` section above.

### Query runs in console but fails in pipeline

Common causes:
- Stray `{` or `}` in the SQL (use `{{` / `}}` to escape literal braces)
- Table not accessible by the Dataflow service account
- Column names in the query don't match what BigQuery returns (check aliases)
- Date/timestamp type mismatch (use `CAST(col AS DATE)` if needed)
