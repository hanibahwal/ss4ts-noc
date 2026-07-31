from pathlib import Path
import re
import subprocess
import sys


ROOT = Path("/opt/ss4ts-noc")
FRONTEND = ROOT / "frontend"
SRC = FRONTEND / "src"

APP = SRC / "App.jsx"
APP_CSS = SRC / "App.css"

CODE_SUFFIXES = {
    ".js",
    ".jsx",
    ".ts",
    ".tsx",
}


def read(path):
    return path.read_text(
        encoding="utf-8",
        errors="ignore",
    )


def line_number(text, position):
    return text[:position].count("\n") + 1


def section(title):
    print()
    print("=" * 92)
    print(title)
    print("=" * 92)


required = [
    APP,
    APP_CSS,
]

missing = [
    str(path)
    for path in required
    if not path.exists()
]

if missing:
    print("❌ ملفات مطلوبة غير موجودة:")

    for path in missing:
        print(f"  - {path}")

    sys.exit(1)


code_files = sorted(
    path
    for path in SRC.rglob("*")
    if (
        path.is_file()
        and path.suffix in CODE_SUFFIXES
    )
)

app_text = read(APP)
app_css = read(APP_CSS)


print("=" * 92)
print(
    " Sprint 1.6.2-D3.4-H3 "
    "— LOADING, ERROR & SUSPENSE UX AUDIT"
)
print("=" * 92)


# =========================================================
# 1) Suspense / Route fallback
# =========================================================

section("1) SUSPENSE & ROUTE FALLBACK")

checks = [
    (
        "Suspense" in app_text,
        "Suspense مستورد",
    ),
    (
        "<Suspense" in app_text,
        "Suspense مستخدم",
    ),
    (
        "function RouteFallback()" in app_text,
        "RouteFallback موجود",
    ),
    (
        "fallback={<RouteFallback />}"
        in app_text,
        "RouteFallback مربوط",
    ),
    (
        'role="status"' in app_text,
        "RouteFallback يستخدم role=status",
    ),
    (
        'aria-live="polite"' in app_text,
        "RouteFallback يستخدم aria-live",
    ),
    (
        'aria-busy="true"' in app_text,
        "RouteFallback يستخدم aria-busy",
    ),
    (
        "جارٍ تحميل الصفحة" in app_text,
        "رسالة التحميل عربية وواضحة",
    ),
    (
        ".route-loading" in app_css,
        "CSS خاص بـ route-loading موجود",
    ),
]

for passed, label in checks:
    print(
        f"{'✅ PASS' if passed else '❌ FAIL'} "
        f"{label}"
    )


# =========================================================
# 2) Loading state inventory
# =========================================================

section("2) LOADING STATE INVENTORY")

loading_patterns = [
    r"\bloading\b",
    r"\bisLoading\b",
    r"\bloading[A-Z]\w*",
    r"جارٍ التحميل",
    r"جاري التحميل",
]

loading_results = []

for path in code_files:
    text = read(path)

    for pattern in loading_patterns:
        for match in re.finditer(
            pattern,
            text,
            re.I,
        ):
            loading_results.append(
                (
                    path.relative_to(ROOT),
                    line_number(
                        text,
                        match.start(),
                    ),
                    text.splitlines()[
                        line_number(
                            text,
                            match.start(),
                        ) - 1
                    ].strip(),
                )
            )


print(
    f"Loading references: "
    f"{len(loading_results)}"
)

for path, line, content in loading_results[:80]:
    print(
        f"  {path}:{line} "
        f"{content[:140]}"
    )


# =========================================================
# 3) Error state inventory
# =========================================================

section("3) ERROR STATE INVENTORY")

error_patterns = [
    r"\berror\b",
    r"\bhasError\b",
    r"\bsetError\b",
    r"فشل",
    r"خطأ",
    r"تعذر",
]

error_results = []

