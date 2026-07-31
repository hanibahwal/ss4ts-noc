from pathlib import Path
import re
import subprocess
import sys


ROOT = Path("/opt/ss4ts-noc")
SRC = ROOT / "frontend/src"

FILES = {
    "SSTable JSX": (
        SRC / "components/ui/SSTable.jsx"
    ),
    "SSTable CSS": (
        SRC / "components/ui/SSTable.css"
    ),
    "UI index": (
        SRC / "components/ui/index.js"
    ),
    "Interfaces JSX": (
        SRC / "components/device/InterfacesTable.jsx"
    ),
    "Interfaces CSS": (
        SRC / "styles/interfaces-pro.css"
    ),
    "Decision JSX": (
        SRC / (
            "components/device/"
            "DecisionIntelligenceCenter.jsx"
        )
    ),
    "Decision CSS": (
        SRC / (
            "components/device/"
            "DecisionIntelligenceCenter.css"
        )
    ),
}


def fail(message, exit_code=1):
    print()
    print(f"❌ {message}")
    sys.exit(exit_code)


def read(path):
    return path.read_text(
        encoding="utf-8",
        errors="ignore",
    )


def run(command, cwd=ROOT):
    return subprocess.run(
        command,
        cwd=cwd,
    )


def check_import(text, name):
    match = re.search(
        r"import\s*\{(?P<body>.*?)\}\s*"
        r"from\s*['\"]\.\./ui['\"]",
        text,
        re.S,
    )

    return bool(
        match
        and re.search(
            rf"\b{re.escape(name)}\b",
            match.group("body"),
        )
    )


def find_manual_tables():
    results = []

    suffixes = {
        ".js",
        ".jsx",
        ".ts",
        ".tsx",
    }

    for path in sorted(
        item
        for item in SRC.rglob("*")
        if item.is_file()
        and item.suffix in suffixes
    ):
        text = read(path)

        lines = [
            text[:match.start()].count("\n") + 1
            for match in re.finditer(
                r"<table(?:\s|>)",
                text,
            )
        ]

        if lines:
            results.append(
                (
                    path.relative_to(ROOT),
                    lines,
                )
            )

    return results


def find_sstable_usages():
    results = []

    suffixes = {
        ".js",
        ".jsx",
        ".ts",
        ".tsx",
    }

    for path in sorted(
        item
        for item in SRC.rglob("*")
        if item.is_file()
        and item.suffix in suffixes
    ):
        text = read(path)

        lines = [
            text[:match.start()].count("\n") + 1
            for match in re.finditer(
                r"<SSTable(?:\s|>)",
                text,
            )
        ]

        if lines:
            results.append(
                (
                    path.relative_to(ROOT),
                    lines,
                )
            )

    return results


missing_files = [
    str(path)
    for path in FILES.values()
    if not path.exists()
]

if missing_files:
    print("❌ ملفات مطلوبة غير موجودة:")

    for path in missing_files:
        print(f"  - {path}")

    sys.exit(1)


sstable_jsx = read(FILES["SSTable JSX"])
sstable_css = read(FILES["SSTable CSS"])
ui_index = read(FILES["UI index"])
interfaces_jsx = read(FILES["Interfaces JSX"])
interfaces_css = read(FILES["Interfaces CSS"])
decision_jsx = read(FILES["Decision JSX"])
decision_css = read(FILES["Decision CSS"])


manual_tables = find_manual_tables()
sstable_usages = find_sstable_usages()

allowed_manual_table_files = {
    Path(
        "frontend/src/components/ui/SSTable.jsx"
    ),
}

unexpected_manual_tables = [
    (path, lines)
    for path, lines in manual_tables
    if path not in allowed_manual_table_files
]


checks = []


def add_check(passed, label, section):
    checks.append(
        {
            "passed": bool(passed),
            "label": label,
            "section": section,
        }
    )


# =========================================================
# H1 — Inventory
# =========================================================

add_check(
    not unexpected_manual_tables,
    "لا توجد جداول HTML يدوية خارج SSTable",
    "H1 — Project Tables Inventory",
)

add_check(
    len(sstable_usages) == 2,
    "يوجد استخدامان إنتاجيان لـ SSTable",
    "H1 — Project Tables Inventory",
)

sstable_usage_paths = {
    str(path)
    for path, _ in sstable_usages
}

add_check(
    (
        "frontend/src/components/device/"
        "DecisionIntelligenceCenter.jsx"
    ) in sstable_usage_paths,
    "Decision Intelligence يستخدم SSTable",
    "H1 — Project Tables Inventory",
)

