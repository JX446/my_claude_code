"""
权限系统模块 (Permission System)
================================

本模块实现了 AI 编程助手的工具调用权限控制，是安全架构的核心组件。
设计理念：多层防护、逐级检查、默认询问。

整体架构流程：
  1. Bash 安全校验（硬性拦截危险命令）
  2. 拒绝规则检查（deny rules，优先级最高，不可绕过）
  3. 模式决策（plan 模式拒绝所有写入，auto 模式自动放行只读）
  4. 允许规则匹配（allow rules，命中则放行）
  5. 兜底策略 → 询问用户（ask user）

支持的三种权限模式：
  - default: 默认模式，按规则匹配，无匹配则询问用户
  - plan:    规划模式，只允许读取操作，禁止一切写入（用于方案设计阶段）
  - auto:    自动模式，自动放行只读工具，写入工具按规则匹配或询问

教学版本说明：
  代码中标注为 "Teaching version" 的部分刻意保持了分步清晰的结构，
  优先考虑可读性和教学价值，而非最优执行效率。
"""

import json
import re
from fnmatch import fnmatch
from pathlib import Path

# ============================================================================
# 一、权限模式定义
# ============================================================================

# 系统支持的三种权限模式。
# - "default": 默认模式，按规则匹配，无匹配则询问用户。
# - "plan":    规划模式，只允许只读操作，所有写入类工具被硬性拒绝。
# - "auto":    自动模式，对只读工具自动放行，减少交互打扰。
MODES = ("default", "plan", "auto")

# 只读工具集合 —— 这些工具不会修改文件系统或系统状态。
# read_file:   读取文件内容
# bash_readonly: 以只读方式执行的 bash 命令（如 ls、cat、grep 等查看操作）
READ_ONLY_TOOLS = {"read_file", "bash_readonly"}

# 写入工具集合 —— 这些工具会修改文件系统或系统状态。
# write_file: 创建或覆盖文件
# edit_file:  编辑已有文件
# bash:       执行任意 Shell 命令（可能包含写操作）
WRITE_TOOLS = {"write_file", "edit_file", "bash"}


# ============================================================================
# 二、Bash 命令安全校验器
# ============================================================================

class BashSecurityValidator:
    """Bash 命令安全校验器。

    在命令执行前进行静态模式匹配，识别潜在的危险操作。
    这是第一道防线，在所有权限规则之前执行，确保危险命令被优先拦截。

    每条校验规则包含两个字段：
      - 名称 (name): 人类可读的规则标识，用于在日志/提示中展示
      - 正则 (pattern): 用于匹配危险模式的正则表达式
    """

    # 预定义的危险命令校验规则列表。
    # 每条规则关注一类特定的安全风险，覆盖了常见的攻击向量。
    VALIDATORS = [
        # Shell 元字符：管道、重定向、后台执行、等。
        # 这些字符可能用于拼接命令、输出重定向或后台运行隐藏进程。
        ("shell_metachar", r"[&|><^%]"),

        # runas：Windows 下以管理员权限运行程序。
        # 任何试图提权的操作都必须拦截。
        ("runas", r"\brunas\b"),

        # 递归删除：Windows 的 del /s 和 rmdir /s，会递归删除整个目录树。
        # /s 表示递归子目录，/q 表示安静模式（不确认），组合使用极度危险。
        # 也可匹配 rmdir /s（删除非空目录）。
        ("recursive_delete", r"\b(del|erase)\b.*\b(/s|/q)\b|\brmdir\b.*\b/s\b"),

        # PowerShell 执行：调用 PowerShell 引擎。
        # PowerShell 是 Windows 下功能强大的脚本引擎，可用于内存注入、
        # 下载执行、绕过防护等高危操作。
        ("powershell", r"\bpowershell(\.exe)?\b"),

        # 编码命令：-EncodedCommand / -enc 参数。
        # Base64 编码后的命令内容无法直接审查，是典型的混淆/绕过手法。
        ("encoded_command", r"-enc(odedcommand)?\b"),

        # 下载并执行：常见的远程下载工具链。
        # Invoke-WebRequest / iwr: PowerShell 内置的 HTTP 客户端
        # curl / wget:          跨平台下载工具
        # Start-Process:        启动外部进程
        # 组合使用即构成"下载-执行"攻击链。
        ("download_exec", r"Invoke-WebRequest|iwr|curl|wget|Start-Process"),

        # 命令替换：$(command) 语法在某此 Shell 上下文中会被展开。
        # 攻击者可利用它嵌套执行任意命令。
        ("cmd_substitution", r"\$\("),

        # 环境变量操作：set / setx 修改环境变量，$env: 访问 PowerShell 环境变量。
        # 可能用于篡改 PATH、注入恶意 DLL 搜索路径等。
        ("env_manipulation", r"\bset[x]?\b|\$env:"),
    ]

    def validate(self, command: str) -> list:
        """对命令字符串执行全部安全校验。

        遍历所有校验规则，返回触发告警的规则列表。

        参数:
            command: 待校验的 Shell 命令字符串

        返回:
            failures: 由 (规则名称, 正则模式) 元组组成的列表。
                      空列表表示命令通过了全部校验，未触发任何告警。
        """
        failures = []
        for name, pattern in self.VALIDATORS:
            if re.search(pattern, command):
                failures.append((name, pattern))
        return failures

    def is_safe(self, command: str) -> bool:
        """判断命令是否完全安全（未触发任何告警规则）。

        参数:
            command: 待校验的 Shell 命令字符串

        返回:
            True 表示安全，False 表示存在可疑模式
        """
        return len(self.validate(command)) == 0

    def describe_failures(self, command: str) -> str:
        """生成人类可读的校验失败描述。

        当命令触发安全规则时，用此方法生成用户友好的提示信息，
        帮助用户理解为什么该命令被拦截或需要确认。

        参数:
            command: 待校验的 Shell 命令字符串

        返回:
            描述字符串，如 "Security flags: powershell (...), encoded_command (...)"
            或 "No issues detected"（无问题时）
        """
        failures = self.validate(command)
        if not failures:
            return "No issues detected"
        parts = [f"{name} (pattern: {pattern})" for name, pattern in failures]
        return "Security flags: " + ", ".join(parts)


