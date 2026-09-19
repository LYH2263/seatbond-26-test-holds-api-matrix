"""合同测试夹具：每个用例独立数据库，用例间不脏读、不互相污染占用。

默认使用 SQLite 内存库（StaticPool 单连接），无需外部服务即可运行；
如需对真实 Postgres 跑合同矩阵，指向一个专用可丢弃库即可：

    SEATBOND_TEST_DATABASE_URL=postgresql+psycopg2://seatbond:seatbond@localhost:5442/seatbond_test \\
        docker compose exec api pytest -q

隔离机制：每个用例前 create_all、用后 drop_all，数据不跨用例残留。
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# 兜底：即使意外触发应用 lifespan，也只落在一个一次性的 SQLite 文件上，
# 且不做种子写入，绝不影响 settings 默认指向的库。
os.environ.setdefault("DATABASE_URL", "sqlite:////tmp/seatbond_contract_bootstrap.db")
os.environ.setdefault("SEED_ON_EMPTY", "false")

from app.database import Base, get_db  # noqa: E402
from app.main import app  # noqa: E402
from app.models.models import Hall, Showtime  # noqa: E402

TEST_DATABASE_URL = os.environ.get("SEATBOND_TEST_DATABASE_URL", "sqlite://")


def _make_engine(url: str):
    if url.startswith("sqlite"):
        return create_engine(
            url,
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
    return create_engine(url)


@pytest.fixture()
def engine():
    eng = _make_engine(TEST_DATABASE_URL)
    Base.metadata.create_all(eng)
    yield eng
    Base.metadata.drop_all(eng)  # 用例结束即清空：不脏读、不互相污染
    eng.dispose()


@pytest.fixture()
def db(engine):
    Session = sessionmaker(bind=engine)
    session = Session()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def client(engine):
    """把应用的 get_db 依赖替换为指向测试库的会话。

    不以上下文管理器方式使用 TestClient：不触发 lifespan，
    避免对 settings 指向的库执行 create_all / seed。
    """
    Session = sessionmaker(bind=engine)

    def _get_db():
        session = Session()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = _get_db
    yield TestClient(app)
    app.dependency_overrides.clear()


@dataclass(frozen=True)
class Venue:
    """基准场地：8 排 × 12 列，过道 5、6 列 → 每排连续段为 1-4 与 7-12。"""

    hall_id: int
    showtime_id: int
    rows: int = 8
    cols: int = 12
    aisles: tuple[int, ...] = field(default=(5, 6))


@pytest.fixture()
def venue(db) -> Venue:
    hall = Hall(name="合同厅", rows=8, cols=12, aisle_cols="5,6")
    db.add(hall)
    db.flush()
    st = Showtime(hall_id=hall.id, film_title="合同影片", start_at=datetime(2030, 1, 1, 20, 0))
    db.add(st)
    db.commit()
    return Venue(hall_id=hall.id, showtime_id=st.id)
