from gcp_pipeline_core.finops.labels import FinOpsLabels

def test_finops_labels_to_dict():
    labels = FinOpsLabels(systapplication1_id="MySystem", environment="PROD")
    d = labels.to_dict()
    
    assert d["system"] == "mysystem"
    assert d["environment"] == "prod"
    assert d["project"] == "gdw-data-core"
    assert d["managed_by"] == "terraform-and-library"

def test_get_standard_labels():
    d = FinOpsLabels.get_standard_labels(systapplication1_id="Test", environment="Dev", run_id="123")
    
    assert d["system"] == "test"
    assert d["environment"] == "dev"
    assert d["run_id"] == "123"
    assert d["managed_by"] == "gcp-pipeline-library"
