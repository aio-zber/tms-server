"""
Tests for datetime utilities module.

Tests timezone handling, UTC conversion, and ISO format serialization.
"""
from datetime import datetime, timezone, timedelta
import pytest

from app.utils.datetime_utils import utc_now, ensure_utc, to_iso_utc


class TestUtcNow:
    """Tests for utc_now() function."""

    def test_returns_timezone_aware_datetime(self):
        """Test that utc_now returns timezone-aware datetime."""
        result = utc_now()
        assert result.tzinfo is not None
        assert result.tzinfo == timezone.utc

    def test_returns_current_time(self):
        """Test that utc_now returns approximately current time."""
        before = datetime.now(timezone.utc)
        result = utc_now()
        after = datetime.now(timezone.utc)

        # Should be within 1 second
        assert before <= result <= after

    def test_consistent_across_calls(self):
        """Test that consecutive calls return similar times."""
        first = utc_now()
        second = utc_now()

        # Should be within 1 second
        diff = abs((second - first).total_seconds())
        assert diff < 1.0


class TestEnsureUtc:
    """Tests for ensure_utc() function."""

    def test_converts_naive_datetime_to_aware(self):
        """Test that naive datetime is converted to UTC aware."""
        naive_dt = datetime(2025, 12, 16, 11, 30, 0, 123456)
        result = ensure_utc(naive_dt)

        assert result is not None
        assert result.tzinfo == timezone.utc
        # Time values should be unchanged
        assert result.year == 2025
        assert result.month == 12
        assert result.day == 16
        assert result.hour == 11
        assert result.minute == 30
        assert result.second == 0
        assert result.microsecond == 123456

    def test_preserves_aware_datetime_in_utc(self):
        """Test that UTC-aware datetime is preserved."""
        aware_dt = datetime(2025, 12, 16, 11, 30, 0, 123456, tzinfo=timezone.utc)
        result = ensure_utc(aware_dt)

        assert result is not None
        assert result.tzinfo == timezone.utc
        assert result == aware_dt

    def test_converts_aware_datetime_to_utc(self):
        """Test that timezone-aware datetime is converted to UTC."""
        # Create datetime in UTC+8
        utc_plus_8 = timezone(timedelta(hours=8))
        aware_dt = datetime(2025, 12, 16, 19, 30, 0, tzinfo=utc_plus_8)  # 19:30 UTC+8

        result = ensure_utc(aware_dt)

        assert result is not None
        assert result.tzinfo == timezone.utc
        # Should be converted to UTC (11:30 UTC)
        assert result.hour == 11
        assert result.minute == 30

    def test_handles_none_input(self):
        """Test that None input returns None."""
        result = ensure_utc(None)
        assert result is None


class TestToIsoUtc:
    """Tests for to_iso_utc() function."""

    def test_converts_naive_datetime_to_iso_with_z_suffix(self):
        """Test that naive datetime is converted to ISO with 'Z' suffix."""
        naive_dt = datetime(2025, 12, 16, 11, 30, 0, 123456)
        result = to_iso_utc(naive_dt)

        assert result is not None
        assert result.endswith('Z')
        assert '+00:00' not in result
        assert '2025-12-16T11:30:00.123456Z' == result

    def test_converts_aware_datetime_to_iso_with_z_suffix(self):
        """Test that UTC-aware datetime is converted to ISO with 'Z' suffix."""
        aware_dt = datetime(2025, 12, 16, 11, 30, 0, 123456, tzinfo=timezone.utc)
        result = to_iso_utc(aware_dt)

        assert result is not None
        assert result.endswith('Z')
        assert '+00:00' not in result
        assert '2025-12-16T11:30:00.123456Z' == result

    def test_converts_non_utc_aware_datetime(self):
        """Test that non-UTC timezone is converted to UTC with 'Z' suffix."""
        # Create datetime in UTC+8
        utc_plus_8 = timezone(timedelta(hours=8))
        aware_dt = datetime(2025, 12, 16, 19, 30, 0, 123456, tzinfo=utc_plus_8)

        result = to_iso_utc(aware_dt)

        assert result is not None
        assert result.endswith('Z')
        # Should be converted to UTC (11:30)
        assert '2025-12-16T11:30:00.123456Z' == result

    def test_handles_datetime_without_microseconds(self):
        """Test datetime without microseconds."""
        dt = datetime(2025, 12, 16, 11, 30, 0)
        result = to_iso_utc(dt)

        assert result is not None
        assert result.endswith('Z')
        assert '2025-12-16T11:30:00Z' == result

    def test_handles_none_input(self):
        """Test that None input returns None."""
        result = to_iso_utc(None)
        assert result is None

    def test_replaces_plus_zero_zero_with_z(self):
        """Test that '+00:00' is replaced with 'Z' (PostgreSQL TIMESTAMPTZ format)."""
        aware_dt = datetime(2025, 12, 16, 11, 30, 0, tzinfo=timezone.utc)
        result = to_iso_utc(aware_dt)

        # Verify '+00:00' is replaced with 'Z'
        assert '+00:00' not in result
        assert result.endswith('Z')


class TestIntegration:
    """Integration tests for datetime utilities."""

    def test_utc_now_to_iso_utc_round_trip(self):
        """Test that utc_now() output can be serialized with to_iso_utc()."""
        now = utc_now()
        iso_str = to_iso_utc(now)

        assert iso_str is not None
        assert iso_str.endswith('Z')
        assert len(iso_str) >= 20  # Minimum length: "2025-12-16T11:30:00Z"

    def test_ensure_utc_to_iso_utc_round_trip(self):
        """Test that ensure_utc() output can be serialized with to_iso_utc()."""
        naive_dt = datetime(2025, 12, 16, 11, 30, 0)
        aware_dt = ensure_utc(naive_dt)
        iso_str = to_iso_utc(aware_dt)

        assert iso_str is not None
        assert iso_str == '2025-12-16T11:30:00Z'

    def test_backend_to_frontend_workflow(self):
        """Test complete workflow: create timestamp -> serialize -> frontend parsing."""
        # Backend creates timestamp
        backend_time = utc_now()

        # Backend serializes for API response
        api_response = to_iso_utc(backend_time)

        # Verify frontend will receive 'Z' suffix
        assert api_response is not None
        assert api_response.endswith('Z')

        # Verify can be parsed back to datetime
        parsed = datetime.fromisoformat(api_response.replace('Z', '+00:00'))
        assert parsed.tzinfo == timezone.utc

        # Verify round-trip preserves time (within microseconds)
        assert abs((parsed - backend_time).total_seconds()) < 0.001
