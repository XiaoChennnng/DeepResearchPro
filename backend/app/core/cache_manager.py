"""
缓存管理器 - SQLite缓存实现
提供统一的缓存接口，支持TTL、压缩、统计等功能
"""

import json
import gzip
import asyncio
from typing import Any, Dict, Optional, List, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass
from sqlalchemy import select, delete, func, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import async_session_maker
from app.db.models import CacheEntry
from app.core.logging import logger


@dataclass
class CacheConfig:
    """缓存配置"""

    default_ttl_hours: int = 24  # 默认TTL（小时）
    max_entries: int = 10000  # 最大条目数
    cleanup_interval_minutes: int = 30  # 清理间隔（分钟）
    compression_threshold: int = 1024  # 压缩阈值（字节）
    enable_stats: bool = True  # 启用统计


class CacheStats:
    """缓存统计信息"""

    def __init__(self):
        self.hits = 0
        self.misses = 0
        self.sets = 0
        self.deletes = 0
        self.expired_cleanups = 0
        self.size_cleanups = 0

    @property
    def hit_rate(self) -> float:
        """命中率"""
        total = self.hits + self.misses
        return self.hits / total if total > 0 else 0.0

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "hits": self.hits,
            "misses": self.misses,
            "sets": self.sets,
            "deletes": self.deletes,
            "expired_cleanups": self.expired_cleanups,
            "size_cleanups": self.size_cleanups,
            "hit_rate": self.hit_rate,
        }


