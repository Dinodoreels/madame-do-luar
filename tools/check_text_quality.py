"""
Verifica problemas comuns de texto antes do deploy.

O foco e impedir que mojibake e mocks silenciosos voltem a entrar nos
arquivos operacionais do projeto.
"""

from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TARGETS = [
    "api.py",
    "frontend/index.html",
    "frontend/app.js",
    "frontend/admin.html",
    "frontend/admin.js",
    "findings.md",
    "README.md",
    "PLANO_IMPLANTACAO_MELHORIAS.md",
    "architecture/schema.sql",
    "architecture/deploy_runbook.md",
    "architecture/maintenance_runbook.md",
]

MOJIBAKE_PATTERNS = [
    ("mojibake_cedilha", "\u00c3\u00a7"),
    ("mojibake_a_til", "\u00c3\u00a3"),
    ("mojibake_e_agudo", "\u00c3\u00a9"),
    ("mojibake_o_agudo", "\u00c3\u00b3"),
    ("mojibake_a_agudo", "\u00c3\u00a1"),
    ("mojibake_i_agudo", "\u00c3\u00ad"),
    ("mojibake_u_agudo", "\u00c3\u00ba"),
    ("mojibake_symbol_prefix", "\u00e2\u0153"),
    ("mojibake_moon_prefix", "\u00e2\u02dc"),
    ("mojibake_emoji_prefix", "\u00f0\u0178"),
    ("replacement_character", "\ufffd"),
]

SILENT_MOCK_PATTERNS = [
    re.compile(r'"gateway"\s*:\s*"mock"'),
    re.compile(r'"status"\s*:\s*"simulated"'),
    re.compile(r"detail\s*=\s*str\("),
    re.compile(r"except\s*:\s*$", re.MULTILINE),
]


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def relative(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def main() -> int:
    issues: list[str] = []

    for path in [ROOT / target for target in TARGETS]:
        if not path.exists():
            continue
        rel = relative(path)
        text = read_text(path)

        for name, marker in MOJIBAKE_PATTERNS:
            if marker in text:
                issues.append(f"{rel}: possivel encoding quebrado: {name}")

        for pattern in SILENT_MOCK_PATTERNS:
            if pattern.search(text):
                issues.append(f"{rel}: possivel mock/erro silencioso: {pattern.pattern}")

    if issues:
        print("TEXT QUALITY FAIL")
        for issue in issues:
            print(f"- {issue}")
        return 1

    print("TEXT QUALITY OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
