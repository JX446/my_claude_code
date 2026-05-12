# My Claude Code

一个学习 Claude Code 理念的 Python 项目，逐步构建了一个具有工具调用能力的 AI Agent 循环系统。

## 项目概述

本项目展示了如何利用大语言模型（LLM）构建一个能够执行多步骤任务的 Coding Agent。通过三个递进阶段的脚本，演示了 Agent 系统的核心组件和演化过程。

## 项目结构

```
my_claude_code/
├── s01_agent_loop.py    # 第一阶段：基础 Agent 循环
├── s02_tool_use.py      # 第二阶段：扩展工具集
├── s03_todo_write.py    # 第三阶段：会话计划管理
├── main.py              # 入口文件
├── pyproject.toml       # 项目配置
├── .env                 # 环境变量配置
└── README.md
```

## 三个阶段的演进

### Stage 1: 基础 Agent 循环 (`s01_agent_loop.py`)

最简单的 Agent 实现，展示了核心循环逻辑：

- **Bash 工具**：在当前工作区执行 shell 命令
- **循环机制**：Agent 不断调用 LLM，直到返回最终答案
- **安全检查**：阻止危险命令（如 `rmdir /s /q`）

**特点**：
- 最小化的代码实现
- 理解 Agent 的基本工作流程

### Stage 2: 扩展工具集 (`s02_tool_use.py`)

在第一阶段基础上扩展了文件操作能力：

- **Bash**：执行 shell 命令
- **read_file**：读取文件内容（支持行数限制）
- **write_file**：写入文件
- **edit_file**：精确替换文件中的文本

**新增功能**：
- `safe_path()`：路径安全检查，防止目录遍历攻击
- 消息规范化：支持 Pydantic Model 和 dict 格式的转换
- 消息合并：优化历史记录

### Stage 3: 会话计划管理 (`s03_todo_write.py`)

引入了任务规划和进度追踪机制：

- **Todo 工具**：管理会话计划，支持多步骤任务
- **计划提醒**：如果长时间未更新计划，自动提醒
- **状态管理**：跟踪每个任务的完成状态

**核心组件**：
- `TodoManager`：管理会话计划状态
- `PLAN_REMINDER_INTERVAL`：计划提醒间隔（默认 3 轮）
- 最多支持 12 个计划项

## 环境配置

在 `.env` 文件中配置：

```env
# API 配置（使用 MiniMax API 作为示例）
OPENAI_BASE_URL=https://api.minimaxi.com/v1
OPENAI_API_KEY=your_api_key_here

ANTHROPIC_BASE_URL=https://api.minimaxi.com/anthropic
ANTHROPIC_API_KEY=your_api_key_here

# 模型配置
MODEL_ID=MiniMax-M2.7
```

## 运行方式

```bash
# 使用 uv 运行
uv run python s03_todo_write.py

# 或直接运行
python s03_todo_write.py
```

交互式提示符：
```
s03 >> 
```

输入指令后，Agent 会自动调用工具完成多步骤任务。输入 `q` 或 `exit` 或直接回车退出。

## 核心概念

### Agent Loop

```
User Input → LLM → [Tool Calls] → Results → LLM → ... → Final Answer
```

Agent 循环持续运行，直到 LLM 返回自然语言回复而非工具调用。

### 工具系统

每个工具都包含：
- **name**：工具名称
- **description**：功能描述
- **input_schema**：输入参数规范

### 会话计划

通过 `todo` 工具，Agent 可以：
- 规划多步骤任务
- 标记当前进行中的步骤
- 追踪完成进度

## 依赖

- `anthropic >= 0.94.0`
- `dotenv >= 0.9.9`
- `openai >= 2.31.0`
- Python >= 3.12

## 学习资源

本项目是对 Claude Code 工作流程的学习实现，重点关注：

1. **工具调用**：如何让 LLM 使用外部工具
2. **安全沙箱**：路径检查和危险命令过滤
3. **状态管理**：会话级别的状态追踪
4. **渐进增强**：从简单循环到完整 Agent 系统

## 许可证

MIT License
