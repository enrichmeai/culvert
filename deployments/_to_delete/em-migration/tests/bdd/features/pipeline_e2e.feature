Feature: End-to-End LOA Migration Pipeline
  As a Data Engineer
  I want to ensure the LOA migration pipeline processes data correctly from arrival to archival
  So that I can verify the system's reliability in lower environments

  @integration @requires_gcp
  Scenario: Process a valid application file through the pipeline
    Given a valid application file "applications_20251228.csv" in the GCS landing zone
    When the LOA migration pipeline is triggered for "applications"
    Then the input file should be validated successfully
    And the Dataflow job should complete successfully
    And the processed records should be available in the BigQuery table "loa_processed.applications"
    And the input file should be moved to the archive folder
    And a completion notification should be sent to the Pub/Sub topic
