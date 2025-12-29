#!/usr/bin/env python3
"""
缓存功能完整测试脚本
"""

import asyncio
import json
import time
from app.core.cache_manager import get_cache_manager


async def test_cache_functionality():
    """测试缓存的完整功能"""
    print("[START] 开始缓存功能测试...")

    # 初始化缓存管理器
    manager = await get_cache_manager()
    print("[OK] 缓存管理器初始化成功")

    # 测试1: 基本设置和获取
    print("\n[TEST1] 测试1: 基本缓存操作")
    test_key = "test_llm_response_001"
    test_data = {
        "response": "这是一个测试的LLM响应内容",
        "model": "gpt-4",
        "tokens": 150,
        "timestamp": time.time(),
    }

    # 设置缓存
    success = await manager.set(
        test_key,
        test_data,
        ttl_hours=24,
        cache_type="llm_response",
        metadata={"agent": "writer", "part": "abstract"},
    )
    print(f"设置缓存: {'成功' if success else '失败'}")

    # 获取缓存
    cached_data = await manager.get(test_key)
    print(f"获取缓存: {'成功' if cached_data else '失败'}")
    if cached_data:
        print(f"数据匹配: {cached_data == test_data}")

    # 测试2: 缓存统计
    print("\n[TEST2] 测试2: 缓存统计")
    stats = await manager.get_stats()
    print(f"总条目数: {stats['total_entries']}")
    print(f"总大小: {stats['total_size_bytes']} 字节")
    print(f"命中率: {stats['performance']['hit_rate']:.2%}")

    # 测试3: 缓存过期
    print("\n[TEST3] 测试3: 缓存过期")
    short_key = "test_short_ttl"
    await manager.set(
        short_key, "短期缓存", ttl_hours=0.001, cache_type="test"
    )  # 3.6秒过期

    print("等待4秒...")
    await asyncio.sleep(4)

    expired_data = await manager.get(short_key)
    print(f"过期数据获取: {'仍存在' if expired_data else '已过期'}")

    # 测试4: 清理过期缓存
    print("\n[TEST4] 测试4: 清理过期缓存")
    cleaned_count = await manager.clear_expired()
    print(f"清理过期缓存: {cleaned_count} 条")

    # 测试5: 类型清理
    print("\n[TEST5] 测试5: 类型清理")
    # 先添加一些不同类型的缓存
    await manager.set("llm_1", "llm data", cache_type="llm_response")
    await manager.set("search_1", "search data", cache_type="search_result")
    await manager.set("llm_2", "more llm data", cache_type="llm_response")

    llm_cleaned = await manager.clear_by_type("llm_response")
    print(f"清理LLM响应缓存: {llm_cleaned} 条")

    # 最终统计
    print("\n[FINAL] 最终统计")
    final_stats = await manager.get_stats()
    print(json.dumps(final_stats, indent=2, ensure_ascii=False))

    print("\n[SUCCESS] 缓存功能测试完成！")


if __name__ == "__main__":
    asyncio.run(test_cache_functionality())
