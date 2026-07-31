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
VITE_CONFIG = FRONTEND / "vite.config.js"
NGINX_CONFIG = FRONTEND / "nginx.conf"

CODE_SUFFIXES = {
    ".js",
    ".jsx",
    ".ts",
    ".tsx",
}

STYLE_SUFFIXES = {
    ".css",
    ".scss",
}


def read(path):
    return path.read_text(
        encoding="utf-8",
        errors="ignore",
    )


def line_number(text, position):
    return text[:position].count("\n") + 1


def human_size(size):
    value = float(size)

    for unit in (
        "B",
        "KB",
        "MB",
        "GB",
    ):
        if value < 1024:
            return f"{value:.2f} {unit}"

        value /= 1024

    return f"{value:.2f} TB"


def section(title):
    print()
    print("=" * 92)
    print(title)
    print("=" * 92)


required = [
    FRONTEND,
    SRC,
    PACKAGE_JSON,
    VITE_CONFIG,
    NGINX_CONFIG,
]

missing = [
    str(path)
    for path in required
    if not path.exists()
]

if missing:
    print("❌ ملفات أو مجلدات مطلوبة غير موجودة:")

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

style_files = sorted(
    path
    for path in SRC.rglob("*")
    if (
        path.is_file()
        and path.suffix in STYLE_SUFFIXES
    )
)


print("=" * 92)
print(
    " Sprint 1.6.2-D3.4-H1 "
    "— PRODUCTION READINESS INVENTORY"
)
print("=" * 92)


# =========================================================
# 1) Project inventory
# =========================================================

section("1) PROJECT INVENTORY")

package = json.loads(
    read(PACKAGE_JSON)
)

dependencies = package.get(
    "dependencies",
    {},
)

dev_dependencies = package.get(
    "devDependencies",
    {},
)

print(f"Source code files ...... {len(code_files)}")
print(f"Style files ............ {len(style_files)}")
print(f"Dependencies ........... {len(dependencies)}")
print(f"Dev dependencies ....... {len(dev_dependencies)}")


# =========================================================
# 2) Console / debugger inventory
# =========================================================

section("2) CONSOLE & DEBUG INVENTORY")

debug_patterns = {
    "console.log": r"\bconsole\.log\s*\(",
    "console.debug": r"\bconsole\.debug\s*\(",
    "console.warn": r"\bconsole\.warn\s*\(",
    "console.error": r"\bconsole\.error\s*\(",
    "debugger": r"\bdebugger\s*;",
}

debug_results = {
    label: []
    for label in debug_patterns
}

for path in code_files:
    text = read(path)

    for label, pattern in debug_patterns.items():
        for match in re.finditer(
            pattern,
            text,
        ):
            debug_results[label].append(
                (
                    path.relative_to(ROOT),
                    line_number(
                        text,
                        match.start(),
                    ),
                )
            )

for label, results in debug_results.items():
    marker = (
        "✅"
        if not results
        else "⚠️"
    )

    print()
    print(
        f"{marker} {label}: "
        f"{len(results)} occurrence(s)"
    )

    for path, line in results[:30]:
        print(f"  {path}:{line}")


# =========================================================
# 3) TODO / FIXME inventory
# =========================================================

section("3) TODO / FIXME / TEMP INVENTORY")

comment_markers = {
    "TODO": r"\bTODO\b",
    "FIXME": r"\bFIXME\b",
    "HACK": r"\bHACK\b",
    "TEMP": r"\bTEMP\b",
}

comment_results = {
    label: []
    for label in comment_markers
}

for path in [
    *code_files,
    *style_files,
]:
    text = read(path)

    for label, pattern in comment_markers.items():
        for match in re.finditer(
            pattern,
            text,
            re.I,
        ):
            comment_results[label].append(
                (
                    path.relative_to(ROOT),
                    line_number(
                        text,
                        match.start(),
                    ),
                )
            )