# ============================================================================
# 三、工作区信任检查
# ============================================================================

def is_workspace_trusted(workspace: Path) -> bool:
    """检查当前工作区是否被用户标记为"可信"。

    信任机制通过一个标记文件实现：
    在工作区的 .claude/.claude_trusted 路径下是否存在一个标记文件。
    如果该文件存在，表示用户信任此工作区，可以适当放宽权限限制。

    为什么需要这个机制？
    - 用户下载的第三方项目可能是恶意的（供应链攻击）。
    - 用户自己的项目可以信任，减少不必要的权限询问。
    - 标记文件由用户手动创建，不会自动生成，确保是显式的信任决策。

    参数:
        workspace: 工作区根目录的 Path 对象

    返回:
        True:  工作区已被用户标记为可信
        False: 工作区未被信任，应以较高安全标准运行
    """
    trusted_maker = workspace / ".claude" / ".claude_trusted"
    return trusted_maker.exists()


# ============================================================================
# 四、全局单例与默认规则
# ============================================================================

# 全局唯一的 Bash 安全校验器实例。
# 所有 PermissionManager 实例共享同一个校验器，
# 因为校验规则是固定的，无需每个管理器单独持有。
bash_validator = BashSecurityValidator()

# 默认权限规则表。
# 规则按优先级排序（deny 优先于 allow），采用列表存储而非字典，
# 因为多条规则可能覆盖相同的工具/内容模式，列表保留了顺序语义。
#
# 每条规则是一个字典，包含以下字段：
#   - tool:     工具名称，如 "read_file"、"bash"、"powershell"；
#               支持通配符 "*" 表示匹配所有工具。
#   - content:  命令内容匹配模式（针对 bash/powershell 等执行工具），
#               支持 fnmatch 通配符（*、?、[...]）。
#   - path:     文件路径匹配模式（针对 read_file/write_file 等文件工具），
#               同样支持 fnmatch 通配符。
#   - behavior: "allow" 或 "deny"，决定匹配后的处理方式。
DEFAULT_RULES = [
    # ---- 拒绝规则（deny） ----
    # 这些规则的优先级最高，在 PermissionManager.check() 中
    # 于所有其他规则之前执行，不可被后续规则覆盖。

    # 危险删除操作：del /s /q
    # Windows 下递归静默删除，可一次性删除整个项目目录。
    {"tool": "cmd", "content": "del /s /q *", "behavior": "deny"},

    # 危险删除操作：rmdir /s /q
    # Windows 下递归静默删除非空目录，同样具有毁灭性。
    {"tool": "cmd", "content": "rmdir /s /q *", "behavior": "deny"},

    # 权限提升：runas
    # 任何试图以管理员身份运行的命令都应被禁止。
    {"tool": "cmd", "content": "runas *", "behavior": "deny"},

    # 权限提升：PowerShell 启动进程并提权
    # Start-Process -Verb RunAs 可以在 PowerShell 中以管理员身份启动任意进程。
    {
        "tool": "powershell",
        "content": "Start-Process * -Verb RunAs*",
        "behavior": "deny",
    },

    # 编码/混淆命令：-EncodedCommand
    # Base64 编码的命令无法直接审查，是恶意载荷的常见载体。
    {"tool": "powershell", "content": "*-EncodedCommand*", "behavior": "deny"},

    # ---- 允许规则（allow） ----
    # 全局范围内最基本的放行规则。

    # 允许读取所有文件。
    # read_file 工具本身是安全的，它只读取内容，不修改任何内容。
    {"tool": "read_file", "path": "*", "behavior": "allow"},
]


