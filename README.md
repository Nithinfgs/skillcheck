# skillcheck

Lint your agent skills before your agent trips over them. `skillcheck` scans folders of `SKILL.md` files
(the format used by Claude Code and other coding agents) and reports structural and quality problems.
Pure Python standard library, offline, no LLM, no network.

## Install

```bash
pip install git+https://github.com/Nithinfgs/skillcheck
# or run from a clone, no install needed:
python -m skillcheck path/to/skills
```

## Usage

```bash
skillcheck ~/.claude/skills              # lint a whole tree
skillcheck ./my-skill                    # lint one skill
skillcheck . --format json               # machine readable
skillcheck . --fail-on warning           # stricter CI gate
skillcheck . --ignore ref-orphan         # skip a rule
```

Exit codes: `0` clean, `1` findings at or above `--fail-on` (default `error`), `2` bad path.

Example (`examples/broken-skill`):

```
E name-format   examples/broken-skill/SKILL.md
    name 'Broken_Skill' must be lowercase letters, digits and single hyphens
E ref-missing   examples/broken-skill/SKILL.md:6
    references 'scripts/missing.sh' which does not exist
W desc-short    examples/broken-skill/SKILL.md
    description is only 12 chars; the agent needs it to decide when to load the skill
```

## Rules

| Rule | Severity | Checks |
|---|---|---|
| `frontmatter` | error | file starts with a closed `---` block |
| `name-missing` / `name-format` / `name-length` | error | name present, `lower-kebab-case`, max 64 chars |
| `name-dir` | warning | name matches the folder name |
| `name-dup` | error | no two skills share a name |
| `desc-missing` / `desc-length` / `desc-markup` | error | description present, max 1024 chars, no HTML/XML tags |
| `desc-short` / `desc-trigger` | warning | description is substantive and says *when* to use the skill |
| `desc-overlap` | warning | two descriptions are so similar the agent may pick the wrong one |
| `unknown-key` | warning | unrecognised frontmatter keys |
| `body-empty` / `body-long` | error / warning | instructions exist and stay under 500 lines |
| `ref-missing` | error | linked files and `scripts/…`, `references/…` paths exist |
| `ref-orphan` | info | files in `scripts/`, `references/`, `assets/` that SKILL.md never mentions |

Paths inside fenced code blocks are not treated as references.

## CI

```yaml
- run: pip install git+https://github.com/Nithinfgs/skillcheck
- run: skillcheck skills/ --fail-on warning
```

## Development

```bash
python -m unittest discover -s tests -t .
```

## Limitations

The frontmatter parser is a small YAML subset (`key: value`, `>` and `|` blocks); nested maps are read as
opaque text. Description similarity is a word-overlap heuristic, not semantic. Rules reflect the common
SKILL.md conventions and may not match every agent's stricter requirements.

## License

MIT