for label, results in comment_results.items():
    marker = (
        "✅"
        if not results
        else "⚠️"
    )

    print(
        f"{marker} {label}: "
        f"{len(results)} occurrence(s)"
    )

    for path, line in results[:20]:
        print(f"  {path}:{line}")


# =========================================================
# 4) Backup / temporary files
# =========================================================

section("4) BACKUP & TEMPORARY FILE INVENTORY")

backup_patterns = [
    "*.bak",
    "*.backup",
    "*.old",
    "*.orig",
    "*.tmp",
    "*~",
    "*.before-*",
]

backup_files = []

for pattern in backup_patterns:
    backup_files.extend(
        path
        for path in FRONTEND.rglob(pattern)
        if path.is_file()
    )

backup_files = sorted(
    set(backup_files)
)

if not backup_files:
    print("✅ لا توجد ملفات Backup أو Temporary داخل frontend")
else:
    for path in backup_files:
        print(
            f"⚠️ {path.relative_to(ROOT)}"
        )


# =========================================================
# 5) Loading / error UX inventory
# =========================================================

section("5) LOADING & ERROR UX INVENTORY")

ux_markers = {
    "Suspense": r"<Suspense(?:\s|>)",
    "Route fallback": r"RouteFallback",
    "role=status": r'role=["\']status["\']',
    "aria-live": r"aria-live=",
    "Loading states": r"\bloading\b",
    "Error states": r"\berror\b",
    "Retry actions": r"إعادة المحاولة|retry",
}

ux_results = {}

for label, pattern in ux_markers.items():
    occurrences = []

    for path in code_files:
        text = read(path)

        for match in re.finditer(
            pattern,
            text,
            re.I,
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

    ux_results[label] = occurrences

    marker = (
        "✅"
        if occurrences
        else "⚠️"
    )

    print(
        f"{marker} {label}: "
        f"{len(occurrences)} occurrence(s)"
    )


# =========================================================
# 6) Large source files
# =========================================================

section("6) LARGE SOURCE FILES")

large_files = sorted(
    (
        path.stat().st_size,
        path,
    )
    for path in code_files
    if path.stat().st_size >= 20 * 1024
)

if not large_files:
    print("✅ لا توجد ملفات Source أكبر من 20 KB")
else:
    for size, path in sorted(
        large_files,
        reverse=True,
    ):
        print(
            f"⚠️ {human_size(size):>10} "
            f"{path.relative_to(ROOT)}"
        )


# =========================================================
# 7) Vite production configuration
# =========================================================

section("7) VITE PRODUCTION CONFIGURATION")

vite_text = read(VITE_CONFIG)

vite_checks = [
    (
        "rolldownOptions" in vite_text,
        "Rolldown options",
    ),
    (
        "codeSplitting" in vite_text,
        "Code splitting",
    ),
    (
        "vendor-react" in vite_text,
        "vendor-react",
    ),
    (
        "vendor-charts" in vite_text,
        "vendor-charts",
    ),
    (
        "vendor-icons" in vite_text,
        "vendor-icons",
    ),
    (
        "sourcemap" in vite_text,
        "Explicit sourcemap setting",
    ),
    (
        "minify" in vite_text,
        "Explicit minify setting",
    ),
]

for passed, label in vite_checks:
    print(
        f"{'✅' if passed else '—'} "
        f"{label}"
    )


# =========================================================
# 8) Nginx production inventory
# =========================================================

section("8) NGINX PRODUCTION INVENTORY")

nginx_text = read(NGINX_CONFIG)

nginx_checks = [
    (
        "try_files" in nginx_text,
        "SPA fallback / try_files",
    ),
    (
        "gzip" in nginx_text,
        "Gzip configuration",
    ),
    (
        "Cache-Control" in nginx_text
        or "expires" in nginx_text,
        "Static asset caching",
    ),
    (
        "X-Content-Type-Options" in nginx_text,
        "X-Content-Type-Options",
    ),
    (
        "X-Frame-Options" in nginx_text,
        "X-Frame-Options",
    ),
    (
        "Content-Security-Policy" in nginx_text,
        "Content-Security-Policy",
    ),
    (
        "Referrer-Policy" in nginx_text,
        "Referrer-Policy",
    ),
]

for passed, label in nginx_checks:
    print(
        f"{'✅' if passed else '⚠️'} "
        f"{label}"
    )


# =========================================================
# 9) Build
# =========================================================

section("9) PRODUCTION BUILD")

build = subprocess.run(
    ["npm", "run", "build"],
    cwd=FRONTEND,
)

if build.returncode != 0:
    print()
    print("❌ فشل npm run build")
    sys.exit(build.returncode)


# =========================================================
# 10) Dist inventory
# =========================================================

section("10) DIST ASSET INVENTORY")

assets_dir = DIST / "assets"

if not assets_dir.exists():
    print("❌ dist/assets غير موجود")
    sys.exit(1)

js_assets = sorted(
    (
        path.stat().st_size,
        path.name,
    )
    for path in assets_dir.glob("*.js")
)

css_assets = sorted(
    (
        path.stat().st_size,
        path.name,
    )
    for path in assets_dir.glob("*.css")
)

print("JavaScript assets:")

for size, name in sorted(
    js_assets,
    reverse=True,
):
    print(
        f"  {human_size(size):>10} {name}"
    )

print()
print("CSS assets:")

for size, name in sorted(
    css_assets,
    reverse=True,
):
    print(
        f"  {human_size(size):>10} {name}"
    )

largest_js = max(
    (
        size
        for size, _ in js_assets
    ),
    default=0,
)

source_maps = list(
    DIST.rglob("*.map")
)


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
        "frontend",
    ],
    cwd=ROOT,
)

