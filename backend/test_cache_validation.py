#!/usr/bin/env python3
"""
缓存功能完整验证
"""

import asyncio
import time
from app.core.cache_manager import get_cache_manager


async def test_cache_complete():
    """完整的缓存功能测试"""
    print("[CACHE TEST] 开始缓存功能验证...")

    try:
        # 获取缓存管理器
        manager = await get_cache_manager()
        print("[OK] 缓存管理器获取成功")

        # 测试基本操作
        test_key = "validation_test_key"
        test_data = {
            "message": "缓存系统工作正常",
            "features": ["TTL", "压缩", "统计", "清理"],
            "timestamp": time.time(),
        }

        # 1. 存储数据
        success = await manager.set(test_key, test_data, cache_type="validation")
        print(f"[SET] 数据存储: {'成功' if success else '失败'}")

        # 2. 读取数据
        retrieved = await manager.get(test_key)
        print(f"[GET] 数据读取: {'成功' if retrieved else '失败'}")

        # 3. 验证数据完整性
        if retrieved:
            data_match = retrieved == test_data
            print(f"[VERIFY] 数据完整性: {'通过' if data_match else '失败'}")

        # 4. 获取统计信息
        stats = await manager.get_stats()
        print(f"[STATS] 缓存条目: {stats.get('total_entries', 0)}")
        print(f"[STATS] 缓存大小: {stats.get('total_size_bytes', 0)} 字节")
        print(f"[STATS] 命中率: {stats.get('performance', {}).get('hit_rate', 0):.1%}")

        # 5. 测试清理功能
        cleaned = await manager.clear_by_type("validation")
        print(f"[CLEAN] 清理测试数据: {cleaned} 条")

        print("[SUCCESS] 缓存功能验证完成")

    except Exception as e:
        print(f"[ERROR] 缓存验证失败: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(test_cache_complete())
