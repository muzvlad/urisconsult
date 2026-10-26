"""Тесты HR-стилей и форматирования дат (spec 026, 027)."""
from datetime import date

from src.config import (
    HR_STATUS_KEYS, HR_STATUS_LABELS, HR_STATUS_STYLES, hr_status_style,
    format_date, format_datetime, parse_user_date, period_range,
)


class TestHrStyles:
    def test_all_keys_have_label_and_saturated_style(self):
        assert set(HR_STATUS_KEYS) == set(HR_STATUS_LABELS) == set(HR_STATUS_STYLES)
        for key in HR_STATUS_KEYS:
            style = HR_STATUS_STYLES[key]
            assert style['bg'].startswith('#') and len(style['bg']) == 7
            assert style['fg'].startswith('#') and len(style['fg']) == 7

    def test_unknown_falls_back_to_not_processed(self):
        assert hr_status_style('unknown') == hr_status_style('not_processed')


class TestDateFormat:
    def test_format_date(self):
        assert format_date('2026-10-26T14:30:00') == '26.10.2026'
        assert format_date('2026-10-26 14:30') == '26.10.2026'
        assert format_date('26.10.2026') == '26.10.2026'
        assert format_date('26.10.2026 14:30') == '26.10.2026 14:30'
        assert format_date('') == ''
        assert format_date(None) == ''

    def test_format_datetime(self):
        assert format_datetime('2026-10-26T14:30:00') == '26.10.2026 14:30'
        assert format_datetime('2026-10-26') == '26.10.2026'
        assert format_datetime('26.10.2026 14:30') == '26.10.2026 14:30'
        assert format_datetime('26.10.2026') == '26.10.2026'

    def test_parse_user_date(self):
        assert parse_user_date('26.10.2026') == '2026-10-26'
        assert parse_user_date('31.02.2026') is None
        assert parse_user_date('2026-10-26') is None
        assert parse_user_date('1.1.2026') is None


class TestPeriodRange:
    def test_presets(self):
        today = date(2026, 3, 10)
        assert period_range('today', today) == ('2026-03-10', '2026-03-10')
        assert period_range('week', today) == ('2026-03-04', '2026-03-10')
        assert period_range('month', today) == ('2026-03-01', '2026-03-10')
        assert period_range('prev_month', today) == ('2026-02-01', '2026-02-28')
        assert period_range('year', today) == ('2026-01-01', '2026-03-10')
        assert period_range('all', today) == (None, None)
        assert period_range('custom', today) == (None, None)
