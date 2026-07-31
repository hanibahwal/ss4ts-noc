from pathlib import Path
import json
import re
import subprocess
import sys


ROOT = Path("/opt/ss4ts-noc")
FRONTEND = ROOT / "frontend"
SRC = FRONTEND / "src"
DIST = FRONTEND / "dist"

PACKAGE_JSON = FRONTEND / "package.json"
VITE_CONFIGS = [
    FRONTEND / "vite.config.js",
    FRONTEND / "vite.config.mjs",
    FRONTEND / "vite.config.ts",
]

CODE_SUFFIXES = {
    ".js",
    ".jsx",
    ".ts",
    ".tsx",
}

if not FRONTEND.exists():
    print("❌ مجلد frontend غير موجود")
    sys.exit(1)

if not SRC.exists():
    print("❌ مجلد frontend/src غير موجود")
    sys.exit(1)

if not PACKAGE_JSON.exists():
    print("❌ frontend/package.json غير موجود")
    sys.exit(1)


def read(path):
    return path.read_text(
        encoding="utf-8",
        errors="ignore",
    )


def human_size(size):
    units = [
        "B",
        "KB",
        "MB",
        "GB",
    ]

    value = float(size)

    for unit in units:
        if value < 1024 or unit == units[-1]:
            return f"{value:.2f} {unit}"

        value /= 1024

    return f"{size} B"


def line_number(text, position):
    return text[:position].count("\n") + 1


print("=" * 88)
print(
    " Sprint 1.6.2-D3.3-P1 "
    "— BUNDLE INVENTORY & BASELINE"
)
print("=" * 88)


# =========================================================
# 1) Package inventory
# =========================================================

print()
print("1) PACKAGE INVENTORY")
print("-" * 88)

package_data = json.loads(
    read(PACKAGE_JSON)
)

dependencies = package_data.get(
    "dependencies",
    {},
)

dev_dependencies = package_data.get(
    "devDependencies",
    {},
)

print(
    f"Dependencies     : {len(dependencies)}"
)

print(
    f"Dev dependencies : {len(dev_dependencies)}"
)

heavy_candidates = [
    "recharts",
    "chart.js",
    "react-chartjs-2",
    "echarts",
    "apexcharts",
    "plotly.js",
    "framer-motion",
    "lucide-react",
    "lodash",
    "moment",
    "date-fns",
    "@mui/material",
    "antd",
]

print()
print("Heavy dependency candidates:")

found_heavy = []

for name in heavy_candidates:
    version = (
        dependencies.get(name)
        or dev_dependencies.get(name)
    )

    if version:
        found_heavy.append(
            (name, version)
        )

        print(
            f"  ⚠️ {name}: {version}"
        )

if not found_heavy:
    print(
        "  ✅ لا توجد مكتبات ثقيلة "
        "معروفة ضمن القائمة الأساسية"
    )


# =========================================================
# 2) Source files inventory
# =========================================================

print()
print("=" * 88)
print("2) SOURCE FILE SIZE INVENTORY")
print("-" * 88)

code_files = sorted(
    path
    for path in SRC.rglob("*")
    if (
        path.is_file()
        and path.suffix in CODE_SUFFIXES
    )
)

source_sizes = sorted(
    (
        path.stat().st_size,
        path,
    )
    for path in code_files
)

largest_source_files = list(
    reversed(
        source_sizes[-20:]
    )
)

for size, path in largest_source_files:
    print(
        f"{human_size(size):>12}  "
        f"{path.relative_to(ROOT)}"
    )


# =========================================================
# 3) React lazy / Suspense inventory
# =========================================================

print()
print("=" * 88)
print("3) CODE SPLITTING INVENTORY")
print("-" * 88)

lazy_usages = []
suspense_usages = []
dynamic_imports = []

