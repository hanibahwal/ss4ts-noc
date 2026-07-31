from pathlib import Path
import json
import os
import re
import subprocess
import sys


ROOT = Path("/opt/ss4ts-noc")
FRONTEND = ROOT / "frontend"
BACKEND = ROOT / "backend"

PACKAGE_JSON = FRONTEND / "package.json"

CODE_SUFFIXES = {
    ".py",
    ".js",
    ".jsx",
    ".ts",
    ".tsx",
}

SECRET_NAME_PATTERNS = [
    re.compile(r"(^|[._-])\.?env($|[._-])", re.I),
    re.compile(r"secret", re.I),
    re.compile(r"credential", re.I),
    re.compile(r"private[_-]?key", re.I),
]

SECRET_CONTENT_PATTERN = re.compile(
    r"""
    (?:
        API[_-]?KEY
        |
        SECRET
        |
        TOKEN
        |
        PASSWORD
        |
        PRIVATE[_-]?KEY
    )
    \s*[:=]\s*
    ['"]?
    (?P<value>[^\s'"]+)
    """,
    re.I | re.X,
)


def read(path: Path) -> str:
    return path.read_text(
        encoding="utf-8",
        errors="ignore",
    )


def section(title: str) -> None:
    print()
    print("=" * 94)
    print(title)
    print("=" * 94)


def run(
    command: list[str],
    cwd: Path = ROOT,
    capture: bool = False,
) -> subprocess.CompletedProcess:
    return subprocess.run(
        command,
        cwd=cwd,
        text=True,
        capture_output=capture,
    )


def relative(path: Path) -> str:
    return str(path.relative_to(ROOT))


required = [
    ROOT,
    FRONTEND,
    BACKEND,
    PACKAGE_JSON,
]

missing = [
    str(path)
    for path in required
    if not path.exists()
]

if missing:
    print("❌ عناصر مطلوبة غير موجودة:")

    for path in missing:
        print(f"  - {path}")

    sys.exit(1)


print("=" * 94)
print(
    " Sprint 1.6.2-D3.5-H1 "
    "— REPOSITORY & RELEASE INVENTORY"
)
print("=" * 94)


# =========================================================
# 1) Git status
# =========================================================

section("1) GIT WORKTREE STATUS")

status = run(
    ["git", "status", "--short"],
    capture=True,
)

if status.returncode != 0:
    print("❌ تعذر قراءة Git status")
    sys.exit(status.returncode)

status_lines = [
    line
    for line in status.stdout.splitlines()
    if line.strip()
]

if status_lines:
    for line in status_lines:
        print(line)
else:
    print("✅ Working tree clean")


modified = [
    line
    for line in status_lines
    if line[:2].strip() in {
        "M",
        "MM",
        "AM",
    }
    or " M " in f" {line[:3]} "
]

untracked = [
    line
    for line in status_lines
    if line.startswith("??")
]

staged = [
    line
    for line in status_lines
    if (
        len(line) >= 2
        and line[0] not in {" ", "?"}
    )
]

print()
print(f"Changed entries ....... {len(status_lines)}")
print(f"Modified candidates ... {len(modified)}")
print(f"Untracked ............. {len(untracked)}")
print(f"Staged ................ {len(staged)}")


# =========================================================
# 2) Branch and commit history
# =========================================================

section("2) BRANCH & COMMIT HISTORY")

branch = run(
    ["git", "branch", "--show-current"],
    capture=True,
)

print(
    "Branch:",
    branch.stdout.strip()
    if branch.returncode == 0
    else "UNKNOWN",
)

log = run(
    ["git", "log", "--oneline", "-12"],
    capture=True,
)

if log.returncode == 0:
    print()
    print(log.stdout.rstrip())
else:
    print("⚠️ تعذر عرض Git history")


# =========================================================
# 3) Frontend package scripts
# =========================================================

section("3) FRONTEND PACKAGE SCRIPTS")

package = json.loads(
    read(PACKAGE_JSON)
)

scripts = package.get("scripts", {})
dependencies = package.get("dependencies", {})
dev_dependencies = package.get(
    "devDependencies",
    {},
)

print("Scripts:")

for name, command in sorted(scripts.items()):
    print(f"  {name:<18} {command}")

print()
print(f"Dependencies .......... {len(dependencies)}")
print(f"Dev dependencies ...... {len(dev_dependencies)}")

expected_scripts = [
    "build",
    "dev",
    "lint",
    "test",
    "preview",
]

print()
print("Expected script coverage:")

for name in expected_scripts:
    print(
        f"{'✅' if name in scripts else '—'} "
        f"{name}"
    )


# =========================================================
# 4) Test inventory
# =========================================================

section("4) TEST INVENTORY")

