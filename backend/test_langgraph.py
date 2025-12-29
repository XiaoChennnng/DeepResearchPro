#!/usr/bin/env python3
"""
LangGraph工作流测试脚本
"""

import asyncio
import os
from app.orchestrator.langgraph_workflow import LangGraphWorkflow


async def test_langgraph_workflow():
    """测试LangGraph工作流"""
    print("[START] 开始LangGraph工作流测试...")

    # 检查环境变量
    if not os.getenv("LLM_API_KEY"):
        print("[ERROR] 请设置LLM_API_KEY环境变量")
        return

    # 创建工作流实例（不传入实际的LLM客户端，用于测试初始化）
    try:
        workflow = LangGraphWorkflow(
            llm_client=None,  # 测试模式
            search_tools={},
            model="gpt-4o-mini",
        )
        print("[OK] LangGraphWorkflow类导入和初始化成功")

        # 检查基本属性是否存在
        if hasattr(workflow, "agents"):
            agent_count = len(workflow.agents)
            print(f"[INFO] Agent数量: {agent_count}")
        else:
            print("[INFO] Agent属性不可用")

        # 检查是否能访问agent_sequence
        if hasattr(workflow, "agent_sequence"):
            sequence_count = len(workflow.agent_sequence)
            print(f"[INFO] 工作流序列长度: {sequence_count}")
        else:
            print("[INFO] 工作流序列不可用")

    except Exception as e:
        print(f"[ERROR] LangGraphWorkflow初始化失败: {e}")
        import traceback

        traceback.print_exc()
        return

    print("[SUCCESS] LangGraph工作流测试完成！")


if __name__ == "__main__":
    asyncio.run(test_langgraph_workflow())