for path in code_files:
    text = read(path)

    for pattern in error_patterns:
        for match in re.finditer(
            pattern,
            text,
            re.I,
        ):
            error_results.append(
                (
                    path.relative_to(ROOT),
                    line_number(
                        text,
                        match.start(),
                    ),
                    text.splitlines()[
                        line_number(
                            text,
                            match.start(),
                        ) - 1
                    ].strip(),
                )
            )


print(
    f"Error references: "
    f"{len(error_results)}"
)

for path, line, content in error_results[:100]:
    print(
        f"  {path}:{line} "
        f"{content[:140]}"
    )


# =========================================================
# 4) Retry actions
# =========================================================

section("4) RETRY ACTIONS")

retry_patterns = [
    r"retry",
    r"refetch",
    r"إعادة المحاولة",
    r"حاول مرة أخرى",
]

retry_results = []

for path in code_files:
    text = read(path)

    for pattern in retry_patterns:
        for match in re.finditer(
            pattern,
            text,
            re.I,
        ):
            retry_results.append(
                (
                    path.relative_to(ROOT),
                    line_number(
                        text,
                        match.start(),
                    ),
                    text.splitlines()[
                        line_number(
                            text,
                            match.start(),
                        ) - 1
                    ].strip(),
                )
            )


print(
    f"Retry references: "
    f"{len(retry_results)}"
)

for path, line, content in retry_results[:60]:
    print(
        f"  {path}:{line} "
        f"{content[:140]}"
    )


# =========================================================
# 5) Error boundaries
# =========================================================

section("5) ERROR BOUNDARY INVENTORY")

boundary_markers = [
    "ErrorBoundary",
    "getDerivedStateFromError",
    "componentDidCatch",
    "react-error-boundary",
]

for marker in boundary_markers:
    occurrences = []

    for path in code_files:
        text = read(path)

        if marker in text:
            occurrences.append(
                path.relative_to(ROOT)
            )

    print(
        f"{'✅' if occurrences else '—'} "
        f"{marker}: {len(occurrences)}"
    )

    for path in occurrences:
        print(f"  {path}")


# =========================================================
# 6) ARIA and visual semantics
# =========================================================

section("6) LOADING & ERROR ACCESSIBILITY")

aria_checks = {
    "role=status": r'role=["\']status["\']',
    "role=alert": r'role=["\']alert["\']',
    "aria-live": r"aria-live=",
    "aria-busy": r"aria-busy=",
    "aria-label": r"aria-label=",
}

for label, pattern in aria_checks.items():
    occurrences = []

    for path in code_files:
        text = read(path)

        for match in re.finditer(
            pattern,
            text,
        ):
            occurrences.append(
                (
                    path.relative_to(ROOT),
                    line_number(
                        text,
                        match.start(),
                    ),
                )
            )

    print(
        f"{'✅' if occurrences else '⚠️'} "
        f"{label}: {len(occurrences)}"
    )

    for path, line in occurrences[:30]:
        print(
            f"  {path}:{line}"
        )


# =========================================================
# 7) Empty-state inventory
# =========================================================

section("7) EMPTY STATE INVENTORY")

empty_patterns = [
    r"لا توجد بيانات",
    r"لا توجد نتائج",
    r"emptyTitle",
    r"emptyDescription",
    r"\bisEmpty\b",
]

empty_results = []

for path in code_files:
    text = read(path)

    for pattern in empty_patterns:
        for match in re.finditer(
            pattern,
            text,
            re.I,
        ):
            empty_results.append(
                (
                    path.relative_to(ROOT),
                    line_number(
                        text,
                        match.start(),
                    ),
                    text.splitlines()[
                        line_number(
                            text,
                            match.start(),
                        ) - 1
                    ].strip(),
                )
            )


print(
    f"Empty-state references: "
    f"{len(empty_results)}"
)

for path, line, content in empty_results[:60]:
    print(
        f"  {path}:{line} "
        f"{content[:140]}"
    )