for path in code_files:
    text = read(path)

    for pattern, target in [
        (
            r"\bReact\.lazy\s*\(",
            lazy_usages,
        ),
        (
            r"\blazy\s*\(",
            lazy_usages,
        ),
        (
            r"<Suspense(?:\s|>)",
            suspense_usages,
        ),
        (
            r"\bimport\s*\(",
            dynamic_imports,
        ),
    ]:
        for match in re.finditer(
            pattern,
            text,
        ):
            target.append(
                (
                    path.relative_to(ROOT),
                    line_number(
                        text,
                        match.start(),
                    ),
                )
            )


def print_occurrences(
    title,
    occurrences,
):
    print()
    print(
        f"{title}: {len(occurrences)}"
    )

    for path, line in occurrences[:30]:
        print(
            f"  {path}:{line}"
        )


print_occurrences(
    "React.lazy usages",
    lazy_usages,
)

print_occurrences(
    "Suspense usages",
    suspense_usages,
)

print_occurrences(
    "Dynamic import usages",
    dynamic_imports,
)


# =========================================================
# 4) Pages and heavy components
# =========================================================

print()
print("=" * 88)
print("4) PAGE & COMPONENT INVENTORY")
print("-" * 88)

pages_dir = SRC / "pages"
components_dir = SRC / "components"

page_files = (
    sorted(
        path
        for path in pages_dir.rglob("*")
        if (
            path.is_file()
            and path.suffix in CODE_SUFFIXES
        )
    )
    if pages_dir.exists()
    else []
)

component_files = (
    sorted(
        path
        for path in components_dir.rglob("*")
        if (
            path.is_file()
            and path.suffix in CODE_SUFFIXES
        )
    )
    if components_dir.exists()
    else []
)

print(
    f"Pages      : {len(page_files)}"
)

for path in page_files:
    print(
        f"  📄 {path.relative_to(ROOT)} "
        f"({human_size(path.stat().st_size)})"
    )

print()
print(
    f"Components : {len(component_files)}"
)

large_components = [
    path
    for path in component_files
    if path.stat().st_size >= 15000
]

print(
    f"Large components >= 15 KB: "
    f"{len(large_components)}"
)

for path in sorted(
    large_components,
    key=lambda item: item.stat().st_size,
    reverse=True,
):
    print(
        f"  ⚠️ {human_size(path.stat().st_size):>10} "
        f"{path.relative_to(ROOT)}"
    )


# =========================================================
# 5) Import inventory
# =========================================================

print()
print("=" * 88)
print("5) LARGE IMPORT INVENTORY")
print("-" * 88)

import_candidates = [
    "recharts",
    "lucide-react",
    "framer-motion",
    "react-router-dom",
    "axios",
]

for library in import_candidates:
    matches = []

    for path in code_files:
        text = read(path)

        if library in text:
            matches.append(
                path.relative_to(ROOT)
            )

    print()
    print(
        f"{library}: {len(matches)} file(s)"
    )

    for path in matches:
        print(
            f"  {path}"
        )


# =========================================================
# 6) Vite configuration
# =========================================================

print()
print("=" * 88)
print("6) VITE CONFIGURATION")
print("-" * 88)

vite_config = next(
    (
        path
        for path in VITE_CONFIGS
        if path.exists()
    ),
    None,
)

if vite_config:
    config_text = read(vite_config)

    print(
        f"Config: {vite_config.relative_to(ROOT)}"
    )

    config_checks = [
        (
            "manualChunks" in config_text,
            "manualChunks",
        ),
        (
            "codeSplitting" in config_text,
            "codeSplitting",
        ),
        (
            "chunkSizeWarningLimit"
            in config_text,
            "chunkSizeWarningLimit",
        ),
        (
            "rollupOptions" in config_text,
            "rollupOptions",
        ),
        (
            "rolldownOptions" in config_text,
            "rolldownOptions",
        ),
    ]

    for passed, label in config_checks:
        print(
            f"{'✅' if passed else '—'} "
            f"{label}"
        )
else:
    print(
        "⚠️ لا يوجد ملف vite.config مخصص"
    )


