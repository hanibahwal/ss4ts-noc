from pathlib import Path
import re
import subprocess
import sys


ROOT = Path("/opt/ss4ts-noc")

SSTABLE_JSX = ROOT / (
    "frontend/src/components/ui/"
    "SSTable.jsx"
)

SSTABLE_CSS = ROOT / (
    "frontend/src/components/ui/"
    "SSTable.css"
)

DECISION = ROOT / (
    "frontend/src/components/device/"
    "DecisionIntelligenceCenter.jsx"
)

INTERFACES = ROOT / (
    "frontend/src/components/device/"
    "InterfacesTable.jsx"
)


required_files = [
    SSTABLE_JSX,
    SSTABLE_CSS,
    DECISION,
    INTERFACES,
]

missing = [
    str(path)
    for path in required_files
    if not path.exists()
]

if missing:
    print("❌ ملفات مطلوبة غير موجودة:")

    for path in missing:
        print(f"  - {path}")

    sys.exit(1)


def read(path):
    return path.read_text(
        encoding="utf-8",
        errors="ignore",
    )


jsx = read(SSTABLE_JSX)
css = read(SSTABLE_CSS)
decision = read(DECISION)
interfaces = read(INTERFACES)


def has(pattern, text, flags=0):
    return bool(
        re.search(
            pattern,
            text,
            flags,
        )
    )


checks = [
    (
        "aria-sort" in jsx,
        "رؤوس الفرز تستخدم aria-sort",
    ),
    (
        "aria-selected" in jsx,
        "الصف المحدد يستخدم aria-selected",
    ),
    (
        "tabIndex" in jsx,
        "الصفوف التفاعلية تستخدم tabIndex",
    ),
    (
        "onKeyDown" in jsx,
        "دعم لوحة المفاتيح موجود",
    ),
    (
        has(
            r"event\.key\s*===\s*['\"]Enter['\"]",
            jsx,
        ),
        "مفتاح Enter مدعوم",
    ),
    (
        has(
            r"event\.key\s*===\s*['\"] ['\"]",
            jsx,
        )
        or has(
            r"event\.key\s*===\s*['\"]Spacebar['\"]",
            jsx,
        ),
        "مفتاح Space مدعوم",
    ),
    (
        "event.preventDefault()" in jsx,
        "منع سلوك Space الافتراضي موجود",
    ),
    (
        "rowAriaLabel" in jsx,
        "SSTable يدعم rowAriaLabel",
    ),
    (
        '<table className="ss-ui-table">'
        in jsx
        and 'scope="col"' in jsx,
        "دلالات الجدول الأصلية محفوظة",
    ),
    (
        ":focus-visible" in css,
        "CSS يحتوي focus-visible",
    ),
    (
        ".is-interactive" in css,
        "تنسيق الصفوف التفاعلية موجود",
    ),
    (
        "onRowClick" in jsx,
        "onRowClick محفوظ",
    ),
    (
        "onRowDoubleClick" in jsx,
        "onRowDoubleClick محفوظ",
    ),
    (
        "selectedRowKey" in jsx,
        "selectedRowKey محفوظ",
    ),
    (
        "rowAriaLabel=" in interfaces,
        "Interfaces يمرر rowAriaLabel",
    ),
    (
        "onRowDoubleClick=" in interfaces,
        "Interfaces يمرر onRowDoubleClick",
    ),
    (
        "<SSTable" in decision,
        "Decision يستخدم SSTable",
    ),
    (
        "<SSTable" in interfaces,
        "Interfaces يستخدم SSTable",
    ),
]


print("=" * 80)
print(
    " Sprint 1.6.2-D3.2-H4 "
    "— SSTABLE ACCESSIBILITY & KEYBOARD AUDIT"
)
print("=" * 80)

failed = []

for passed, label in checks:
    print(
        f"{'✅ PASS' if passed else '❌ FAIL'} "
        f"{label}"
    )

    if not passed:
        failed.append(label)


print()
print("=" * 80)
print(" ACCESSIBILITY DETAILS")
print("=" * 80)

details = {
    "aria-sort occurrences":
        jsx.count("aria-sort"),
    "aria-selected occurrences":
        jsx.count("aria-selected"),
    "tabIndex occurrences":
        jsx.count("tabIndex"),
    "onKeyDown occurrences":
        jsx.count("onKeyDown"),
    "focus-visible occurrences":
        css.count(":focus-visible"),
}

for label, value in details.items():
    print(f"{label}: {value}")


print()
print("=" * 80)
print(" BUILD CHECK")
print("=" * 80)

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
print("=" * 80)
print(" GIT CHECK")
print("=" * 80)

git_check = subprocess.run(
    [
        "git",
        "diff",
        "--check",
        "--",
        str(SSTABLE_JSX.relative_to(ROOT)),
        str(SSTABLE_CSS.relative_to(ROOT)),
        str(DECISION.relative_to(ROOT)),
        str(INTERFACES.relative_to(ROOT)),
    ],
    cwd=ROOT,
)

if git_check.returncode != 0:
    print()
    print("❌ فشل git diff --check")
    sys.exit(git_check.returncode)


print()
print("=" * 80)

if failed:
    print(
        "⚠️ D3.2-H4 Audit اكتمل مع ملاحظات."
    )

    print(
        "الخطوة التالية ستكون إضافة "
        "خصائص الوصولية الناقصة فقط."
    )

    sys.exit(2)

print(
    "✅ Sprint 1.6.2-D3.2-H4 "
    "— SSTable Accessibility & Keyboard Hardening مكتمل"
)

print("=" * 80)
