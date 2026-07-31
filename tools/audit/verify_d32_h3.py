from pathlib import Path
import re
import subprocess
import sys


ROOT = Path("/opt/ss4ts-noc")

JSX = ROOT / (
    "frontend/src/components/device/"
    "DecisionIntelligenceCenter.jsx"
)

CSS = ROOT / (
    "frontend/src/components/device/"
    "DecisionIntelligenceCenter.css"
)

SSTABLE = ROOT / (
    "frontend/src/components/ui/"
    "SSTable.jsx"
)


required_files = [
    JSX,
    CSS,
    SSTABLE,
]

missing_files = [
    str(path)
    for path in required_files
    if not path.exists()
]

if missing_files:
    print("❌ ملفات مطلوبة غير موجودة:")

    for path in missing_files:
        print(f"  - {path}")

    sys.exit(1)


jsx = JSX.read_text(
    encoding="utf-8",
    errors="ignore",
)

css = CSS.read_text(
    encoding="utf-8",
    errors="ignore",
)

sstable = SSTABLE.read_text(
    encoding="utf-8",
    errors="ignore",
)


def extract_block(
    text,
    start_marker,
    end_marker,
):
    start = text.find(start_marker)

    if start == -1:
        return ""

    end = text.find(
        end_marker,
        start,
    )

    if end == -1:
        return ""

    return text[start:end]


columns_block = extract_block(
    jsx,
    "const DECISION_PILOT_COLUMNS =",
    "\n\nexport default function",
)

sstable_blocks = re.findall(
    r"<SSTable\b.*?/>",
    jsx,
    re.S,
)

decision_table_block = ""

for block in sstable_blocks:
    if "DECISION_PILOT_COLUMNS" in block:
        decision_table_block = block
        break


# ===== تم تصحيح الأعمدة هنا =====
expected_column_keys = [
    "stage",
    "title",
    "description",
    "status",
]

column_keys = re.findall(
    r"key:\s*['\"]([^'\"]+)['\"]",
    columns_block,
)

checks = [
    (
        "const DECISION_PILOT_COLUMNS"
        in jsx,
        "DECISION_PILOT_COLUMNS موجودة",
    ),
    (
        "const decisionPilotRows"
        in jsx,
        "decisionPilotRows موجودة",
    ),
    (
        bool(decision_table_block),
        "SSTable الخاص بـ Decision موجود",
    ),
    (
        "columns={DECISION_PILOT_COLUMNS}"
        in decision_table_block,
        "الأعمدة مربوطة",
    ),
    (
        "rows={decisionPilotRows}"
        in decision_table_block,
        "الصفوف مربوطة",
    ),
    (
        bool(
            re.search(
                r'rowKey=["\']id["\']',
                decision_table_block,
            )
        ),
        "rowKey=id",
    ),
    (
        'density="compact"'
        in decision_table_block,
        "density=compact",
    ),
    (
        "stickyHeader"
        in decision_table_block,
        "stickyHeader مفعل",
    ),
    (
        "striped"
        in decision_table_block,
        "striped مفعل",
    ),
    (
        "hoverable"
        in decision_table_block,
        "hoverable مفعل",
    ),
    (
        "bordered"
        in decision_table_block,
        "bordered مفعل",
    ),
    (
        "emptyTitle="
        in decision_table_block,
        "emptyTitle موجود",
    ),
    (
        "emptyDescription="
        in decision_table_block,
        "emptyDescription موجود",
    ),
    (
        len(column_keys) >= 4,
        "يوجد على الأقل 4 أعمدة",
    ),
    (
        all(
            key in column_keys
            for key in expected_column_keys
        ),
        "الأعمدة الأساسية موجودة",
    ),
    (
        ".decision-pilot-table"
        in css,
        "Decision table CSS موجود",
    ),
    (
        ".decision-pilot-table__header"
        in css,
        "Decision table header CSS موجود",
    ),
    (
        "rowKey" in sstable,
        "SSTable يدعم rowKey",
    ),
    (
        "emptyTitle" in sstable,
        "SSTable يدعم Empty State",
    ),
    (
        "stickyHeader" in sstable,
        "SSTable يدعم Sticky Header",
    ),
]


print("=" * 78)
print(
    " Sprint 1.6.2-D3.2-H3 "
    "— DECISION TABLE HARDENING AUDIT"
)
print("=" * 78)

failed = []

for passed, label in checks:
    print(
        f"{'✅ PASS' if passed else '❌ FAIL'} "
        f"{label}"
    )

    if not passed:
        failed.append(label)


print()
print("=" * 78)
print(" COLUMN INVENTORY")
print("=" * 78)

print("Columns:", column_keys)
print("Total:", len(column_keys))


print()
print("=" * 78)
print(" DECISION TABLE BLOCK")
print("=" * 78)

if decision_table_block:
    print(decision_table_block)
else:
    print("❌ لم يتم العثور على SSTable block")


print()
print("=" * 78)
print(" LEGACY / DUPLICATE CSS CHECK")
print("=" * 78)

legacy_markers = [
    ".decision-pilot-table table",
    ".decision-pilot-table thead",
    ".decision-pilot-table tbody",
    ".decision-pilot-table th",
    ".decision-pilot-table td",
]

for marker in legacy_markers:
    found = marker in css

    print(
        f"{'⚠️ FOUND' if found else '✅ CLEAN'} "
        f"{marker}"
    )


print()
print("=" * 78)
print(" BUILD CHECK")
print("=" * 78)

if failed:
    print("⚠️ توجد ملاحظات قبل البناء:")

    for item in failed:
        print(f"  - {item}")

build = subprocess.run(
    ["npm", "run", "build"],
    cwd=ROOT / "frontend",
)

if build.returncode != 0:
    print()
    print("❌ فشل npm run build")
    sys.exit(build.returncode)


print()
print("=" * 78)
print(" GIT CHECK")
print("=" * 78)

git_check = subprocess.run(
    [
        "git",
        "diff",
        "--check",
        "--",
        str(JSX.relative_to(ROOT)),
        str(CSS.relative_to(ROOT)),
        str(SSTABLE.relative_to(ROOT)),
    ],
    cwd=ROOT,
)

if git_check.returncode != 0:
    print()
    print("❌ فشل git diff --check")
    sys.exit(git_check.returncode)


print()
print("=" * 78)

if failed:
    print("⚠️ D3.2-H3 Audit اكتمل مع ملاحظات.")

    print(
        "الخطوة التالية ستكون Hardening "
        "للخصائص الناقصة فقط."
    )

    sys.exit(2)

print(
    "✅ Sprint 1.6.2-D3.2-H3 "
    "— Decision Intelligence Table Hardening Audit مكتمل"
)

print("=" * 78)