class SQLiteCacheBackend:
    """SQLite缓存后端"""

    def __init__(self, config: Optional[CacheConfig] = None):
        self.config = config or CacheConfig()
        self.stats = CacheStats()
        self._cleanup_task: Optional[asyncio.Task] = None

    async def start(self):
        """启动缓存管理器"""
        logger.info("[CacheManager] 启动SQLite缓存后端")
        # 启动定期清理任务
        self._cleanup_task = asyncio.create_task(self._periodic_cleanup())

    async def stop(self):
        """停止缓存管理器"""
        logger.info("[CacheManager] 停止SQLite缓存后端")
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass

    async def get(self, key: str) -> Optional[Any]:
        """获取缓存值"""
        async with async_session_maker() as session:
            try:
                # 查询缓存条目
                stmt = select(CacheEntry).where(
                    and_(
                        CacheEntry.cache_key == key,
                        or_(
                            CacheEntry.expires_at.is_(None),
                            CacheEntry.expires_at > datetime.utcnow(),
                        ),
                    )
                )
                result = await session.execute(stmt)
                entry = result.scalar_one_or_none()

                if entry is None:
                    if self.config.enable_stats:
                        self.stats.misses += 1
                    return None

                # 更新访问统计
                entry.touch()
                await session.commit()

                # 解压缩和反序列化
                value = self._deserialize_value(entry)

                if self.config.enable_stats:
                    self.stats.hits += 1

                logger.debug(f"[CacheManager] 缓存命中: {key}")
                return value

            except Exception as e:
                logger.error(f"[CacheManager] 获取缓存失败 {key}: {e}")
                return None

    async def set(
        self,
        key: str,
        value: Any,
        ttl_hours: Optional[int] = None,
        cache_type: str = "default",
        metadata: Optional[Dict] = None,
    ) -> bool:
        """设置缓存值"""
        async with async_session_maker() as session:
            try:
                # 计算过期时间
                expires_at = None
                if ttl_hours is not None:
                    expires_at = datetime.utcnow() + timedelta(hours=ttl_hours)
                elif self.config.default_ttl_hours > 0:
                    expires_at = datetime.utcnow() + timedelta(
                        hours=self.config.default_ttl_hours
                    )

                # 序列化和压缩
                serialized_value, is_compressed, value_size = self._serialize_value(
                    value
                )

                # 检查是否已存在
                stmt = select(CacheEntry).where(CacheEntry.cache_key == key)
                result = await session.execute(stmt)
                existing_entry = result.scalar_one_or_none()

                if existing_entry:
                    # 更新现有条目
                    existing_entry.cache_value = serialized_value
                    existing_entry.cache_type = cache_type
                    existing_entry.cache_metadata = metadata
                    existing_entry.expires_at = expires_at
                    existing_entry.is_compressed = is_compressed
                    existing_entry.value_size = value_size
                    existing_entry.updated_at = datetime.utcnow()
                    existing_entry.touch()
                else:
                    # 创建新条目
                    new_entry = CacheEntry(
                        cache_key=key,
                        cache_value=serialized_value,
                        cache_type=cache_type,
                        cache_metadata=metadata,
                        expires_at=expires_at,
                        is_compressed=is_compressed,
                        value_size=value_size,
                    )
                    session.add(new_entry)

                await session.commit()

                if self.config.enable_stats:
                    self.stats.sets += 1

                # 检查是否需要清理（异步执行）
                asyncio.create_task(self._check_and_cleanup())

                logger.debug(f"[CacheManager] 缓存设置: {key} (type: {cache_type})")
                return True

            except Exception as e:
                logger.error(f"[CacheManager] 设置缓存失败 {key}: {e}")
                await session.rollback()
                return False

    async def delete(self, key: str) -> bool:
        """删除缓存条目"""
        async with async_session_maker() as session:
            try:
                stmt = delete(CacheEntry).where(CacheEntry.cache_key == key)
                result = await session.execute(stmt)
                await session.commit()

                deleted_count = result.rowcount
                if deleted_count > 0 and self.config.enable_stats:
                    self.stats.deletes += 1

                logger.debug(f"[CacheManager] 缓存删除: {key}")
                return deleted_count > 0

            except Exception as e:
                logger.error(f"[CacheManager] 删除缓存失败 {key}: {e}")
                await session.rollback()
                return False

    async def clear_expired(self) -> int:
        """清理过期条目"""
        async with async_session_maker() as session:
            try:
                # 删除过期条目
                stmt = delete(CacheEntry).where(
                    and_(
                        CacheEntry.expires_at.is_not(None),
                        CacheEntry.expires_at <= datetime.utcnow(),
                    )
                )
                result = await session.execute(stmt)
                await session.commit()

                cleaned_count = result.rowcount
                if self.config.enable_stats:
                    self.stats.expired_cleanups += cleaned_count

                logger.info(f"[CacheManager] 清理过期缓存: {cleaned_count} 条")
                return cleaned_count

            except Exception as e:
                logger.error(f"[CacheManager] 清理过期缓存失败: {e}")
                await session.rollback()
                return 0

    async def clear_by_type(self, cache_type: str) -> int:
        """按类型清理缓存"""
        async with async_session_maker() as session:
            try:
                stmt = delete(CacheEntry).where(CacheEntry.cache_type == cache_type)
                result = await session.execute(stmt)
                await session.commit()

                cleaned_count = result.rowcount
                logger.info(
                    f"[CacheManager] 清理类型缓存 {cache_type}: {cleaned_count} 条"
                )
                return cleaned_count

            except Exception as e:
                logger.error(f"[CacheManager] 清理类型缓存失败 {cache_type}: {e}")
                await session.rollback()
                return 0

    async def get_stats(self) -> Dict[str, Any]:
        """获取缓存统计信息"""
        async with async_session_maker() as session:
            try:
                # 获取基本统计
                stmt = select(
                    func.count(CacheEntry.id).label("total_entries"),
                    func.sum(CacheEntry.value_size).label("total_size"),
                    func.avg(CacheEntry.access_count).label("avg_access_count"),
                )
                result = await session.execute(stmt)
                row = result.first()

                # 按类型统计
                type_stmt = select(
                    CacheEntry.cache_type,
                    func.count(CacheEntry.id).label("count"),
                    func.sum(CacheEntry.value_size).label("size"),
                ).group_by(CacheEntry.cache_type)
                type_result = await session.execute(type_stmt)
                type_stats = {
                    type_row.cache_type: {
                        "count": type_row.count,
                        "size": type_row.size or 0,
                    }
                    for type_row in type_result
                }

                return {
                    "total_entries": row.total_entries or 0 if row else 0,
                    "total_size_bytes": row.total_size or 0 if row else 0,
                    "avg_access_count": float(row.avg_access_count or 0)
                    if row
                    else 0.0,
                    "type_stats": type_stats,
                    "performance": self.stats.to_dict(),
                    "config": {
                        "default_ttl_hours": self.config.default_ttl_hours,
                        "max_entries": self.config.max_entries,
                        "compression_threshold": self.config.compression_threshold,
                    },
                }

            except Exception as e:
                logger.error(f"[CacheManager] 获取统计信息失败: {e}")
                return {}

    def _serialize_value(self, value: Any) -> Tuple[str, bool, int]:
        """序列化并可选压缩值"""
        # 序列化为JSON
        json_str = json.dumps(value, ensure_ascii=False, default=str)
        original_size = len(json_str.encode("utf-8"))

        # 检查是否需要压缩
        if original_size > self.config.compression_threshold:
            compressed = gzip.compress(json_str.encode("utf-8"))
            return compressed.hex(), True, original_size
        else:
            return json_str, False, original_size

    def _deserialize_value(self, entry: CacheEntry) -> Any:
        """反序列化值"""
        if entry.cache_value is None:
            return None

        try:
            if entry.is_compressed:
                # 解压缩
                compressed_data = bytes.fromhex(entry.cache_value)
                json_str = gzip.decompress(compressed_data).decode("utf-8")
            else:
                json_str = entry.cache_value

            return json.loads(json_str)

        except Exception as e:
            logger.error(f"[CacheManager] 反序列化失败: {e}")
            return None

    async def _check_and_cleanup(self):
        """检查并执行清理"""
        try:
            async with async_session_maker() as session:
                # 检查总条目数
                stmt = select(func.count(CacheEntry.id))
                result = await session.execute(stmt)
                total_count = result.scalar() or 0

                if total_count > self.config.max_entries:
                    # 清理最少访问的条目
                    cleanup_count = (
                        total_count - self.config.max_entries + 100
                    )  # 多清理100条

                    # 找到最少访问的条目
                    stmt = (
                        select(CacheEntry)
                        .order_by(
                            CacheEntry.access_count.asc(),
                            CacheEntry.last_accessed.asc().nullsfirst(),
                        )
                        .limit(cleanup_count)
                    )

                    result = await session.execute(stmt)
                    entries_to_delete = result.scalars().all()

                    # 删除这些条目
                    for entry in entries_to_delete:
                        await session.delete(entry)

                    await session.commit()

                    if self.config.enable_stats:
                        self.stats.size_cleanups += len(entries_to_delete)

                    logger.info(
                        f"[CacheManager] 清理低频缓存: {len(entries_to_delete)} 条"
                    )

        except Exception as e:
            logger.error(f"[CacheManager] 缓存大小清理失败: {e}")

    async def _periodic_cleanup(self):
        """定期清理任务"""
        while True:
            try:
                await asyncio.sleep(self.config.cleanup_interval_minutes * 60)
                await self.clear_expired()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"[CacheManager] 定期清理失败: {e}")


