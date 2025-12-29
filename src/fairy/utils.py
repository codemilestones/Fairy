
"""研究工具与实用程序

本模块为研究代理提供搜索和内容处理的实用程序，
包括网络搜索功能和内容摘要工具。
"""

from pathlib import Path
from datetime import datetime
from typing_extensions import Annotated, List, Literal

from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import tool, InjectedToolArg
from tavily import TavilyClient

from fairy.state_research import Summary
from fairy.prompts import summarize_webpage_prompt

# ===== 工具函数 =====

def get_today_str() -> str:
    """获取当前日期的人类可读格式。"""
    return datetime.now().strftime("%a %b %-d, %Y")

def get_current_dir() -> Path:
    """获取模块所在的当前目录。

    此函数兼容 Jupyter notebook 和常规 Python 脚本。

    返回值：
        表示当前目录的 Path 对象
    """
    try:
        return Path(__file__).resolve().parent
    except NameError:  # __file__ 未定义
        return Path.cwd()

# ===== 配置 =====

from fairy.init_model import init_model

summarization_model = init_model(model="gpt-4.1-mini")
tavily_client = TavilyClient()

# ===== 搜索函数 =====

def tavily_search_multiple(
    search_queries: List[str], 
    max_results: int = 3, 
    topic: Literal["general", "news", "finance"] = "general", 
    include_raw_content: bool = True, 
) -> List[dict]:
    """使用 Tavily API 执行多个查询的搜索。

    参数：
        search_queries: 要执行的搜索查询列表
        max_results: 每个查询返回的最大结果数
        topic: 搜索结果的主题过滤器
        include_raw_content: 是否包含原始网页内容

    返回值：
        搜索结果字典列表
    """

    # 顺序执行搜索。注意：可使用 AsyncTavilyClient 来并行化此步骤。
    search_docs = []
    for query in search_queries:
        result = tavily_client.search(
            query,
            max_results=max_results,
            include_raw_content=include_raw_content,
            topic=topic
        )
        search_docs.append(result)

    return search_docs

def summarize_webpage_content(webpage_content: str) -> str:
    """使用配置的摘要模型对网页内容进行摘要。

    参数：
        webpage_content: 需要摘要的原始网页内容

    返回值：
        包含关键摘录的格式化摘要
    """
    try:
        # 设置用于摘要的结构化输出模型
        structured_model = summarization_model.with_structured_output(Summary)

        # 生成摘要
        summary = structured_model.invoke([
            HumanMessage(content=summarize_webpage_prompt.format(
                webpage_content=webpage_content, 
                date=get_today_str()
            ))
        ])

        # 以清晰的结构格式化摘要
        formatted_summary = (
            f"<summary>\n{summary.summary}\n</summary>\n\n"
            f"<key_excerpts>\n{summary.key_excerpts}\n</key_excerpts>"
        )

        return formatted_summary

    except Exception as e:
        print(f"网页摘要失败: {str(e)}")
        return webpage_content[:1000] + "..." if len(webpage_content) > 1000 else webpage_content

def deduplicate_search_results(search_results: List[dict]) -> dict:
    """按 URL 对搜索结果去重，避免处理重复内容。

    参数：
        search_results: 搜索结果字典列表

    返回值：
        URL 映射到唯一结果的字典
    """
    unique_results = {}

    for response in search_results:
        for result in response['results']:
            url = result['url']
            if url not in unique_results:
                unique_results[url] = result

    return unique_results

def process_search_results(unique_results: dict) -> dict:
    """处理搜索结果，在可能的情况下生成内容摘要。

    参数：
        unique_results: 唯一搜索结果的字典

    返回值：
        包含摘要的已处理结果字典
    """
    summarized_results = {}

    for url, result in unique_results.items():
        # 如果没有原始内容可用于摘要，则使用现有内容
        if not result.get("raw_content"):
            content = result['content']
        else:
            # 对原始内容进行摘要以便更好地处理
            content = summarize_webpage_content(result['raw_content'])

        summarized_results[url] = {
            'title': result['title'],
            'content': content
        }

    return summarized_results

def format_search_output(summarized_results: dict) -> str:
    """将搜索结果格式化为结构清晰的字符串输出。

    参数：
        summarized_results: 已处理的搜索结果字典

    返回值：
        具有清晰来源分隔的格式化搜索结果字符串
    """
    if not summarized_results:
        return "未找到有效的搜索结果。请尝试不同的搜索查询或使用其他搜索 API。"

    formatted_output = "搜索结果：\n\n"

    for i, (url, result) in enumerate(summarized_results.items(), 1):
        formatted_output += f"\n\n--- 来源 {i}: {result['title']} ---\n"
        formatted_output += f"URL: {url}\n\n"
        formatted_output += f"摘要：\n{result['content']}\n\n"
        formatted_output += "-" * 80 + "\n"

    return formatted_output

# ===== 研究工具 =====

@tool(parse_docstring=True)
def tavily_search(
    query: str,
    max_results: Annotated[int, InjectedToolArg] = 3,
    topic: Annotated[Literal["general", "news", "finance"], InjectedToolArg] = "general",
) -> str:
    """从 Tavily 搜索 API 获取结果并进行内容摘要。

    Args:
        query: 要执行的单个搜索查询。
        max_results: 返回的最大结果数。
        topic: 用于过滤结果的主题（"general"、"news"、"finance"）。

    Returns:
        包含摘要的格式化搜索结果字符串。
    """
    # 执行单个查询的搜索
    search_results = tavily_search_multiple(
        [query],  # 将单个查询转换为列表以供内部函数使用
        max_results=max_results,
        topic=topic,
        include_raw_content=True,
    )

    # 按 URL 去重以避免处理重复内容
    unique_results = deduplicate_search_results(search_results)

    # 处理结果并生成摘要
    summarized_results = process_search_results(unique_results)

    # 格式化输出以供使用
    return format_search_output(summarized_results)

@tool(parse_docstring=True)
def think_tool(reflection: str) -> str:
    """用于研究进展战略性反思和决策的工具。

    在每次搜索后使用此工具，系统地分析结果并规划下一步行动。
    这在研究工作流中创建一个刻意的暂停，以便做出高质量的决策。

    使用时机（示例）：
    - 收到搜索结果后：我找到了哪些关键信息？
    - 决定下一步之前：我是否有足够的信息来全面回答？
    - 评估研究缺口时：我还缺少哪些具体信息？
    - 结束研究之前：我现在能提供完整的答案吗？

    Args:
        reflection: 关于研究进展、发现、缺口和下一步行动的详细反思。

    Returns:
        确认反思已记录以供决策使用。
    """
    return f"反思已记录：{reflection}"
