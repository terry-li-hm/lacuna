#!/usr/bin/env python3
"""Update alias-to-UUID mappings in ~/bin/lacuna and CLAUDE.md after corpus re-seed.

Usage:
    python3 tools/update_aliases.py [--ids-file /tmp/lacuna-new-ids.json]
"""
import json, re, argparse
from pathlib import Path

DISPLAY_MAP = {
    "hkma-cp":     "HKMA GenAI Consumer Protection 2024",
    "hkma-gai":    "HKMA GenAI Financial Services 2024",
    "hkma-sandbox":"HKMA GenAI Sandbox Arrangement 2024",
    "hkma-spm":    "HKMA SPM CA-G-1 Revised 2024",
    "eu-ai-act":   "EU AI Act (Regulation 2024/1689)",
    "fca":         "FCA AI Update 2024",
    "mas-consult": "MAS AI Risk Management Consultation 2025",
    "mas-mrmf":    "MAS AI Model Risk Management 2024",
    "nist-rmf":    "NIST AI Risk Management Framework 1.0",
    "nist-iso42001":"NIST AI RMF to ISO 42001 Crosswalk",
    "sg-genai":    "Singapore GenAI Governance Framework 2024",
    "demo-baseline":"Codex Argentum v1.1",
}
BASELINE_ALIASES = {"demo-baseline", "nist-rmf", "nist-iso42001"}

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--ids-file", default="/tmp/lacuna-new-ids.json")
    args = parser.parse_args()

    NEW_IDS = json.loads(Path(args.ids_file).read_text())
    valid = {alias: uid for alias, uid in NEW_IDS.items() if uid not in ("ERROR", None)}

    CLI_PATH = Path.home() / "bin/lacuna"
    CLI = CLI_PATH.read_text()

    ALIAS_LINES = "\n".join(f'    "{a}": "{u}",' for a, u in sorted(valid.items()))
    CLI = re.sub(r'(ALIASES\s*=\s*\{)[^}]*(})', f'\\1\n{ALIAS_LINES}\n\\2', CLI, flags=re.DOTALL)

    DN = {valid[a]: DISPLAY_MAP[a] for a in valid if a in DISPLAY_MAP}
    DN_LINES = "\n".join(f'    "{uid}": "{name}",' for uid, name in DN.items())
    CLI = re.sub(r'(DISPLAY_NAMES\s*=\s*\{)[^}]*(})', f'\\1\n{DN_LINES}\n\\2', CLI, flags=re.DOTALL)

    BL = [valid[a] for a in BASELINE_ALIASES if a in valid]
    BL_LINES = "\n".join(f'    "{u}",' for u in BL)
    CLI = re.sub(r'(BASELINES\s*=\s*\{)[^}]*(})', f'\\1\n{BL_LINES}\n\\2', CLI, flags=re.DOTALL)

    CLI_PATH.write_text(CLI)
    import ast; ast.parse(CLI)
    print(f"Updated {CLI_PATH} — syntax OK")

    # Update CLAUDE.md key doc IDs section
    CLAUDE = Path("CLAUDE.md").read_text() if Path("CLAUDE.md").exists() else Path("docs/CLAUDE.md").read_text()
    CLAUDE_PATH = Path("CLAUDE.md") if Path("CLAUDE.md").exists() else Path("docs/CLAUDE.md")
    for alias, uid in valid.items():
        CLAUDE = re.sub(rf'`[0-9a-f-]{{36}}`(.*?alias: `{alias}`)', f'`{uid}`\\1', CLAUDE)
    # Update demo gap analysis UUIDs
    if "hkma-cp" in valid:
        CLAUDE = re.sub(r'(circular_doc_id: )`[0-9a-f-]{36}`', f'\\1`{valid["hkma-cp"]}`', CLAUDE)
    if "demo-baseline" in valid:
        CLAUDE = re.sub(r'(baseline_id: )`[0-9a-f-]{36}`', f'\\1`{valid["demo-baseline"]}`', CLAUDE)
    CLAUDE_PATH.write_text(CLAUDE)
    print(f"Updated {CLAUDE_PATH}")

    print(f"\nUpdated {len(valid)} alias mappings")

if __name__ == "__main__":
    main()