# ============================================================================
# 五、权限管理器
# ============================================================================

class PermissionManager:
    """权限管理器 —— 权限系统的核心调度器。

    职责：
    1. 持有当前会话的权限模式和规则集。
    2. 对每个工具调用请求执行多层检查，返回决策结果。
    3. 提供交互式询问界面（ask_user），让用户在需要时做出决策。
    4. 跟踪连续拒绝次数，提醒用户可切换模式以减少打扰。

    决策返回值格式：
        {"behavior": "allow"|"deny"|"ask", "reason": "..."}

    检查流程（四步决策链）：
        Step 0: Bash 安全校验 —— 识别危险模式，严重者直接拒绝
        Step 1: 拒绝规则匹配 —— deny 规则命中则立即拒绝，不可绕过
        Step 2: 模式决策   —— plan 模式拒绝写入，auto 模式放行只读
        Step 3: 允许规则匹配 —— allow 规则命中则放行，同时重置拒绝计数器
        Step 4: 兜底询问   —— 以上均未命中，返回 "ask" 由用户决定
    """

    def __init__(self, mode: str = "default", rules: list | None = None) -> None:
        """初始化权限管理器。

        参数:
            mode:  权限模式，必须是 MODES 中的一种。
                   默认 "default"（按规则匹配，无匹配则询问用户）。
            rules: 自定义规则集，若为 None 则使用 DEFAULT_RULES。
                   规则列表中的 deny 规则优先级高于 allow 规则。
                   允许调用方传入自定义规则以适应不同场景（测试、企业策略等）。

        异常:
            ValueError: 当 mode 不在 MODES 中时抛出，提供合法的选项列表。
        """
        if mode not in MODES:
            raise ValueError(f"Unknown mode: {mode}. Choose from {MODES}")
        self.mode = mode

        # 规则集 —— 拷贝传入的列表，避免外部修改影响内部状态。
        # 注意：这里使用 `list()` 而非 `.copy()`，兼顾 None 的默认处理。
        self.rules = rules or list(DEFAULT_RULES)

        # 连续拒绝计数器 —— 用于检测用户是否频繁拒绝同一类操作。
        # 当连续拒绝次数超过阈值时，提示用户可切换到 plan 模式。
        self.consecutive_denials = 0
        self.max_consecutive_denials = 3

    def check(self, tool_name: str, tool_input: dict) -> dict:
        """对工具调用请求执行完整的权限检查。

        这是权限系统的核心入口：每个工具调用在执行前都应经过此方法审核。

        参数:
            tool_name:  工具名称，如 "read_file"、"bash"、"write_file" 等
            tool_input: 工具调用参数字典，至少应包含以下字段之一：
                        - "command": Shell 命令字符串（bash/powershell 工具）
                        - "path":    文件路径字符串（read_file/write_file 工具）

        返回:
            dict: {"behavior": "allow"|"deny"|"ask", "reason": str}
                  behavior="allow": 允许执行，直接放行
                  behavior="deny":  拒绝执行，reason 解释原因
                  behavior="ask":   需要询问用户的确认

        设计说明（教学版）：
            各步骤在代码中是顺序展开的，而非压缩成一个紧凑的决策树。
            这样每个检查步骤的输入、输出和转换逻辑一目了然。
            生产版本可能会将这些步骤重构为管道/责任链模式以提高扩展性。
        """
        # =====================================================================
        # Step 0: Bash 安全校验（在所有 deny 规则之前执行）
        # 这是第一道防线，针对命令执行类工具（bash）进行模式检测。
        # 教学版将此步骤独立出来，意图是让学习者清楚看到：
        #   安全检查 → 通用规则 → 模式决策 → 用户询问 这个分层架构。
        # =====================================================================
        if tool_name == "bash":
            command = tool_input.get("command", "")
            failuers = bash_validator.validate(command)
            if failuers:
                # 将校验失败分为两类处理：

                # 第一类：严重模式（目前已注释为仅含 sudo 和 rm_rf，
                # 实际未在 VALIDATORS 中定义，预留扩展点）。
                # 这类操作一旦匹配，直接拒绝，不给用户选择权。
                severe = {"sudo", "rm_rf"}
                severe_hits = [f for f in failuers if f[0] in severe]

                # 生成可读的失败描述，用于返回给用户。
                desc = bash_validator.describe_failures(command)

                if severe_hits:
                    return {"behavior": "deny", "reason": f"Bash validator: {desc}"}

                # 第二类：非严重但可疑的模式（如包含元字符、调用 PowerShell 等）。
                # 这类操作不是绝对禁止的，但需要用户明确确认。
                # 在非交互式 Agent 循环中无法即时询问，因此先拒绝并给出原因。
                return {
                    "behavior": "deny",
                    "reason": f"Bash validator flagged: {desc}",
                }

        # =====================================================================
        # Step 1: 拒绝规则检查（deny rules —— 不可绕过的硬性拦截）
        # 遍历规则列表，只检查 behavior == "deny" 的规则。
        # 这些规则代表了系统的安全底线，任何情况下都不能绕过。
        # =====================================================================
        for rule in self.rules:
            if rule["behavior"] != "deny":
                continue
            if self._matches(rule, tool_name, tool_input):
                return {"behavior": "deny", "reason": f"Blocked by deny rule: {rule}"}

        # =====================================================================
        # Step 2: 基于当前权限模式的决策
        # 不同模式在未匹配 deny 规则后的行为不同。
        # =====================================================================

        # Plan（规划）模式：
        # 所有写入操作被硬性拒绝，只允许只读操作。
        # 用于方案设计阶段，AI 可以自由浏览代码但不能做任何修改。
        if self.mode == "plan":
            if tool_name in WRITE_TOOLS:
                return {
                    "behavior": "deny",
                    "reason": "Plan mode: write operations are blocked",
                }
            # 不是写入工具即放行（包括只读工具和其他未分类工具）。
            return {"behavior": "allow", "reason": "Plan mode: read-only allowed"}

        # Auto（自动）模式：
        # 对只读工具自动放行，减少用户在浏览代码时的交互打扰。
        # 写入工具不在此处自动放行，继续进入下一步（规则匹配或询问）。
        if self.mode == "auto":
            # read_file 被额外列在这里，与 READ_ONLY_TOOLS 有重叠。
            # 这是为了确保即使 READ_ONLY_TOOLS 定义变化，
            # read_file 在 auto 模式下始终被自动放行。
            if tool_name in READ_ONLY_TOOLS or tool_name == "read_file":
                return {
                    "behavior": "allow",
                    "reason": "Auto mode: read-only tool auto-approved",
                }
            # 注意：这里的 pass 是有意为之。
            # auto 模式下写入工具不在此处做决策，
            # 而是继续进入 Step 3（allow 规则匹配）和 Step 4（询问用户）。
            # 这样架构清晰：auto 模式 = 只读自动放行 + 写入仍需确认。
            pass

        # =====================================================================
        # Step 3: 允许规则匹配（allow rules）
        # 遍历规则列表，检查 behavior == "allow" 的规则。
        # 命中后重置连续拒绝计数器，避免误触发模式切换提示。
        # =====================================================================
        for rule in self.rules:
            if rule["behavior"] != "allow":
                continue
            if self._matches(rule, tool_name, tool_input):
                # 成功匹配允许规则，重置连续拒绝计数。
                # 这说明用户的交互是正常的（有允许有拒绝），
                # 不需要提示切换模式。
                self.consecutive_denials = 0
                return {"behavior": "allow", "reason": f"Matched allow rule: {rule}"}

        # =====================================================================
        # Step 4: 兜底策略 —— 询问用户
        # 当以上所有检查步骤都没有匹配时，
        # 系统无法自行决定，需要用户的判断。
        # 返回 "ask" 行为，由上层调用 ask_user() 进行交互。
        # =====================================================================
        return {
            "behavior": "ask",
            "reason": f"No rule matched for {tool_name}, asking user",
        }

    def ask_user(self, tool_name: str, tool_input: dict) -> bool:
        """以交互方式向用户询问是否允许执行当前操作。

        当 PermissionManager.check() 返回 behavior="ask" 时，
        由调用方调用此方法让用户做出最终决定。

        交互选项：
          - y / yes:   本次允许执行
          - n / no:    本次拒绝执行
          - always:    本次允许，并将该工具永久加入 allow 规则列表

        连续拒绝追踪：
          当用户连续拒绝操作时，递增计数器。
          一旦超过 max_consecutive_denials（默认 3 次），
          输出提示建议用户切换到 plan 模式。
          这意味着用户可能只想要 AI 浏览和分析代码，而非修改代码。

        参数:
            tool_name:  被询问的工具名称
            tool_input: 工具的调用参数

        返回:
            True:  用户同意执行
            False: 用户拒绝执行（或发生异常如 EOF/KeyboardInterrupt）
        """
        # 截取前 200 个字符作为预览，避免过长的命令/内容占满终端。
        preview = json.dumps(tool_input, ensure_ascii=False)[:200]
        print(f"\n [请求] {tool_name}: {preview}")

        try:
            answer = input("是否允许? (y/n/always): ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            # EOF（管道关闭/输入结束）或用户按 Ctrl+C 时，
            # 安全策略默认拒绝，符合最小权限原则。
            return False

        # 用户选择 "always"：永久放行该工具。
        # 将一条新的 allow 规则添加到规则列表末尾。
        # 注意：这条规则是 path: "*" 的全局放行，
        # 意味着该工具对所有文件路径都生效。
        if answer == "always":
            self.rules.append({"tool": tool_name, "path": "*", "behavior": "allow"})
            self.consecutive_denials = 0
            return True

        # 用户选择 "yes" / "y"：仅本次放行。
        if answer in ("yes", "y"):
            self.consecutive_denials = 0
            return True

        # 用户选择 "no" / "n" 或其他任何输入：拒绝执行。
        # 递增连续拒绝计数器，用于检测是否频繁拒绝。
        self.consecutive_denials += 1
        if self.consecutive_denials > self.max_consecutive_denials:
            print(
                f"  [{self.consecutive_denials} consecutive denials -- "
                "consider switching to plan mode]"
            )
        return False

    def _matches(self, rule: dict, tool_name: str, tool_input: dict) -> bool:
        """判断一条规则是否匹配给定的工具调用。

        这是权限匹配的核心逻辑，支持三维匹配：
          1. 工具名称匹配（tool）
          2. 文件路径匹配（path）—— 使用 fnmatch 支持 Unix Shell 风格的通配符
          3. 命令内容匹配（content）—— 同样使用 fnmatch 通配符

        匹配策略：
          - 规则中未指定的字段（不存在对应的 key）不做检查，视为匹配。
            例如，如果规则中没有 "path" 键，则不对路径做任何限制。
          - 通配符 "*" 匹配任意值。
          - 所有已指定的字段都必须同时匹配，规则才算命中（AND 逻辑）。

        参数:
            rule:       规则字典，包含可选的 "tool"、"path"、"content" 键
            tool_name:  待匹配的工具名称
            tool_input: 待匹配的工具参数字典

        返回:
            True:  规则命中，该工具调用应被此规则处理
            False: 规则未命中，继续检查下一条规则
        """

        # 1. 工具名称匹配
        #    如果规则指定了 tool 且不是通配符 "*"，则必须精确匹配。
        #    如果规则未指定 tool，则跳过此项检查（匹配所有工具）。
        if rule.get("tool") and rule["tool"] != "*":
            if rule["tool"] != tool_name:
                return False

        # 2. 文件路径匹配（使用 fnmatch 通配符匹配）
        #    从 tool_input 中提取 "path" 字段（如 read_file、write_file 的参数），
        #    与规则中指定的 path 模式进行通配符匹配。
        #    例如：rule["path"]="*.py" 匹配所有以 .py 结尾的路径。
        if "path" in rule and rule["path"] != "*":
            path = tool_input.get("path", "")
            if not fnmatch(path, rule["path"]):
                return False

        # 3. 命令内容匹配（使用 fnmatch 通配符匹配）
        #    从 tool_input 中提取 "command" 字段（如 bash 的参数），
        #    与规则中指定的 content 模式进行通配符匹配。
        #    例如：rule["content"]="npm install *" 匹配所有 npm install 命令。
        if rule.get("content"):
            command = tool_input.get("command", "")
            if not fnmatch(command, rule["content"]):
                return False

        # 所有已指定的字段都匹配成功，规则命中。
        return True