# =========================================================
# 8) App preview
# =========================================================

section("8) APP.JSX PREVIEW")

for number, line in enumerate(
    app_text.splitlines(),
    start=1,
):
    print(
        f"{number:4}: {line}"
    )


# =========================================================
# 9) App.css preview
# =========================================================

section("9) APP.CSS ROUTE LOADING PREVIEW")

css_lines = app_css.splitlines()

route_loading_lines = [
    index
    for index, line in enumerate(
        css_lines,
        start=1,
    )
    if "route-loading" in line
]

if not route_loading_lines:
    print("⚠️ لا توجد قواعد route-loading")
else:
    start = max(
        min(route_loading_lines) - 10,
        1,
    )

    end = min(
        max(route_loading_lines) + 40,
        len(css_lines),
    )

    for number in range(
        start,
        end + 1,
    ):
        print(
            f"{number:4}: "
            f"{css_lines[number - 1]}"
        )


# =========================================================
# 10) Build
# =========================================================

section("10) PRODUCTION BUILD")

build = subprocess.run(
    ["npm", "run", "build"],
    cwd=FRONTEND,
)

if build.returncode != 0:
    print()
    print("❌ فشل npm run build")
    sys.exit(build.returncode)


# =========================================================
# 11) Git check
# =========================================================

section("11) GIT WHITESPACE CHECK")

git_check = subprocess.run(
    [
        "git",
        "diff",
        "--check",
        "--",
        "frontend/src/App.jsx",
        "frontend/src/App.css",
        "frontend/src/components",
        "frontend/src/pages",
        "frontend/src/hooks",
    ],
    cwd=ROOT,
)

if git_check.returncode != 0:
    print()
    print("❌ فشل git diff --check")
    sys.exit(git_check.returncode)

print("✅ git diff --check ناجح")


# =========================================================
# 12) Summary
# =========================================================

section(
    " Sprint 1.6.2-D3.4-H3 "
    "— UX HARDENING SUMMARY"
)

has_boundary = any(
    marker in read(path)
    for path in code_files
    for marker in boundary_markers
)

print(
    f"Suspense .............. "
    f"{'YES' if '<Suspense' in app_text else 'NO'}"
)

print(
    f"Route fallback ........ "
    f"{'YES' if 'RouteFallback' in app_text else 'NO'}"
)

print(
    f"Route loading CSS ..... "
    f"{'YES' if '.route-loading' in app_css else 'NO'}"
)

print(
    f"Loading references .... "
    f"{len(loading_results)}"
)

print(
    f"Error references ...... "
    f"{len(error_results)}"
)

print(
    f"Retry references ...... "
    f"{len(retry_results)}"
)

print(
    f"Empty states .......... "
    f"{len(empty_results)}"
)

print(
    f"Error Boundary ........ "
    f"{'YES' if has_boundary else 'NO'}"
)

print()

notes = []

if ".route-loading" not in app_css:
    notes.append(
        "RouteFallback بلا تنسيق بصري واضح"
    )

if not has_boundary:
    notes.append(
        "لا يوجد Error Boundary عام للتطبيق"
    )

if not retry_results:
    notes.append(
        "لا توجد آلية Retry واضحة"
    )

if not any(
    "role=\"alert\"" in read(path)
    or "role='alert'" in read(path)
    for path in code_files
):
    notes.append(
        "حالات الخطأ لا تستخدم role=alert"
    )


if notes:
    print("⚠️ ملاحظات UX Hardening:")

    for note in notes:
        print(f"  - {note}")

    print()
    print(
        "➡️ الخطوة التالية: تنفيذ "
        "التحسينات الناقصة فقط"
    )
else:
    print(
        "✅ Loading / Error / Suspense UX "
        "جاهزة للإنتاج"
    )


print()
print(
    "✅ Sprint 1.6.2-D3.4-H3 "
    "— Audit مكتمل"
)

print("=" * 92)
