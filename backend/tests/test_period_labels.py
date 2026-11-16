from datetime import date

from app.api.v1.endpoints.analytics import cycle_label_prefix, format_period_range, period_label


def test_period_range_uses_indonesian_months_and_compacts_same_month():
    assert format_period_range(date(2026, 11, 9), date(2026, 11, 22)) == "9–22 Nov 2026"
    assert format_period_range(date(2026, 10, 26), date(2026, 11, 8)) == "26 Okt – 8 Nov 2026"
    assert format_period_range(date(2026, 12, 28), date(2027, 1, 10)) == "28 Des 2026 – 10 Jan 2027"
    assert format_period_range(date(2026, 8, 1), date(2026, 8, 31)) == "1–31 Agu 2026"


def test_period_label_has_no_nested_brackets():
    label = period_label(cycle_label_prefix("biweekly", 14, 25), date(2026, 11, 9), date(2026, 11, 22)) + " · berjalan"
    assert label == "Siklus 2 mingguan · 9–22 Nov 2026 · berjalan"
    assert "(" not in label
    assert cycle_label_prefix("monthly_date", 30, 25) == "Siklus bulanan, gajian tgl 25"
    assert cycle_label_prefix("custom", 10, 25) == "Siklus 10 hari"
