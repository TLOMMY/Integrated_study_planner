import os
import json
import re
from langchain_openai import ChatOpenAI
from langchain.schema import HumanMessage, SystemMessage
from app.config import settings

# DeepSeek 兼容 OpenAI API
llm = ChatOpenAI(
    model="deepseek-chat",
    openai_api_key=os.getenv("DEEPSEEK_API_KEY"),
    openai_api_base="https://api.deepseek.com/v1",
    temperature=0.7,
)


class AIService:
    @staticmethod
    def generate_plan(prompt: str, energy_level: int):
        system_prompt = f"""你是一个智能学习规划助手。用户当前精力等级为{energy_level}/10。
请根据用户需求生成详细的学习计划，**必须**返回以下JSON格式（不要包含任何其他解释文本）：
{{
    "plan_summary": "总体计划描述（一句话）",
    "tasks": [
        {{"title": "具体任务1", "duration_minutes": 30, "priority": "high"}},
        {{"title": "具体任务2", "duration_minutes": 45, "priority": "medium"}}
    ]
}}
注意：duration_minutes 必须是整数，priority 为 "high"/"medium"/"low"。
"""
        try:
            response = llm.invoke([
                SystemMessage(content=system_prompt),
                HumanMessage(content=prompt)
            ])
            content = response.content
            # 尝试提取 JSON（大模型可能输出 ```json ... ``` 或直接输出）
            json_match = re.search(r'\{.*\}', content, re.DOTALL)
            if json_match:
                json_str = json_match.group()
                plan_data = json.loads(json_str)
            else:
                # 降级：尝试直接解析
                plan_data = json.loads(content)

            # 确保有 tasks 字段
            if "tasks" not in plan_data:
                plan_data["tasks"] = []
            return plan_data
        except Exception as e:
            # 解析失败时返回一个默认结构
            return {
                "plan_summary": "生成计划失败，请稍后重试",
                "tasks": [],
                "error": str(e)
            }

    @staticmethod
    def reschedule(user_id: int, disruption_desc: str):
        prompt = f"原计划被打乱，原因：{disruption_desc}。请重新生成今日剩余时间的学习计划。"
        # 可以传入用户原有计划作为上下文（这里简化）
        return AIService.generate_plan(prompt, energy_level=5)