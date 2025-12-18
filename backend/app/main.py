"""
DeepResearch Pro 后端主入口
多Agent协同研究系统的后端服务
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import traceback

from app.core.config import settings
from app.core.logging import logger
from app.db.database import init_db
from app.api.router import api_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    应用生命周期管理器
    负责应用启动和关闭时的资源管理
    """
    logger.info("[DeepResearch Pro] 后端启动中...")

    # 初始化数据库
    await init_db()
    logger.info("[DeepResearch Pro] 数据库初始化完成")

    yield

    # 清理资源
    logger.info("[DeepResearch Pro] 后端关闭")


def create_app() -> FastAPI:
    """
    创建并配置FastAPI应用实例
    设置中间件、路由和全局异常处理
    """
    app = FastAPI(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        description="深度研究平台 - 多Agent协同研究系统",
        docs_url="/docs" if settings.DEBUG else None,
        redoc_url="/redoc" if settings.DEBUG else None,
        lifespan=lifespan,
    )

    # 全局异常处理器
    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        error_trace = traceback.format_exc()
        logger.error(f"[全局异常] {request.method} {request.url}\n{error_trace}")
        return JSONResponse(
            status_code=500,
            content={
                "detail": str(exc),
                "trace": error_trace if settings.DEBUG else None,
            },
        )

    # CORS中间件配置
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # 注册路由
    app.include_router(api_router, prefix="/api")

    return app


# 创建应用实例
app = create_app()


@app.get("/health")
async def health_check():
    """健康检查接口"""
    return {
        "status": "healthy",
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app", host=settings.HOST, port=settings.PORT, reload=settings.DEBUG
    )
