from pathlib import Path
import json
import re
import subprocess
import sys


ROOT = Path("/opt/ss4ts-noc")
FRONTEND = ROOT / "frontend"
SRC = FRONTEND / "src"
DIST = FRONTEND / "dist"
ASSETS = DIST / "assets"

PACKAGE_JSON = FRONTEND / "package.json"

VITE_CONFIGS = [
    FRONTEND / "vite.config.js",
    FRONTEND / "vite.config.mjs",
    FRONTEND / "vite.config.ts",
]


def read(path):
    return path.read_text(
        encoding="utf-8",
        errors="ignore",
    )


def human_size(size):
    value = float(size)

    for unit in [
        "B",
        "KB",
        "MB",
        "GB",
    ]:
        if value < 1024:
            return f"{value:.2f} {unit}"

        value /= 1024

    return f"{value:.2f} TB"


def print_section(title):
    print()
    print("=" * 92)
    print(title)
    print("=" * 92)


if not FRONTEND.exists():
    print("❌ مجلد frontend غير موجود")
    sys.exit(1)

if not SRC.exists():
    print("❌ مجلد frontend/src غير موجود")
    sys.exit(1)

if not PACKAGE_JSON.exists():
    print("❌ frontend/package.json غير موجود")
    sys.exit(1)


vite_config = next(
    (
        path
        for path in VITE_CONFIGS
        if path.exists()
    ),
    None,
)

if vite_config is None:
    print("❌ لم يتم العثور على vite.config")
    sys.exit(1)


print("=" * 92)
print(
    " Sprint 1.6.2-D3.3-P3 "
    "— VENDOR BUNDLE OPTIMIZATION AUDIT"
)
print("=" * 92)


# =========================================================
# 1) Package inventory
# =========================================================

print_section("1) PACKAGE INVENTORY")

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

print()
print("Runtime dependencies:")

for name, version in sorted(
    dependencies.items()
):
    print(
        f"  {name:<30} {version}"
    )


# =========================================================
# 2) Dependency usage
# =========================================================

print_section("2) DEPENDENCY SOURCE USAGE")

code_suffixes = {
    ".js",
    ".jsx",
    ".ts",
    ".tsx",
}

code_files = sorted(
    path
    for path in SRC.rglob("*")
    if (
        path.is_file()
        and path.suffix in code_suffixes
    )
)

dependency_usage = {}

for dependency in dependencies:
    matches = []

    pattern = re.compile(
        rf"""
        (?:
            from\s+['"]{re.escape(dependency)}
            (?:/[^'"]*)?['"]
            |
            import\s*\(\s*
            ['"]{re.escape(dependency)}
            (?:/[^'"]*)?['"]
        )
        """,
        re.X,
    )

    for path in code_files:
        text = read(path)

        if pattern.search(text):
            matches.append(
                path.relative_to(ROOT)
            )

    dependency_usage[dependency] = matches


for dependency, paths in sorted(
    dependency_usage.items()
):
    print()
    print(
        f"{dependency}: {len(paths)} file(s)"
    )

    for path in paths:
        print(f"  {path}")


# =========================================================
# 3) Vite config
# =========================================================

print_section("3) VITE CONFIGURATION")

config_text = read(vite_config)

print(
    f"Config file: {vite_config.relative_to(ROOT)}"
)

print()
print("Current config:")
print("-" * 92)

for number, line in enumerate(
    config_text.splitlines(),
    start=1,
):
    print(
        f"{number:4}: {line}"
    )


