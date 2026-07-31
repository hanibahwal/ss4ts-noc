from pathlib import Path
import re
import subprocess
import sys


ROOT = Path("/opt/ss4ts-noc")

FILES = {
    "Decision Intelligence": ROOT / (
        "frontend/src/components/device/"
        "DecisionIntelligenceCenter.jsx"
    ),
    "Interfaces": ROOT / (
        "frontend/src/components/device/"
        "InterfacesTable.jsx"
    ),
}

SSTABLE = ROOT / (
    "frontend/src/components/ui/"
    "SSTable.jsx"
)


missing = [
    str(path)
    for path in [
        *FILES.values(),
        SSTABLE,
    ]
    if not path.exists()
]

if missing:
    print("❌ ملفات غير موجودة:")

    for path in missing:
        print(f"  - {path}")

    sys.exit(1)


def read(path):
    return path.read_text(
        encoding="utf-8",
        errors="ignore",
    )


def find_sstable_blocks(text):
    blocks = []
    start = 0

    while True:
        opening = text.find(
            "<SSTable",
            start,
        )

        if opening == -1:
            break

        closing = text.find(
            "/>",
            opening,
        )

        if closing == -1:
            break

        closing += 2

        blocks.append(
            text[opening:closing]
        )

        start = closing

    return blocks


def has_prop(block, prop):
    return bool(
        re.search(
            rf"\b{re.escape(prop)}"
            rf"(?:\s*=|\s|/>)",
            block,
        )
    )


required_common = [
    "columns",
    "rows",
    "rowKey",
    "density",
    "hoverable",
    "bordered",
    "emptyTitle",
    "emptyDescription",
]

optional_features = [
    "loading",
    "error",
    "selectedRowKey",
    "sortColumn",
    "sortDirection",
    "onSort",
    "onRowClick",
    "onRowDoubleClick",
    "rowClassName",
    "rowAriaLabel",
    "stickyHeader",
    "striped",
]


print("=" * 78)
print(" Sprint 1.6.2-D3.2-H2 — SSTABLE CONSISTENCY AUDIT")
print("=" * 78)


failed = []
reports = {}


for label, path in FILES.items():
    text = read(path)
    blocks = find_sstable_blocks(text)

    print()
    print(f"{label}")
    print("-" * 78)

    if not blocks:
        print("❌ لا يوجد SSTable")

        failed.append(
            f"{label}: لا يوجد SSTable"
        )

        continue

    print(
        f"SSTable instances: {len(blocks)}"
    )

    if len(blocks) != 1:
        failed.append(
            f"{label}: عدد SSTable ليس واحدًا"
        )

    block = blocks[0]

    report = {
        prop: has_prop(
            block,
            prop,
        )
        for prop in (
            required_common
            + optional_features
        )
    }

    reports[label] = report

    print()
    print("Required common props:")

    for prop in required_common:
        passed = report[prop]

        print(
            f"{'✅' if passed else '❌'} "
            f"{prop}"
        )

        if not passed:
            failed.append(
                f"{label}: missing {prop}"
            )

    print()
    print("Optional capabilities:")

    for prop in optional_features:
        passed = report[prop]

        print(
            f"{'✅' if passed else '—'} "
            f"{prop}"
        )


print()
print("=" * 78)
print(" SSTABLE COMPONENT CAPABILITIES")
print("=" * 78)

sstable_text = read(SSTABLE)

component_props = [
    "columns",
    "rows",
    "loading",
    "error",
    "rowKey",
    "selectedRowKey",
    "onRowClick",
    "onRowDoubleClick",
    "sortColumn",
    "sortDirection",
    "onSort",
    "rowClassName",
    "rowAriaLabel",
    "density",
    "stickyHeader",
    "striped",
    "hoverable",
    "bordered",
    "emptyTitle",
    "emptyDescription",
]

for prop in component_props:
    passed = bool(
        re.search(
            rf"\b{re.escape(prop)}\b",
            sstable_text,
        )
    )

    print(
        f"{'✅ PASS' if passed else '❌ FAIL'} "
        f"{prop}"
    )

    if not passed:
        failed.append(
            f"SSTable component missing {prop}"
        )


print()
print("=" * 78)
print(" CONSISTENCY COMPARISON")
print("=" * 78)

if len(reports) == len(FILES):
    for prop in required_common:
        values = {
            label: report[prop]
            for label, report
            in reports.items()
        }

        consistent = len(
            set(values.values())
        ) == 1

        print(
            f"{'✅ CONSISTENT' if consistent else '❌ DIFFERENT'} "
            f"{prop}: {values}"
        )

        if not consistent:
            failed.append(
                f"Inconsistent prop: {prop}"
            )


print()
print("=" * 78)
print(" BUILD CHECK")
print("=" * 78)

if failed:
    print(
        "⚠️ توجد ملاحظات قبل البناء:"
    )

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
    print(
        "⚠️ D3.2-H2 Audit اكتمل مع ملاحظات."
    )

    print(
        "المرحلة التالية ستكون توحيد "
        "الخصائص الناقصة فقط."
    )

    sys.exit(2)

print(
    "✅ Sprint 1.6.2-D3.2-H2 "
    "— SSTable Consistency Audit مكتمل"
)

print("=" * 78)
