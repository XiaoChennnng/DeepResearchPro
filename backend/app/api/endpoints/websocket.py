"""
WebSocket端点 - 实时推送Agent执行状态
"""

from typing import Dict, Set
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from app.core.logging import logger

router = APIRouter()


class ConnectionManager:
    """
    WebSocket连接管理器
    管理所有客户端连接，按任务ID分组
    """

    def __init__(self):
        # task_id -> 连接集合
        self.active_connections: Dict[int, Set[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, task_id: int):
        """接受新连接"""
        await websocket.accept()
        if task_id not in self.active_connections:
            self.active_connections[task_id] = set()
        self.active_connections[task_id].add(websocket)
        logger.info(f"WebSocket连接建立: task_id={task_id}")

    def disconnect(self, websocket: WebSocket, task_id: int):
        """断开连接"""
        if task_id in self.active_connections:
            self.active_connections[task_id].discard(websocket)
            if not self.active_connections[task_id]:
                del self.active_connections[task_id]
        logger.info(f"WebSocket连接断开: task_id={task_id}")

    async def broadcast_to_task(self, task_id: int, message: dict):
        """向特定任务的所有连接广播消息"""
        if task_id not in self.active_connections:
            return

        # 创建连接集合的副本进行迭代，避免并发修改问题
        connections = self.active_connections[task_id].copy()
        dead_connections = set()

        for connection in connections:
            try:
                await connection.send_json(message)
            except Exception as e:
                logger.warning(f"发送消息失败: {e}")
                dead_connections.add(connection)

        # 在迭代完成后移除死连接
        for dead in dead_connections:
            self.active_connections[task_id].discard(dead)

    async def broadcast_all(self, message: dict):
        """向所有连接广播消息"""
        for task_id in list(self.active_connections.keys()):
            await self.broadcast_to_task(task_id, message)


# 全局连接管理器实例
manager = ConnectionManager()


@router.websocket("/research/{task_id}")
async def websocket_endpoint(websocket: WebSocket, task_id: int):
    """研究任务WebSocket端点"""
    logger.info(
        f"[WebSocket] 收到连接请求: task_id={task_id}, client={getattr(websocket.client, 'host', None)}:{getattr(websocket.client, 'port', None)}"
    )

    await manager.connect(websocket, task_id)
    logger.info(f"[WebSocket] 连接已接受: task_id={task_id}")

    try:
        await websocket.send_json(
            {
                "type": "connected",
                "task_id": task_id,
                "message": "小陈的WebSocket连接成功，准备接收实时更新",
            }
        )

        while True:
            try:
                data = await websocket.receive_json()
            except WebSocketDisconnect:
                raise
            except Exception as e:
                logger.warning(
                    f"[WebSocket] 收到无法解析的消息: task_id={task_id}, error={e}"
                )
                continue

            msg_type = data.get("type")
            if msg_type == "ping":
                await websocket.send_json({"type": "pong"})
            elif msg_type == "pause":
                logger.info(f"[WebSocket] 收到暂停请求: task_id={task_id}")

    except WebSocketDisconnect:
        logger.info(f"[WebSocket] 客户端主动断开: task_id={task_id}")
        manager.disconnect(websocket, task_id)
    except Exception as e:
        logger.error(f"[WebSocket] 连接异常: task_id={task_id}, error={e}")
        manager.disconnect(websocket, task_id)


def get_ws_manager() -> ConnectionManager:
    """获取WebSocket管理器实例，供其他模块使用"""
    return manager
