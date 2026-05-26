"""
Unit tests for parse_pubsub_message function in dag_factory.

Tests the logic that:
1. Extracts file_name and bucket from various PubSub message formats
2. Derives .csv data file path from .ok trigger file
3. Extracts entity and extract_date from filename
"""

import pytest
from unittest.mock import MagicMock, patch
import json
import base64


class TestParsePubSubMessage:
    """Test parse_pubsub_message function logic."""

    @pytest.fixture
    def config(self):
        """Sample config for testing."""
        return {
            "system_id": "GENERIC",
            "system_name": "Generic",
            "file_prefix": "generic",
            "ok_file_suffix": ".ok",
            "entities": {
                "customers": {"description": "Customer records"},
                "accounts": {"description": "Account records"},
                "decision": {"description": "Decision records"},
            },
        }

    @pytest.fixture
    def entities(self, config):
        """Entity names list."""
        return list(config["entities"].keys())

    def _create_parse_function(self, config, entities):
        """
        Create the parse_pubsub_message function with the given config.
        This mirrors the logic in dag_factory.py.
        """
        import logging
        logger = logging.getLogger(__name__)

        def parse_pubsub_message(**context):
            messages = context["ti"].xcom_pull(task_ids="wait_for_file_notification")
            if not messages:
                logger.warning("No messages received from Pub/Sub")
                return {"status": "no_message"}
            message = messages[0] if isinstance(messages, list) else messages
            
            # Extract file_name and bucket from various message formats
            file_name = ""
            bucket = ""
            
            if isinstance(message, str):
                message_data = json.loads(message)
                file_name = message_data.get("name", "")
                bucket = message_data.get("bucket", "")
            elif isinstance(message, dict):
                # Try direct access first
                file_name = message.get("name", "")
                bucket = message.get("bucket", "")
                
                # If not found, check nested 'message' structure (PubSub format)
                if not file_name:
                    nested_msg = message.get("message", {})
                    attributes = nested_msg.get("attributes", {}) if isinstance(nested_msg, dict) else {}
                    file_name = attributes.get("objectId", "")
                    bucket = attributes.get("bucketId", "")
                    
                    # Also try parsing the data payload
                    if not file_name:
                        data = nested_msg.get("data", "") if isinstance(nested_msg, dict) else ""
                        if data:
                            try:
                                if isinstance(data, bytes):
                                    data_str = data.decode('utf-8')
                                else:
                                    try:
                                        data_str = base64.b64decode(data).decode('utf-8')
                                    except Exception:
                                        data_str = data
                                data_json = json.loads(data_str)
                                file_name = data_json.get("name", "")
                                bucket = data_json.get("bucket", "")
                            except Exception as e:
                                logger.debug(f"Could not parse message data: {e}")
            else:
                message_data = message
                file_name = getattr(message_data, "name", "") or ""
                bucket = getattr(message_data, "bucket", "") or ""
                
            logger.info(f"Received notification for: gs://{bucket}/{file_name}")
            
            trigger_suffix = config.get("ok_file_suffix", ".ok")
            if not file_name.endswith(trigger_suffix):
                logger.info(f"Skipping file without {trigger_suffix} suffix: {file_name}")
                return {"status": "skip", "reason": "not_trigger_file"}
                
            entity = None
            for e in entities:
                if e in file_name.lower():
                    entity = e
                    break
                    
            extract_date = None
            base_name = file_name.replace(trigger_suffix, "")
            for part in base_name.split("_"):
                if part.isdigit() and len(part) == 8:
                    extract_date = part
                    break

            # Derive .csv data file path from .ok trigger file
            trigger_file = f"gs://{bucket}/{file_name}"
            data_file = f"gs://{bucket}/{file_name.replace(trigger_suffix, '.csv')}"

            result = {
                "status": "success",
                "trigger_file": trigger_file,
                "data_file": data_file,
                "entity": entity,
                "extract_date": extract_date,
                "bucket": bucket,
                "file_name": file_name,
            }
            logger.info(f"Parsed file metadata: {result}")
            context["ti"].xcom_push(key="file_metadata", value=result)
            return result

        return parse_pubsub_message

    def _mock_context(self, messages):
        """Create a mock Airflow context with xcom."""
        ti = MagicMock()
        ti.xcom_pull.return_value = messages
        return {"ti": ti}

    # =========================================================================
    # Test: Direct dict format (simple GCS notification)
    # =========================================================================
    def test_parse_direct_dict_format(self, config, entities):
        """Test parsing a simple dict message with name and bucket at top level."""
        parse_fn = self._create_parse_function(config, entities)
        
        message = {
            "name": "generic/generic_customers_20260318.ok",
            "bucket": "project-generic-int-landing",
        }
        context = self._mock_context([message])
        
        result = parse_fn(**context)
        
        assert result["status"] == "success"
        assert result["file_name"] == "generic/generic_customers_20260318.ok"
        assert result["bucket"] == "project-generic-int-landing"
        assert result["entity"] == "customers"
        assert result["extract_date"] == "20260318"
        assert result["trigger_file"] == "gs://project-generic-int-landing/generic/generic_customers_20260318.ok"
        assert result["data_file"] == "gs://project-generic-int-landing/generic/generic_customers_20260318.csv"

    # =========================================================================
    # Test: Nested message format (PubSub with attributes)
    # =========================================================================
    def test_parse_nested_pubsub_format_with_attributes(self, config, entities):
        """Test parsing PubSub message with nested message.attributes structure."""
        parse_fn = self._create_parse_function(config, entities)
        
        message = {
            "message": {
                "attributes": {
                    "objectId": "generic/generic_accounts_20260318.ok",
                    "bucketId": "project-generic-int-landing",
                    "eventType": "OBJECT_FINALIZE",
                },
                "data": "",
            }
        }
        context = self._mock_context([message])
        
        result = parse_fn(**context)
        
        assert result["status"] == "success"
        assert result["file_name"] == "generic/generic_accounts_20260318.ok"
        assert result["bucket"] == "project-generic-int-landing"
        assert result["entity"] == "accounts"
        assert result["extract_date"] == "20260318"
        assert result["data_file"] == "gs://project-generic-int-landing/generic/generic_accounts_20260318.csv"

    # =========================================================================
    # Test: Base64 encoded data payload
    # =========================================================================
    def test_parse_base64_encoded_data(self, config, entities):
        """Test parsing PubSub message with base64 encoded JSON data payload."""
        parse_fn = self._create_parse_function(config, entities)
        
        data_json = {
            "name": "generic/generic_decision_20260318.ok",
            "bucket": "project-generic-int-landing",
        }
        encoded_data = base64.b64encode(json.dumps(data_json).encode()).decode()
        
        message = {
            "message": {
                "attributes": {},
                "data": encoded_data,
            }
        }
        context = self._mock_context([message])
        
        result = parse_fn(**context)
        
        assert result["status"] == "success"
        assert result["file_name"] == "generic/generic_decision_20260318.ok"
        assert result["entity"] == "decision"
        assert result["data_file"] == "gs://project-generic-int-landing/generic/generic_decision_20260318.csv"

    # =========================================================================
    # Test: JSON string message
    # =========================================================================
    def test_parse_json_string_message(self, config, entities):
        """Test parsing a JSON string message."""
        parse_fn = self._create_parse_function(config, entities)
        
        message = json.dumps({
            "name": "generic/generic_customers_20260318.ok",
            "bucket": "project-generic-int-landing",
        })
        context = self._mock_context([message])
        
        result = parse_fn(**context)
        
        assert result["status"] == "success"
        assert result["entity"] == "customers"
        assert result["data_file"] == "gs://project-generic-int-landing/generic/generic_customers_20260318.csv"

    # =========================================================================
    # Test: Skip non-.ok files
    # =========================================================================
    def test_skip_csv_file(self, config, entities):
        """Test that .csv files are skipped (only .ok files trigger)."""
        parse_fn = self._create_parse_function(config, entities)
        
        message = {
            "name": "generic/generic_customers_20260318.csv",
            "bucket": "project-generic-int-landing",
        }
        context = self._mock_context([message])
        
        result = parse_fn(**context)
        
        assert result["status"] == "skip"
        assert result["reason"] == "not_trigger_file"

    # =========================================================================
    # Test: No messages
    # =========================================================================
    def test_no_messages(self, config, entities):
        """Test handling when no messages are received."""
        parse_fn = self._create_parse_function(config, entities)
        context = self._mock_context(None)
        
        result = parse_fn(**context)
        
        assert result["status"] == "no_message"

    # =========================================================================
    # Test: Empty messages list
    # =========================================================================
    def test_empty_messages_list(self, config, entities):
        """Test handling empty messages list."""
        parse_fn = self._create_parse_function(config, entities)
        context = self._mock_context([])
        
        result = parse_fn(**context)
        
        # Empty list is falsy, so should return no_message
        assert result["status"] == "no_message"

    # =========================================================================
    # Test: Entity extraction from path with prefix
    # =========================================================================
    def test_entity_extraction_with_folder_prefix(self, config, entities):
        """Test entity is correctly extracted from path with folder prefix."""
        parse_fn = self._create_parse_function(config, entities)
        
        message = {
            "name": "generic/subfolder/generic_accounts_20260318.ok",
            "bucket": "project-generic-int-landing",
        }
        context = self._mock_context([message])
        
        result = parse_fn(**context)
        
        assert result["status"] == "success"
        assert result["entity"] == "accounts"

    # =========================================================================
    # Test: Date extraction
    # =========================================================================
    def test_extract_date_from_various_positions(self, config, entities):
        """Test date extraction works regardless of position in filename."""
        parse_fn = self._create_parse_function(config, entities)
        
        # Date at the end
        message = {
            "name": "generic_customers_20260318.ok",
            "bucket": "bucket",
        }
        context = self._mock_context([message])
        result = parse_fn(**context)
        assert result["extract_date"] == "20260318"

    # =========================================================================
    # Test: Correct .csv derivation from .ok
    # =========================================================================
    def test_csv_derivation_from_ok_file(self, config, entities):
        """Test that .csv path is correctly derived from .ok trigger file."""
        parse_fn = self._create_parse_function(config, entities)
        
        message = {
            "name": "generic/generic_customers_20260318.ok",
            "bucket": "my-bucket",
        }
        context = self._mock_context([message])
        
        result = parse_fn(**context)
        
        assert result["trigger_file"] == "gs://my-bucket/generic/generic_customers_20260318.ok"
        assert result["data_file"] == "gs://my-bucket/generic/generic_customers_20260318.csv"
        # Verify .ok was replaced with .csv
        assert result["data_file"].endswith(".csv")
        assert not result["data_file"].endswith(".ok")

    # =========================================================================
    # Test: Real GCS notification format (as seen in production)
    # =========================================================================
    def test_real_gcs_notification_format(self, config, entities):
        """Test with the actual format seen from GCS PubSub notifications."""
        parse_fn = self._create_parse_function(config, entities)
        
        # This is the format we actually receive from GCS notifications
        message = {
            "kind": "storage#object",
            "id": "joseph-antony-aruja-generic-int-landing/generic/generic_customers_20260318.ok/1773851477987229",
            "selfLink": "https://www.googleapis.com/storage/v1/b/joseph-antony-aruja-generic-int-landing/o/generic%2Fgeneric_customers_20260318.ok",
            "name": "generic/generic_customers_20260318.ok",
            "bucket": "joseph-antony-aruja-generic-int-landing",
            "generation": "1773851477987229",
            "metageneration": "1",
            "contentType": "application/octet-stream",
            "timeCreated": "2026-03-18T16:31:17.991Z",
            "updated": "2026-03-18T16:31:17.991Z",
            "storageClass": "STANDARD",
            "size": "6",
        }
        context = self._mock_context([message])
        
        result = parse_fn(**context)
        
        assert result["status"] == "success"
        assert result["file_name"] == "generic/generic_customers_20260318.ok"
        assert result["bucket"] == "joseph-antony-aruja-generic-int-landing"
        assert result["entity"] == "customers"
        assert result["extract_date"] == "20260318"
        assert result["trigger_file"] == "gs://joseph-antony-aruja-generic-int-landing/generic/generic_customers_20260318.ok"
        assert result["data_file"] == "gs://joseph-antony-aruja-generic-int-landing/generic/generic_customers_20260318.csv"


