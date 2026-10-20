"""Lint agent skill folders (SKILL.md) for structural and quality problems."""
from __future__ import annotations

import re
from dataclasses import dataclass, asdict
from pathlib import Path

KNOWN_KEYS = {"name", "description", "license", "allowed-tools", "metadata",
              "compatibility", "model", "version", "argument-hint"}
NAME_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
LINK_RE = re.compile(r"\]\(([^)#\s]+)(?:#[^)]*)?\)")
TICK_RE = re.compile(r"`((?:\./)?(?:scripts|references|assets|resources|templates)/[^`\s]+)`")
TRIGGER_HINTS = ("use when", "use this", "when the user", "when you", "trigger",
                 "use for", "use to", "use if", "whenever")
MAX_BODY_LINES = 500
SEVERITY_ORDER = {"error": 0, "warning": 1, "info": 2}


@dataclass
class Finding:
    rule: str
    severity: str
    path: str
    message: str
    line: int = 0

    def to_dict(self):
        return asdict(self)


def parse_frontmatter(text: str):
    """Return (dict, body_start_line, error). Minimal YAML: key: value, folded/literal blocks."""
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return None, 0, "missing frontmatter (file must start with '---')"
    end = next((i for i in range(1, len(lines)) if lines[i].strip() == "---"), None)
    if end is None:
        return None, 0, "frontmatter is not closed with '---'"
    data, key, buf, mode = {}, None, [], None

    def flush():
        if key is not None:
            sep = "\n" if mode == "|" else " "
            data[key] = sep.join(s.strip() for s in buf).strip()

    for raw in lines[1:end]:
        m = re.match(r"^([A-Za-z0-9_-]+):\s*(.*)$", raw)
        if m and not raw.startswith((" ", "\t")):
            flush()
            key, val = m.group(1), m.group(2).strip()
            if val in (">", "|", ">-", "|-"):
                mode, buf = val[0], []
            else:
                mode, buf = None, [val.strip("\"'")]
        elif key is not None and raw.strip():
            buf.append(raw)
        elif key is not None and not raw.strip():
            buf.append("")
    flush()
    return data, end + 1, None


def _words(s: str):
    return {w for w in re.findall(r"[a-z]{4,}", s.lower())}


def lint_skill(skill_md: Path) -> tuple[list[Finding], dict]:
    out: list[Finding] = []
    rel = str(skill_md)
    add = lambda rule, sev, msg, line=0: out.append(Finding(rule, sev, rel, msg, line))
    text = skill_md.read_text(encoding="utf-8", errors="replace")
    fm, body_start, err = parse_frontmatter(text)
    if err:
        add("frontmatter", "error", err, 1)
        return out, {}
    name, desc = fm.get("name", ""), fm.get("description", "")
    if not name:
        add("name-missing", "error", "frontmatter has no 'name'")
    else:
        if not NAME_RE.match(name):
            add("name-format", "error", f"name '{name}' must be lowercase letters, digits and single hyphens")
        if len(name) > 64:
            add("name-length", "error", f"name is {len(name)} chars (max 64)")
        if name != skill_md.parent.name:
            add("name-dir", "warning", f"name '{name}' differs from folder '{skill_md.parent.name}'")
    if not desc:
        add("desc-missing", "error", "frontmatter has no 'description'")
    else:
        if len(desc) > 1024:
            add("desc-length", "error", f"description is {len(desc)} chars (max 1024)")
        if len(desc) < 40:
            add("desc-short", "warning", f"description is only {len(desc)} chars; the agent needs it to decide when to load the skill")
        if not any(h in desc.lower() for h in TRIGGER_HINTS):
            add("desc-trigger", "warning", "description never says WHEN to use the skill (e.g. 'Use when ...')")
        if re.search(r"</?[a-zA-Z][^>]*>", desc):
            add("desc-markup", "error", "description contains XML/HTML tags")
    for k in fm:
        if k not in KNOWN_KEYS:
            add("unknown-key", "warning", f"unknown frontmatter key '{k}'")
    body = text.splitlines()[body_start:]
    if not "".join(body).strip():
        add("body-empty", "error", "skill has no instructions after the frontmatter", body_start)
    if len(body) > MAX_BODY_LINES:
        add("body-long", "warning", f"body is {len(body)} lines (>{MAX_BODY_LINES}); move detail into references/ files")
    # references
    refs: dict[str, int] = {}
    in_fence = False
    for i, line in enumerate(body, body_start + 1):
        if line.lstrip().startswith("```"):
            in_fence = not in_fence
        for m in LINK_RE.finditer(line):
            t = m.group(1)
            if not re.match(r"^(https?:|mailto:|/|~)", t):
                refs.setdefault(t.lstrip("./") if t.startswith("./") else t, i)
        if not in_fence:
            for m in TICK_RE.finditer(line):
                refs.setdefault(m.group(1).removeprefix("./"), i)
    root = skill_md.parent
    for ref, line in refs.items():
        if not (root / ref).exists():
            add("ref-missing", "error", f"references '{ref}' which does not exist", line)
    referenced = {str((root / r).resolve()) for r in refs}
    for sub in ("scripts", "references", "assets"):
        d = root / sub
        if d.is_dir():
            for f in sorted(p for p in d.rglob("*") if p.is_file() and not p.name.startswith(".")):
                if str(f.resolve()) not in referenced and f.relative_to(root).as_posix() not in text:
                    add("ref-orphan", "info", f"{f.relative_to(root).as_posix()} is never mentioned in SKILL.md")
    return out, {"name": name, "description": desc}


def lint_tree(root: Path) -> list[Finding]:
    root = Path(root)
    files = [root] if root.is_file() else sorted(root.rglob("SKILL.md"))
    files = [f for f in files if not any(p in {"node_modules", ".git"} for p in f.parts)]
    findings, meta = [], []
    for f in files:
        fs, m = lint_skill(f)
        findings += fs
        if m.get("name"):
            meta.append((f, m))
    for i, (fa, a) in enumerate(meta):
        for fb, b in meta[i + 1:]:
            if a["name"] == b["name"]:
                findings.append(Finding("name-dup", "error", str(fb), f"duplicate skill name '{a['name']}' (also in {fa})"))
                continue
            wa, wb = _words(a["description"]), _words(b["description"])
            if len(wa) >= 6 and len(wb) >= 6:
                j = len(wa & wb) / len(wa | wb)
                if j >= 0.6:
                    findings.append(Finding("desc-overlap", "warning", str(fb),
                        f"description is {j:.0%} similar to '{a['name']}' ({fa}); the agent may pick the wrong skill"))
    if not files:
        findings.append(Finding("no-skills", "error", str(root), "no SKILL.md found"))
    findings.sort(key=lambda f: (SEVERITY_ORDER[f.severity], f.path, f.line))
    return findings