add_check(
    (
        "frontend/src/components/device/"
        "InterfacesTable.jsx"
    ) in sstable_usage_paths,
    "Interfaces يستخدم SSTable",
    "H1 — Project Tables Inventory",
)

add_check(
    "export { default as SSTable }"
    in ui_index,
    "SSTable مصدّر من UI index",
    "H1 — Project Tables Inventory",
)


# =========================================================
# H2 — Consistency
# =========================================================

common_props = [
    "columns",
    "rows",
    "rowKey",
    "density",
    "stickyHeader",
    "striped",
    "hoverable",
    "bordered",
    "emptyTitle",
    "emptyDescription",
]

for prop in common_props:
    add_check(
        prop in decision_jsx,
        f"Decision يحتوي الخاصية {prop}",
        "H2 — SSTable Consistency",
    )

    add_check(
        prop in interfaces_jsx,
        f"Interfaces يحتوي الخاصية {prop}",
        "H2 — SSTable Consistency",
    )


# =========================================================
# H3 — Decision Table Hardening
# =========================================================

expected_decision_columns = [
    "stage",
    "title",
    "description",
    "status",
]

decision_columns_match = re.search(
    r"const\s+DECISION_PILOT_COLUMNS\s*=\s*"
    r"\[(?P<body>.*?)\]\s*",
    decision_jsx,
    re.S,
)

decision_column_keys = []

if decision_columns_match:
    decision_column_keys = re.findall(
        r"key:\s*['\"]([^'\"]+)['\"]",
        decision_columns_match.group("body"),
    )

add_check(
    "const DECISION_PILOT_COLUMNS" in decision_jsx,
    "DECISION_PILOT_COLUMNS موجودة",
    "H3 — Decision Table Hardening",
)

add_check(
    "const decisionPilotRows" in decision_jsx,
    "decisionPilotRows موجودة",
    "H3 — Decision Table Hardening",
)

add_check(
    decision_column_keys
    == expected_decision_columns,
    "أعمدة Decision صحيحة وبالترتيب",
    "H3 — Decision Table Hardening",
)

add_check(
    "columns={DECISION_PILOT_COLUMNS}"
    in decision_jsx,
    "أعمدة Decision مربوطة",
    "H3 — Decision Table Hardening",
)

add_check(
    "rows={decisionPilotRows}"
    in decision_jsx,
    "صفوف Decision مربوطة",
    "H3 — Decision Table Hardening",
)

add_check(
    'rowKey="id"' in decision_jsx,
    "Decision يستخدم rowKey=id",
    "H3 — Decision Table Hardening",
)

decision_legacy_markers = [
    ".decision-pilot-table table",
    ".decision-pilot-table thead",
    ".decision-pilot-table tbody",
    ".decision-pilot-table th",
    ".decision-pilot-table td",
]

for marker in decision_legacy_markers:
    add_check(
        marker not in decision_css,
        f"CSS قديم غير موجود: {marker}",
        "H3 — Decision Table Hardening",
    )


# =========================================================
# H4 — Accessibility & Keyboard
# =========================================================

accessibility_checks = [
    (
        "aria-sort=" in sstable_jsx,
        "aria-sort موجود",
    ),
    (
        "'ascending'" in sstable_jsx,
        "حالة ascending مدعومة",
    ),
    (
        "'descending'" in sstable_jsx,
        "حالة descending مدعومة",
    ),
    (
        "'none'" in sstable_jsx,
        "حالة sort none مدعومة",
    ),
    (
        'scope="col"' in sstable_jsx,
        "scope=col موجود",
    ),
    (
        "aria-selected" in sstable_jsx,
        "aria-selected موجود",
    ),
    (
        "rowAriaLabel" in sstable_jsx,
        "rowAriaLabel مدعوم",
    ),
    (
        "aria-label" in sstable_jsx,
        "aria-label موجود",
    ),
    (
        "tabIndex" in sstable_jsx,
        "tabIndex موجود",
    ),
    (
        "onKeyDown" in sstable_jsx,
        "onKeyDown موجود",
    ),
    (
        "event.key ===" in sstable_jsx
        and "'Enter'" in sstable_jsx,
        "مفتاح Enter مدعوم",
    ),
    (
        "event.key ===" in sstable_jsx
        and "' '" in sstable_jsx,
        "مفتاح Space مدعوم",
    ),
    (
        "event.preventDefault()" in sstable_jsx,
        "منع السلوك الافتراضي موجود",
    ),
    (
        ":focus-visible" in sstable_css,
        "focus-visible موجود",
    ),
    (
        ".is-interactive" in sstable_css,
        "تنسيق الصف التفاعلي موجود",
    ),
    (
        "rowAriaLabel=" in interfaces_jsx,
        "Interfaces يمرر rowAriaLabel",
    ),
    (
        "onRowDoubleClick="
        in interfaces_jsx,
        "Interfaces يمرر النقر المزدوج",
    ),
]

