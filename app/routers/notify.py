"""预测与通知接口。"""

import datetime as dt

from fastapi import APIRouter, Depends

from .. import auth, cycle, db

router = APIRouter(prefix="/api", tags=["notify"])


def _records(user_id: int) -> list[dict]:
    with db.get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM daily_records WHERE user_id=? ORDER BY date", (user_id,)
        ).fetchall()
    return [dict(r) for r in rows]


@router.get("/predictions")
def get_predictions(user: dict = Depends(auth.get_current_user)):
    return cycle.predict(cycle.period_starts(_records(user["id"])))


@router.get("/notifications")
def get_notifications(user: dict = Depends(auth.get_current_user)):
    records = _records(user["id"])
    pred = cycle.predict(cycle.period_starts(records))
    period_started = False
    if pred.get("next_period"):
        anchor = dt.date.fromisoformat(pred["next_period"])
        period_started = any(
            cycle.is_period_day(r) and dt.date.fromisoformat(r["date"]) >= anchor
            for r in records
        )
    return {
        "predictions": pred,
        "notifications": cycle.build_notifications(pred, period_started=period_started),
    }
