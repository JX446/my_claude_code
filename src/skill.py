import re
from dataclasses import dataclass
from pathlib import Path


@dataclass
class SkillManifest:
    name: str
    description: str
    path: Path


@dataclass
class SkillDocument:
    manifest: SkillManifest
    body: str


class SkillRegistry:
    def __init__(self, skill_dir: Path) -> None:
        self.skill_dir = skill_dir
        self.documents: dict[str, SkillDocument] = {}
        self._load_all()

    # 注册目标路径所有的SKILL
    def _load_all(self) -> None:
        if not self.skill_dir.exists():
            return

        for path in sorted(self.skill_dir.rglob("SKILL.md")):
            meta, body = self._parse_frontmatter(path.read_text(encoding="utf-8"))
            name = meta.get("name", path.parent.name)
            description = meta.get("description", "No description")
            manifest = SkillManifest(name=name, description=description, path=path)
            self.documents[name] = SkillDocument(manifest=manifest, body=body.strip())

    # 解析SKILL
    def _parse_frontmatter(self, text: str) -> tuple[dict, str]:
        match = re.match(r"^---\n(.*?)\n---\n(.*)", text, re.DOTALL)
        if not match:
            return {}, text
        meta = {}
        for line in match.group(1).strip().splitlines():
            if ":" not in line:
                continue
            key, value = line.split(":", 1)
            meta[key.strip()] = value.strip()
        return meta, match.group(2)

    # 返回目前可用的SKILL的description
    def describe_available(self) -> str:
        if not self.documents:
            return "(No skill available)"
        lines = []
        for name in sorted(self.documents):
            manifest = self.documents[name].manifest
            lines.append(f"- {manifest.name}: {manifest.description}")
        return "\n".join(lines)

    # 加载目标SKILL的全文
    def load_full_text(self, name: str) -> str:
        document = self.documents[name]
        if not document:
            known = ",".join(sorted(self.documents)) or "None"
            return f"Error: Unkown skill '{name}'. Available skills: {known}"
        return f'<skill name="{document.manifest.name}">\n{document.body}\n</skill>'


WORKDIR = Path.cwd()
SKILL_DIR = WORKDIR / "skills"
SKILL_REGISTRY = SkillRegistry(SKILL_DIR)
