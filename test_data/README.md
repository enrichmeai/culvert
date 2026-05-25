# Test Data Fixtures

Fixtures used by the framework's unit tests, local Airflow stack, and the
end-to-end harness (`scripts/gcp/e2e_pipeline_test.sh`).

## Layout

```
test_data/
├── generic_customers_20260417.csv    # + .ok
├── generic_accounts_20260417.csv     # + .ok
├── generic_decision_20260417.csv     # + .ok
├── generic_applications_20260417.csv # + .ok
└── generic_customers_20260318.csv    # legacy single-row smoke file
```

Each `.csv` carries an `HDR|…` header line and a `TRL|RecordCount=…|Checksum=…`
trailer line. The accompanying `.ok` file is the landing-signal artefact the
mainframe ingestion pattern expects.

## Valid / invalid mix

Every fixture has **8 valid rows and 2 deliberately-invalid rows**, chosen to
exercise the different failure modes:

- `customers` — one row with a malformed postcode + bad timestamp; one with a
  non-date `date_of_birth`.
- `accounts` — one row with a null `balance_gbp`; one with a non-existent
  `customer_id` foreign key; one with a non-numeric balance.
- `decision` — all 7 rows are valid. Used for clean-path tests.
- `applications` — all 7 rows are valid. Used for clean-path tests.

The reconciliation engine should reject the invalid rows into the error bucket
and still mark the run green. The data-quality scorer should give each fixture
a grade of at least B.

## Regenerating

The fixture contents are hand-curated rather than generated. If you change the
`EntitySchema` definitions, update the corresponding CSV by hand and update the
`TRL|RecordCount=…` number. The integrity checksum (`Checksum=…`) is advisory
only in these fixtures and is not verified by default.
