from pathlib import Path
import re
import subprocess
import sys


ROOT = Path("/opt/ss4ts-noc")
FRONTEND = ROOT / "frontend"
SRC = FRONTEND / "src"

APP_FILES = [
    SRC / "App.jsx",
    SRC / "App.js",
    SRC / "routes.jsx",
    SRC / "router.jsx",
]

MAIN_FILES = [
    SRC / "main.jsx",
    SRC / "main.js",
]

PAGES = SRC / "pages"


def read(path):
    return path.read_text(
        encoding="utf-8",
        errors="ignore",
    )


app_file = next(
    (
        path
        for path in APP_FILES
        if path.exists()
    ),
    None,
)

main_file = next(
    (
        path
        for path in MAIN_FILES
        if path.exists()
    ),
    None,
)

if app_file is None:
    print("❌ لم يتم العثور على App أو Router")
    sys.exit(1)

if main_file is None:
    print("❌ لم يتم العثور على main.jsx")
    sys.exit(1)

if not PAGES.exists():
    print("❌ مجلد frontend/src/pages غير موجود")
    sys.exit(1)


app_text = read(app_file)
main_text = read(main_file)

page_files = sorted(
    path
    for path in PAGES.glob("*")
    if (
        path.is_file()
        and path.suffix in {
            ".jsx",
            ".js",
            ".tsx",
            ".ts",
        }
    )
)


print("=" * 88)
print(
    " Sprint 1.6.2-D3.3-P2 "
    "— ROUTE-LEVEL CODE SPLITTING AUDIT"
)
print("=" * 88)


# =========================================================
# 1) Files
# =========================================================

print()
print("1) ROUTING FILES")
print("-" * 88)

print(
    f"App file  : {app_file.relative_to(ROOT)}"
)

print(
    f"Main file : {main_file.relative_to(ROOT)}"
)

print(
    f"Pages     : {len(page_files)}"
)

for path in page_files:
    print(
        f"  📄 {path.relative_to(ROOT)}"
    )


# =========================================================
# 2) React imports
# =========================================================

print()
print("=" * 88)
print("2) REACT LAZY / SUSPENSE STATUS")
print("-" * 88)

lazy_present = bool(
    re.search(
        r"\b(?:React\.)?lazy\s*\(",
        app_text,
    )
)

suspense_imported = bool(
    re.search(
        r"\bSuspense\b",
        app_text,
    )
)

suspense_used = bool(
    re.search(
        r"<Suspense(?:\s|>)",
        app_text,
    )
)

dynamic_imports = list(
    re.finditer(
        r"\bimport\s*\(",
        app_text,
    )
)

print(
    f"{'✅' if lazy_present else '❌'} "
    f"React.lazy موجود"
)

print(
    f"{'✅' if suspense_imported else '❌'} "
    f"Suspense مستورد"
)

print(
    f"{'✅' if suspense_used else '❌'} "
    f"Suspense مستخدم"
)

print(
    f"{'✅' if dynamic_imports else '❌'} "
    f"Dynamic imports: {len(dynamic_imports)}"
)


# =========================================================
# 3) Static page imports
# =========================================================

print()
print("=" * 88)
print("3) STATIC PAGE IMPORTS")
print("-" * 88)

static_page_imports = []

for match in re.finditer(
    r"import\s+"
    r"(?P<name>[A-Za-z_$][A-Za-z0-9_$]*)"
    r"\s+from\s+"
    r"['\"](?P<path>\./pages/[^'\"]+)['\"]",
    app_text,
):
    static_page_imports.append(
        {
            "name": match.group("name"),
            "path": match.group("path"),
            "line": (
                app_text[:match.start()].count("\n")
                + 1
            ),
        }
    )

if not static_page_imports:
    print("✅ لا توجد Static page imports")
else:
    for item in static_page_imports:
        print(
            f"⚠️ L{item['line']} "
            f"{item['name']} "
            f"from {item['path']}"
        )


# =========================================================
# 4) Route inventory
# =========================================================

