
"""研究代理实现模块

本模块实现了一个研究代理，能够执行迭代式网络搜索并综合信息，
以回答复杂的研究问题。
"""

from pydantic import BaseModel, Field
from typing_extensions import Literal

from langgraph.graph import StateGraph, START, END
from langchain_core.messages import SystemMessage, HumanMessage, ToolMessage, filter_messages
from fairy.init_model import init_model
from fairy.state_research import ResearcherState, ResearcherOutputState
from fairy.utils import tavily_search, get_today_str, think_tool
from fairy.prompts import research_agent_prompt, compress_research_system_prompt, compress_research_human_message

# ===== 配置 =====

# 设置工具和模型绑定
tools = [tavily_search, think_tool]
tools_by_name = {tool.name: tool for tool in tools}

# 初始化模型
model = init_model(model="gpt-4.1")
model_with_tools = model.bind_tools(tools)
summarization_model = init_model(model="gpt-4.1-mini")
compress_model = init_model(model="gpt-4.1")

# ===== 代理节点 =====

def llm_call(state: ResearcherState):
    """分析当前状态并决定下一步行动。

    模型分析当前对话状态，并决定是否：
    1. 调用搜索工具收集更多信息
    2. 基于已收集的信息提供最终答案

    返回包含模型响应的更新状态。
    """
    return {
        "researcher_messages": [
            model_with_tools.invoke(
                [SystemMessage(content=research_agent_prompt.format(date=get_today_str()))]
                + state["researcher_messages"]
            )
        ]
    }

def tool_node(state: ResearcherState):
    """执行上一次 LLM 响应中的所有工具调用。

    执行前一次 LLM 响应中的全部工具调用，
    返回包含工具执行结果的更新状态。
    """
    tool_calls = state["researcher_messages"][-1].tool_calls

    # 执行所有工具调用
    observations = []
    for tool_call in tool_calls:
        tool = tools_by_name[tool_call["name"]]
        observations.append(tool.invoke(tool_call["args"]))

    # 创建工具消息输出
    tool_outputs = [
        ToolMessage(
            content=observation,
            name=tool_call["name"],
            tool_call_id=tool_call["id"]
        ) for observation, tool_call in zip(observations, tool_calls)
    ]

    return {"researcher_messages": tool_outputs}

def compress_research(state: ResearcherState) -> dict:
    """将研究发现压缩为简洁的摘要。

    汇总所有研究消息和工具输出，生成适合
    上级代理决策使用的精炼摘要。
    """

    system_message = compress_research_system_prompt.format(date=get_today_str())
    research_topic = state.get("research_topic", "")
    messages = (
        [SystemMessage(content=system_message)]
        + state.get("researcher_messages", [])
        + [HumanMessage(content=compress_research_human_message.format(research_topic=research_topic))]
    )
    response = compress_model.invoke(messages)

    # 从工具消息和 AI 消息中提取原始笔记
    raw_notes = [
        str(m.content) for m in filter_messages(
            state["researcher_messages"], 
            include_types=["tool", "ai"]
        )
    ]

    return {
        "compressed_research": str(response.content),
        "raw_notes": ["\n".join(raw_notes)]
    }

# ===== 路由逻辑 =====

def should_continue(state: ResearcherState) -> Literal["tool_node", "compress_research"]:
    """判断是否继续研究或提供最终答案。

    根据 LLM 是否发起工具调用，决定代理应继续研究循环
    还是提供最终答案。

    返回值：
        "tool_node": 继续执行工具调用
        "compress_research": 停止搜索并压缩研究结果
    """
    messages = state["researcher_messages"]
    last_message = messages[-1]

    # 如果 LLM 发起工具调用，则继续执行工具
    if last_message.tool_calls:
        return "tool_node"
    # 否则，返回最终答案
    return "compress_research"

# ===== 图构建 =====

# 构建代理工作流
agent_builder = StateGraph(ResearcherState, output_schema=ResearcherOutputState)

# 向图中添加节点
agent_builder.add_node("llm_call", llm_call)
agent_builder.add_node("tool_node", tool_node)
agent_builder.add_node("compress_research", compress_research)

# 添加边以连接节点
agent_builder.add_edge(START, "llm_call")
agent_builder.add_conditional_edges(
    "llm_call",
    should_continue,
    {
        "tool_node": "tool_node", # 继续研究循环
        "compress_research": "compress_research", # 提供最终答案
    },
)
agent_builder.add_edge("tool_node", "llm_call") # 循环回去继续研究
agent_builder.add_edge("compress_research", END)

# 编译代理
researcher_agent = agent_builder.compile()
