# Segment Transform - Terraform Outputs

output "segments_bucket" {
  value = google_storage_bucket.segments.name
}

output "cdp_dataset" {
  value = google_bigquery_dataset.cdp.dataset_id
}

output "job_control_dataset" {
  value = google_bigquery_dataset.job_control.dataset_id
}

output "customer_risk_profile_table" {
  value = "${google_bigquery_dataset.cdp.dataset_id}.${google_bigquery_table.customer_risk_profile.table_id}"
}