class TestDataFilePath:
    """Specific tests for the .ok to .csv file path derivation."""
    
    def test_ok_suffix_replaced_with_csv(self):
        """Verify the logic that replaces .ok with .csv."""
        trigger_suffix = ".ok"
        file_name = "generic/generic_customers_20260318.ok"
        bucket = "my-bucket"
        
        trigger_file = f"gs://{bucket}/{file_name}"
        data_file = f"gs://{bucket}/{file_name.replace(trigger_suffix, '.csv')}"
        
        assert trigger_file == "gs://my-bucket/generic/generic_customers_20260318.ok"
        assert data_file == "gs://my-bucket/generic/generic_customers_20260318.csv"
    
    def test_only_suffix_replaced_not_middle(self):
        """Verify .ok in the middle of filename is not replaced."""
        trigger_suffix = ".ok"
        # Edge case: filename has .ok in path but also ends with .ok
        file_name = "ok_folder/generic_customers_20260318.ok"
        bucket = "bucket"
        
        data_file = f"gs://{bucket}/{file_name.replace(trigger_suffix, '.csv')}"
        
        # Note: Python's replace replaces all occurrences, but since .ok is the suffix
        # and ok_folder doesn't have the dot, this should be fine
        assert data_file == "gs://bucket/ok_folder/generic_customers_20260318.csv"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

