"""
API路由汇总
"""

from fastapi import APIRouter

from app.api.endpoints import research, websocket, export, settings, inverter

api_router = APIRouter()

# 研究任务接口
api_router.include_router(research.router, prefix="/research", tags=["研究任务"])

# WebSocket接口
api_router.include_router(websocket.router, prefix="/ws", tags=["WebSocket"])

# 导出接口
api_router.include_router(export.router, prefix="/export", tags=["导出功能"])

# 逆变器接口
api_router.include_router(inverter.router, prefix="/inverter", tags=["数据逆变器"])

api_router.include_router(settings.router, prefix="/settings", tags=["设置"])
