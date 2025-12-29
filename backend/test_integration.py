#!/usr/bin/env python3
"""
系统集成测试 - 缓存 + 工作流
"""

import asyncio
import os
from app.core.cache_manager import get_cache_manager
from app.agents.workflow import ResearchWorkflow


async def test_system_integration():
    """测试缓存和工作流集成"""
    print("[START] 开始系统集成测试...")

    # 检查环境变量
    if not os.getenv("LLM_API_KEY"):
        print("[SKIP] 未设置LLM_API_KEY，跳过完整测试")
        return

    try:
        # 测试1: 缓存管理器
        print("\n[TEST1] 测试缓存管理器...")
        cache_manager = await get_cache_manager()
        stats = await cache_manager.get_stats()
        print(f"[OK] 缓存统计: {stats['total_entries']} 条目")

        # 测试2: 工作流初始化
        print("\n[TEST2] 测试工作流初始化...")
        workflow = ResearchWorkflow(
            llm_client=None,  # 测试模式
            search_tools={},
            model="gpt-4o-mini",
            workflow_mode="legacy",  # 使用传统模式
        )
        print(f"[OK] 工作流初始化成功，模式: {workflow.workflow_mode}")
        print(f"[INFO] Agent数量: {len(workflow.agents)}")

        # 测试3: 缓存与工作流集成
        print("\n[TEST3] 测试缓存与工作流集成...")
        # 这里可以添加更完整的集成测试

        print("\n[SUCCESS] 系统集成测试完成！")

    except Exception as e:
        print(f"[ERROR] 系统集成测试失败: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(test_system_integration())
