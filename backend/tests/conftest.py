"""合同测试夹具：每个用例独享一套全新数据表，保证用例间不脏读、不互相污染占用。

隔离手段：
1. 进程级兜底——导入 app 之前把 DATABASE_URL 指到临时 SQLite 并关闭种子数据，
   防止应用自身引擎/生命周期误连真实 Postgres（docker compose 注入的 DSN 同样被覆盖）；
2. 每个测试函数使用独立的临时 SQLite 库文件，建表 → 用例 → 整表 drop；
3. 通过 FastAPI 依赖覆盖把 get_db 绑到该隔离库，接口落库与断言都发生在同一库内。
"""

from __future__ import annotations

import os
import tempfile

# 必须在任何 app 模块导入之前生效（app.config 在导入时读取环境变量）
_APP_DB = os.path.join(tempfile.mkdtemp(prefix="seatbond-app-"), "app.db")
os.environ["DATABASE_URL"] = f"sqlite:///{_APP_DB}"
os.environ["SEED_ON_EMPTY"] = "false"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402

from app.database import Base, get_db  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture()
def isolated_engine(tmp_path):
    """每用例一个全新 SQLite 库文件：建表 → 用例 → 整表删除，杜绝残留占用。"""
    engine = create_engine(
        f"sqlite:///{tmp_path}/contract.db",
        connect_args={"check_same_thread": False},  # TestClient 在独立线程中运行应用
    )
    Base.metadata.create_all(engine)
    try:
        yield engine
    finally:
        Base.metadata.drop_all(engine)
        engine.dispose()


@pytest.fixture()
def db_session(isolated_engine):
    """测试侧直连会话：布置影厅/场次/既有持座等前置数据。"""
    session_factory = sessionmaker(bind=isolated_engine, autoflush=False, expire_on_commit=False)
    session = session_factory()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def client(isolated_engine):
    """接口侧客户端：get_db 覆盖到同一隔离库，请求提交的数据测试侧立即可见。"""
    session_factory = sessionmaker(bind=isolated_engine, autoflush=False)

    def _override_get_db():
        session = session_factory()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = _override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
