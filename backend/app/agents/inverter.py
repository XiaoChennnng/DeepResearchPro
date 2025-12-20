"""
Inverter Agent - 数据逆变器Agent
负责读取111.csv并进行数据转换处理
"""

from typing import Dict, Any, List, Optional
import json
import csv
from pathlib import Path

from app.agents.base import BaseAgent
from app.db.models import AgentType
from app.core.logging import logger
from app.orchestrator.context_orchestrator import AgentExecutionResult


class InverterAgent(BaseAgent):
    """
    逆变器Agent
    读取111.csv并进行数据转换处理
    """

    ROLE_DESCRIPTION = """你是一个专业的数据转换专家。你的职责是：
1. 读取并解析CSV数据文件
2. 识别数据结构和模式
3. 执行数据逆变转换操作
4. 验证转换结果的准确性
5. 生成转换报告

你必须确保数据转换的准确性和完整性，每个转换步骤都要有记录。"""

    def __init__(
        self,
        llm=None,
        model: Optional[str] = None,
        llm_factory=None,
        status_callback=None,
    ):
        super().__init__(
            agent_type=AgentType.ANALYZER,  # 使用现有类型，可根据需要扩展
            name="数据逆变器Agent",
            llm_client=llm,
            model=model,
            llm_factory=llm_factory,
            status_callback=status_callback,
        )

    async def execute(self, context: Dict[str, Any]) -> AgentExecutionResult:
        """
        执行数据逆变转换
        """
        self._start_timer()
        logger.info("[InverterAgent] 开始数据逆变转换")

        try:
            # 读取111.csv文件
            csv_data = self._read_csv_file()

            if not csv_data:
                logger.warning("[InverterAgent] 未找到111.csv文件或文件为空")
                self._stop_timer()
                return self._create_result(
                    success=False,
                    output={"conversion": {}},
                    errors=["111.csv文件不存在或为空"],
                )

            logger.info(f"[InverterAgent] 读取到 {len(csv_data)} 行数据")

            await self.update_subtask(
                f"正在处理 {len(csv_data)} 行CSV数据，进行逆变转换"
            )

            # 执行数据转换
            conversion_result = await self._process_inversion(csv_data, context)

            self._stop_timer()

            # 构建输出
            output = {
                "conversion": conversion_result,
                "original_rows": len(csv_data),
                "converted_rows": len(conversion_result.get("converted_data", [])),
                "processing_time_ms": self.get_metrics()["duration_ms"],
                "report": conversion_result.get("report", ""),
            }

            logger.info(f"[InverterAgent] 转换完成，处理 {len(csv_data)} 行数据")

            return self._create_result(success=True, output=output)

        except Exception as e:
            self._stop_timer()
            error_msg = f"数据转换失败: {str(e)}"
            logger.error(f"[InverterAgent] {error_msg}")
            return self._create_result(
                success=False, output={"conversion": {}}, errors=[error_msg]
            )

    def _read_csv_file(self) -> List[Dict[str, Any]]:
        """
        读取111.csv文件
        """
        file_path = Path("111.csv")
        if not file_path.exists():
            logger.warning(f"[InverterAgent] 文件不存在: {file_path.absolute()}")
            return []

        try:
            with open(file_path, "r", encoding="utf-8") as file:
                # 尝试检测分隔符
                sample = file.read(1024)
                file.seek(0)
                sniffer = csv.Sniffer()
                delimiter = sniffer.sniff(sample).delimiter

                reader = csv.DictReader(file, delimiter=delimiter)
                data = list(reader)

            logger.info(
                f"[InverterAgent] 成功读取CSV文件，字段: {list(data[0].keys()) if data else '无数据'}"
            )
            return data

        except Exception as e:
            logger.error(f"[InverterAgent] 读取CSV文件失败: {e}")
            return []

    async def _process_inversion(
        self, csv_data: List[Dict[str, Any]], context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        执行数据逆变转换
        这里实现具体的转换逻辑，根据需求调整
        """
        if not self.llm_client:
            return self._simple_inversion(csv_data)

        # 获取查询参数或其他上下文
        query = context.get("core_context", {}).get("query", "数据转换")

        # 构建数据描述
        data_sample = csv_data[:5]  # 取前5行作为样本
        fields = list(csv_data[0].keys()) if csv_data else []

        prompt = f"""请分析以下CSV数据样本，并执行数据逆变转换操作。

研究任务：{query}

数据字段：{", ".join(fields)}

数据样本（前5行）：
{json.dumps(data_sample, ensure_ascii=False, indent=2)}

请执行以下转换操作：
1. 分析数据结构和模式
2. 识别需要逆变转换的字段
3. 执行数据类型转换（如果需要）
4. 生成逆变后的数据格式
5. 验证转换结果

请返回JSON格式的转换结果：
{{
    "analysis": {{
        "field_count": 字段数量,
        "row_count": 行数,
        "data_types": {{"字段名": "推断类型"}},
        "patterns": ["识别的模式"]
    }},
    "converted_data": [
        {{
            "original": {{原始行数据}},
            "converted": {{转换后数据}},
            "transformations": ["执行的转换操作"]
        }},
        ...
    ],
    "statistics": {{
        "successful_conversions": 成功转换行数,
        "failed_conversions": 失败转换行数,
        "transformation_types": ["转换类型统计"]
    }},
    "report": "转换过程和结果的详细报告"
}}

转换要求：
1. 保留所有原始数据
2. 明确标注每个转换操作
3. 报告任何转换失败的情况
4. 提供数据质量评估"""

        try:
            response = await self.call_llm(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=4096,
                json_mode=True,
            )

            result = json.loads(response)
            return result

        except Exception as e:
            logger.error(f"[InverterAgent] LLM转换失败: {e}")
            return self._simple_inversion(csv_data)

    def _simple_inversion(self, csv_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        简单转换（无LLM时使用）
        执行基础的数据类型转换和格式化
        """
        if not csv_data:
            return {"converted_data": [], "statistics": {}, "report": "无数据可转换"}

        converted_data = []
        successful = 0
        failed = 0

        for i, row in enumerate(csv_data):
            try:
                # 基础转换：尝试转换数字类型
                converted_row = {}
                transformations = []

                for key, value in row.items():
                    if value is None or value == "":
                        converted_row[key] = None
                        continue

                    # 尝试转换为数字
                    try:
                        if "." in str(value):
                            converted_row[key] = float(value)
                            transformations.append(f"{key}: 字符串 -> 浮点数")
                        else:
                            converted_row[key] = int(value)
                            transformations.append(f"{key}: 字符串 -> 整数")
                    except ValueError:
                        # 保持字符串类型，但清理空白字符
                        converted_row[key] = str(value).strip()
                        if str(value) != converted_row[key]:
                            transformations.append(f"{key}: 清理空白字符")

                converted_data.append(
                    {
                        "original": row,
                        "converted": converted_row,
                        "transformations": transformations,
                    }
                )
                successful += 1

            except Exception as e:
                logger.warning(f"[InverterAgent] 第{i + 1}行转换失败: {e}")
                converted_data.append(
                    {
                        "original": row,
                        "converted": row,
                        "transformations": [],
                        "error": str(e),
                    }
                )
                failed += 1

        # 分析数据类型
        fields = list(csv_data[0].keys()) if csv_data else []
        data_types = {}
        for field in fields:
            sample_values = [
                row.get(field) for row in csv_data[:10] if row.get(field) is not None
            ]
            if sample_values:
                types = [type(v).__name__ for v in sample_values]
                most_common = max(set(types), key=types.count)
                data_types[field] = most_common

        return {
            "analysis": {
                "field_count": len(fields),
                "row_count": len(csv_data),
                "data_types": data_types,
                "patterns": ["基础类型转换"],
            },
            "converted_data": converted_data,
            "statistics": {
                "successful_conversions": successful,
                "failed_conversions": failed,
                "transformation_types": ["类型转换", "空白清理"],
            },
            "report": f"简单转换完成：成功{successful}行，失败{failed}行。执行了基础的数据类型转换和格式清理。",
        }
