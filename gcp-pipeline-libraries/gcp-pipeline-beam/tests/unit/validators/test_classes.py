"""Unit tests for the class-based composable validators."""

from __future__ import annotations

import pytest

from gcp_pipeline_beam.validators import (
    CompositeValidator,
    DateValidator,
    NumericValidator,
    PostcodeValidator,
    RegexValidator,
    RequiredValidator,
    SSNValidator,
    ValidationResult,
)


# ----- RequiredValidator --------------------------------------------------- #

def test_required_accepts_non_empty_string():
    assert RequiredValidator().validate("alice", "name").is_valid


def test_required_rejects_none():
    result = RequiredValidator().validate(None, "name")
    assert not result.is_valid
    assert result.errors[0].error_type == "REQUIRED"


def test_required_rejects_empty_string():
    assert not RequiredValidator().validate("", "name").is_valid


def test_required_rejects_whitespace_only():
    assert not RequiredValidator().validate("   \t", "name").is_valid


# ----- RegexValidator ------------------------------------------------------ #

def test_regex_matches_valid_pattern():
    v = RegexValidator(r"\d{10}")
    assert v.validate("0000000001", "customer_id").is_valid


def test_regex_rejects_non_matching():
    v = RegexValidator(r"\d{10}")
    assert not v.validate("abc", "customer_id").is_valid


def test_regex_skips_validation_when_value_is_none():
    # Null policy belongs to RequiredValidator.
    v = RegexValidator(r"\d{10}")
    assert v.validate(None, "customer_id").is_valid


# ----- DateValidator ------------------------------------------------------- #

def test_date_accepts_iso_format():
    assert DateValidator(["%Y-%m-%d"]).validate("1985-03-22", "dob").is_valid


def test_date_accepts_compact_format():
    assert DateValidator(["%Y-%m-%d", "%Y%m%d"]).validate("19850322", "dob").is_valid


def test_date_rejects_garbage():
    assert not DateValidator().validate("not-a-date", "dob").is_valid


# ----- NumericValidator ---------------------------------------------------- #

def test_numeric_accepts_integer_string():
    assert NumericValidator().validate("42", "balance").is_valid


def test_numeric_accepts_float_string():
    assert NumericValidator().validate("1250.45", "balance").is_valid


def test_numeric_rejects_non_numeric():
    assert not NumericValidator().validate("bad-number", "balance").is_valid


def test_numeric_enforces_min_when_provided():
    v = NumericValidator(min_value=0.0)
    assert not v.validate("-1", "balance").is_valid
    assert v.validate("0", "balance").is_valid


def test_numeric_enforces_max_when_provided():
    v = NumericValidator(max_value=100.0)
    assert not v.validate("1000", "balance").is_valid
    assert v.validate("50", "balance").is_valid


# ----- SSNValidator -------------------------------------------------------- #

def test_ssn_accepts_dashed_format():
    assert SSNValidator().validate("123-45-6789", "ssn").is_valid


def test_ssn_accepts_bare_format():
    assert SSNValidator().validate("123456789", "ssn").is_valid


def test_ssn_rejects_wrong_length():
    assert not SSNValidator().validate("12-345-6789", "ssn").is_valid


# ----- PostcodeValidator --------------------------------------------------- #

def test_postcode_accepts_london():
    assert PostcodeValidator().validate("SW1A 1AA", "postcode").is_valid


def test_postcode_accepts_no_space():
    assert PostcodeValidator().validate("EH89YL", "postcode").is_valid


def test_postcode_rejects_gibberish():
    assert not PostcodeValidator().validate("ZZZZZZZ", "postcode").is_valid


# ----- Composition --------------------------------------------------------- #

def test_result_union_is_commutative_on_errors():
    ok = ValidationResult.ok()
    bad = ValidationResult.invalid("x", "?", "bad")
    merged = ok | bad
    assert not merged.is_valid
    assert len(merged.errors) == 1


def test_composite_requires_all_children_to_pass():
    pipeline = CompositeValidator([
        RequiredValidator(),
        RegexValidator(r"\d{10}"),
    ])
    assert pipeline.validate("0000000001", "customer_id").is_valid
    assert not pipeline.validate("", "customer_id").is_valid
    assert not pipeline.validate("abc", "customer_id").is_valid
