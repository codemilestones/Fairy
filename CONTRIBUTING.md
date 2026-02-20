# Contributing to Fairy

感谢你对 Fairy 项目的关注！我们欢迎各种形式的贡献。

## 🤝 如何贡献

### 报告 Bug

1. 在 [Issues](https://github.com/codemilestones/Fairy/issues) 中搜索是否已有类似问题
2. 如果没有，创建新的 Issue，包含：
   - 清晰的标题
   - 详细的复现步骤
   - 期望行为 vs 实际行为
   - 环境信息（Python 版本、操作系统等）

### 提交代码

1. **Fork 仓库**
   ```bash
   # 点击 GitHub 页面右上角的 Fork 按钮
   ```

2. **克隆你的 Fork**
   ```bash
   git clone https://github.com/YOUR_USERNAME/Fairy.git
   cd Fairy
   ```

3. **创建功能分支**
   ```bash
   git checkout -b feature/your-feature-name
   ```

4. **安装依赖**
   ```bash
   uv sync
   ```

5. **进行修改**
   - 遵循现有代码风格
   - 添加必要的测试
   - 更新文档

6. **运行测试**
   ```bash
   uv run pytest
   uv run black .
   uv run ruff check .
   ```

7. **提交更改**
   ```bash
   git add .
   git commit -m "描述你的更改"
   ```

8. **推送到你的 Fork**
   ```bash
   git push origin feature/your-feature-name
   ```

9. **创建 Pull Request**
   - 访问原仓库的 Pull Requests 页面
   - 点击 "New Pull Request"
   - 提供清晰的描述说明你的更改

## 📝 代码规范

### Python 代码风格

- 使用 `black` 进行代码格式化
- 使用 `ruff` 进行 linting
- 遵循 PEP 8 规范
- 添加类型注解（使用 `mypy` 检查）
- 编写文档字符串

### Commit 消息规范

使用清晰的 commit 消息：

```
类型(范围): 简短描述

详细描述（可选）

- 勾选点列出具体更改
```

类型包括：
- `feat`: 新功能
- `fix`: Bug 修复
- `docs`: 文档更新
- `style`: 代码格式（不影响功能）
- `refactor`: 重构
- `test`: 添加测试
- `chore`: 构建/工具链更新

示例：
```
feat(supervisor): add parallel task execution

- Implement multi-agent task delegation
- Add result aggregation logic
- Update documentation
```

## 🎯 项目结构

```
Fairy/
├── src/fairy/           # 核心代码
│   ├── init_model.py
│   ├── prompts.py
│   ├── research_agent.py
│   ├── research_agent_scope.py
│   ├── research_agent_mcp.py
│   ├── multi_agent_supervisor.py
│   ├── research_agent_full.py
│   └── utils.py
├── apps/                # Web 应用
│   ├── backend/         # FastAPI 后端
│   └── frontend/        # Next.js 前端
├── tests/               # 测试文件
└── docs/                # 文档
```

## ✅ 开发流程

1. 在开始工作前，先创建 Issue 讨论你的想法
2. 等待维护者确认后开始开发
3. 确保所有测试通过
4. 更新相关文档
5. 提交 Pull Request

## 🐛 调试技巧

### 使用 LangGraph Studio

```bash
langgraph dev
```

访问 http://localhost:8123 查看和调试 Agent 流程。

### 日志调试

设置环境变量启用详细日志：

```bash
export LANGCHAIN_VERBOSE=true
export LANGCHAIN_DEBUG=true
```

## 💡 功能建议

我们欢迎功能建议！请：

1. 先搜索现有 Issues
2. 创建新 Issue，包含：
   - 功能描述
   - 使用场景
   - 可能的实现方案
3. 等待社区讨论

## 📧 联系方式

- GitHub Issues: [github.com/codemilestones/Fairy/issues](https://github.com/codemilestones/Fairy/issues)
- Discussions: [github.com/codemilestones/Fairy/discussions](https://github.com/codemilestones/Fairy/discussions)

## 📜 行为准则

请尊重所有贡献者，保持友好和专业的交流。

---

再次感谢你的贡献！🎉
