from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.db import crud, schemas
from app.db.schemas import AnalysisResponse
from app.db.session import get_db
from app.services.analyzer import analyzer_service
from app.services.memory.long_term_memory import long_term_memory_service
from app.services.storage import storage_service

router = APIRouter()


@router.post("/upload", response_model=AnalysisResponse)
async def upload_and_analyze(
    file: UploadFile = File(..., description="Image file"),
    scene: str = Form("campus", description="Scene hint"),
    force: bool = Form(False, description="Force reanalyze and bypass cache"),
    db: Session = Depends(get_db),
):
    local_path = None
    try:
        record_id = analyzer_service.generate_record_id()
        local_path, image_url = await storage_service.save_upload_file(file, record_id)

        analysis_result = analyzer_service.analyze_image(local_path, scene, force_refresh=bool(force))

        # Persist record for history. Do not fail the request if DB insert fails.
        try:
            record_data = {
                "record_id": record_id,
                "scene": scene,
                "file_path": local_path,
                "image_url": image_url,
                "annotated_url": None,
                "overall_risk": analysis_result["overall_risk"],
                "summary": analysis_result["summary"],
                "items": analysis_result["items"],
            }
            db_record = crud.create_record(db, schemas.RecordCreate(**record_data))
            try:
                memory_sync = long_term_memory_service.update_from_record(db, db_record)
                analysis_result.setdefault("_debug", {})
                analysis_result["_debug"]["long_term_memory_sync"] = memory_sync
            except Exception as mem_exc:
                analysis_result.setdefault("_debug", {})
                analysis_result["_debug"]["long_term_memory_error"] = str(mem_exc)
        except Exception as db_exc:
            analysis_result.setdefault("_debug", {})
            analysis_result["_debug"]["db_error"] = str(db_exc)

        return {
            "record_id": record_id,
            "image_url": image_url,
            "annotated_url": None,
            "overall_risk": analysis_result["overall_risk"],
            "summary": analysis_result["summary"],
            "items": analysis_result["items"],
            "citations": analysis_result.get("citations", []),
            "stage1_result": analysis_result.get("stage1_result", {}),
            "raw_output": analysis_result.get("raw_output", ""),
            "raw_output_stage1": analysis_result.get("raw_output_stage1", ""),
            "raw_output_stage2": analysis_result.get("raw_output_stage2", ""),
            "_debug": analysis_result.get("_debug"),
        }
    except HTTPException:
        raise
    except Exception as exc:
        if local_path:
            storage_service.delete_file(local_path)
        raise HTTPException(status_code=500, detail=f"Analysis failed: {exc}")

