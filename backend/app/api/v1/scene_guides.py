from fastapi import APIRouter, Query

from app.services.scene_guides import scene_guides_service

router = APIRouter()


@router.get("/")
def get_scene_guide(scene: str = Query("campus", max_length=40)):
    return scene_guides_service.get_guide(scene)
