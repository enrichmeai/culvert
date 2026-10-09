"""examples/python-quickstart/ingest.py runs end to end, with GCS and BigQuery faked (#13)."""

from __future__ import annotations

import hashlib
import pathlib
import runpy
import sys

from google.cloud import bigquery, storage

EXAMPLE = pathlib.Path(__file__).resolve().parents[3] / "examples" / "python-quickstart" / "ingest.py"


class Blob:
    """Reads like a GCS blob: metadata reload, ranged downloads, and the library's BlobReader."""

    def __init__(self, data):
        self.data = data
        self.generation = None
        self.chunk_size = None

    def reload(self):
        self.generation = 1

    def download_as_bytes(self, start=None, end=None, **kwargs):
        return self.data[start or 0:None if end is None else end + 1]

    def open(self, mode="rb", **kwargs):
        from google.cloud.storage.fileio import BlobReader
        return BlobReader(self, **kwargs)


class Bucket:
    def __init__(self, objects, name):
        self.objects, self.name = objects, name

    def blob(self, path):
        return Blob(self.objects[f"gs://{self.name}/{path}"])


class StorageClient:
    objects = {}

    def bucket(self, name):
        return Bucket(self.objects, name)


class BigQueryClient:
    loads = []

    def __init__(self, project=None):
        self.project = project

    def load_table_from_json(self, rows, destination, job_config=None):
        BigQueryClient.loads.append((self.project, destination, rows))

        class Done:
            def result(self):
                return None
        return Done()


def test_the_quickstart_loads_paid_orders_with_hashed_emails(monkeypatch, capsys):
    StorageClient.objects = {"gs://shop/orders.jsonl": (
        b'{"id": 1, "status": "paid", "email": "a@b.c"}\n'
        b'{"id": 2, "status": "open", "email": "d@e.f"}\n'
        b'{"id": 3, "status": "paid", "email": null}\n')}
    BigQueryClient.loads = []
    monkeypatch.setattr(storage, "Client", StorageClient)
    monkeypatch.setattr(bigquery, "Client", BigQueryClient)
    monkeypatch.setattr(sys, "argv", ["ingest.py", "gs://shop/orders.jsonl", "proj.sales.orders"])

    runpy.run_path(str(EXAMPLE), run_name="__main__")

    (project, table, loaded), = BigQueryClient.loads
    assert (project, table) == ("proj", "proj.sales.orders")
    hashed = hashlib.sha256(b"culvert-pii-salta@b.c").hexdigest()
    assert loaded == [{"id": 1, "status": "paid", "email": hashed},
                      {"id": 3, "status": "paid", "email": None}]
    assert capsys.readouterr().out.strip() == "3 read, 2 loaded into proj.sales.orders"


def test_the_example_is_at_most_20_lines_of_code():
    lines = EXAMPLE.read_text().split('"""', 2)[2].splitlines()
    code = [line for line in lines if line.strip()]
    assert len(code) <= 20, f"{len(code)} lines"
