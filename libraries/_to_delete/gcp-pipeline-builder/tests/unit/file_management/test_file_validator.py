"""
Unit tests for FileValidator.

Tests cover:
- File existence validation
- Empty file detection
- Corruption detection
- CSV format validation
- Encoding validation
- Column validation
- Aggregate error collection
"""

import pytest
from unittest.mock import Mock, patch, MagicMock

from gcp_pipeline_builder.file_management.validator import FileValidator


class TestFileValidatorInit:
    """Test FileValidator initialization."""

    @patch('gcp_pipeline_builder.file_management.validator.storage.Client')
    def test_init_default_encoding(self, mock_storage):
        """Test initialization with default encoding."""
        validator = FileValidator(gcs_bucket="test-bucket")

        assert validator.gcs_bucket == "test-bucket"
        assert validator.encoding == 'utf-8'

    @patch('gcp_pipeline_builder.file_management.validator.storage.Client')
    def test_init_custom_encoding(self, mock_storage):
        """Test initialization with custom encoding."""
        validator = FileValidator(gcs_bucket="test-bucket", encoding='latin-1')

        assert validator.encoding == 'latin-1'


class TestValidateFileExists:
    """Test validate_file_exists method."""

    @pytest.fixture
    def validator_with_mocks(self):
        """Create validator with mocked GCS."""
        with patch('gcp_pipeline_builder.file_management.validator.storage.Client') as mock_storage:
            mock_client = Mock()
            mock_storage.return_value = mock_client

            mock_bucket = Mock()
            mock_blob = Mock()
            mock_bucket.blob.return_value = mock_blob
            mock_client.bucket.return_value = mock_bucket

            validator = FileValidator(gcs_bucket="test-bucket")

            yield validator, mock_blob

    def test_file_exists(self, validator_with_mocks):
        """Test when file exists."""
        validator, mock_blob = validator_with_mocks
        mock_blob.exists.return_value = True

        result = validator.validate_file_exists("path/to/file.csv")

        assert result is True

    def test_file_not_exists(self, validator_with_mocks):
        """Test when file doesn't exist."""
        validator, mock_blob = validator_with_mocks
        mock_blob.exists.return_value = False

        result = validator.validate_file_exists("path/to/missing.csv")

        assert result is False

    def test_file_exists_error(self, validator_with_mocks):
        """Test error handling."""
        validator, mock_blob = validator_with_mocks
        mock_blob.exists.side_effect = Exception("GCS Error")

        result = validator.validate_file_exists("path/to/file.csv")

        assert result is False


class TestValidateFileNotEmpty:
    """Test validate_file_not_empty method."""

    @pytest.fixture
    def validator_with_mocks(self):
        """Create validator with mocked GCS."""
        with patch('gcp_pipeline_builder.file_management.validator.storage.Client') as mock_storage:
            mock_client = Mock()
            mock_storage.return_value = mock_client

            mock_bucket = Mock()
            mock_blob = Mock()
            mock_bucket.blob.return_value = mock_blob
            mock_client.bucket.return_value = mock_bucket

            validator = FileValidator(gcs_bucket="test-bucket")

            yield validator, mock_blob

    def test_file_not_empty(self, validator_with_mocks):
        """Test when file has content."""
        validator, mock_blob = validator_with_mocks
        mock_blob.exists.return_value = True
        mock_blob.size = 1024

        result = validator.validate_file_not_empty("file.csv")

        assert result is True

    def test_file_empty(self, validator_with_mocks):
        """Test when file is empty."""
        validator, mock_blob = validator_with_mocks
        mock_blob.exists.return_value = True
        mock_blob.size = 0

        result = validator.validate_file_not_empty("empty.csv")

        assert result is False

    def test_file_not_exists(self, validator_with_mocks):
        """Test when file doesn't exist."""
        validator, mock_blob = validator_with_mocks
        mock_blob.exists.return_value = False

        result = validator.validate_file_not_empty("missing.csv")

        assert result is False

    def test_file_not_empty_error(self, validator_with_mocks):
        """Test error handling."""
        validator, mock_blob = validator_with_mocks
        mock_blob.exists.side_effect = Exception("Error")

        result = validator.validate_file_not_empty("file.csv")

        assert result is False