config_checks = [
    (
        "manualChunks" in config_text,
        "manualChunks",
    ),
    (
        "rolldownOptions" in config_text,
        "rolldownOptions",
    ),
    (
        "rollupOptions" in config_text,
        "rollupOptions",
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
]

print()
print("Configuration features:")

for passed, label in config_checks:
    print(
        f"{'✅' if passed else '—'} "
        f"{label}"
    )


# =========================================================
# 4) Build
# =========================================================

print_section("4) PRODUCTION BUILD BASELINE")

build = subprocess.run(
    ["npm", "run", "build"],
    cwd=FRONTEND,
)

if build.returncode != 0:
    print()
    print("❌ فشل npm run build")
    sys.exit(build.returncode)


# =========================================================
# 5) Asset inventory
# =========================================================

print_section("5) JAVASCRIPT CHUNK INVENTORY")

if not ASSETS.exists():
    print("❌ dist/assets غير موجود")
    sys.exit(1)

js_assets = sorted(
    (
        path.stat().st_size,
        path,
    )
    for path in ASSETS.glob("*.js")
)

if not js_assets:
    print("❌ لا توجد JavaScript assets")
    sys.exit(1)


for size, path in sorted(
    js_assets,
    reverse=True,
):
    print(
        f"{human_size(size):>12}  "
        f"{path.name}"
    )


largest_size, largest_path = max(
    js_assets,
    key=lambda item: item[0],
)

total_js_size = sum(
    size
    for size, _ in js_assets
)


# =========================================================
# 6) Chunk content signatures
# =========================================================

print_section("6) CHUNK CONTENT SIGNATURES")

signatures = {
    "React Core": [
        "react.production",
        "createElement",
        "useState",
        "useEffect",
    ],
    "React DOM": [
        "react-dom",
        "createRoot",
        "flushSync",
    ],
    "React Router": [
        "react-router",
        "BrowserRouter",
        "useNavigate",
        "useLocation",
    ],
    "Recharts": [
        "recharts",
        "ResponsiveContainer",
        "LineChart",
        "CartesianGrid",
    ],
    "Lucide": [
        "lucide",
        "createLucideIcon",
    ],
    "D3": [
        "d3-",
        "bisector",
        "interpolate",
        "scaleLinear",
    ],
}

chunk_signatures = {}

for size, path in sorted(
    js_assets,
    reverse=True,
):
    text = read(path)

    detected = []

    for label, markers in signatures.items():
        score = sum(
            marker in text
            for marker in markers
        )

        if score:
            detected.append(
                (
                    label,
                    score,
                )
            )

    chunk_signatures[path.name] = detected

    print()
    print(
        f"{path.name} "
        f"({human_size(size)})"
    )

    if not detected:
        print(
            "  — لم يتم اكتشاف توقيع واضح"
        )
    else:
        for label, score in detected:
            print(
                f"  ⚠️ {label}: "
                f"score={score}"
            )


# =========================================================
# 7) Node modules package sizes
# =========================================================

print_section("7) NODE_MODULES PACKAGE SIZE")

node_modules = FRONTEND / "node_modules"

package_sizes = []

for dependency in dependencies:
    package_path = (
        node_modules
        / dependency
    )

    if not package_path.exists():
        continue

    total_size = sum(
        path.stat().st_size
        for path in package_path.rglob("*")
        if path.is_file()
    )

    package_sizes.append(
        (
            total_size,
            dependency,
        )
    )


for size, dependency in sorted(
    package_sizes,
    reverse=True,
):
    print(
        f"{human_size(size):>12}  "
        f"{dependency}"
    )


# =========================================================
# 8) Candidate vendor strategy
# =========================================================

print_section("8) VENDOR CHUNK CANDIDATES")

candidate_groups = {
    "vendor-react": [
        "react",
        "react-dom",
        "react-router-dom",
    ],
    "vendor-charts": [
        "recharts",
    ],
    "vendor-icons": [
        "lucide-react",
    ],
}

for chunk_name, packages in candidate_groups.items():
    installed = [
        package
        for package in packages
        if package in dependencies
    ]

    print()
    print(
        f"{chunk_name}: "
        f"{', '.join(installed) if installed else '—'}"
    )

    used_files = set()

    for package in installed:
        used_files.update(
            dependency_usage.get(
                package,
                [],
            )
        )

    print(
        f"  Source consumers: "
        f"{len(used_files)}"
    )

    for path in sorted(used_files):
        print(f"    {path}")


# =========================================================
# 9) Risk checks
# =========================================================

print_section("9) OPTIMIZATION RISK CHECKS")

risk_checks = [
    (
        "recharts" in dependencies,
        "Charts vendor chunk مطلوب",
    ),
    (
        "lucide-react" in dependencies,
        "Icons vendor chunk ممكن",
    ),
    (
        "react-router-dom" in dependencies,
        "React/router vendor chunk مطلوب",
    ),
    (
        "manualChunks" not in config_text,
        "لا توجد استراتيجية manualChunks حالية",
    ),
    (
        largest_size > 300 * 1024,
        "أكبر Chunk ما زال يتجاوز 300 KB",
    ),
]

for found, label in risk_checks:
    print(
        f"{'⚠️' if found else '✅'} "
        f"{label}"
    )


# =========================================================
# 10) Git check
# =========================================================

print_section("10) GIT WHITESPACE CHECK")

git_check = subprocess.run(
    [
        "git",
        "diff",
        "--check",
        "--",
        str(
            vite_config.relative_to(ROOT)
        ),
        "frontend/src",
    ],
    cwd=ROOT,
)

if git_check.returncode != 0:
    print()
    print("❌ فشل git diff --check")
    sys.exit(git_check.returncode)

print("✅ git diff --check ناجح")


# =========================================================
# 11) Final summary
# =========================================================

print_section(
    " Sprint 1.6.2-D3.3-P3 "
    "— VENDOR OPTIMIZATION BASELINE"
)

print(
    f"JavaScript chunks ..... "
    f"{len(js_assets)}"
)

print(
    f"Largest chunk ......... "
    f"{human_size(largest_size)}"
)

print(
    f"Largest chunk file .... "
    f"{largest_path.name}"
)

print(
    f"Total JavaScript ...... "
    f"{human_size(total_js_size)}"
)

print(
    f"manualChunks .......... "
    f"{'YES' if 'manualChunks' in config_text else 'NO'}"
)

print()

if (
    largest_size > 300 * 1024
    and "manualChunks" not in config_text
):
    print(
        "⚠️ المشروع جاهز لتنفيذ "
        "Vendor Chunk Strategy"
    )

    print(
        "➡️ الخطوة التالية: تقسيم "
        "React / Charts / Icons"
    )
else:
    print(
        "✅ لا توجد حاجة عاجلة "
        "لتقسيم Vendor إضافي"
    )

print()
print(
    "✅ Sprint 1.6.2-D3.3-P3 "
    "— Vendor Audit مكتمل"
)

print("=" * 92)
