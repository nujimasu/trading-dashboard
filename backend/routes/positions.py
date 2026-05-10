"""保有ポジション管理 API"""
from fastapi import APIRouter, HTTPException, Query
from typing import Optional

from backend.services import positions_service as ps

router = APIRouter()


@router.get("/api/positions")
def list_positions(
    status: Optional[str] = Query(None, regex="^(open|closed)$"),
    limit: int = Query(200, ge=1, le=1000),
):
    return {"positions": ps.list_positions(status=status, limit=limit)}


@router.get("/api/positions/{position_id}")
def get_position(position_id: int):
    p = ps.get_position(position_id)
    if not p:
        raise HTTPException(404, "ポジションが見つかりません")
    return p


@router.post("/api/positions")
def create_position(payload: dict):
    try:
        return ps.create_position(payload)
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.patch("/api/positions/{position_id}")
def update_position(position_id: int, payload: dict):
    p = ps.update_position(position_id, payload)
    if not p:
        raise HTTPException(404, "ポジションが見つかりません")
    return p


@router.post("/api/positions/{position_id}/close")
def close_position(position_id: int, payload: dict):
    try:
        p = ps.close_position(position_id, payload)
        if not p:
            raise HTTPException(404, "ポジションが見つかりません")
        return p
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.delete("/api/positions/{position_id}")
def delete_position(position_id: int):
    ps.delete_position(position_id)
    return {"deleted": True}


@router.get("/api/positions/{position_id}/journal")
def list_journal(position_id: int):
    return {"entries": ps.list_journal(position_id)}


@router.post("/api/positions/{position_id}/journal")
def add_journal(position_id: int, payload: dict):
    try:
        return ps.add_journal(position_id, payload)
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.delete("/api/journal/{entry_id}")
def delete_journal(entry_id: int):
    ps.delete_journal(entry_id)
    return {"deleted": True}
