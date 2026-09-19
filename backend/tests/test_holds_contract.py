"""持座创建与列表 API 合同矩阵。

矩阵覆盖：
- 场次不存在            → 404，且不产生持座与冲突日志
- 成功落库              → 200，返回持座关键字段（场次/排/起止列/人数/单号）
- 连续空座不足          → 409，且写入一条原因可核对的冲突日志
- 与既有持座重叠        → 409，且写入一条原因可核对的冲突日志
- 人数越界              → 422，不落库、不记日志
- 列表接口              → /holds 倒序、/conflicts 字段形态、/seatmap 404

未实现能力（幂等重放、预检确认）以 xfail(strict=True) 标注并注明原因：
断言保持目标合同不放宽，能力落地后 XPASS 会迫使移除标记。
"""

from __future__ import annotations

import re
from datetime import datetime

import pytest

import app.api.router as router_mod
from app.models.models import SeatHold
from app.services.bond_engine import HoldSpan

# ---------------------------------------------------------------------------
# 工具
# ---------------------------------------------------------------------------


def make_hold(db, showtime_id: int, row: int, start_col: int, end_col: int, seq: int = 0) -> SeatHold:
    """直接在库里落一条既有持座，用于构造占用/重叠场景。"""
    hold = SeatHold(
        showtime_id=showtime_id,
        order_code=f"SB-T{seq:04d}",
        row=row,
        start_col=start_col,
        end_col=end_col,
        party_size=end_col - start_col + 1,
    )
    db.add(hold)
    db.commit()
    db.refresh(hold)
    return hold


def _case(**kw):
    base = dict(
        party_size=2,
        preferred_row=None,
        bad_showtime=False,
        preset=(),  # 预置持座 (row, start_col, end_col)
        force_block=None,  # 模拟过期快照强制返回的候选块 (row, start_col, end_col)
        want_status=200,
        want_reason=None,  # 期望冲突日志原因包含的子串
    )
    base.update(kw)
    return base


# ---------------------------------------------------------------------------
# 创建持座合同矩阵
# ---------------------------------------------------------------------------

CREATE_CASES = [
    pytest.param(_case(bad_showtime=True, want_status=404), id="场次不存在-返回404"),
    pytest.param(_case(party_size=3), id="空场锁座成功-返回200并落库"),
    pytest.param(
        _case(party_size=7, want_status=409, want_reason="无足够连续空座"),
        id="过道断开致连续段不足-409并记冲突日志",
    ),
    pytest.param(
        _case(
            party_size=5,
            preset=tuple((r, 9, 10) for r in range(1, 9)),  # 每排 7-12 段被 9-10 打孔
            want_status=409,
            want_reason="无足够连续空座",
        ),
        id="占用打孔后连座不足-409并记冲突日志",
    ),
    pytest.param(
        _case(
            party_size=3,
            preset=((3, 2, 4),),
            force_block=(3, 2, 4),
            want_status=409,
            want_reason="与既有持座重叠",
        ),
        id="与既有持座重叠-409并记冲突日志",
    ),
    pytest.param(_case(party_size=0, want_status=422), id="人数为0-返回422"),
    pytest.param(_case(party_size=13, want_status=422), id="人数超上限-返回422"),
    pytest.param(_case(party_size=2, preferred_row=99), id="偏好排出界-回退自动撮合成功"),
]


@pytest.mark.parametrize("case", CREATE_CASES)
def test_create_hold_contract_matrix(client, db, venue, monkeypatch, case):
    for i, (r, s, e) in enumerate(case["preset"]):
        make_hold(db, venue.showtime_id, r, s, e, seq=i + 1)

    if case["force_block"]:
        r, s, e = case["force_block"]
        stale = HoldSpan(row=r, start_col=s, end_col=e)
        # 选座引擎在一致快照下不会返回重叠块，重叠分支是为并发竞态兜底：
        # 这里模拟"读到过期占用快照"的交错，确定性触发该分支。
        monkeypatch.setattr(router_mod, "find_bond_across_rows", lambda _s, _h, _n: stale)

    showtime_id = 999999 if case["bad_showtime"] else venue.showtime_id
    payload = {"showtime_id": showtime_id, "party_size": case["party_size"]}
    if case["preferred_row"] is not None:
        payload["preferred_row"] = case["preferred_row"]

    resp = client.post("/api/holds", json=payload)
    assert resp.status_code == case["want_status"], resp.text

    # 持座落库核对：仅成功用例新增一条，预置数据不被污染
    holds = client.get("/api/holds").json()
    assert len(holds) == len(case["preset"]) + (1 if case["want_status"] == 200 else 0)
    if case["want_status"] == 200:
        body = resp.json()
        for key in ("id", "showtime_id", "order_code", "row", "start_col", "end_col", "party_size", "status"):
            assert key in body, f"响应缺少关键字段 {key}"

    # 冲突日志核对：条数与原因
    conflicts = client.get("/api/conflicts").json()
    if case["want_reason"]:
        assert len(conflicts) == 1, f"应写入恰好一条冲突日志，实际 {len(conflicts)}"
        entry = conflicts[0]
        assert case["want_reason"] in entry["reason"]
        assert entry["party_size"] == case["party_size"]
        assert entry["showtime_id"] == venue.showtime_id
    else:
        assert conflicts == []


