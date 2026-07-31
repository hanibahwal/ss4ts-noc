from pathlib import Path
import re
import subprocess
import sys


ROOT = Path("/opt/ss4ts-noc")

COMPONENT = ROOT / (
    "frontend/src/components/device/"
    "InterfacesTable.jsx"
)

TABLE_COMPONENT = ROOT / (
    "frontend/src/components/ui/"
    "SSTable.jsx"
)

TABLE_CSS = ROOT / (
    "frontend/src/components/ui/"
    "SSTable.css"
)

LEGACY_CSS = ROOT / (
    "frontend/src/styles/"
    "interfaces-pro.css"
)


required_files = [
    COMPONENT,
    TABLE_COMPONENT,
    TABLE_CSS,
    LEGACY_CSS,
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


component_text = COMPONENT.read_text()
table_text = TABLE_COMPONENT.read_text()
table_css_text = TABLE_CSS.read_text()
legacy_css_text = LEGACY_CSS.read_text()


checks = [
    (
        component_text.count("<SSTable") == 1,
        "يوجد استخدام واحد لـ SSTable",
    ),
    (
        '<table className="interfaces-pro-table">'
        not in component_text,
        "الجدول التقليدي محذوف من JSX",
    ),
    (
        "<thead>" not in component_text,
        "thead التقليدي محذوف",
    ),
    (
        "<tbody>" not in component_text,
        "tbody التقليدي محذوف",
    ),
    (
        "columns={interfaceColumns}"
        in component_text,
        "Interface Columns Adapter مربوط",
    ),
    (
        "rows={displayedInterfaces}"
        in component_text,
        "الصفوف المفلترة مربوطة",
    ),
    (
        "searchTerm" in component_text
        and "setSearchTerm" in component_text,
        "البحث ما زال موجودًا",
    ),
    (
        "statusFilter" in component_text
        and "setStatusFilter" in component_text,
        "فلتر الحالة ما زال موجودًا",
    ),
    (
        "sortColumn" in component_text
        and "sortDirection" in component_text
        and "handleSort" in component_text,
        "الفرز ما زال موجودًا",
    ),
    (
        "effectiveSelectedInterface"
        in component_text,
        "حالة الواجهة المحددة موجودة",
    ),
    (
        "onRowDoubleClick="
        in component_text,
        "النقر المزدوج موجود",
    ),
    (
        "renderActionCell"
        in component_text,
        "زر عرض الرسم موجود",
    ),
    (
        "rowClassName="
        in component_text
        and "has-errors" in component_text
        and "is-down" in component_text,
        "تمييز الأخطاء والتوقف موجود",
    ),
    (
        "loading" in component_text,
        "حالة التحميل موجودة",
    ),
    (
        "error" in component_text,
        "حالة الخطأ موجودة",
    ),
    (
        "emptyTitle=" in component_text
        and "emptyDescription="
        in component_text,
        "حالة النتائج الفارغة موجودة",
    ),
    (
        "onRowClick" in table_text,
        "SSTable يدعم النقر على الصف",
    ),
    (
        "onRowDoubleClick" in table_text,
        "SSTable يدعم النقر المزدوج",
    ),
    (
        "rowClassName" in table_text,
        "SSTable يدعم تنسيق الصف",
    ),
    (
        "selectedRowKey" in table_text,
        "SSTable يدعم تحديد الصف",
    ),
    (
        "onSort" in table_text,
        "SSTable يدعم الفرز",
    ),
    (
        ".ss-ui-table" in table_css_text,
        "CSS الخاص بـ SSTable موجود",
    ),
]


legacy_selectors = [
    ".interfaces-pro-table",
    ".interfaces-pro-sort",
]

legacy_findings = {}

for selector in legacy_selectors:
    legacy_findings[selector] = [
        index
        for index, line in enumerate(
            legacy_css_text.splitlines(),
            start=1,
        )
        if selector in line
    ]


print("=" * 72)
print(" Sprint 1.6.2-D3.1-H4.5 — REGRESSION AUDIT")
print("=" * 72)

failed = []

for passed, label in checks:
    print(
        f"{'✅ PASS' if passed else '❌ FAIL'} "
        f"{label}"
    )

    if not passed:
        failed.append(label)


print()
print("=" * 72)
print(" LEGACY CSS INVENTORY")
print("=" * 72)

for selector, lines in legacy_findings.items():
    if lines:
        print(
            f"⚠️ FOUND  {selector} "
            f"في الأسطر: "
            f"{', '.join(map(str, lines))}"
        )
    else:
        print(
            f"✅ CLEAN  {selector}"
        )


print()
print("=" * 72)
print(" UNUSED LEGACY JSX CHECK")
print("=" * 72)

legacy_jsx_markers = [
    "interfaces-pro-table",
    "interfaces-pro-sort",
]

for marker in legacy_jsx_markers:
    count = component_text.count(marker)

    print(
        f"{marker}: JSX occurrences={count}"
    )


print()
print(
    f"Functional checks passed: "
    f"{len(checks) - len(failed)}/"
    f"{len(checks)}"
)

if failed:
    print()
    print("❌ فشل Regression Audit:")

    for item in failed:
        print(f"  - {item}")

    sys.exit(1)


print()
print("=" * 72)
print(" BUILD CHECK")
print("=" * 72)

build = subprocess.run(
    ["npm", "run", "build"],
    cwd=ROOT / "frontend",
)

if build.returncode != 0:
    print()
    print("❌ فشل npm run build")
    sys.exit(build.returncode)


print()
print("=" * 72)
print(" GIT WHITESPACE CHECK")
print("=" * 72)

git_check = subprocess.run(
    [
        "git",
        "diff",
        "--check",
        "--",
        str(COMPONENT.relative_to(ROOT)),
        str(TABLE_COMPONENT.relative_to(ROOT)),
        str(TABLE_CSS.relative_to(ROOT)),
        str(LEGACY_CSS.relative_to(ROOT)),
    ],
    cwd=ROOT,
)

if git_check.returncode != 0:
    print()
    print("❌ فشل git diff --check")
    sys.exit(git_check.returncode)


print()
print("=" * 72)
print("✅ Regression Audit ناجح")
print("⚠️ لم يتم حذف CSS القديم بعد")
print(
    "الخطوة التالية: مراجعة نتائج "
    "LEGACY CSS INVENTORY قبل الحذف."
)
print("=" * 72)