if git_check.returncode != 0:
    print()
    print("❌ فشل git diff --check")
    sys.exit(git_check.returncode)

print("✅ Frontend git diff --check ناجح")


# =========================================================
# 12) Summary
# =========================================================

section(
    " Sprint 1.6.2-D3.4-H1 "
    "— PRODUCTION READINESS SUMMARY"
)

console_log_count = len(
    debug_results["console.log"]
)

console_debug_count = len(
    debug_results["console.debug"]
)

debugger_count = len(
    debug_results["debugger"]
)

todo_count = sum(
    len(results)
    for results in comment_results.values()
)

print(
    f"Source files .......... {len(code_files)}"
)

print(
    f"Console.log ........... {console_log_count}"
)

print(
    f"Console.debug ......... {console_debug_count}"
)

print(
    f"Debugger .............. {debugger_count}"
)

print(
    f"TODO/FIXME/TEMP ....... {todo_count}"
)

print(
    f"Backup files .......... {len(backup_files)}"
)

print(
    f"Large source files .... {len(large_files)}"
)

print(
    f"JavaScript chunks ..... {len(js_assets)}"
)

print(
    f"Largest JS chunk ...... "
    f"{human_size(largest_js)}"
)

print(
    f"Source maps ........... {len(source_maps)}"
)

print()

blockers = []

if debugger_count:
    blockers.append(
        "يوجد debugger داخل الكود"
    )

if console_log_count:
    blockers.append(
        "يوجد console.log داخل كود الإنتاج"
    )

if backup_files:
    blockers.append(
        "توجد ملفات Backup داخل frontend"
    )

if largest_js > 300 * 1024:
    blockers.append(
        "أكبر JavaScript chunk يتجاوز 300 KB"
    )


if blockers:
    print("⚠️ ملاحظات Production Readiness:")

    for blocker in blockers:
        print(f"  - {blocker}")

    print()
    print(
        "➡️ المرحلة التالية: "
        "D3.4-H2 Production Cleanup"
    )
else:
    print(
        "✅ لا توجد Blockers أساسية "
        "في فحص Production Readiness"
    )


print()
print(
    "✅ Sprint 1.6.2-D3.4-H1 "
    "— Production Readiness Inventory مكتمل"
)

print("=" * 92)
