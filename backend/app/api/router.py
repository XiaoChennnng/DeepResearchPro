"""
API路由汇总
小陈我把所有路由都集中在这里，别到处找
"""

from fastapi import APIRouter

from app.api.endpoints import research, websocket, export, settings

api_router = APIRouter()

# 研究任务相关接口
api_router.include_router(research.router, prefix="/research", tags=["研究任务"])

# WebSocket 接口
api_router.include_router(websocket.router, prefix="/ws", tags=["WebSocket"])

# 导出接口
api_router.include_router(export.router, prefix="/export", tags=["导出功能"])

api_router.include_router(settings.router, prefix="/settings", tags=["设置"])
