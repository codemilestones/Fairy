"""
基于 MCP (Model Context Protocol) 的研究代理实现

本模块实现了一个使用本地文件系统的研究代理，
通过 MCP 协议访问本地文件进行研究。
"""

from typing_extensions import Literal
from datetime import datetime

from langchain_core.messages import SystemMessage, HumanMessage, ToolMessage, filter_messages
from langgraph.graph import StateGraph, START, END

from fairy.init_model import init_model
from fairy.state_research import ResearcherState, ResearcherOutputState
from fairy.prompts import research_agent_prompt_with_mcp
from fairy.utils import get_today_str, think_tool

# ===== 配置 =====

# 初始化模型
model = init_model(model="gpt-4.1")

# ===== MCP 工具（模拟） =====

# 注意：这里需要根据实际的 MCP server 配置来定义工具
# 以下是示例工具定义

def list_allowed_directories() -> str:
    """列出允许访问的目录"""
    return "允许访问的目录: /home/user/documents"

def list_directory(path: str) -> str:
    """列出目录内容"""
    import os
    try:
        contents = os.listdir(path)
        return "\n".join(contents)
    except Exception as e:
        return f"错误: {str(e)}"

def read_file(path: str) -> str:
    """读取文件内容"""
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return f.read()
    except Exception as e:
        return f"错误: {str(e)}"

def read_multiple_files(paths: list) -> str:
    """读取多个文件"""
    results = []
    for path in paths:
        content = read_file(path)
        results.append(f"=== {path} ===\n{content}")
    return "\n\n".join(results)

def search_files(query: str, directory: str = ".") -> str:
    """搜索文件内容"""
    import os
    import glob

    results = []
    for root, dirs, files in os.walk(directory):
        for file in files:
            if file.endswith('.txt') or file.endswith('.md'):
                file_path = os.path.join(root, file)
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                        if query.lower() in content.lower():
                            results.append(file_path)
                except:
                    pass

    return "\n".join(results) if results else "未找到匹配的文件"


# ===== 工具定义 =====

from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field

class ListDirectoryInput(BaseModel):
    path: str = Field(description="目录路径")

class ReadFileInput(BaseModel):
    path: str = Field(description="文件路径")

class ReadMultipleFilesInput(BaseModel):
    paths: list = Field(description="文件路径列表")

class SearchFilesInput(BaseModel):
    query: str = Field(description="搜索关键词")
    directory: str = Field(default=".", description="搜索目录")

tools = [
    StructuredTool.from_function(
        func=list_allowed_directories,
        name="list_allowed_directories",
        description="列出允许访问的目录"
    ),
    StructuredTool.from_function(
        func=list_directory,
        name="list_directory",
        description="列出目录中的文件",
        args_schema=ListDirectoryInput
    ),
    StructuredTool.from_function(
        func=read_file,
        name="read_file",
        description="读取单个文件的内容",
        args_schema=ReadFileInput
    ),
    StructuredTool.from_function(
        func=read_multiple_files,
        name="read_multiple_files",
        description="一次读取多个文件（更高效）",
        args_schema=ReadMultipleFilesInput
    ),
    StructuredTool.from_function(
        func=search_files,
        name="search_files",
        description="搜索包含特定内容的文件",
        args_schema=SearchFilesInput
    ),
    think_tool
]

tools_by_name = {tool.name: tool for tool in tools}
model_with_tools = model.bind_tools(tools)


# ===== 代理节点 =====

def llm_call(state: ResearcherState):
    """分析当前状态并决定下一步行动"""
    return {
        "researcher_messages": [
            model_with_tools.invoke(
                [SystemMessage(content=research_agent_prompt_with_mcp.format(date=get_today_str()))]
                + state["researcher_messages"]
            )
        ]
    }


def tool_node(state: ResearcherState):
    """执行工具调用"""
    tool_calls = state["researcher_messages"][-1].tool_calls

    observations = []
    for tool_call in tool_calls:
        tool = tools_by_name[tool_call["name"]]
        observations.append(tool.invoke(tool_call["args"]))

    tool_outputs = [
        ToolMessage(
            content=observation,
            name=tool_call["name"],
            tool_call_id=tool_call["id"]
        ) for observation, tool_call in zip(observations, tool_calls)
    ]

    return {"researcher_messages": tool_outputs}


def compress_research(state: ResearcherState) -> dict:
    """压缩研究发现"""
    # 从工具消息中提取内容
    raw_notes = [
        str(m.content) for m in filter_messages(
            state["researcher_messages"],
            include_types=["tool", "ai"]
        )
    ]

    # 简单压缩（实际可以使用更复杂的逻辑）
    compressed = "\n\n".join(raw_notes)

    return {
        "compressed_research": compressed,
        "raw_notes": ["\n".join(raw_notes)]
    }


# ===== 路由逻辑 =====

def should_continue(state: ResearcherState) -> Literal["tool_node", "compress_research"]:
    """判断是否继续研究"""
    messages = state["researcher_messages"]
    last_message = messages[-1]

    if last_message.tool_calls:
        return "tool_node"
    return "compress_research"


# ===== 图构建 =====

agent_builder = StateGraph(ResearcherState, output_schema=ResearcherOutputState)

agent_builder.add_node("llm_call", llm_call)
agent_builder.add_node("tool_node", tool_node)
agent_builder.add_node("compress_research", compress_research)

agent_builder.add_edge(START, "llm_call")
agent_builder.add_conditional_edges(
    "llm_call",
    should_continue,
    {
        "tool_node": "tool_node",
        "compress_research": "compress_research",
    },
)
agent_builder.add_edge("tool_node", "llm_call")
agent_builder.add_edge("compress_research", END)

agent_mcp = agent_builder.compile()
