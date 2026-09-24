"""单杆挂件数上限：达上限跳过、取件后可再挂、未配置不限、上限校验。"""

from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app.models.models import HangRail, RailPlacement, Store, WorkOrder
from app.services.seed import seed_if_empty


@pytest.fixture()
def db():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()
    Base.metadata.drop_all(engine)


@pytest.fixture()
def client(db):
    # 不进入 lifespan（避免触碰真实数据库），仅覆盖 get_db
    app.dependency_overrides[get_db] = lambda: db
    yield TestClient(app)
    app.dependency_overrides.clear()


def make_rails(db, a_limit=2):
    store = Store(name="测试店")
    db.add(store)
    db.flush()
    a = HangRail(store_id=store.id, label="A 杆", length_cm=200, max_active_items=a_limit)
    b = HangRail(store_id=store.id, label="B 杆", length_cm=200)
    db.add_all([a, b])
    db.flush()
    return store, a, b


def add_order(db, store, code, length_cm=10, status="ready"):
    order = WorkOrder(
        store_id=store.id,
        ticket_code=code,
        garment_name=f"衣物{code}",
        length_cm=length_cm,
        status=status,
        due_at=datetime.utcnow() + timedelta(days=1),
    )
    db.add(order)
    db.flush()
    return order


def hang_direct(db, rail, order, start_cm=0):
    order.status = "hung"
    order.hung_at = datetime.utcnow()
    db.add(
        RailPlacement(
            rail_id=rail.id,
            order_id=order.id,
            start_cm=start_cm,
            end_cm=start_cm + order.length_cm,
        )
    )
    db.flush()


def placement_of(db, order):
    return db.scalar(
        select(RailPlacement).where(
            RailPlacement.order_id == order.id, RailPlacement.active == 1
        )
    )


def fill_rail_a(db, store, a):
    o1 = add_order(db, store, "T-001")
    o2 = add_order(db, store, "T-002")
    hang_direct(db, a, o1, 0)
    hang_direct(db, a, o2, 10)
    return o1, o2


def test_hang_skips_rail_at_item_limit(client, db):
    """达上限跳过：A 上限 2 且已挂 2 件，厘米充足时第三件也不得落 A。"""
    store, a, b = make_rails(db)
    fill_rail_a(db, store, a)
    o3 = add_order(db, store, "T-003")

    res = client.post("/api/hang", json={"order_id": o3.id})
    assert res.status_code == 200
    assert placement_of(db, o3).rail_id == b.id

    occ = client.get(f"/api/occupancy/{a.id}").json()
    assert occ["active_count"] == 2
    assert occ["max_active_items"] == 2


def test_hang_explicit_full_rail_rejected(client, db):
    """指定达上限的杆：即使剩余厘米够也必须拒绝。"""
    store, a, _b = make_rails(db)
    fill_rail_a(db, store, a)
    o3 = add_order(db, store, "T-003")

    res = client.post("/api/hang", json={"order_id": o3.id, "rail_id": a.id})
    assert res.status_code == 409
    assert "上限" in res.json()["detail"]
    assert db.get(WorkOrder, o3.id).status == "ready"


def test_hang_again_after_pickup(client, db):
    """取一件释放后计数下降，可再挂上 A。"""
    store, a, _b = make_rails(db)
    o1, _o2 = fill_rail_a(db, store, a)
    o3 = add_order(db, store, "T-003")

    res = client.post("/api/pickup", json={"ticket_code": o1.ticket_code})
    assert res.status_code == 200

    res = client.post("/api/hang", json={"order_id": o3.id, "rail_id": a.id})
    assert res.status_code == 200
    assert placement_of(db, o3).rail_id == a.id

    occ = client.get(f"/api/occupancy/{a.id}").json()
    assert occ["active_count"] == 2


def test_rail_without_limit_accepts_many(client, db):
    """未配置上限的杆不限制件数。"""
    store, _a, b = make_rails(db)
    orders = [add_order(db, store, f"T-10{i}") for i in range(3)]
    for o in orders:
        res = client.post("/api/hang", json={"order_id": o.id, "rail_id": b.id})
        assert res.status_code == 200
    occ = client.get(f"/api/occupancy/{b.id}").json()
    assert occ["max_active_items"] is None
    assert occ["active_count"] == 3


def test_limit_update_rejected_below_current_count(client, db):
    """上限小于当前已挂数时禁止保存。"""
    store, a, _b = make_rails(db)
    fill_rail_a(db, store, a)

    res = client.patch(f"/api/rails/{a.id}", json={"max_active_items": 1})
    assert res.status_code == 400
    assert "上限" in res.json()["detail"]
    assert db.get(HangRail, a.id).max_active_items == 2

    res = client.patch(f"/api/rails/{a.id}", json={"max_active_items": 2})
    assert res.status_code == 200
    assert res.json()["active_count"] == 2


def test_limit_can_be_raised_and_cleared(client, db):
    store, a, _b = make_rails(db)
    fill_rail_a(db, store, a)
    o3 = add_order(db, store, "T-003")

    res = client.patch(f"/api/rails/{a.id}", json={"max_active_items": 3})
    assert res.status_code == 200
    assert client.post("/api/hang", json={"order_id": o3.id, "rail_id": a.id}).status_code == 200

    res = client.patch(f"/api/rails/{a.id}", json={"max_active_items": None})
    assert res.status_code == 200
    assert res.json()["max_active_items"] is None
    o4 = add_order(db, store, "T-004")
    assert client.post("/api/hang", json={"order_id": o4.id, "rail_id": a.id}).status_code == 200


def test_seed_rail_a_limit_two_third_goes_to_b(client, db):
    """种子：A 杆上限 2，已挂 2 件时第三件不得上 A。"""
    seed_if_empty(db)
    rails = client.get("/api/rails").json()
    a = next(r for r in rails if r["label"] == "A 杆")
    assert a["max_active_items"] == 2
    assert a["active_count"] == 2

    orders = client.get("/api/orders").json()
    o3 = next(o for o in orders if o["ticket_code"] == "HR-2003")
    res = client.post("/api/hang", json={"order_id": o3["id"]})
    assert res.status_code == 200

    occ = client.get(f"/api/occupancy/{a['id']}").json()
    assert occ["active_count"] == 2
    assert all(s["ticket_code"] != "HR-2003" for s in occ["segments"])