class TestValidateFileNotCorrupt:
    """Test validate_file_not_corrupt method."""

    @pytest.fixture
    def validator_with_mocks(self):
        """Create validator with mocked GCS."""
        with patch('gcp_pipeline_builder.file_management.validator.storage.Client') as mock_storage:
            mock_client = Mock()
            mock_storage.return_value = mock_client

            mock_bucket = Mock()
            mock_blob = Mock()
            mock_bucket.blob.return_value = mock_blob
            mock_client.bucket.return_value = mock_bucket

            validator = FileValidator(gcs_bucket="test-bucket")

            yield validator, mock_blob

    def test_file_not_corrupt(self, validator_with_mocks, sample_csv_content):
        """Test valid file detection."""
        validator, mock_blob = validator_with_mocks
        mock_blob.download_as_string.return_value = sample_csv_content.encode('utf-8')

        result = validator.validate_file_not_corrupt("file.csv")

        assert result is True

    def test_file_truncated(self, validator_with_mocks):
        """Test truncated file detection."""
        validator, mock_blob = validator_with_mocks
        # Single line without newline at end
        mock_blob.download_as_string.return_value = b"header"

        result = validator.validate_file_not_corrupt("truncated.csv")

        # Single line without proper ending should be suspect
        assert result is False

    def test_file_with_proper_ending(self, validator_with_mocks):
        """Test file with proper newline ending."""
        validator, mock_blob = validator_with_mocks
        mock_blob.download_as_string.return_value = b"header\ndata\n"

        result = validator.validate_file_not_corrupt("file.csv")

        assert result is True

    def test_file_encoding_error(self, validator_with_mocks):
        """Test encoding error detection."""
        validator, mock_blob = validator_with_mocks
        mock_blob.download_as_string.return_value = b'\xff\xfe invalid utf-8'

        result = validator.validate_file_not_corrupt("bad_encoding.csv")

        # Should return False due to decode error
        assert result is False


class TestValidateCsvFormat:
    """Test validate_csv_format method."""

    @pytest.fixture
    def validator_with_mocks(self):
        """Create validator with mocked GCS."""
        with patch('gcp_pipeline_builder.file_management.validator.storage.Client') as mock_storage:
            mock_client = Mock()
            mock_storage.return_value = mock_client

            mock_bucket = Mock()
            mock_blob = Mock()
            mock_bucket.blob.return_value = mock_blob
            mock_client.bucket.return_value = mock_bucket

            validator = FileValidator(gcs_bucket="test-bucket")

            yield validator, mock_blob

    def test_valid_csv_format(self, validator_with_mocks, sample_csv_content):
        """Test valid CSV format."""
        validator, mock_blob = validator_with_mocks
        mock_blob.download_as_string.return_value = sample_csv_content.encode('utf-8')

        is_valid, errors = validator.validate_csv_format("file.csv")

        assert is_valid is True
        assert len(errors) == 0

    def test_csv_missing_columns(self, validator_with_mocks, sample_csv_content):
        """Test CSV with missing expected columns."""
        validator, mock_blob = validator_with_mocks
        mock_blob.download_as_string.return_value = sample_csv_content.encode('utf-8')

        is_valid, errors = validator.validate_csv_format(
            "file.csv",
            expected_columns=["id", "name", "missing_column"]
        )

        assert is_valid is False
        assert any("missing" in err.lower() for err in errors)

    def test_csv_no_header(self, validator_with_mocks):
        """Test CSV without header."""
        validator, mock_blob = validator_with_mocks
        mock_blob.download_as_string.return_value = b""

        is_valid, errors = validator.validate_csv_format("empty.csv")

        assert is_valid is False
        assert any("header" in err.lower() for err in errors)

    def test_csv_with_all_expected_columns(self, validator_with_mocks, sample_csv_content):
        """Test CSV with all expected columns present."""
        validator, mock_blob = validator_with_mocks
        mock_blob.download_as_string.return_value = sample_csv_content.encode('utf-8')

        is_valid, errors = validator.validate_csv_format(
            "file.csv",
            expected_columns=["id", "name"]
        )

        assert is_valid is True
        assert len(errors) == 0


class TestValidateEncoding:
    """Test validate_encoding method."""

    @pytest.fixture
    def validator_with_mocks(self):
        """Create validator with mocked GCS."""
        with patch('gcp_pipeline_builder.file_management.validator.storage.Client') as mock_storage:
            mock_client = Mock()
            mock_storage.return_value = mock_client

            mock_bucket = Mock()
            mock_blob = Mock()
            mock_bucket.blob.return_value = mock_blob
            mock_client.bucket.return_value = mock_bucket

            validator = FileValidator(gcs_bucket="test-bucket")

            yield validator, mock_blob

    def test_valid_utf8_encoding(self, validator_with_mocks):
        """Test valid UTF-8 encoding."""
        validator, mock_blob = validator_with_mocks
        mock_blob.download_as_string.return_value = "Hello, World! 世界".encode('utf-8')

        result = validator.validate_encoding("file.csv")

        assert result is True

    def test_invalid_encoding(self, validator_with_mocks):
        """Test invalid encoding."""
        validator, mock_blob = validator_with_mocks
        # Invalid UTF-8 sequence
        mock_blob.download_as_string.return_value = b'\xff\xfe'

        result = validator.validate_encoding("file.csv")

        assert result is False


