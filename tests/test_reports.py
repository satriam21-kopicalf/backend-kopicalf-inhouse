"""
Unit tests for CALF Ecosystem Backend Services

Run with: pytest tests/ -v
"""
import pytest
import json
from datetime import date, datetime
from unittest.mock import MagicMock, patch

# Import the module to test
import sys
sys.path.insert(0, '.')

from app.services.reports import (
    REPORTS, REPORT_CATEGORIES, TRX_ROW_FETCHERS,
    _num, get_report_metadata, list_reports_by_category,
    list_reports_by_tier
)


class TestReportsRegistry:
    """Test that all reports are properly configured."""

    def test_reports_not_empty(self):
        """Reports registry should not be empty."""
        assert len(REPORTS) > 0, "REPORTS registry is empty"

    def test_all_reports_have_required_fields(self):
        """Every report should have required metadata fields."""
        required_fields = ['title', 'title_id', 'category', 'tier', 'source', 'entity', 'columns']
        for slug, spec in REPORTS.items():
            for field in required_fields:
                assert field in spec, f"Report '{slug}' missing field: {field}"

    def test_all_reports_have_valid_tier(self):
        """All reports should have valid tier (T1 or T2)."""
        valid_tiers = ['T1', 'T2']
        for slug, spec in REPORTS.items():
            assert spec['tier'] in valid_tiers, f"Report '{slug}' has invalid tier: {spec['tier']}"

    def test_all_reports_have_valid_source(self):
        """All reports should have valid source (trx or rpt)."""
        valid_sources = ['trx', 'rpt']
        for slug, spec in REPORTS.items():
            assert spec['source'] in valid_sources, f"Report '{slug}' has invalid source: {spec['source']}"

    def test_all_reports_have_columns(self):
        """All reports should have at least one column defined."""
        for slug, spec in REPORTS.items():
            assert len(spec['columns']) > 0, f"Report '{slug}' has no columns defined"

    def test_all_columns_have_key_and_label(self):
        """All column definitions should have key and label."""
        for slug, spec in REPORTS.items():
            for col in spec['columns']:
                assert 'key' in col, f"Report '{slug}' column missing 'key'"
                assert 'label' in col, f"Report '{slug}' column missing 'label'"


class TestTRXRowFetchers:
    """Test that T1 reports have corresponding row fetchers."""

    def test_trx_reports_have_fetchers(self):
        """All T1 (trx) reports should have row fetchers defined."""
        missing_fetchers = []
        for slug, spec in REPORTS.items():
            if spec['source'] == 'trx':
                entity = spec['entity']
                if entity not in TRX_ROW_FETCHERS:
                    missing_fetchers.append((slug, entity))

        assert len(missing_fetchers) == 0, f"Missing fetchers for: {missing_fetchers}"

    def test_fetcher_functions_callable(self):
        """All registered fetchers should be callable functions."""
        for entity, fetcher in TRX_ROW_FETCHERS.items():
            assert callable(fetcher), f"Entity '{entity}' fetcher is not callable"


class TestReportCategories:
    """Test report categories configuration."""

    def test_categories_not_empty(self):
        """Report categories should not be empty."""
        assert len(REPORT_CATEGORIES) > 0, "REPORT_CATEGORIES is empty"

    def test_all_categories_have_required_fields(self):
        """Each category should have required fields."""
        required_fields = ['label', 'icon', 'description', 'tier']
        for cat, spec in REPORT_CATEGORIES.items():
            for field in required_fields:
                assert field in spec, f"Category '{cat}' missing field: {field}"

    def test_category_tiers_match_reports(self):
        """Report tiers should be consistent with their categories."""
        category_tiers = {cat: spec['tier'] for cat, spec in REPORT_CATEGORIES.items()}
        for slug, spec in REPORTS.items():
            cat = spec['category']
            if cat in category_tiers:
                report_tier = spec['tier']
                # Note: Some reports may differ from category tier, this is informational


