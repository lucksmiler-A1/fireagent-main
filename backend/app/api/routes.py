"""
API 路由配置
"""
from fastapi import APIRouter
from app.api.v1 import agent, analysis, chat, memory, records, scene_guides

# 创建主路由器
api_router = APIRouter()

# 挂载 v1 版本的路由
api_router.include_router(
    analysis.router,
    prefix="/analysis",
    tags=["analysis"]
)

api_router.include_router(
    records.router,
    prefix="/records",
    tags=["records"]
)

api_router.include_router(
    chat.router,
    prefix="/chat",
    tags=["chat"]
)

api_router.include_router(
    agent.router,
    prefix="/agent",
    tags=["agent"]
)

api_router.include_router(
    scene_guides.router,
    prefix="/scene-guides",
    tags=["scene-guides"]
)

api_router.include_router(
    memory.router,
    prefix="/memory",
    tags=["memory"]
)
