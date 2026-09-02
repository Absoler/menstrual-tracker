"""每日记录接口：按用户隔离，客户端无关的 JSON。"""

import datetime as dt
import json
import sqlite3

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from .. import auth, cycle, db

router = APIRouter(prefix="/api/records", tags=["records"])

COLORS = ("bright_red", "dark_red", "pink", "brown", "black", "orange", "grey")
CLOTS = ("none", "small", "large")
PAIN = ("none", "mild", "moderate", "severe")
SYMPTOMS = (
    "bloating", "headache", "breast_tenderness", "nausea", "fatigue",
    "diarrhea", "constipation", "appetite_change", "acne", "insomnia",
)
MOODS = ("calm", "happy", "anxious", "irritable", "sad", "tired")


class RecordIn(BaseModel):
    flow: str = "none"
    colors: list[str] = []
    clots: str = "none"
    pain: str = "none"
    symptoms: list[str] = []
    mood: list[str] = []
    medication: str = ""
    notes: str = ""


def _check(value: str, allowed: tuple[str, ...], field: str) -> None:
    if value not in allowed:
        raise HTTPException(status_code=422, detail=f"{field} 取值无效: {value}")


def _check_list(values: list[str], allowed: tuple[str, ...], field: str) -> None:
    for value in values:
        _check(value, allowed, field)


def _validate(body: RecordIn) -> None:
    _check(body.flow, cycle.FLOW_VALUES, "经量")
    _check_list(body.colors, COLORS, "颜色")
    _check(body.clots, CLOTS, "血块")
    _check(body.pain, PAIN, "疼痛")
    _check_list(body.symptoms, SYMPTOMS, "症状")
    _check_list(body.mood, MOODS, "情绪")


def row_to_record(row: sqlite3.Row) -> dict:
    return {
        "date": row["date"],
        "flow": row["flow"],
        "colors": json.loads(row["colors"]),
        "clots": row["clots"],
        "pain": row["pain"],
        "symptoms": json.loads(row["symptoms"]),
        "mood": json.loads(row["mood"]),
        "medication": row["medication"],
        "notes": row["notes"],
    }


@router.get("")
def list_records(
    month: str = Query(..., pattern=r"^\d{4}-\d{2}$"),
    user: dict = Depends(auth.get_current_user),
):
    first = dt.date.fromisoformat(month + "-01")
    next_month = (first + dt.timedelta(days=32)).replace(day=1)
    with db.get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM daily_records WHERE user_id=? AND date>=? AND date<? ORDER BY date",
            (user["id"], first.isoformat(), next_month.isoformat()),
        ).fetchall()
    return {"records": [row_to_record(r) for r in rows]}


@router.put("/{date}")
def upsert_record(date: str, body: RecordIn, user: dict = Depends(auth.get_current_user)):
    try:
        dt.date.fromisoformat(date)
    except ValueError:
        raise HTTPException(status_code=422, detail="日期格式应为 YYYY-MM-DD")
    _validate(body)
    with db.get_db() as conn:
        conn.execute(
            """
            INSERT INTO daily_records
                (user_id, date, flow, colors, clots, pain, symptoms, mood, medication, notes, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
            ON CONFLICT(user_id, date) DO UPDATE SET
                flow=excluded.flow, colors=excluded.colors, clots=excluded.clots,
                pain=excluded.pain, symptoms=excluded.symptoms, mood=excluded.mood,
                medication=excluded.medication, notes=excluded.notes,
                updated_at=excluded.updated_at
            """,
            (
                user["id"], date, body.flow,
                json.dumps(body.colors, ensure_ascii=False), body.clots, body.pain,
                json.dumps(body.symptoms, ensure_ascii=False),
                json.dumps(body.mood, ensure_ascii=False),
                body.medication, body.notes,
            ),
        )
    return {"ok": True, "date": date}


@router.delete("/{date}")
def delete_record(date: str, user: dict = Depends(auth.get_current_user)):
    with db.get_db() as conn:
        conn.execute(
            "DELETE FROM daily_records WHERE user_id=? AND date=?",
            (user["id"], date),
        )
    return {"ok": True, "date": date}
