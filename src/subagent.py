import re
from pathlib import Path

from logger import log_tool_call
from permission import PermissionManager
from skill import SKILL_REGISTRY
from tools import CHILD_TOOLS, TOOL_HANDLERS

WORKDIR = Path.cwd()

SUBAGENT_SYSTEM = f"""You are a coding subagent at {WORKDIR}.
Complete the given task, then summarize your findings.
Skills available:
{SKILL_REGISTRY.describe_available()}
"""


class AgentTemplate:
    """
    Parse agent definition from markdown frontmatter.
    Real Claude Code loads agent definitions from .claude/agents/*.md.
    Frontmatter fields: name, tools, disallowedTools, skills, hooks,
    model, effort, permissionMode, maxTurns, memory, isolation, color,
    background, initialPrompt, mcpServers.
    3 sources: built-in, custom (.claude/agents/), plugin-provided.
    """

    def __init__(self, path):
        self.path = Path(path)
        self.name = self.path.stem
        self.config = {}
        self.system_prompt = ""
        self._parse()

    def _parse(self):
        text = self.path.read_text()
        match = re.match(r"^---\s*\n(.*?)\n---\s*\n(.*)", text, re.DOTALL)
        if not match:
            self.system_prompt = text
            return
        for line in match.group(1).splitlines():
            if ":" in line:
                k, _, v = line.partition(":")
                self.config[k.strip()] = v.strip()
        self.system_prompt = match.group(2).strip()
        self.name = self.config.get("name", self.name)


def subagent_loop(client, model, prompt: str, perms: PermissionManager) -> str:
    """Run a subagent with fresh context. Returns the subagent's final text response."""
    sub_messages = [{"role": "user", "content": prompt}]
    response = None
    for _ in range(30):
        response = client.messages.create(
            model=model,
            system=SUBAGENT_SYSTEM,
            messages=sub_messages,
            tools=CHILD_TOOLS,
            max_tokens=8000,
        )
        sub_messages.append({"role": "assistant", "content": response.content})
        if response.stop_reason != "tool_use":
            break
        results = []
        for block in response.content:
            if block.type == "tool_use":
                # 权限检查：调用 PermissionManager.check() 的多层决策链
                decision = perms.check(block.name, dict(block.input or {}))
                if decision["behavior"] == "deny":
                    output = f"⛔ [Denied] {decision.get('reason', '')}"
                    log_tool_call(block.name, output[:100])
                    results.append(
                        {
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": output,
                        }
                    )
                    continue
                elif decision["behavior"] == "ask":
                    output = f"⏳ [Ask required] {decision.get('reason', '')}\n(Agent loop non-interactive. Add allow rule or switch mode.)"
                    log_tool_call(block.name, output[:100])
                    results.append(
                        {
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": output,
                        }
                    )
                    continue
                # behavior == "allow" → 继续执行
                handler = TOOL_HANDLERS.get(block.name)
                output = (
                    handler(**block.input) if handler else f"Unknown tool: {block.name}"
                )
                results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": str(output)[:500],
                    }
                )
        sub_messages.append({"role": "user", "content": results})  # type: ignore
    if response is None:
        return "(no response)"
    else:
        return (
            "".join(b.text for b in response.content if hasattr(b, "text"))
            or "(no summary)"
        )
