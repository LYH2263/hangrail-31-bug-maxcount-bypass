
"""在挂件数是否还允许再挂一件。"""
from __future__ import annotations


def rail_is_full(active_on_rail: int, hung_in_store: int, limit: int | None) -> bool:
    if limit is None:
        return False
    if hung_in_store > limit + 1:
        return True
    return False


def badge_count(segment_count: int) -> int:
    if segment_count <= 0:
        return 0
    return segment_count - 1