for passed, label in accessibility_checks:
    add_check(
        passed,
        label,
        "H4 — Accessibility & Keyboard",
    )


# =========================================================
# H5 — Visual & Responsive
# =========================================================

visual_checks = [
    (
        ".ss-ui-table-wrap" in sstable_css,
        "Table wrapper موجود",
    ),
    (
        "overflow-x: auto;" in sstable_css,
        "التمرير الأفقي مفعل",
    ),
    (
        "max-width: 100%;" in sstable_css,
        "max-width للحاوية موجود",
    ),
    (
        "min-width: 0;" in sstable_css,
        "min-width للحاوية موجود",
    ),
    (
        "text-overflow: ellipsis;"
        in sstable_css,
        "ellipsis للنصوص الطويلة موجود",
    ),
    (
        "overflow: hidden;" in sstable_css,
        "إخفاء تجاوز النص موجود",
    ),
    (
        "white-space: nowrap;"
        in sstable_css,
        "nowrap موجود",
    ),
    (
        "position: sticky;"
        in sstable_css,
        "Sticky Header موجود",
    ),
    (
        "top: 0;" in sstable_css,
        "Sticky Header مثبت من الأعلى",
    ),
    (
        ".ss-ui-table-wrap--density-compact"
        in sstable_css,
        "Compact density موجود",
    ),
    (
        ".ss-ui-table-wrap--density-comfortable"
        in sstable_css,
        "Comfortable density موجود",
    ),
    (
        "@media" in sstable_css,
        "Responsive media query موجود",
    ),
    (
        ".is-selected" in sstable_css,
        "تنسيق الصف المحدد موجود",
    ),
    (
        ".has-errors" in sstable_css,
        "تنسيق صف الأخطاء موجود",
    ),
    (
        ".is-down" in sstable_css,
        "تنسيق الصف المتوقف موجود",
    ),
    (
        ".interfaces-pro-table-wrapper"
        in interfaces_css,
        "Interfaces wrapper محفوظ",
    ),
    (
        ".decision-pilot-table"
        in decision_css,
        "Decision wrapper محفوظ",
    ),
]

for passed, label in visual_checks:
    add_check(
        passed,
        label,
        "H5 — Visual & Responsive",
    )


# =========================================================
# H6 — Final Regression
# =========================================================

interface_required_features = [
    "searchTerm",
    "setSearchTerm",
    "statusFilter",
    "setStatusFilter",
    "sortColumn",
    "sortDirection",
    "handleSort",
    "effectiveSelectedInterface",
    "renderActionCell",
    "onRowDoubleClick=",
    "rowClassName=",
    "rowAriaLabel=",
    "has-errors",
    "is-down",
]

for feature in interface_required_features:
    add_check(
        feature in interfaces_jsx,
        f"Interface regression محفوظ: {feature}",
        "H6 — Final Regression",
    )

legacy_interface_markers = [
    '<table className="interfaces-pro-table">',
    "<thead>",
    "<tbody>",
    "function SortButton(",
    "interfaces-pro-sort",
]

for marker in legacy_interface_markers:
    add_check(
        marker not in interfaces_jsx,
        f"Legacy JSX محذوف: {marker}",
        "H6 — Final Regression",
    )

add_check(
    not re.search(
        r"\.interfaces-pro-table"
        r"(?!-wrapper)",
        interfaces_css,
    ),
    "Legacy Interfaces table CSS محذوف",
    "H6 — Final Regression",
)

add_check(
    ".interfaces-pro-sort"
    not in interfaces_css,
    "Legacy sort CSS محذوف",
    "H6 — Final Regression",
)

add_check(
    check_import(
        interfaces_jsx,
        "SSTable",
    ),
    "Interfaces يستورد SSTable",
    "H6 — Final Regression",
)

add_check(
    check_import(
        decision_jsx,
        "SSTable",
    ),
    "Decision يستورد SSTable",
    "H6 — Final Regression",
)


# =========================================================
# Print audit
# =========================================================

print("=" * 88)
print(
    " Sprint 1.6.2-D3.2-H6 "
    "— SSTABLE FINAL REGRESSION & ROLLOUT CLOSURE"
)
print("=" * 88)

