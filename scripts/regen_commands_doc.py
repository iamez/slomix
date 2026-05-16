"""Regenerate docs/COMMANDS.md from @commands.command declarations in cogs + mixins.

Run from anywhere; the repo root is derived from the script's own location
(scripts/regen_commands_doc.py -> repo root is its parent's parent).
"""
import ast
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
COGS_DIR = ROOT / "bot" / "cogs"
ULTIMATE = ROOT / "bot" / "ultimate_bot.py"

def get_cmd_decorator_args(deco):
    if not isinstance(deco, ast.Call):
        return None
    func = deco.func
    if isinstance(func, ast.Attribute):
        if func.attr not in ("command", "group"):
            return None
        if isinstance(func.value, ast.Name) and func.value.id != "commands":
            return None
    elif isinstance(func, ast.Name) and func.id != "command":
        return None
    else:
        return None

    name = None
    aliases = []
    hidden = False
    for kw in deco.keywords:
        if kw.arg == "name" and isinstance(kw.value, ast.Constant):
            name = kw.value.value
        elif kw.arg == "aliases" and isinstance(kw.value, ast.List):
            aliases = [el.value for el in kw.value.elts if isinstance(el, ast.Constant)]
        elif kw.arg == "hidden" and isinstance(kw.value, ast.Constant):
            hidden = bool(kw.value.value)
    if name is None and deco.args and isinstance(deco.args[0], ast.Constant):
        name = deco.args[0].value
    return (name, aliases, hidden)

def first_line(docstring):
    if not docstring:
        return "(no description)"
    return docstring.strip().splitlines()[0].strip().rstrip(".")

def extract_commands(path):
    tree = ast.parse(path.read_text())
    out = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.AsyncFunctionDef, ast.FunctionDef)):
            for deco in node.decorator_list:
                meta = get_cmd_decorator_args(deco)
                if meta is None:
                    continue
                name, aliases, hidden = meta
                if name is None:
                    name = node.name
                desc = first_line(ast.get_docstring(node))
                out.append((name, aliases, desc, hidden))
                break
    return out

def cog_for_mixin_dir(dirname):
    """proximity_mixins -> proximity_cog.py (or similar)."""
    base = dirname.replace("_mixins", "")
    candidate = COGS_DIR / f"{base}_cog.py"
    if candidate.exists():
        return candidate.name
    # Try just base.py (e.g. automation_commands.py)
    candidate = COGS_DIR / f"{base}.py"
    if candidate.exists():
        return candidate.name
    return f"{base}_cog.py (inferred)"

def format_aliases(aliases):
    return ", ".join(f"`{a}`" for a in aliases) if aliases else "(none)"

def format_table(commands):
    rows = ["| Command | Aliases | Description |", "|---|---|---|"]
    for name, aliases, desc, hidden in sorted(commands):
        if hidden:
            continue
        desc_safe = desc.replace("|", "\\|")
        rows.append(f"| `{name}` | {format_aliases(aliases)} | {desc_safe} |")
    return "\n".join(rows)

# Aggregate commands by cog (combining mixin files with their parent cog)
cog_commands = {}  # cog_filename -> list of (name, aliases, desc, hidden, source_file)

# Walk top-level cog files
for cog_file in sorted(COGS_DIR.glob("*.py")):
    if cog_file.name == "__init__.py":
        continue
    cmds = extract_commands(cog_file)
    if cmds:
        cog_commands.setdefault(cog_file.name, []).extend((n, a, d, h, str(cog_file.relative_to(ROOT))) for n, a, d, h in cmds)

# Walk mixin subdirs
for mixin_dir in sorted(COGS_DIR.glob("*_mixins")):
    parent_cog = cog_for_mixin_dir(mixin_dir.name)
    for mixin_file in sorted(mixin_dir.glob("*.py")):
        if mixin_file.name == "__init__.py":
            continue
        cmds = extract_commands(mixin_file)
        if cmds:
            cog_commands.setdefault(parent_cog, []).extend((n, a, d, h, str(mixin_file.relative_to(ROOT))) for n, a, d, h in cmds)

# Build sections
sections = []
total = 0
total_hidden = 0
for cog_name in sorted(cog_commands):
    cmds = cog_commands[cog_name]
    visible_cmds = [c for c in cmds if not c[3]]
    hidden_cmds = [c for c in cmds if c[3]]
    total += len(visible_cmds)
    total_hidden += len(hidden_cmds)
    # Strip source-file suffix when formatting table (use original tuple shape)
    table_cmds = [(n, a, d, h) for n, a, d, h, _ in cmds]
    title = cog_name.replace("_cog.py", "").replace("_commands.py", "").replace(".py", "").replace("_", " ").title()
    # Collect unique source files for this cog
    sources = sorted(set(src for *_, src in cmds))
    src_str = ", ".join(f"`{s}`" for s in sources)
    sections.append(f"## {title} cog ({src_str})\n\n{format_table(table_cmds)}")

# Core commands
cmds = extract_commands(ULTIMATE)
if cmds:
    visible = [c for c in cmds if not c[3]]
    hidden = [c for c in cmds if c[3]]
    total += len(visible)
    total_hidden += len(hidden)
    sections.append(f"## Core commands (`bot/ultimate_bot.py`)\n\n{format_table(cmds)}")

header = f"""# ET:Legacy Bot — Commands Reference

This document lists Discord bot commands declared in the repository (via `@commands.command(...)` and `@commands.group(...)`), with aliases and short descriptions. It is **auto-generated** from the source by `scripts/regen_commands_doc.py` — re-run that script after adding, renaming, or removing commands.

**Coverage:** {total} visible commands across {len(sections)} cog files / cog-mixin groups{f" (+ {total_hidden} hidden/admin-only commands not listed)" if total_hidden else ""}.

> Hidden commands (`@commands.command(hidden=True)`) are intentionally excluded.
> Slash commands (`@app_commands.command(...)`) are NOT in this list — none are currently declared in the repo.
"""

content = header + "\n\n---\n\n" + "\n\n---\n\n".join(sections) + "\n"
(ROOT / "docs" / "COMMANDS.md").write_text(content)
print(f"Wrote docs/COMMANDS.md — {total} visible commands, {total_hidden} hidden, {len(sections)} cog groups")
