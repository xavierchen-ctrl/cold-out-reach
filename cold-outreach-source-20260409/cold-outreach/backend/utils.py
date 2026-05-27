"""
通用工具函式
"""
from datetime import datetime, timezone, timedelta

TW_TZ = timezone(timedelta(hours=8))  # UTC+8 (Asia/Taipei)


def now_tw() -> datetime:
    """回傳台灣時間（UTC+8），naive datetime（不帶 tzinfo），SQLAlchemy 相容。"""
    return datetime.now(tz=TW_TZ).replace(tzinfo=None)
