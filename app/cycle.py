"""周期预测纯函数：不依赖 Web 框架与数据库，便于测试和复用。"""

from __future__ import annotations

import datetime as dt
import statistics
from typing import Iterable

FLOW_VALUES = ("none", "spotting", "light", "medium", "heavy")
LEAD_DAYS = 3  # 提前提醒天数


def is_period_day(record: dict) -> bool:
    """当天是否有经血（点滴及以上都算）。"""
    return record.get("flow") in FLOW_VALUES[1:]


def period_starts(records: Iterable[dict]) -> list[dt.date]:
    """从每日记录中识别每次经期首日；连续有经量的日子算同一次经期。"""
    starts: list[dt.date] = []
    last_period_date: dt.date | None = None
    for rec in sorted(records, key=lambda r: r["date"]):
        day = dt.date.fromisoformat(rec["date"])
        if is_period_day(rec):
            if last_period_date is None or (day - last_period_date).days > 1:
                starts.append(day)
            last_period_date = day
    return starts


def cycle_lengths(starts: list[dt.date]) -> list[int]:
    """相邻经期首日的间隔；过滤明显异常值（<10 天视为误记录）。"""
    return [(b - a).days for a, b in zip(starts, starts[1:]) if (b - a).days >= 10]


def predict(starts: list[dt.date], max_cycles: int = 6) -> dict:
    """预测下次月经与排卵日。少于 2 次经期记录时返回 insufficient。"""
    if len(starts) < 2:
        return {
            "status": "insufficient",
            "message": "需要至少 2 次经期记录才能预测",
            "next_period": None,
            "ovulation": None,
            "range_days": None,
            "cycle_median": None,
            "samples": len(starts),
        }
    lengths = cycle_lengths(starts)[-max_cycles:]
    median = int(statistics.median(lengths) + 0.5)  # 四舍五入，避免银行家舍入
    spread = max(1, round(statistics.pstdev(lengths))) if len(lengths) >= 2 else 1
    next_period = starts[-1] + dt.timedelta(days=median)
    ovulation = next_period - dt.timedelta(days=14)  # 黄体期约 14 天
    return {
        "status": "ok",
        "message": "预测仅供参考，个体差异较大",
        "next_period": next_period.isoformat(),
        "ovulation": ovulation.isoformat(),
        "range_days": spread,
        "cycle_median": median,
        "samples": len(starts),
    }


def build_notifications(pred: dict, today: dt.date | None = None, period_started: bool = False) -> list[dict]:
    """根据预测结果生成通知栏条目；period_started 表示预测日之后是否已来月经。"""
    today = today or dt.date.today()
    if pred.get("status") != "ok":
        return [{
            "type": "info",
            "date": today.isoformat(),
            "title": "数据积累中",
            "message": pred.get("message", "记录更多周期后可开始预测"),
        }]

    next_period = dt.date.fromisoformat(pred["next_period"])
    ovulation = dt.date.fromisoformat(pred["ovulation"])
    spread = pred["range_days"]
    items = []

    days_to_period = (next_period - today).days
    if 0 <= days_to_period <= LEAD_DAYS:
        items.append({
            "type": "period",
            "date": next_period.isoformat(),
            "title": "月经将至",
            "message": f"预计 {days_to_period} 天后（{next_period} 前后 {spread} 天）月经来临",
        })
    elif days_to_period < 0 and not period_started and -days_to_period > spread:
        items.append({
            "type": "late",
            "date": today.isoformat(),
            "title": "月经可能推迟",
            "message": f"预计 {next_period} 来潮，已超过 {spread} 天；若持续异常建议咨询医生",
        })

    days_to_ovulation = (ovulation - today).days
    if 0 <= days_to_ovulation <= LEAD_DAYS:
        items.append({
            "type": "ovulation",
            "date": ovulation.isoformat(),
            "title": "排卵期将至",
            "message": f"预计 {days_to_ovulation} 天后（{ovulation} 前后 1 天）排卵",
        })
    return items
