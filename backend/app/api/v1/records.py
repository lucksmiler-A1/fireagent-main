from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db import crud
from app.db.schemas import Record, RecordInsightsResponse, RecordListItem, RecordListResponse
from app.db.session import get_db
from app.services.memory.long_term_memory import long_term_memory_service
from app.services.record_insights import record_insights_service
from app.services.result_cache import result_cache_service
from app.services.storage import storage_service

router = APIRouter()


@router.get("/", response_model=RecordListResponse)
def get_records(
    limit: int = Query(20, ge=1, le=50),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    records = crud.get_records_with_limit_offset(db, limit=limit, offset=offset)
    total = crud.get_records_count(db)
    return RecordListResponse(total=total, records=[RecordListItem.from_orm(x) for x in records])


@router.get("/insights", response_model=RecordInsightsResponse)
def get_record_insights(
    days: int = Query(7, ge=3, le=30),
    db: Session = Depends(get_db),
):
    return record_insights_service.build_insights(db, days=days)


@router.delete("/")
def clear_records(db: Session = Depends(get_db)):
    deleted_records, file_paths = crud.delete_all_records(db)
    memory_cleanup = crud.delete_all_memory_state(db)
    deleted_files = 0
    for path in file_paths:
        if storage_service.delete_file(path):
            deleted_files += 1
    deleted_cache_files = result_cache_service.clear_all()
    long_memory_index_cleared = long_term_memory_service.clear_embedding_index()
    return {
        "deleted_records": deleted_records,
        "deleted_files": deleted_files,
        "deleted_cache_files": deleted_cache_files,
        "deleted_memory_tasks": memory_cleanup.get("deleted_tasks", 0),
        "deleted_risk_profiles": memory_cleanup.get("deleted_profiles", 0),
        "long_memory_index_cleared": bool(long_memory_index_cleared),
    }


@router.get("/{record_id}", response_model=Record)
def get_record(record_id: str, db: Session = Depends(get_db)):
    record = crud.get_record(db, record_id)
    if not record:
        raise HTTPException(status_code=404, detail="Record not found")
    return Record.from_orm(record)