frontend_test_patterns = [
    "*.test.js",
    "*.test.jsx",
    "*.spec.js",
    "*.spec.jsx",
    "*.test.ts",
    "*.test.tsx",
    "*.spec.ts",
    "*.spec.tsx",
]

frontend_tests = []

for pattern in frontend_test_patterns:
    frontend_tests.extend(
        path
        for path in FRONTEND.rglob(pattern)
        if (
            path.is_file()
            and "node_modules" not in path.parts
            and "dist" not in path.parts
        )
    )

frontend_tests = sorted(set(frontend_tests))

backend_tests = sorted(
    path
    for path in BACKEND.rglob("test_*.py")
    if path.is_file()
)

backend_test_dirs = sorted(
    path
    for path in BACKEND.rglob("tests")
    if path.is_dir()
)

print(
    f"Frontend test files ... {len(frontend_tests)}"
)

for path in frontend_tests[:40]:
    print(f"  {relative(path)}")

print()
print(
    f"Backend test files .... {len(backend_tests)}"
)

for path in backend_tests[:60]:
    print(f"  {relative(path)}")

print()
print(
    f"Backend test dirs ..... {len(backend_test_dirs)}"
)

for path in backend_test_dirs:
    print(f"  {relative(path)}")


# =========================================================
# 5) Backend structure
# =========================================================

section("5) BACKEND STRUCTURE")

backend_python = sorted(
    path
    for path in BACKEND.rglob("*.py")
    if (
        path.is_file()
        and "__pycache__" not in path.parts
    )
)

print(
    f"Python files .......... {len(backend_python)}"
)

structure_targets = [
    BACKEND / "app/main.py",
    BACKEND / "requirements.txt",
    BACKEND / "pyproject.toml",
    BACKEND / "pytest.ini",
    ROOT / "requirements.txt",
]

for path in structure_targets:
    print(
        f"{'✅' if path.exists() else '—'} "
        f"{relative(path) if path.exists() else path.name}"
    )

fastapi_markers = {
    "FastAPI(": 0,
    "APIRouter(": 0,
    "@router.": 0,
}

for path in backend_python:
    text = read(path)

    for marker in fastapi_markers:
        fastapi_markers[marker] += text.count(marker)

print()
print("FastAPI markers:")

for marker, count in fastapi_markers.items():
    print(f"  {marker:<15} {count}")


# =========================================================
# 6) Deployment inventory
# =========================================================

section("6) DEPLOYMENT FILE INVENTORY")

deployment_candidates = [
    FRONTEND / "vite.config.js",
    FRONTEND / "vite.config.ts",
    FRONTEND / "nginx.conf",
    FRONTEND / "Dockerfile",
    BACKEND / "Dockerfile",
    ROOT / "Dockerfile",
    ROOT / "docker-compose.yml",
    ROOT / "docker-compose.yaml",
    ROOT / "compose.yml",
    ROOT / "compose.yaml",
]

for path in deployment_candidates:
    if path.exists():
        print(f"✅ {relative(path)}")
    else:
        print(f"—  {relative(path)}")


# =========================================================
# 7) Environment and secret file inventory
# =========================================================

section("7) ENVIRONMENT & SECRET INVENTORY")

ignored_dirs = {
    ".git",
    "node_modules",
    "dist",
    "__pycache__",
    ".venv",
    "venv",
}

candidate_files = []

for path in ROOT.rglob("*"):
    if not path.is_file():
        continue

    if any(
        part in ignored_dirs
        for part in path.parts
    ):
        continue

    name = path.name

    if any(
        pattern.search(name)
        for pattern in SECRET_NAME_PATTERNS
    ):
        candidate_files.append(path)

candidate_files = sorted(set(candidate_files))

if candidate_files:
    for path in candidate_files:
        tracked_check = run(
            [
                "git",
                "ls-files",
                "--error-unmatch",
                relative(path),
            ],
            capture=True,
        )

        tracked = tracked_check.returncode == 0

        print(
            f"{'⚠️ TRACKED' if tracked else 'ℹ️ LOCAL'} "
            f"{relative(path)}"
        )
else:
    print("✅ لا توجد أسماء ملفات أسرار واضحة")


# =========================================================
# 8) Potential hard-coded secrets
# =========================================================

section("8) POTENTIAL HARD-CODED SECRET CHECK")

scan_files = sorted(
    path
    for path in ROOT.rglob("*")
    if (
        path.is_file()
        and path.suffix in CODE_SUFFIXES
        and not any(
            part in ignored_dirs
            for part in path.parts
        )
    )
)

secret_hits = []

safe_placeholder_values = {
    "",
    "changeme",
    "example",
    "your_token",
    "your_password",
    "test",
    "none",
    "null",
}

