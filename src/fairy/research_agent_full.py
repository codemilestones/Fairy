"""
完整版研究代理 - 整合所有功能

本模块实现了一个完整的研究代理，包含：
1. 网络搜索研究
2. MCP 文件访问
3. Supervisor 协调
4. 完整的研究工作流
"""

from typing import Literal, List
from datetime import datetime

from langchain_core.messages import SystemMessage, HumanMessage, AIMessage, ToolMessage, filter_messages
from langgraph.graph import StateGraph, START, END
from pydantic import BaseModel, Field

from fairy.init_model import init_model
from fairy.prompts import (
    research_agent_prompt,
    lead_researcher_prompt,
    compress_research_system_prompt,
    compress_research_human_message,
    final_report_generation_prompt
)
from fairy.utils import tavily_search, get_today_str, think_tool
from fairy.research_agent_scope import scope_research

# ===== 配置 =====

model = init_model(model="gpt-4.1")

# ===== 完整版状态 =====

class FullResearchState(dict):
    """完整研究系统的状态"""
    # 输入
    messages: List
    research_question: str

    # 范围界定阶段
    needs_clarification: bool
    clarification_question: str
    research_brief: str

    # Supervisor 阶段
    should_delegate: bool
    subtasks: List[dict]
    agent_results: List[dict]

    # 最终输出
    final_report: str


# ===== 节点实现 =====

def scope_node(state: FullResearchState):
    """范围界定节点"""
    # 调用 scope_research 子图
    result = scope_research.invoke({
        "messages": state["messages"]
    })

    updates = {}
    if "research_brief" in result:
        updates["research_brief"] = result["research_brief"]
    if "messages" in result:
        updates["messages"] = result["messages"]

    return updates


def supervisor_node(state: FullResearchState):
    """Supervisor 节点 - 分析并分配任务"""
    from fairy.multi_agent_supervisor import analyze_task

    analysis = analyze_task(state.get("research_brief", state["research_question"]))

    return {
        "should_delegate": analysis.should_delegate,
        "subtasks": [task.dict() for task in analysis.subtasks],
        "messages": [AIMessage(content=f"任务分析: {analysis.reasoning}")]
    }


def research_node(state: FullResearchState):
    """研究执行节点"""
    from fairy.research_agent import researcher_agent

    agent_results = []

    for subtask in state["subtasks"]:
        # 调用 research agent
        agent_state = {
            "researcher_messages": [HumanMessage(content=subtask["task"])],
            "tool_call_iterations": 0,
            "research_topic": subtask["task"],
            "compressed_research": "",
            "raw_notes": []
        }

        result = researcher_agent.invoke(agent_state)
        agent_results.append({
            "task": subtask["task"],
            "compressed_research": result["compressed_research"],
            "raw_notes": result.get("raw_notes", [])
        })

    return {"agent_results": agent_results}


def aggregate_node(state: FullResearchState):
    """聚合节点 - 生成最终报告"""
    from fairy.multi_agent_supervisor import aggregate_results

    research_question = state.get("research_brief", state["research_question"])

    final_report = aggregate_results(research_question, state["agent_results"])

    return {
        "final_report": final_report,
        "messages": [AIMessage(content="✅ 研究完成！")]
    }


# ===== 路由逻辑 =====

def should_delegate(state: FullResearchState) -> Literal["supervisor", "single_research"]:
    """判断是否需要多 Agent"""
    # 如果已经有研究简报，检查是否需要拆分
    if "research_brief" in state and state["research_brief"]:
        return "supervisor" if state.get("should_delegate", False) else "single_research"

    # 否则先进行范围界定
    return "supervisor"


# ===== 构建完整图 =====

def build_full_agent():
    """构建完整的研究 Agent"""
    builder = StateGraph(FullResearchState)

    # 添加节点
    builder.add_node("scope", scope_node)
    builder.add_node("supervisor", supervisor_node)
    builder.add_node("research", research_node)
    builder.add_node("aggregate", aggregate_node)

    # 添加边
    builder.add_edge(START, "scope")
    builder.add_conditional_edges(
        "scope",
        should_delegate,
        {
            "supervisor": "supervisor",
            "single_research": "research"  # 单 Agent 研究路径（简化）
        }
    )
    builder.add_edge("supervisor", "research")
    builder.add_edge("research", "aggregate")
    builder.add_edge("aggregate", END)

    return builder.compile()


# 编译
agent = build_full_agent()
