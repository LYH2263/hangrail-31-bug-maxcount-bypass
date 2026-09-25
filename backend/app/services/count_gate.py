
"""在挂件数是否还允许再挂一件。

件数的唯一口径：该杆 active=1 的占位数（一件衣物一个 active 段）。
展示角标、占位图段数、上杆校验都必须使用同一计数。
"""
from __future__ import annotations


def rail_is_full(active_on_rail: int, limit: int | None) -> bool:
    """达到（或超过）件数上限即禁止再挂；limit 为 None 表示不限件数。"""
    if limit is None:
        return False
    return active_on_rail >= limit