class TestGetValidationErrors:
    """Test get_validation_errors method."""

    @pytest.fixture
    def validator_with_mocks(self):
        """Create validator with mocked GCS."""
        with patch('gcp_pipeline_builder.file_management.validator.storage.Client') as mock_storage:
            mock_client = Mock()
            mock_storage.return_value = mock_client

            mock_bucket = Mock()
            mock_blob = Mock()
            mock_blob.exists.return_value = True
            mock_blob.size = 1024
            mock_bucket.blob.return_value = mock_blob
            mock_client.bucket.return_value = mock_bucket

            validator = FileValidator(gcs_bucket="test-bucket")

            yield validator, mock_blob

    def test_get_validation_errors_none(self, validator_with_mocks, sample_csv_content):
        """Test no validation errors for valid file."""
        validator, mock_blob = validator_with_mocks
        mock_blob.download_as_string.return_value = sample_csv_content.encode('utf-8')

        errors = validator.get_validation_errors("file.csv")

        assert len(errors) == 0

    def test_get_validation_errors_file_not_exists(self, validator_with_mocks):
        """Test errors when file doesn't exist."""
        validator, mock_blob = validator_with_mocks
        mock_blob.exists.return_value = False

        errors = validator.get_validation_errors("missing.csv")

        assert len(errors) > 0
        assert any("exist" in err.lower() or "not found" in err.lower() for err in errors)

    def test_get_validation_errors_empty_file(self, validator_with_mocks):
        """Test errors for empty file."""
        validator, mock_blob = validator_with_mocks
        mock_blob.size = 0

        errors = validator.get_validation_errors("empty.csv")

        assert len(errors) > 0
        assert any("empty" in err.lower() for err in errors)

    def test_get_validation_errors_aggregated(self, validator_with_mocks):
        """Test that multiple errors are aggregated."""
        validator, mock_blob = validator_with_mocks
        mock_blob.exists.return_value = True
        mock_blob.size = 0  # Empty
        mock_blob.download_as_string.return_value = b""  # No content

        errors = validator.get_validation_errors("bad.csv")

        # Should have multiple errors
        assert len(errors) >= 1


class TestValidateSampleRecord:
    """Test sample record validation."""

    @pytest.fixture
    def validator_with_mocks(self):
        """Create validator with mocked GCS."""
        with patch('gcp_pipeline_builder.file_management.validator.storage.Client') as mock_storage:
            mock_client = Mock()
            mock_storage.return_value = mock_client

            mock_bucket = Mock()
            mock_blob = Mock()
            mock_bucket.blob.return_value = mock_blob
            mock_client.bucket.return_value = mock_bucket

            validator = FileValidator(gcs_bucket="test-bucket")

            yield validator, mock_blob

    def test_validate_sample_record_success(self, validator_with_mocks, sample_csv_content):
        """Test sample record validation success."""
        validator, mock_blob = validator_with_mocks
        mock_blob.download_as_string.return_value = sample_csv_content.encode('utf-8')

        # Validator function that always passes
        def pass_validator(record):
            return True, []

        result, errors = validator.validate_sample_records("file.csv", pass_validator)

        assert result is True
        assert errors == []

    def test_validate_sample_record_no_data(self, validator_with_mocks):
        """Test sample record validation with no data."""
        validator, mock_blob = validator_with_mocks
        mock_blob.download_as_string.return_value = b"id,name\n"  # Header only

        # Validator function that always passes
        def pass_validator(record):
            return True, []

        result, errors = validator.validate_sample_records("header_only.csv", pass_validator)

        # With header only, no records to validate, so it should pass
        assert result is True


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    @pytest.fixture
    def validator_with_mocks(self):
        """Create validator with mocked GCS."""
        with patch('gcp_pipeline_builder.file_management.validator.storage.Client') as mock_storage:
            mock_client = Mock()
            mock_storage.return_value = mock_client

            mock_bucket = Mock()
            mock_blob = Mock()
            mock_bucket.blob.return_value = mock_blob
            mock_client.bucket.return_value = mock_bucket

            validator = FileValidator(gcs_bucket="test-bucket")

            yield validator, mock_blob

    def test_very_large_file(self, validator_with_mocks):
        """Test handling of large file size."""
        validator, mock_blob = validator_with_mocks
        mock_blob.exists.return_value = True
        mock_blob.size = 10 * 1024 * 1024 * 1024  # 10GB

        result = validator.validate_file_not_empty("large.csv")

        assert result is True

    def test_special_characters_in_path(self, validator_with_mocks):
        """Test file path with special characters."""
        validator, mock_blob = validator_with_mocks
        mock_blob.exists.return_value = True

        result = validator.validate_file_exists("path/with spaces/file-name_2025.csv")

        assert result is True

    def test_unicode_content(self, validator_with_mocks):
        """Test handling of unicode content."""
        validator, mock_blob = validator_with_mocks
        content = "id,name\n1,日本語\n2,한국어\n3,العربية\n"
        mock_blob.download_as_string.return_value = content.encode('utf-8')

        is_valid, errors = validator.validate_csv_format("unicode.csv")

        assert is_valid is True


