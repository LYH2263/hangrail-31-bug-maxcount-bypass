from datetime import datetime
from pydantic import BaseModel, Field


class StoreOut(BaseModel):
    id: int
    name: str
    model_config = {"from_attributes": True}


class RailOut(BaseModel):
    id: int
    store_id: int
    label: str
    length_cm: float
    max_active_items: int | None  # NULL = 不限件数
    active_count: int  # 当前 active 占位件数
    model_config = {"from_attributes": True}


class RailUpdate(BaseModel):
    # null 表示清除上限（不限件数）
    max_active_items: int | None = Field(default=None, ge=1)


class OrderOut(BaseModel):
    id: int
    store_id: int
    ticket_code: str
    garment_name: str
    length_cm: float
    status: str
    due_at: datetime
    hung_at: datetime | None
    model_config = {"from_attributes": True}


class HangRequest(BaseModel):
    order_id: int
    rail_id: int | None = None


class PickupRequest(BaseModel):
    ticket_code: str


class OccupancySeg(BaseModel):
    order_id: int
    ticket_code: str
    garment_name: str
    start_cm: float
    end_cm: float


class OccupancyOut(BaseModel):
    rail_id: int
    label: str
    length_cm: float
    max_active_items: int | None
    active_count: int
    segments: list[OccupancySeg]