print()
print("=" * 88)
print("4) ROUTE INVENTORY")
print("-" * 88)

route_paths = re.findall(
    r"<Route\b[^>]*?"
    r"path\s*=\s*"
    r"['\"]([^'\"]+)['\"]",
    app_text,
    re.S,
)

route_elements = re.findall(
    r"<Route\b[^>]*?"
    r"element\s*=\s*\{\s*"
    r"<([A-Za-z_$][A-Za-z0-9_$]*)",
    app_text,
    re.S,
)

print(
    f"Route paths    : {len(route_paths)}"
)

for path in route_paths:
    print(f"  🧭 {path}")

print()
print(
    f"Route elements : {len(route_elements)}"
)

for element in route_elements:
    print(f"  🧩 {element}")


# =========================================================
# 5) Router type
# =========================================================

print()
print("=" * 88)
print("5) ROUTER IMPLEMENTATION")
print("-" * 88)

router_markers = [
    "BrowserRouter",
    "HashRouter",
    "Routes",
    "Route",
    "createBrowserRouter",
    "RouterProvider",
]

for marker in router_markers:
    print(
        f"{'✅' if marker in app_text or marker in main_text else '—'} "
        f"{marker}"
    )


# =========================================================
# 6) App source preview
# =========================================================

print()
print("=" * 88)
print("6) APP.JSX PREVIEW")
print("-" * 88)

app_lines = app_text.splitlines()

for number, line in enumerate(
    app_lines[:260],
    start=1,
):
    print(
        f"{number:4}: {line}"
    )

if len(app_lines) > 260:
    print(
        f"... truncated; total lines={len(app_lines)}"
    )


# =========================================================
# 7) Main source preview
# =========================================================

print()
print("=" * 88)
print("7) MAIN.JSX PREVIEW")
print("-" * 88)

main_lines = main_text.splitlines()

for number, line in enumerate(
    main_lines[:160],
    start=1,
):
    print(
        f"{number:4}: {line}"
    )


# =========================================================
# 8) Build baseline
# =========================================================

print()
print("=" * 88)
print("8) BUILD BASELINE")
print("-" * 88)

build = subprocess.run(
    ["npm", "run", "build"],
    cwd=FRONTEND,
)

if build.returncode != 0:
    print("❌ فشل npm run build")
    sys.exit(build.returncode)


# =========================================================
# 9) Git check
# =========================================================

print()
print("=" * 88)
print("9) GIT CHECK")
print("-" * 88)

git_check = subprocess.run(
    [
        "git",
        "diff",
        "--check",
        "--",
        str(app_file.relative_to(ROOT)),
        str(main_file.relative_to(ROOT)),
        "frontend/src/pages",
    ],
    cwd=ROOT,
)

if git_check.returncode != 0:
    print("❌ فشل git diff --check")
    sys.exit(git_check.returncode)


# =========================================================
# 10) Summary
# =========================================================

print()
print("=" * 88)
print(" D3.3-P2 AUDIT SUMMARY")
print("=" * 88)

print(
    f"Static page imports ... "
    f"{len(static_page_imports)}"
)

print(
    f"React.lazy usages ..... "
    f"{1 if lazy_present else 0}"
)

print(
    f"Suspense usage ........ "
    f"{1 if suspense_used else 0}"
)

print(
    f"Dynamic imports ....... "
    f"{len(dynamic_imports)}"
)

print(
    f"Routes detected ....... "
    f"{len(route_paths)}"
)

print()

if static_page_imports and not lazy_present:
    print(
        "⚠️ التطبيق ما زال يستخدم "
        "Static page imports"
    )

    print(
        "➡️ جاهز لتنفيذ Route-Level "
        "Code Splitting"
    )
else:
    print(
        "✅ Route-Level Code Splitting "
        "موجود مسبقًا أو لا توجد Imports ثابتة"
    )

print()
print(
    "✅ Sprint 1.6.2-D3.3-P2 "
    "— Audit مكتمل"
)

print("=" * 88)