# ---------------------------------------------------------------------------
# 成功落库：关键字段 + 座位图占用抽查
# ---------------------------------------------------------------------------


def test_success_returns_key_fields(client, venue):
    resp = client.post("/api/holds", json={"showtime_id": venue.showtime_id, "party_size": 3})
    assert resp.status_code == 200, resp.text
    body = resp.json()

    assert body["showtime_id"] == venue.showtime_id
    assert body["party_size"] == 3
    assert body["status"] == "held"
    assert body["id"] >= 1
    assert re.fullmatch(r"SB-\d{5}", body["order_code"]), body["order_code"]

    # 起止列连续、长度等于人数、不跨过道（合法连续段为 1-4 / 7-12）
    assert body["end_col"] - body["start_col"] + 1 == 3
    assert not any(a in range(body["start_col"], body["end_col"] + 1) for a in venue.aisles)
    # 空场首单按引擎约定取最左块：1 排 1-3 列
    assert (body["row"], body["start_col"], body["end_col"]) == (1, 1, 3)

    # 列表接口可见同一单
    holds = client.get("/api/holds").json()
    assert [h["id"] for h in holds] == [body["id"]]
    assert holds[0]["order_code"] == body["order_code"]


def test_success_marks_seatmap_cells_occupied(client, venue):
    resp = client.post("/api/holds", json={"showtime_id": venue.showtime_id, "party_size": 3})
    assert resp.status_code == 200
    hold = resp.json()

    sm = client.get(f"/api/seatmap/{venue.showtime_id}").json()
    assert sm["showtime_id"] == venue.showtime_id
    cells = {(c["row"], c["col"]): c for c in sm["cells"]}

    # 持座区间每一格都变为占用
    for col in range(hold["start_col"], hold["end_col"] + 1):
        cell = cells[(hold["row"], col)]
        assert cell["occupied"] is True, f"{hold['row']}排{col}列应为占用"
        assert cell["heat"] == 1.0

    # 抽查相邻格子未被污染：同排下一列、下一排同列仍空闲
    neighbor = cells[(hold["row"], hold["end_col"] + 1)]
    assert neighbor["occupied"] is False and neighbor["heat"] == 0.0
    below = cells[(hold["row"] + 1, hold["start_col"])]
    assert below["occupied"] is False

    # 过道格形态抽查（5、6 列）
    aisle = cells[(hold["row"], 5)]
    assert aisle["is_aisle"] is True and aisle["occupied"] is False


def test_preferred_row_honored(client, venue):
    resp = client.post(
        "/api/holds",
        json={"showtime_id": venue.showtime_id, "party_size": 2, "preferred_row": 6},
    )
    assert resp.status_code == 200
    assert resp.json()["row"] == 6


# ---------------------------------------------------------------------------
# 列表接口合同
# ---------------------------------------------------------------------------


def test_holds_list_descending_by_id(client, venue):
    first = client.post("/api/holds", json={"showtime_id": venue.showtime_id, "party_size": 2}).json()
    second = client.post("/api/holds", json={"showtime_id": venue.showtime_id, "party_size": 2}).json()
    holds = client.get("/api/holds").json()
    assert [h["id"] for h in holds] == [second["id"], first["id"]]
    assert holds[0]["order_code"] == second["order_code"]


def test_conflicts_list_entry_shape(client, venue):
    client.post("/api/holds", json={"showtime_id": venue.showtime_id, "party_size": 7})
    conflicts = client.get("/api/conflicts").json()
    assert len(conflicts) == 1
    entry = conflicts[0]
    assert set(entry) >= {"id", "showtime_id", "party_size", "reason", "created_at"}
    assert entry["party_size"] == 7
    datetime.fromisoformat(entry["created_at"])  # 时间字段可解析


def test_seatmap_unknown_showtime_returns_404(client):
    assert client.get("/api/seatmap/424242").status_code == 404


# ---------------------------------------------------------------------------
# 尚未实现的能力：xfail 标注，不为变绿放宽断言
# ---------------------------------------------------------------------------


@pytest.mark.xfail(
    strict=True,
    reason="幂等能力未实现：无 Idempotency-Key/请求去重，重复提交当前会生成新的持座单",
)
def test_repeated_submit_is_idempotent(client, venue):
    payload = {"showtime_id": venue.showtime_id, "party_size": 2}
    first = client.post("/api/holds", json=payload)
    second = client.post("/api/holds", json=payload)
    assert first.status_code == second.status_code == 200
    assert second.json()["order_code"] == first.json()["order_code"]
    assert len(client.get("/api/holds").json()) == 1


@pytest.mark.xfail(
    strict=True,
    reason="预检确认未实现：HoldRequest 无 dry_run/confirm 字段，预检请求当前会直接落库",
)
def test_dry_run_does_not_persist(client, venue):
    resp = client.post(
        "/api/holds",
        json={"showtime_id": venue.showtime_id, "party_size": 2, "dry_run": True},
    )
    assert resp.status_code == 200
    assert client.get("/api/holds").json() == []
    sm = client.get(f"/api/seatmap/{venue.showtime_id}").json()
    assert all(not c["occupied"] for c in sm["cells"])
