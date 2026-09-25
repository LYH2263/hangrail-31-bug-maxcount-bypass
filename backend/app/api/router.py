from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.models import HangRail, RailPlacement, Store, WorkOrder
from app.schemas.schemas import (
    HangRequest,
    OccupancyOut,
    OccupancySeg,
    OrderOut,
    PickupRequest,
    RailOut,
    RailUpdate,
    StoreOut,
)
from app.services.count_gate import rail_is_full
from app.services.rail_engine import Segment, first_fit

api_router = APIRouter()


def _active_count(db: Session, rail_id: int) -> int:
    return db.scalar(
        select(func.count())
        .select_from(RailPlacement)
        .where(RailPlacement.rail_id == rail_id, RailPlacement.active == 1)
    ) or 0


def _rail_out(db: Session, rail: HangRail) -> RailOut:
    return RailOut(
        id=rail.id,
        store_id=rail.store_id,
        label=rail.label,
        length_cm=rail.length_cm,
        max_active_items=rail.max_active_items,
        active_count=_active_count(db, rail.id),
    )


@api_router.get("/health")
def health():
    return {"status": "ok"}


@api_router.get("/stores", response_model=list[StoreOut])
def stores(db: Session = Depends(get_db)):
    return db.scalars(select(Store).order_by(Store.id)).all()


@api_router.get("/rails", response_model=list[RailOut])
def rails(db: Session = Depends(get_db)):
    rows = db.scalars(select(HangRail).order_by(HangRail.id)).all()
    return [_rail_out(db, r) for r in rows]


@api_router.patch("/rails/{rail_id}", response_model=RailOut)
def update_rail(rail_id: int, body: RailUpdate, db: Session = Depends(get_db)):
    rail = db.get(HangRail, rail_id)
    if not rail:
        raise HTTPException(404, "挂杆不存在")
    current = _active_count(db, rail.id)
    if body.max_active_items is not None and body.max_active_items < current:
        raise HTTPException(400, f"上限不能小于当前已挂件数（当前 {current} 件）")
    rail.max_active_items = body.max_active_items
    db.commit()
    db.refresh(rail)
    return _rail_out(db, rail)


@api_router.get("/orders", response_model=list[OrderOut])
def orders(db: Session = Depends(get_db)):
    return db.scalars(select(WorkOrder).order_by(WorkOrder.id.desc())).all()


@api_router.get("/occupancy/{rail_id}", response_model=OccupancyOut)
def occupancy(rail_id: int, db: Session = Depends(get_db)):
    rail = db.get(HangRail, rail_id)
    if not rail:
        raise HTTPException(404, "挂杆不存在")
    placements = db.scalars(
        select(RailPlacement).where(RailPlacement.rail_id == rail_id, RailPlacement.active == 1)
    ).all()
    segs = []
    for p in placements:
        order = db.get(WorkOrder, p.order_id)
        if not order:
            continue
        segs.append(
            OccupancySeg(
                order_id=order.id,
                ticket_code=order.ticket_code,
                garment_name=order.garment_name,
                start_cm=p.start_cm,
                end_cm=p.end_cm,
            )
        )
    segs.sort(key=lambda s: s.start_cm)
    return OccupancyOut(
        rail_id=rail.id,
        label=rail.label,
        length_cm=rail.length_cm,
        max_active_items=rail.max_active_items,
        active_count=len(placements),
        segments=segs,
    )


@api_router.post("/hang", response_model=OrderOut)
def hang(body: HangRequest, db: Session = Depends(get_db)):
    order = db.get(WorkOrder, body.order_id)
    if not order:
        raise HTTPException(404, "工单不存在")
    if order.status not in ("ready", "overdue"):
        raise HTTPException(400, "工单状态不可上杆")
    rail_q = select(HangRail).where(HangRail.store_id == order.store_id)
    if body.rail_id:
        rail_q = rail_q.where(HangRail.id == body.rail_id)
    rails = db.scalars(rail_q.order_by(HangRail.id)).all()
    if not rails:
        raise HTTPException(404, "无可用挂杆")

    hit_item_limit = False
    for rail in rails:
        active = db.scalars(
            select(RailPlacement).where(RailPlacement.rail_id == rail.id, RailPlacement.active == 1)
        ).all()
        # 件数上限仅统计 active 占位；达到上限即使厘米够也跳过该杆
        if rail_is_full(len(active), rail.max_active_items):
            hit_item_limit = True
            continue
        occupied = [Segment(p.start_cm, p.end_cm) for p in active]
        place = first_fit(rail.length_cm, occupied, order.length_cm)
        if place is None:
            continue
        db.add(
            RailPlacement(
                rail_id=rail.id,
                order_id=order.id,
                start_cm=place.start_cm,
                end_cm=place.end_cm,
            )
        )
        order.status = "hung"
        order.hung_at = datetime.utcnow()
        db.commit()
        db.refresh(order)
        return order

    if hit_item_limit:
        raise HTTPException(409, "挂杆件数已达上限")
    raise HTTPException(409, "挂杆空间不足")


@api_router.post("/pickup", response_model=OrderOut)
def pickup(body: PickupRequest, db: Session = Depends(get_db)):
    order = db.scalar(select(WorkOrder).where(WorkOrder.ticket_code == body.ticket_code))
    if not order:
        raise HTTPException(404, "取件码无效")
    if order.status != "hung":
        raise HTTPException(400, "工单未在挂杆上")
    placements = db.scalars(
        select(RailPlacement).where(RailPlacement.order_id == order.id, RailPlacement.active == 1)
    ).all()
    for p in placements:
        p.active = 0
    order.status = "picked"
    db.commit()
    db.refresh(order)
    return order


@api_router.post("/overdue/scan", response_model=list[OrderOut])
def overdue_scan(db: Session = Depends(get_db)):
    now = datetime.utcnow()
    hung = db.scalars(select(WorkOrder).where(WorkOrder.status == "hung")).all()
    marked = []
    for o in hung:
        if o.due_at < now:
            o.status = "overdue"
            marked.append(o)
    ready = db.scalars(select(WorkOrder).where(WorkOrder.status == "ready")).all()
    for o in ready:
        if o.due_at < now:
            o.status = "overdue"
            marked.append(o)
    db.commit()
    return marked


@api_router.get("/overdue", response_model=list[OrderOut])
def overdue_list(db: Session = Depends(get_db)):
    return db.scalars(select(WorkOrder).where(WorkOrder.status == "overdue").order_by(WorkOrder.due_at)).all()
