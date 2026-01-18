from typing import Optional
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import os

# 使用 HTTPBearer 方案，auto_error=False 以便我们手动处理错误并返回 401 而不是默认的 403
security = HTTPBearer(auto_error=False)

async def get_current_user(credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)) -> dict:
    """
    验证当前用户是否登录
    """
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated (Missing Token)",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = credentials.credentials
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated (Empty Token)",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # 暂时返回一个模拟的用户对象或仅返回 Token
    return {"token": token, "is_authenticated": True}
