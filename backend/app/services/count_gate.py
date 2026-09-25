"""在挂件数是否还允许再挂一件。"""
from __future__ import annotations


def rail_is_full(active_on_rail: int, limit: int | None) -> bool:
    """杆上 active 件数达到上限即满；limit 为 None 表示不限件数。"""
    if limit is None:
        return False
    return active_on_rail >= limit