for path in scan_files:
    text = read(path)

    for match in SECRET_CONTENT_PATTERN.finditer(text):
        value = match.group("value").strip()

        if value.lower() in safe_placeholder_values:
            continue

        line = (
            text[:match.start()].count("\n")
            + 1
        )

        secret_hits.append(
            (
                path,
                line,
                value[:8] + "…"
                if len(value) > 8
                else value,
            )
        )

if secret_hits:
    print(
        "⚠️ نتائج محتملة تحتاج مراجعة "
        "يدوية، ولم تُعرض القيم كاملة:"
    )

    for path, line, masked in secret_hits[:60]:
        print(
            f"  {relative(path)}:{line} "
            f"value={masked}"
        )
else:
    print(
        "✅ لم يتم العثور على أسرار "
        "واضحة داخل ملفات الكود"
    )


# =========================================================
# 9) Frontend build
# =========================================================

section("9) FRONTEND PRODUCTION BUILD")

build = run(
    ["npm", "run", "build"],
    cwd=FRONTEND,
)

if build.returncode != 0:
    print("❌ Frontend build failed")
    sys.exit(build.returncode)

print("✅ Frontend build successful")


# =========================================================
# 10) Backend Python compile
# =========================================================

section("10) BACKEND PYTHON COMPILE")

compile_result = run(
    [
        sys.executable,
        "-m",
        "compileall",
        "-q",
        "app",
    ],
    cwd=BACKEND,
)

if compile_result.returncode != 0:
    print("❌ Backend Python compile failed")
    sys.exit(compile_result.returncode)

print("✅ Backend Python syntax compile successful")


# =========================================================
# 11) Optional backend tests
# =========================================================

section("11) BACKEND TEST CAPABILITY")

pytest_check = run(
    [
        sys.executable,
        "-m",
        "pytest",
        "--version",
    ],
    cwd=BACKEND,
    capture=True,
)

pytest_available = (
    pytest_check.returncode == 0
)

print(
    f"{'✅' if pytest_available else '—'} "
    "pytest available"
)

if pytest_available and backend_tests:
    print(
        "ℹ️ الاختبارات موجودة، "
        "وسيتم تشغيلها في D3.5-H3"
    )
elif not backend_tests:
    print(
        "⚠️ لم يتم العثور على ملفات "
        "Backend tests تقليدية"
    )


# =========================================================
# 12) Git whitespace
# =========================================================

section("12) GIT WHITESPACE CHECK")

git_check = run(
    ["git", "diff", "--check"],
)

if git_check.returncode != 0:
    print("❌ git diff --check failed")
    sys.exit(git_check.returncode)

print("✅ git diff --check successful")


# =========================================================
# 13) Summary
# =========================================================

section(
    " Sprint 1.6.2-D3.5-H1 "
    "— RELEASE INVENTORY SUMMARY"
)

print(
    f"Git changed entries ... {len(status_lines)}"
)

print(
    f"Git untracked ......... {len(untracked)}"
)

print(
    f"Frontend tests ........ {len(frontend_tests)}"
)

print(
    f"Backend tests ......... {len(backend_tests)}"
)

print(
    f"Backend Python files .. {len(backend_python)}"
)

print(
    f"Secret-name files ..... {len(candidate_files)}"
)

print(
    f"Potential secret hits . {len(secret_hits)}"
)

print(
    f"Frontend build ........ PASS"
)

print(
    f"Backend compile ....... PASS"
)

print(
    f"Git whitespace ........ PASS"
)

print()

notes = []

if status_lines:
    notes.append(
        "Working tree يحتوي تغييرات "
        "يجب فصلها قبل Release Candidate"
    )

if "lint" not in scripts:
    notes.append(
        "لا يوجد Frontend lint script"
    )

if "test" not in scripts:
    notes.append(
        "لا يوجد Frontend test script"
    )

if not backend_tests:
    notes.append(
        "تغطية Backend tests غير مؤكدة"
    )

if candidate_files:
    notes.append(
        "توجد ملفات بيئة أو أسرار "
        "تحتاج مراجعة Git tracking"
    )

if secret_hits:
    notes.append(
        "توجد قيم محتملة تحتاج "
        "مراجعة يدوية"
    )


if notes:
    print("⚠️ Release readiness notes:")

    for note in notes:
        print(f"  - {note}")

    print()
    print(
        "➡️ المرحلة التالية: "
        "D3.5-H2 Code Quality Gate"
    )
else:
    print(
        "✅ لا توجد ملاحظات أساسية "
        "في Release inventory"
    )


print()
print(
    "✅ Sprint 1.6.2-D3.5-H1 "
    "— Repository & Release Inventory مكتمل"
)

print("=" * 94)