# =========================================================
# 7) Build baseline
# =========================================================

print()
print("=" * 88)
print("7) PRODUCTION BUILD BASELINE")
print("-" * 88)

build = subprocess.run(
    [
        "npm",
        "run",
        "build",
    ],
    cwd=FRONTEND,
)

if build.returncode != 0:
    print()
    print("❌ فشل npm run build")
    sys.exit(build.returncode)


# =========================================================
# 8) Dist inventory
# =========================================================

print()
print("=" * 88)
print("8) DIST ASSET INVENTORY")
print("-" * 88)

if not DIST.exists():
    print(
        "❌ dist غير موجود بعد البناء"
    )
    sys.exit(1)

assets = sorted(
    (
        path.stat().st_size,
        path,
    )
    for path in DIST.rglob("*")
    if path.is_file()
)

js_assets = [
    (size, path)
    for size, path in assets
    if path.suffix == ".js"
]

css_assets = [
    (size, path)
    for size, path in assets
    if path.suffix == ".css"
]

for label, asset_group in [
    (
        "JavaScript assets",
        js_assets,
    ),
    (
        "CSS assets",
        css_assets,
    ),
]:
    print()
    print(label)

    if not asset_group:
        print("  لا توجد ملفات")
        continue

    for size, path in sorted(
        asset_group,
        reverse=True,
    ):
        print(
            f"  {human_size(size):>12} "
            f"{path.relative_to(FRONTEND)}"
        )


largest_js_size = (
    max(
        (
            size
            for size, _ in js_assets
        ),
        default=0,
    )
)

total_js_size = sum(
    size
    for size, _ in js_assets
)

total_css_size = sum(
    size
    for size, _ in css_assets
)


# =========================================================
# 9) Git check
# =========================================================

print()
print("=" * 88)
print("9) GIT WHITESPACE CHECK")
print("-" * 88)

git_check = subprocess.run(
    [
        "git",
        "diff",
        "--check",
        "--",
        "frontend",
    ],
    cwd=ROOT,
)

if git_check.returncode != 0:
    print()
    print(
        "❌ فشل git diff --check "
        "داخل frontend"
    )
    sys.exit(git_check.returncode)

print(
    "✅ Frontend git diff --check ناجح"
)


# =========================================================
# 10) Final baseline summary
# =========================================================

print()
print("=" * 88)
print(
    " Sprint 1.6.2-D3.3-P1 "
    "— PERFORMANCE BASELINE SUMMARY"
)
print("=" * 88)

print(
    f"Source files .......... {len(code_files)}"
)

print(
    f"Pages ................. {len(page_files)}"
)

print(
    f"Components ............ {len(component_files)}"
)

print(
    f"Large components ...... {len(large_components)}"
)

print(
    f"React.lazy usages ..... {len(lazy_usages)}"
)

print(
    f"Suspense usages ....... {len(suspense_usages)}"
)

print(
    f"Dynamic imports ....... {len(dynamic_imports)}"
)

print(
    f"JS asset count ........ {len(js_assets)}"
)

print(
    f"Largest JS chunk ...... "
    f"{human_size(largest_js_size)}"
)

print(
    f"Total JS size ......... "
    f"{human_size(total_js_size)}"
)

print(
    f"Total CSS size ........ "
    f"{human_size(total_css_size)}"
)

print()

if largest_js_size > 500 * 1024:
    print(
        "⚠️ أكبر JavaScript chunk "
        "يتجاوز 500 KB"
    )

    print(
        "➡️ المرحلة التالية: "
        "D3.3-P2 Route-Level Code Splitting"
    )
else:
    print(
        "✅ أكبر JavaScript chunk "
        "أقل من أو يساوي 500 KB"
    )

print()
print(
    "✅ Sprint 1.6.2-D3.3-P1 "
    "— Bundle Inventory & Baseline مكتمل"
)

print("=" * 88)
