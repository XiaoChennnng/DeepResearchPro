"""
启动脚本
小陈说：直接运行这个文件启动后端服务
python run.py
"""
import sys
import io

# 小陈说：Windows的gbk编码是个SB，强制用UTF-8
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

import uvicorn
from app.core.config import settings

if __name__ == "__main__":
    print(f"""
    ================================================================

       DeepResearch Pro 后端服务
       小陈出品，必属精品

       API文档: http://{settings.HOST}:{settings.PORT}/docs
       健康检查: http://{settings.HOST}:{settings.PORT}/health

    ================================================================
    """)

    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
        log_level="info" if settings.DEBUG else "warning"
    )
