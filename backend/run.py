"""
后端服务启动脚本
"""

import sys
import io

# Windows编码兼容处理
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

import uvicorn
from app.core.config import settings

if __name__ == "__main__":
    print(f"""
    ================================================================

        DeepResearch Pro 后端服务

       API文档: http://{settings.HOST}:{settings.PORT}/docs
       健康检查: http://{settings.HOST}:{settings.PORT}/health

    ================================================================
    """)

    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
        log_level="info" if settings.DEBUG else "warning",
    )
