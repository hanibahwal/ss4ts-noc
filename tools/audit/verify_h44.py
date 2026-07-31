from pathlib import Path
import re
import subprocess
import sys

FILE = Path(
    "frontend/src/components/device/InterfacesTable.jsx"
)

if not FILE.exists():
    print("❌ FAIL: InterfacesTable.jsx غير موجود")
    sys.exit(1)

text = FILE.read_text()


def check_import(name):
    match = re.search(
        r"import\s*\{(?P<body>.*?)\}\s*from\s*['\"]\.\./ui['\"]",
        text,
        re.S,
    )

    if not match:
        return False

    return bool(
        re.search(
            rf"\b{re.escape(name)}\b",
            match.group("body"),
        )
    )


checks = [
    (
        check_import("SSTable"),
        "SSTable مستورد من ../ui",
    ),
    (
        text.count("<SSTable") == 1,
        "يوجد استخدام واحد لـ SSTable",
    ),
    (
        "columns={interfaceColumns}" in text,
        "columns مربوطة",
    ),
    (
        "rows={displayedInterfaces}" in text,
        "rows مربوطة",
    ),
    (
        bool(
            re.search(
                r"rowKey=\{\s*\(row\)\s*=>\s*row\.if_descr\s*\}",
                text,
                re.S,
            )
        ),
        "rowKey مربوط",
    ),
    (
        bool(
            re.search(
                r"selectedRowKey=\{\s*effectiveSelectedInterface\s*\}",
                text,
                re.S,
            )
        ),
        "selectedRowKey مربوط",
    ),
    (
        "sortColumn={sortColumn}" in text,
        "sortColumn مربوط",
    ),
    (
        "sortDirection={sortDirection}" in text,
        "sortDirection مربوط",
    ),
    (
        "onSort={handleSort}" in text,
        "onSort مربوط",
    ),
    (
        bool(
            re.search(
                r"onRowDoubleClick=\{\s*\(row\)\s*=>.*?selectInterface\(\s*row\.if_descr",
                text,
                re.S,
            )
        ),
        "onRowDoubleClick مربوط",
    ),
    (
        "rowClassName=" in text,
        "rowClassName مربوط",
    ),
    (
        "rowAriaLabel=" in text,
        "rowAriaLabel مربوط",
    ),
    (
        'density="compact"' in text,
        "density=compact",
    ),
    (
        "stickyHeader" in text,
        "stickyHeader",
    ),
    (
        "striped" in text,
        "striped",
    ),
    (
        "hoverable" in text,
        "hoverable",
    ),
    (
        "bordered" in text,
        "bordered",
    ),
    (
        "emptyTitle=" in text,
        "emptyTitle",
    ),
    (
        "emptyDescription=" in text,
        "emptyDescription",
    ),
    (
        '<table className="interfaces-pro-table">' not in text,
        "تم حذف الجدول القديم",
    ),
    (
        "<thead>" not in text,
        "تم حذف thead",
    ),
    (
        "<tbody>" not in text,
        "تم حذف tbody",
    ),
]

print("=" * 70)
print(" Sprint 1.6.2-D3.1-H4.4 FINAL AUDIT ")
print("=" * 70)

failed = []

for ok, msg in checks:
    print(f"{'✅ PASS' if ok else '❌ FAIL'}  {msg}")
    if not ok:
        failed.append(msg)

print()
print(f"Passed : {len(checks)-len(failed)}/{len(checks)}")
print(f"Failed : {len(failed)}/{len(checks)}")

if failed:
    print("\nالعناصر الناقصة:")
    for item in failed:
        print(f" - {item}")
    sys.exit(1)

print("\nتشغيل npm build...\n")

build = subprocess.run(
    ["npm", "run", "build"],
    cwd="frontend",
)

if build.returncode != 0:
    print("❌ Build Failed")
    sys.exit(build.returncode)

print("\nتشغيل git diff --check...\n")

gitcheck = subprocess.run(
    [
        "git",
        "diff",
        "--check",
        "--",
        str(FILE),
    ]
)

if gitcheck.returncode != 0:
    print("❌ Git whitespace check failed")
    sys.exit(gitcheck.returncode)

print()
print("=" * 70)
print("🎉 SUCCESS")
print("✅ Sprint 1.6.2-D3.1-H4.4 مكتمل 100%")
print("=" * 70)
