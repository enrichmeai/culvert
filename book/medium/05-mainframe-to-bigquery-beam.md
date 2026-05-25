# Mainframe to BigQuery: Parsing HDR/TRL Files with Apache Beam

### If you've ever had to ingest a mainframe extract into BigQuery, you've felt this pain. Here's how to actually handle it.

![End-to-end mainframe data flow](../diagrams/01-end-to-end-flow.svg)

---

Let me show you a file.

```
HDR|customers|20260417|0001|500000
0001|Alice Smith|1985-03-22|SW1A 1AA|2010-06-12T09:14:00Z
0002|Bob Jones |1979-11-04|EH8 9YL |2007-02-19T14:22:30Z
...
0500000|Zara Patel|1992-08-15|M1 1AA|2020-12-30T16:45:00Z
TRL|customers|20260417|0001|500000
```

That's a mainframe extract. HDR record at the top carries metadata — entity name, extract date, batch number, expected record count. TRL record at the bottom repeats it as a self-check. Body rows in between.

This pattern is older than most engineers who have to work with it. It's also basically everywhere: banks, insurers, telcos, governments. If you're migrating from a mainframe to GCP, you're going to meet HDR/TRL.

Apache Beam doesn't understand it natively. Nobody's open library does. So every team writes a parser. Every parser has its own bugs.

Here's how I solved it in `gcp-pipeline-framework`.

---

## Why HDR/TRL is trickier than it looks

Beam's parallel execution model assumes records are independent. HDR/TRL rows are not:

- The HDR is one record that describes all following records.
- The TRL is one record that cross-checks the count of all preceding records.
- Neither can be processed like a normal body row.

If you naively feed the whole file through a `beam.io.ReadFromText`, Beam happily shreds HDR and TRL across workers, and you end up with a pipeline that either crashes on parse or — worse — silently drops them and proceeds as though they weren't there.

You have to be deliberate.

---

## The pattern: a custom source

The framework solves this with a component called `HDRTRLParser`. It's a custom source that:

1. Reads the file as a single stream.
2. Peels off the HDR and TRL rows.
3. Yields the body as a normal PCollection.
4. Exposes the parsed HDR/TRL metadata as a side input.

Calling it looks like this:

```python
from gcp_pipeline_beam.file_management import HDRTRLParser
from gcp_pipeline_beam.pipelines.beam import BeamPipelineBuilder
from gcp_pipeline_beam.transforms import RobustCsvParseDoFn, SchemaValidateRecordDoFn
from my_schemas import CustomerSchema

builder = BeamPipelineBuilder(schema=CustomerSchema)

with builder.pipeline() as p:
    parser = HDRTRLParser(file_uri=options.input_file)
    raw, envelope = parser.expand(p)

    valid, invalid = (
        raw
        | "ParseCsv" >> beam.ParDo(RobustCsvParseDoFn(schema=CustomerSchema))
        | "Validate" >> beam.ParDo(SchemaValidateRecordDoFn(schema=CustomerSchema))
                           .with_outputs("invalid", main="valid")
    )

    builder.write_valid(valid, table=options.bq_table)
    builder.write_invalid(invalid, bucket=options.error_bucket)
    builder.reconcile(envelope=envelope, valid=valid, invalid=invalid)
```

Seven lines of pipeline body. Every production concern — audit, cost, error routing, reconciliation — handled by the builder.

---

## Robust CSV parsing (which is harder than it sounds)

Mainframe CSVs are not the same thing as `pandas.to_csv()` output. They have:

- Trailing whitespace on every field, because the mainframe pads to fixed widths.
- Mixed encodings (EBCDIC, latin-1, UTF-8) in the same batch.
- Embedded delimiters that may or may not be escaped.
- Empty trailing columns omitted on some rows.
- Date fields where `00000000` means null, not 1 January year zero.

`RobustCsvParseDoFn` handles all of this. The key pattern is that heavy initialisation goes in `setup()`, not `__init__`:

```python
class RobustCsvParseDoFn(beam.DoFn):
    def __init__(self, schema):
        self.schema = schema

    def setup(self):
        # Runs ONCE per worker, not once per element
        self._encodings = ["utf-8", "latin-1", "cp037"]

    def process(self, element):
        line = self._decode(element)
        if line is None:
            yield beam.pvalue.TaggedOutput(
                "invalid", {"reason": "decode-failed", "raw": repr(element)}
            )
            return
        cells = self._split(line)
        record = self._coerce(cells)
        yield record
```

This is the difference between a Dataflow job that runs in 8 minutes and one that runs in 8 hours. `__init__` runs on the driver. `setup()` runs on each worker. If you do the work in `__init__`, you pay for it every time Beam picks an element.

---

## Split-file reassembly

Mainframes love sending one logical extract as five files because their network can't cope with anything bigger:

```
customers.20260417.001of005.csv
customers.20260417.002of005.csv
customers.20260417.003of005.csv
customers.20260417.004of005.csv
customers.20260417.005of005.csv
customers.20260417.001of005.ok
customers.20260417.002of005.ok
...
```

Each chunk has its own HDR and TRL. Each `.ok` file signals completion. The pipeline must wait for all five, concatenate in order, then process as one logical extract.