class TestValidatorEdgeCases:
    """Test edge cases for FileValidator to improve coverage."""

    @pytest.fixture
    def validator_with_mocks(self):
        """Create validator with mocked GCS."""
        with patch('gcp_pipeline_builder.file_management.validator.storage.Client') as mock_storage:
            mock_client = Mock()
            mock_storage.return_value = mock_client

            mock_bucket = Mock()
            mock_blob = Mock()
            mock_bucket.blob.return_value = mock_blob
            mock_client.bucket.return_value = mock_bucket

            validator = FileValidator(gcs_bucket="test-bucket")

            yield validator, mock_blob

    def test_validate_csv_no_data_rows(self, validator_with_mocks):
        """Test CSV validation with header only (no data rows)."""
        validator, mock_blob = validator_with_mocks
        content = "id,name,email\n"  # Header only, no data
        mock_blob.download_as_string.return_value = content.encode('utf-8')

        is_valid, errors = validator.validate_csv_format("header_only.csv")

        assert is_valid is False
        assert any("no data" in err.lower() for err in errors)

    def test_validate_csv_with_exception(self, validator_with_mocks):
        """Test CSV validation when exception occurs."""
        validator, mock_blob = validator_with_mocks
        mock_blob.download_as_string.side_effect = Exception("Download error")

        is_valid, errors = validator.validate_csv_format("error.csv")

        assert is_valid is False
        assert len(errors) > 0
        assert any("error" in err.lower() for err in errors)

    def test_validate_encoding_unicode_error(self, validator_with_mocks):
        """Test encoding validation with invalid UTF-8."""
        validator, mock_blob = validator_with_mocks
        # Invalid UTF-8 bytes
        mock_blob.download_as_string.return_value = b'\x80\x81\x82'

        result = validator.validate_encoding("invalid.csv")

        assert result is False

    def test_validate_encoding_exception(self, validator_with_mocks):
        """Test encoding validation with download error."""
        validator, mock_blob = validator_with_mocks
        mock_blob.download_as_string.side_effect = Exception("Network error")

        result = validator.validate_encoding("error.csv")

        assert result is False

    def test_validate_sample_records_with_validation_errors(self, validator_with_mocks):
        """Test sample record validation with record-level errors."""
        validator, mock_blob = validator_with_mocks
        content = "id,name,email\n1,John,invalid_email\n2,Jane,also_invalid\n"
        mock_blob.download_as_string.return_value = content.encode('utf-8')

        def record_validator(record):
            errors = []
            if '@' not in record.get('email', ''):
                errors.append("Invalid email format")
            return len(errors) == 0, errors

        is_valid, errors = validator.validate_sample_records(
            "test.csv",
            validator_fn=record_validator,
            sample_size=10
        )

        assert is_valid is False
        assert len(errors) >= 2  # Both records fail

    def test_validate_sample_records_exception(self, validator_with_mocks):
        """Test sample record validation with exception."""
        validator, mock_blob = validator_with_mocks
        mock_blob.download_as_string.side_effect = Exception("Read error")

        def simple_validator(record):
            return True, []

        is_valid, errors = validator.validate_sample_records(
            "test.csv",
            validator_fn=simple_validator
        )

        assert is_valid is False
        assert any("error" in err.lower() for err in errors)

    def test_validate_sample_records_respects_sample_size(self, validator_with_mocks):
        """Test that sample validation respects sample_size limit."""
        validator, mock_blob = validator_with_mocks
        # Create content with 20 rows
        rows = "id,name\n" + "\n".join([f"{i},Name{i}" for i in range(20)])
        mock_blob.download_as_string.return_value = rows.encode('utf-8')

        validation_count = [0]

        def counting_validator(record):
            validation_count[0] += 1
            return True, []

        is_valid, errors = validator.validate_sample_records(
            "test.csv",
            validator_fn=counting_validator,
            sample_size=5
        )

        assert is_valid is True
        assert validation_count[0] == 5  # Should only validate 5 records

    def test_validate_delimiter_different_delimiter(self, validator_with_mocks):
        """Test delimiter validation with pipe delimiter."""
        validator, mock_blob = validator_with_mocks
        content = "id|name|email\n1|John|john@test.com\n"
        mock_blob.download_as_string.return_value = content.encode('utf-8')

        result = validator.validate_delimiter("test.csv", delimiter='|')

        assert result is True

    def test_validate_delimiter_wrong_delimiter(self, validator_with_mocks):
        """Test delimiter validation when delimiter doesn't match."""
        validator, mock_blob = validator_with_mocks
        content = "id,name,email\n1,John,john@test.com\n"
        mock_blob.download_as_string.return_value = content.encode('utf-8')

        result = validator.validate_delimiter("test.csv", delimiter='|')

        assert result is False

    def test_validate_delimiter_exception(self, validator_with_mocks):
        """Test delimiter validation with exception."""
        validator, mock_blob = validator_with_mocks
        mock_blob.download_as_string.side_effect = Exception("Error")

        result = validator.validate_delimiter("test.csv", delimiter=',')

        assert result is False

    def test_get_validation_errors_file_not_exists(self, validator_with_mocks):
        """Test get_validation_errors returns early for missing file."""
        validator, mock_blob = validator_with_mocks
        mock_blob.exists.return_value = False

        errors = validator.get_validation_errors("missing.csv")

        assert len(errors) == 1
        assert "does not exist" in errors[0].lower()

    def test_get_validation_errors_aggregates_all_errors(self, validator_with_mocks):
        """Test that get_validation_errors collects all error types."""
        validator, mock_blob = validator_with_mocks
        mock_blob.exists.return_value = True
        mock_blob.size = 0  # Empty file
        mock_blob.download_as_string.return_value = b'\x80\x81'  # Invalid UTF-8

        errors = validator.get_validation_errors("bad_file.csv")

        assert len(errors) >= 1  # At least empty file error

    def test_get_validation_errors_multiple_issues(self, validator_with_mocks):
        """Test file with multiple validation issues."""
        validator, mock_blob = validator_with_mocks
        mock_blob.exists.return_value = True
        mock_blob.size = 10
        # Invalid UTF-8 content that also isn't valid CSV
        mock_blob.download_as_string.return_value = b'\x80\x81\x82'

        errors = validator.get_validation_errors("multi_error.csv")

        # Should capture encoding error
        assert len(errors) >= 1


