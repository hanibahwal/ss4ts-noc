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

INTERFACES_CSS = ROOT / (
    "frontend/src/styles/"
    "interfaces-pro.css"
)

DECISION_CSS = ROOT / (
    "frontend/src/components/device/"
    "DecisionIntelligenceCenter.css"
)


required_files = [
    SSTABLE_JSX,
    SSTABLE_CSS,
    INTERFACES_CSS,
    DECISION_CSS,
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
interfaces_css = read(INTERFACES_CSS)
decision_css = read(DECISION_CSS)


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
        ".ss-ui-table-wrap" in css,
        "Table wrapper موجود",
    ),
    (
        has(
            r"\.ss-ui-table-wrap\s*\{[^}]*"
            r"overflow-x\s*:\s*auto",
            css,
            re.S,
        ),
        "التمرير الأفقي مفعل",
    ),
    (
        has(
            r"\.ss-ui-table\s*\{[^}]*"
            r"min-width\s*:",
            css,
            re.S,
        ),
        "للجدول min-width",
    ),
    (
        ".ss-ui-table-wrap--sticky" in css,
        "وضع Sticky موجود",
    ),
    (
        has(
            r"\.ss-ui-table-wrap--sticky.*?"
            r"\.ss-ui-table\s+thead",
            css,
            re.S,
        ),
        "Sticky header مربوط بـ thead",
    ),
    (
        "position: sticky" in css,
        "position: sticky موجود",
    ),
    (
        "top: 0" in css,
        "موضع الرأس ثابت من الأعلى",
    ),
    (
        ".ss-ui-table-wrap--density-compact"
        in css,
        "Compact density موجود",
    ),
    (
        ".ss-ui-table-wrap--density-comfortable"
        in css,
        "Comfortable density موجود",
    ),
    (
        "white-space: nowrap" in css,
        "منع التفاف النص موجود",
    ),
    (
        "text-overflow: ellipsis" in css
        or "overflow: hidden" in css,
        "معالجة النصوص الطويلة موجودة",
    ),
    (
        ":focus-visible" in css,
        "Focus-visible موجود",
    ),
    (
        ".is-selected" in css,
        "تنسيق الصف المحدد موجود",
    ),
    (
        ".has-errors" in css,
        "تنسيق صف الأخطاء موجود",
    ),
    (
        ".is-down" in css,
        "تنسيق الصف المتوقف موجود",
    ),
    (
        "@media" in css,
        "Media query موجود",
    ),
    (
        has(
            r"@media\s*\([^)]*max-width",
            css,
        ),
        "Responsive max-width query موجود",
    ),
    (
        "width: 100%" in css,
        "العرض الكامل موجود",
    ),
    (
        "max-width: 100%" in css
        or "min-width: 0" in css,
        "منع تجاوز الحاوية موجود",
    ),
    (
        '<table className="ss-ui-table">'
        in jsx,
        "SSTable يستخدم class الصحيح",
    ),
    (
        "stickyHeader" in jsx,
        "دعم stickyHeader موجود",
    ),
    (
        "density" in jsx,
        "دعم density موجود",
    ),
    (
        ".interfaces-pro-table-wrapper"
        in interfaces_css,
        "Interfaces wrapper محفوظ",
    ),
    (
        ".decision-pilot-table"
        in decision_css,
        "Decision table wrapper محفوظ",
    ),
]


print("=" * 82)
print(
    " Sprint 1.6.2-D3.2-H5 "
    "— SSTABLE VISUAL & RESPONSIVE AUDIT"
)
print("=" * 82)

failed = []

for passed, label in checks:
    print(
        f"{'✅ PASS' if passed else '❌ FAIL'} "
        f"{label}"
    )

    if not passed:
        failed.append(label)


print()
print("=" * 82)
print(" RESPONSIVE DETAILS")
print("=" * 82)

details = {
    "media queries":
        len(
            re.findall(
                r"@media",
                css,
            )
        ),
    "sticky declarations":
        css.count("position: sticky"),
    "overflow-x declarations":
        css.count("overflow-x"),
    "min-width declarations":
        css.count("min-width"),
    "focus-visible declarations":
        css.count(":focus-visible"),
    "ellipsis declarations":
        css.count("text-overflow"),
}

for label, value in details.items():
    print(f"{label}: {value}")


print()
print("=" * 82)
print(" BUILD CHECK")
print("=" * 82)

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
print("=" * 82)
print(" GIT CHECK")
print("=" * 82)

git_check = subprocess.run(
    [
        "git",
        "diff",
        "--check",
        "--",
        str(SSTABLE_JSX.relative_to(ROOT)),
        str(SSTABLE_CSS.relative_to(ROOT)),
        str(INTERFACES_CSS.relative_to(ROOT)),
        str(DECISION_CSS.relative_to(ROOT)),
    ],
    cwd=ROOT,
)

if git_check.returncode != 0:
    print()
    print("❌ فشل git diff --check")
    sys.exit(git_check.returncode)


print()
print("=" * 82)

if failed:
    print(
        "⚠️ D3.2-H5 Audit اكتمل مع ملاحظات."
    )

    print(
        "الخطوة التالية ستكون إضافة "
        "التحسينات البصرية الناقصة فقط."
    )

    sys.exit(2)

print(
    "✅ Sprint 1.6.2-D3.2-H5 "
    "— SSTable Visual & Responsive Hardening مكتمل"
)

print("=" * 82)