The framework wraps this up in `SplitFileHandler.wait_for_complete_set(prefix)`. It polls GCS until every chunk plus its `.ok` marker has landed. Returns a sorted list of URIs. The pipeline reads that as one input.

Unglamorous. Easy to get wrong. Worth having ready-made.

---

## Validators that compose

Field-level validation is built around small, composable validator classes:

```python
from gcp_pipeline_beam.validators import (
    SSNValidator, DateValidator, NumericValidator,
    RegexValidator, RequiredValidator
)

postcode_validator = RegexValidator(r"^[A-Z]{1,2}[0-9R][0-9A-Z]? ?[0-9][A-Z]{2}$")
birth_date_validator = DateValidator(formats=["%Y-%m-%d", "%d/%m/%Y", "%Y%m%d"])

field_validators = {
    "customer_id": [RequiredValidator(), RegexValidator(r"^\d{10}$")],
    "postcode": [postcode_validator],
    "date_of_birth": [RequiredValidator(), birth_date_validator],
}
```

Each validator returns `Valid` or `Invalid(reason)`. They compose: `RequiredValidator` short-circuits the rest if the field's missing. `SchemaValidateRecordDoFn` runs them all, attaches results as `_validation` metadata, and routes via Beam's tagged outputs.

Looks trivial when you read it. This is usually what people get wrong on their first try.

---

## The error bucket pattern

Bad records don't fail the job. They go to a structured bucket:

```
gs://generic-error-bucket/
└── system=generic/
    └── entity=customers/
        └── extract_date=20260417/
            └── run_id=20260417T091400Z-7f3a/
                ├── invalid.jsonl
                └── manifest.json
```

`invalid.jsonl` has one JSON object per rejected record, with the original raw input, parsed cells, and per-field error reasons.

`manifest.json` summarises the run: counts, rejection rate, audit run_id, a link to `job_control.audit_events`.

The layout is consistent across every entity, so one scanner tool produces a daily "rejection summary" for the data steward. No bespoke code per entity.

---

## Dataflow Flex Templates

The whole thing packages as a Dataflow Flex Template — a Docker image, registered with Dataflow, launched on demand with a JSON parameter set.

```bash
# CI builds the image
gcloud builds submit --config cloudbuild.yaml

# CI registers the template
gcloud dataflow flex-template build \
    gs://templates/customers-ingestion.json \
    --image=gcr.io/my-project/customers-ingestion:latest \
    --sdk-language=PYTHON

# Airflow launches it
gcloud dataflow flex-template run customers-20260417 \
    --template-file-gcs-location=gs://templates/customers-ingestion.json \
    --parameters=input_file=gs://landing/customers.csv,bq_table=odp_generic.customers
```

Steps 1 and 2 happen in CI. Only step 3 runs in production. Clean separation.

---

## What I got right, what I'd change

Strengths of this ingestion layer:

- HDR/TRL parsing is **battle-tested** — 359 unit tests exercise every edge case I've ever hit.
- The `BeamPipelineBuilder` removes the audit/FinOps/error-routing boilerplate from every pipeline author's plate.
- The compositional validator pattern scales — we've added twenty new validators without refactoring any old ones.

Things I'd change:

- The builder is a bit **magical** — it hides the audit trail, FinOps wiring, and error routing. A more explicit "lower-level" API would help when you need an unusual topology.
- **Streaming support is uneven.** The framework is batch-first. The Postgres CDC reference deployment exists but is marked as planned.
- **Performance tuning is manual.** Choosing the right worker count, machine type, shuffle mode is still on the user. A "deployment profile" abstraction would help.

---

## Try it

```bash
pip install gcp-pipeline-framework
python -m gcp_pipeline_framework.reconstruct --dest ~/my-pipeline
cd ~/my-pipeline
ls deployments/original-data-to-bigqueryload/
```

The reference ingestion is there. Fork it, rename it, point it at your schemas, ship.

---

## Next in the series

Next post: **JOIN vs MAP — two transformation patterns every data engineer should know.** The second unit of the three-unit model, deep.

---

*If you've ever parsed an EBCDIC file at 3am, you already know why this post exists. Tell me your war story in the comments.*

---

### About the author

**Joseph Aruja** — Lead Software Engineer based in Leeds, UK. Twenty-five years across banking, government, retail, transport, healthcare, and travel — including NHS Spine (technical lead, Release 7A), HSBC / First Direct / M&S Bank, GOV.UK / Home Office / DWP, Jaguar Land Rover, Booking.com, Smart Ticketing on Manchester Metrolink, and Wm Morrison's Evolve mainframe-integration programme. Member of the JSR 255 (JMX) Java Community Process specification group. Currently Senior Lead Engineer on a financial-services mainframe-to-cloud migration.

Connect on [LinkedIn](https://www.linkedin.com/in/josepharuja/) · email joseph.a.aruja@gmail.com

**Want the long form?** This series is part of a book — *Building Production-Grade Data Pipelines on Google Cloud* — available at [link — add before publishing]. **If this post was useful, a clap helps more than you'd think, and follow for the next instalment.**
