from pathlib import Path
import re
import subprocess
import sys


ROOT = Path("/opt/ss4ts-noc")
SRC = ROOT / "frontend/src"

if not SRC.exists():
    print("❌ frontend/src غير موجود")
    sys.exit(1)


CODE_SUFFIXES = {
    ".jsx",
    ".js",
    ".tsx",
    ".ts",
}

CSS_SUFFIXES = {
    ".css",
    ".scss",
}


def read_text(path):
    try:
        return path.read_text(
            encoding="utf-8",
        )
    except UnicodeDecodeError:
        return path.read_text(
            encoding="utf-8",
            errors="ignore",
        )


code_files = sorted(
    path
    for path in SRC.rglob("*")
    if (
        path.is_file()
        and path.suffix in CODE_SUFFIXES
    )
)

css_files = sorted(
    path
    for path in SRC.rglob("*")
    if (
        path.is_file()
        and path.suffix in CSS_SUFFIXES
    )
)


manual_tables = []
ss_tables = []
table_imports = []
table_css = []


for path in code_files:
    text = read_text(path)
    relative = path.relative_to(ROOT)

    manual_matches = list(
        re.finditer(
            r"<table(?:\s|>)",
            text,
        )
    )

    ss_matches = list(
        re.finditer(
            r"<SSTable(?:\s|>)",
            text,
        )
    )

    import_matches = list(
        re.finditer(
            r"\bSSTable\b",
            text,
        )
    )

    if manual_matches:
        manual_tables.append(
            (
                relative,
                [
                    text[:match.start()].count("\n")
                    + 1
                    for match in manual_matches
                ],
            )
        )

    if ss_matches:
        ss_tables.append(
            (
                relative,
                [
                    text[:match.start()].count("\n")
                    + 1
                    for match in ss_matches
                ],
            )
        )

    if (
        import_matches
        and not ss_matches
        and path.name != "SSTable.jsx"
    ):
        table_imports.append(
            relative
        )


for path in css_files:
    text = read_text(path)
    relative = path.relative_to(ROOT)

    selectors = sorted(
        set(
            match.group(0)
            for match in re.finditer(
                r"\.[A-Za-z0-9_-]*table"
                r"[A-Za-z0-9_-]*",
                text,
            )
        )
    )

    if selectors:
        table_css.append(
            (
                relative,
                selectors,
            )
        )


print("=" * 76)
print(" Sprint 1.6.2-D3.2-H1 — PROJECT TABLES INVENTORY")
print("=" * 76)

print()
print("1) Manual HTML Tables")
print("-" * 76)

if not manual_tables:
    print("✅ لا توجد جداول HTML يدوية")
else:
    for path, lines in manual_tables:
        print(
            f"⚠️ {path}"
        )
        print(
            "   Lines: "
            + ", ".join(
                map(str, lines)
            )
        )


print()
print("2) SSTable Usage")
print("-" * 76)

if not ss_tables:
    print("❌ لا يوجد أي استخدام لـ SSTable")
else:
    for path, lines in ss_tables:
        print(
            f"✅ {path}"
        )
        print(
            "   Lines: "
            + ", ".join(
                map(str, lines)
            )
        )


print()
print("3) SSTable Imports Without Usage")
print("-" * 76)

if not table_imports:
    print("✅ لا توجد imports زائدة")
else:
    for path in table_imports:
        print(
            f"⚠️ {path}"
        )


print()
print("4) Table-related CSS Inventory")
print("-" * 76)

if not table_css:
    print("✅ لا توجد CSS مرتبطة بالجداول")
else:
    for path, selectors in table_css:
        print(f"📄 {path}")

        for selector in selectors:
            print(
                f"   {selector}"
            )


print()
print("=" * 76)
print(" SUMMARY")
print("=" * 76)

print(
    f"Manual table files : "
    f"{len(manual_tables)}"
)

print(
    f"SSTable files      : "
    f"{len(ss_tables)}"
)

print(
    f"Unused imports     : "
    f"{len(table_imports)}"
)

print(
    f"Table CSS files    : "
    f"{len(table_css)}"
)


print()
print("=" * 76)
print(" BUILD CHECK")
print("=" * 76)

build = subprocess.run(
    ["npm", "run", "build"],
    cwd=ROOT / "frontend",
)

if build.returncode != 0:
    print()
    print("❌ فشل npm run build")
    sys.exit(build.returncode)


print()
print("=" * 76)
print(" GIT CHECK")
print("=" * 76)

git_check = subprocess.run(
    [
        "git",
        "diff",
        "--check",
    ],
    cwd=ROOT,
)

if git_check.returncode != 0:
    print()
    print("❌ فشل git diff --check")
    sys.exit(git_check.returncode)


print()
print("=" * 76)
print("✅ Sprint D3.2-H1 Inventory اكتمل")
print()
print(
    "الخطوة التالية تعتمد على ملفات "
    "Manual HTML Tables الظاهرة أعلاه."
)
print("=" * 76)