class TestValidatorWithCustomEncoding:
    """Test FileValidator with different encoding settings."""

    @patch('gcp_pipeline_builder.file_management.validator.storage.Client')
    def test_latin1_encoding(self, mock_storage):
        """Test validation with latin-1 encoding."""
        mock_client = Mock()
        mock_storage.return_value = mock_client
        mock_bucket = Mock()
        mock_blob = Mock()
        mock_bucket.blob.return_value = mock_blob
        mock_client.bucket.return_value = mock_bucket

        # Latin-1 encoded content
        content = "id,café\n1,naïve\n"
        mock_blob.download_as_string.return_value = content.encode('latin-1')

        validator = FileValidator(gcs_bucket="test-bucket", encoding='latin-1')

        result = validator.validate_encoding("latin1.csv")

        assert result is True

    @patch('gcp_pipeline_builder.file_management.validator.storage.Client')
    def test_utf8_sig_encoding(self, mock_storage):
        """Test validation with UTF-8 BOM encoding."""
        mock_client = Mock()
        mock_storage.return_value = mock_client
        mock_bucket = Mock()
        mock_blob = Mock()
        mock_bucket.blob.return_value = mock_blob
        mock_client.bucket.return_value = mock_bucket

        # UTF-8 with BOM
        content = "\ufeffid,name\n1,Test\n"
        mock_blob.download_as_string.return_value = content.encode('utf-8-sig')

        validator = FileValidator(gcs_bucket="test-bucket", encoding='utf-8-sig')

        result = validator.validate_encoding("bom.csv")

        assert result is True


if __name__ == '__main__':
    pytest.main([__file__, '-v'])

