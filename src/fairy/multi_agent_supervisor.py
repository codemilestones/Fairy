"""
多 Agent 研究系统的 Supervisor 实现

本模块实现了一个监督者 Agent，负责：
1. 分析研究问题并决定是否拆分任务
2. 将任务分配给多个子 Agent 并行执行
3. 聚合所有 Agent 的研究结果
4. 生成最终的研究报告
"""

from typing import Literal, List
from datetime import datetime

from langchain_core.messages import SystemMessage, HumanMessage, AIMessage, get_buffer_string
from langgraph.graph import StateGraph, START, END
from pydantic import BaseModel, Field

from fairy.init_model import init_model
from fairy.prompts import lead_researcher_prompt
from fairy.research_agent import researcher_agent
from fairy.state_research import ResearcherState, ResearcherOutputState

# ===== 配置 =====

# 初始化模型
model = init_model(model="gpt-4.1")

# ===== Pydantic 模型 =====

class SubTask(BaseModel):
    """子任务定义"""
    agent_id: str = Field(description="Agent ID")
    task: str = Field(description="研究任务描述")

class TaskAnalysis(BaseModel):
    """任务分析结果"""
    should_delegate: bool = Field(description="是否需要拆分任务")
    subtasks: List[SubTask] = Field(description="子任务列表")
    reasoning: str = Field(description="拆分逻辑说明")


# ===== Supervisor Agent 实现 =====

def analyze_task(research_question: str, max_concurrent: int = 3) -> TaskAnalysis:
    """
    分析研究问题并决定如何分配任务

    Args:
        research_question: 研究问题
        max_concurrent: 最大并行 Agent 数量

    Returns:
        TaskAnalysis: 任务分析结果
    """
    from fairy.prompts import lead_researcher_prompt

    # 使用结构化输出
    structured_model = model.with_structured_output(TaskAnalysis)

    # 构建提示
    prompt = lead_researcher_prompt.format(
        date=datetime.now().strftime("%a %b %-d, %Y"),
        max_concurrent_research_units=max_concurrent,
        max_researcher_iterations=5
    )

    messages = [
        SystemMessage(content=prompt),
        HumanMessage(content=f"研究问题: {research_question}")
    ]

    # 调用模型
    response = structured_model.invoke(messages)
    return response


def aggregate_results(research_question: str, agent_results: List[dict]) -> str:
    """
    聚合所有 Agent 的研究结果

    Args:
        research_question: 原始研究问题
        agent_results: 各个 Agent 的研究结果

    Returns:
        str: 最终报告
    """
    from fairy.prompts import final_report_generation_prompt

    # 构建研究结果文本
    findings_text = "\n\n".join([
        f"### 研究任务 {i+1}: {result['task']}\n\n{result['compressed_research']}"
        for i, result in enumerate(agent_results)
    ])

    # 构建消息
    prompt = final_report_generation_prompt.format(
        research_brief=research_question,
        findings=findings_text,
        date=datetime.now().strftime("%a %b %-d, %Y")
    )

    messages = [
        HumanMessage(content=prompt)
    ]

    # 调用模型生成报告
    response = model.invoke(messages)
    return response.content


# ===== 简化的 Supervisor Graph =====

def create_supervisor_graph():
    """
    创建 Supervisor Graph

    这是一个简化版本，实际使用时可以根据需要扩展
    """
    from langgraph.graph import StateGraph, START, END

    # 定义状态
    class SupervisorState(dict):
        research_question: str
        subtasks: List[dict]
        agent_results: List[dict]
        final_report: str

    # 定义节点
    def delegate_node(state: SupervisorState):
        """任务分配节点"""
        analysis = analyze_task(state["research_question"])
        return {
            "subtasks": [task.dict() for task in analysis.subtasks],
            "messages": [AIMessage(content=f"任务拆分: {analysis.reasoning}")]
        }

    def research_node(state: SupervisorState):
        """研究执行节点（简化版，实际应该并行调用多个 Agent）"""
        agent_results = []

        for subtask in state["subtasks"]:
            # 调用 research agent
            agent_state: ResearcherState = {
                "researcher_messages": [HumanMessage(content=subtask["task"])],
                "tool_call_iterations": 0,
                "research_topic": subtask["task"],
                "compressed_research": "",
                "raw_notes": []
            }

            # 运行 research agent
            result = researcher_agent.invoke(agent_state)
            agent_results.append({
                "task": subtask["task"],
                "compressed_research": result["compressed_research"],
                "raw_notes": result.get("raw_notes", [])
            })

        return {"agent_results": agent_results}

    def aggregate_node(state: SupervisorState):
        """结果聚合节点"""
        final_report = aggregate_results(
            state["research_question"],
            state["agent_results"]
        )
        return {
            "final_report": final_report,
            "messages": [AIMessage(content="研究报告已完成")]
        }

    # 构建图
    builder = StateGraph(SupervisorState)
    builder.add_node("delegate", delegate_node)
    builder.add_node("research", research_node)
    builder.add_node("aggregate", aggregate_node)

    builder.add_edge(START, "delegate")
    builder.add_edge("delegate", "research")
    builder.add_edge("research", "aggregate")
    builder.add_edge("aggregate", END)

    return builder.compile()


# ===== 编译图 =====

supervisor_agent = create_supervisor_graph()