sections = [
    "H1 — Project Tables Inventory",
    "H2 — SSTable Consistency",
    "H3 — Decision Table Hardening",
    "H4 — Accessibility & Keyboard",
    "H5 — Visual & Responsive",
    "H6 — Final Regression",
]

all_failed = []

section_results = {}

for section in sections:
    section_checks = [
        item
        for item in checks
        if item["section"] == section
    ]

    section_failed = [
        item
        for item in section_checks
        if not item["passed"]
    ]

    section_results[section] = (
        len(section_checks),
        len(section_failed),
    )

    print()
    print(section)
    print("-" * 88)

    for item in section_checks:
        print(
            f"{'✅ PASS' if item['passed'] else '❌ FAIL'} "
            f"{item['label']}"
        )

        if not item["passed"]:
            all_failed.append(
                (
                    section,
                    item["label"],
                )
            )


print()
print("=" * 88)
print(" INVENTORY DETAILS")
print("=" * 88)

print()
print("Manual HTML tables:")

for path, lines in manual_tables:
    marker = (
        "✅ ALLOWED"
        if path in allowed_manual_table_files
        else "❌ UNEXPECTED"
    )

    print(
        f"{marker} {path} "
        f"lines={','.join(map(str, lines))}"
    )

print()
print("SSTable usages:")

for path, lines in sstable_usages:
    print(
        f"✅ {path} "
        f"lines={','.join(map(str, lines))}"
    )

print()
print(
    "Decision columns:",
    decision_column_keys,
)


# =========================================================
# Stop before build on structural failures
# =========================================================

print()
print("=" * 88)
print(" STATIC SUMMARY")
print("=" * 88)

total_checks = len(checks)
failed_count = len(all_failed)

print(
    f"Passed: {total_checks - failed_count}/"
    f"{total_checks}"
)

print(
    f"Failed: {failed_count}/"
    f"{total_checks}"
)

if all_failed:
    print()
    print("❌ توجد مشاكل تمنع إغلاق Sprint:")

    for section, label in all_failed:
        print(
            f"  - [{section}] {label}"
        )

    sys.exit(1)


# =========================================================
# Build
# =========================================================

print()
print("=" * 88)
print(" FRONTEND BUILD")
print("=" * 88)

build = run(
    ["npm", "run", "build"],
    cwd=ROOT / "frontend",
)

if build.returncode != 0:
    fail(
        "فشل npm run build",
        build.returncode,
    )

print("✅ Frontend build ناجح")


# =========================================================
# Scoped Git check
# =========================================================

print()
print("=" * 88)
print(" SCOPED GIT WHITESPACE CHECK")
print("=" * 88)

scoped_paths = [
    str(
        path.relative_to(ROOT)
    )
    for path in FILES.values()
]

git_check = run(
    [
        "git",
        "diff",
        "--check",
        "--",
        *scoped_paths,
    ],
)

if git_check.returncode != 0:
    fail(
        "فشل git diff --check "
        "على ملفات SSTable Rollout",
        git_check.returncode,
    )

print("✅ Scoped git diff --check ناجح")


# =========================================================
# Commit history evidence
# =========================================================

print()
print("=" * 88)
print(" ROLLOUT COMMIT HISTORY")
print("=" * 88)

log = subprocess.run(
    [
        "git",
        "log",
        "--oneline",
        "-12",
    ],
    cwd=ROOT,
    capture_output=True,
    text=True,
)

if log.returncode == 0:
    print(log.stdout.rstrip())
else:
    print(
        "⚠️ تعذر عرض Git history، "
        "لكن بقية الفحوص نجحت."
    )


# =========================================================
# Final summary
# =========================================================

print()
print("=" * 88)
print(" Sprint 1.6.2-D3.2 — FINAL ROLLOUT SUMMARY")
print("=" * 88)

for section in sections:
    total, failed = section_results[section]

    status = (
        "✅ PASS"
        if failed == 0
        else "❌ FAIL"
    )

    print(
        f"{status} "
        f"{section} "
        f"({total - failed}/{total})"
    )

print()
print("Build ............. ✅ PASS")
print("Git check ......... ✅ PASS")
print("Regression ........ ✅ PASS")
print("Legacy cleanup .... ✅ PASS")
print("Accessibility ..... ✅ PASS")
print("Responsive ........ ✅ PASS")

print()
print("🎉 Sprint 1.6.2-D3.2 مكتمل تقنيًا بنسبة 100%")
print(
    "✅ H6 — SSTable Final Regression "
    "& Rollout Closure مكتمل"
)
print("=" * 88)
