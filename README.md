# Fairy

Fairy is a lightweight web agent that supports deep research capabilities, built with [LangGraph](https://github.com/langchain-ai/langgraph).

## ✨ Features

- **🔬 Deep Research**: Iterative web search with intelligent stopping criteria
- **🎯 Scope Definition**: User clarification and research brief generation
- **🤖 Multi-Agent System**: Supervisor + Research Agents for parallel task execution
- **📁 MCP Support**: Local file system access via Model Context Protocol
- **🔗 LangGraph Studio**: Visual debugging and monitoring
- **🌐 Web Demo**: Full-featured Next.js + FastAPI application

## 🏗️ Architecture

```
User Query
     ↓
Scope Research (Clarification + Brief)
     ↓
Supervisor Agent (Task Analysis)
     ↓
  ┌────┴────┬────────┬────────┐
  ↓         ↓        ↓        ↓
Agent 1   Agent 2  Agent 3  Agent N
(Parallel Research)
  ↓         ↓        ↓        ↓
  └────┬────┴────────┴────────┘
       ↓
Aggregate Results
       ↓
   Final Report
```

## 📦 Installation

```bash
# Install dependencies
uv sync
```

## 🚀 Quick Start

### 1) Configure Environment Variables

Copy the environment template:
```bash
cp env.template .env
```

Edit `.env` and add your API keys:
```bash
MODEL_BASE_URL=https://api.openai.com/v1
MODEL_API_KEY=your_api_key_here
TAVILY_API_KEY=your_tavily_key_here
```

### 2) Run with LangGraph Studio

```bash
langgraph dev
```

Open [LangGraph Studio](http://localhost:8123) to visualize and debug the agents.

### 3) Web Demo (Next.js + FastAPI)

**Backend Setup:**
```bash
cd apps/backend
cp env.template .env
# Edit .env with your API keys
uv sync
uv run uvicorn app.main:app --reload --port 8000
```

**Frontend Setup:**
```bash
cd apps/frontend
cp env.template .env.local
npm install
npm run dev
```

Open `http://localhost:3000` to see the demo.

## 📚 Available Graphs

- `scope_research`: User clarification and research brief generation
- `research_agent`: Single agent with web search
- `research_agent_mcp`: Agent with local file system access
- `research_agent_supervisor`: Multi-agent coordinator
- `research_agent_full`: Complete workflow with all features

## 🔧 Development

```bash
# Run tests
uv run pytest

# Format code
uv run black .
uv run ruff check .

# Type check
uv run mypy src/
```

## 📖 Documentation

- **[LangGraph Tutorial](https://langchain-ai.github.io/langgraph/)**: Learn LangGraph concepts
- **[Deep Research Blog](https://codemilestones.github.io/codemls/)**: Building multi-agent research systems

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- [LangChain](https://github.com/langchain-ai/langchain) for the excellent framework
- [LangGraph](https://github.com/langchain-ai/langgraph) for the agent orchestration
- [Tavily](https://tavily.com/) for the search API