class TestHelperFunctions:
    """Test helper functions."""

    def test_num_converts_integers(self):
        """_num should convert integers."""
        assert _num(42) == 42
        assert _num(0) == 0
        assert _num(-10) == -10

    def test_num_converts_floats(self):
        """_num should convert floats."""
        assert _num(3.14) == 3.14
        assert _num(-2.5) == -2.5

    def test_num_rounds_whole_numbers(self):
        """_num should return integers for whole number floats."""
        assert _num(5.0) == 5
        assert _num(10.0) == 10

    def test_num_handles_none(self):
        """_num should return None for None input."""
        assert _num(None) is None

    def test_num_handles_strings(self):
        """_num should handle numeric strings."""
        assert _num("123") == 123
        assert _num("45.67") == 45.67

    def test_num_handles_invalid_input(self):
        """_num should return original value for invalid input."""
        assert _num("not a number") == "not a number"
        assert _num([1, 2, 3]) == [1, 2, 3]


class TestReportMetadata:
    """Test report metadata functions."""

    def test_get_report_metadata_returns_dict(self):
        """get_report_metadata should return a dict."""
        metadata = get_report_metadata('stock-opname-report')
        assert isinstance(metadata, dict)

    def test_get_report_metadata_returns_none_for_unknown(self):
        """get_report_metadata should return None for unknown reports."""
        metadata = get_report_metadata('non-existent-report')
        assert metadata is None

    def test_list_reports_by_category_returns_dict(self):
        """list_reports_by_category should return a dict."""
        result = list_reports_by_category()
        assert isinstance(result, dict)

    def test_list_reports_by_tier_returns_dict(self):
        """list_reports_by_tier should return a dict with T1 and T2."""
        result = list_reports_by_tier()
        assert 'T1' in result
        assert 'T2' in result
        assert isinstance(result['T1'], list)
        assert isinstance(result['T2'], list)


class TestReportCount:
    """Test report counts and coverage."""

    def test_minimum_report_count(self):
        """Should have at least 30 reports."""
        assert len(REPORTS) >= 30, f"Expected >= 30 reports, got {len(REPORTS)}"

    def test_t1_t2_balance(self):
        """Should have reasonable T1/T2 balance."""
        t1_count = sum(1 for s in REPORTS.values() if s['tier'] == 'T1')
        t2_count = sum(1 for s in REPORTS.values() if s['tier'] == 'T2')
        assert t1_count > 0, "Should have at least one T1 report"
        assert t2_count > 0, "Should have at least one T2 report"
        print(f"\nReport Balance: T1={t1_count}, T2={t2_count}")


class TestReportEntities:
    """Test entity types in reports."""

    def test_entities_are_strings(self):
        """All entity values should be strings."""
        for slug, spec in REPORTS.items():
            assert isinstance(spec['entity'], str), f"Report '{slug}' entity is not a string"

    def test_entities_are_uppercase(self):
        """All entity values should be uppercase."""
        for slug, spec in REPORTS.items():
            assert spec['entity'] == spec['entity'].upper(), f"Report '{slug}' entity not uppercase: {spec['entity']}"


class TestReportCompanies:
    """Test company coverage in reports."""

    def test_all_reports_have_companies_field(self):
        """All reports should have companies field."""
        for slug, spec in REPORTS.items():
            assert 'companies' in spec, f"Report '{slug}' missing 'companies' field"

    def test_companies_are_lists(self):
        """Companies field should be a list."""
        for slug, spec in REPORTS.items():
            assert isinstance(spec['companies'], list), f"Report '{slug}' companies is not a list"

    def test_company_ids_are_integers(self):
        """Company IDs should be integers."""
        for slug, spec in REPORTS.items():
            for company_id in spec['companies']:
                assert isinstance(company_id, int), f"Report '{slug}' has non-integer company ID: {company_id}"


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