class CacheManager:
    """缓存管理器主类"""

    def __init__(self, backend: Optional[SQLiteCacheBackend] = None):
        self.backend = backend or SQLiteCacheBackend()
        self._started = False

    async def start(self):
        """启动缓存管理器"""
        if not self._started:
            await self.backend.start()
            self._started = True
            logger.info("[CacheManager] 缓存管理器已启动")

    async def stop(self):
        """停止缓存管理器"""
        if self._started:
            await self.backend.stop()
            self._started = False
            logger.info("[CacheManager] 缓存管理器已停止")

    async def get(self, key: str) -> Optional[Any]:
        """获取缓存值"""
        return await self.backend.get(key)

    async def set(
        self,
        key: str,
        value: Any,
        ttl_hours: Optional[int] = None,
        cache_type: str = "default",
        metadata: Optional[Dict] = None,
    ) -> bool:
        """设置缓存值"""
        return await self.backend.set(key, value, ttl_hours, cache_type, metadata)

    async def delete(self, key: str) -> bool:
        """删除缓存条目"""
        return await self.backend.delete(key)

    async def clear_expired(self) -> int:
        """清理过期条目"""
        return await self.backend.clear_expired()

    async def clear_by_type(self, cache_type: str) -> int:
        """按类型清理缓存"""
        return await self.backend.clear_by_type(cache_type)

    async def get_stats(self) -> Dict[str, Any]:
        """获取缓存统计信息"""
        return await self.backend.get_stats()

    @classmethod
    def generate_key(cls, content: str, cache_type: str = "") -> str:
        """生成缓存键"""
        return CacheEntry.generate_key(content, cache_type)


# 全局缓存管理器实例
_cache_manager: Optional[CacheManager] = None


async def get_cache_manager() -> CacheManager:
    """获取全局缓存管理器实例"""
    global _cache_manager
    if _cache_manager is None:
        _cache_manager = CacheManager()
        await _cache_manager.start()
    return _cache_manager


async def init_cache_manager():
    """初始化缓存管理器"""
    manager = await get_cache_manager()
    return manager


async def close_cache_manager():
    """关闭缓存管理器"""
    global _cache_manager
    if _cache_manager:
        await _cache_manager.stop()
        _cache_manager = None
