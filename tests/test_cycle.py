import datetime as dt

from app.cycle import build_notifications, period_starts, predict


def test_period_starts_finds_contiguous_periods():
    records = [
        {"date": "2026-01-01", "flow": "none"},
        {"date": "2026-01-05", "flow": "light"},
        {"date": "2026-01-06", "flow": "medium"},
        {"date": "2026-02-03", "flow": "light"},
        {"date": "2026-02-04", "flow": "spotting"},
    ]
    assert period_starts(records) == [dt.date(2026, 1, 5), dt.date(2026, 2, 3)]


def test_predict_uses_median_cycle_length():
    starts = [dt.date(2026, 1, 5), dt.date(2026, 2, 3), dt.date(2026, 3, 3)]
    pred = predict(starts)
    assert pred["status"] == "ok"
    assert pred["cycle_median"] == 29
    assert pred["next_period"] == "2026-04-01"  # 3/3 + 29 天
    assert pred["ovulation"] == "2026-03-18"  # 下次月经前 14 天


def test_predict_needs_two_periods():
    pred = predict([dt.date(2026, 1, 5)])
    assert pred["status"] == "insufficient"
    assert pred["next_period"] is None


def test_notifications_period_approaching():
    starts = [dt.date(2026, 1, 5), dt.date(2026, 2, 3), dt.date(2026, 3, 3)]
    pred = predict(starts)
    items = build_notifications(pred, today=dt.date(2026, 3, 30))
    assert [item["type"] for item in items] == ["period"]


def test_notifications_ovulation_approaching():
    starts = [dt.date(2026, 1, 5), dt.date(2026, 2, 3), dt.date(2026, 3, 3)]
    pred = predict(starts)
    items = build_notifications(pred, today=dt.date(2026, 3, 17))
    assert [item["type"] for item in items] == ["ovulation"]


def test_notifications_late_when_overdue():
    starts = [dt.date(2026, 1, 5), dt.date(2026, 2, 3), dt.date(2026, 3, 3)]
    pred = predict(starts)
    items = build_notifications(pred, today=dt.date(2026, 4, 8), period_started=False)
    assert any(item["type"] == "late" for item in items)


def test_notifications_insufficient():
    pred = predict([dt.date(2026, 1, 5)])
    items = build_notifications(pred, today=dt.date(2026, 3, 29))
    assert items[0]["type"] == "info"
