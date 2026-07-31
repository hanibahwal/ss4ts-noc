from pathlib import Path
import json
import os
import subprocess
import sys


ROOT = Path("/opt/ss4ts-noc")
FRONTEND = ROOT / "frontend"
BACKEND = ROOT / "backend"

PACKAGE_JSON = FRONTEND / "package.json"

REQUIRED = [
    ROOT,
    FRONTEND,
    BACKEND,
    PACKAGE_JSON,
]


def section(title):
    print()
    print("=" * 96)
    print(title)
    print("=" * 96)


def run(
    command,
    cwd=ROOT,
    capture=False,
    env=None,
):
    return subprocess.run(
        command,
        cwd=cwd,
        text=True,
        capture_output=capture,
        env=env,
    )


def relative(path):
    return str(path.relative_to(ROOT))


missing = [
    str(path)
    for path in REQUIRED
    if not path.exists()
]

if missing:
    print("❌ عناصر مطلوبة غير موجودة:")

    for item in missing:
        print(f"  - {item}")

    sys.exit(1)


package = json.loads(
    PACKAGE_JSON.read_text(
        encoding="utf-8",
    )
)

scripts = package.get(
    "scripts",
    {},
)


print("=" * 96)
print(
    " Sprint 1.6.2-D3.5-H3 "
    "— FINAL RELEASE READINESS"
)
print("=" * 96)


# =========================================================
# 1) Git branch and head
# =========================================================

section("1) GIT RELEASE CONTEXT")

branch = run(
    [
        "git",
        "branch",
        "--show-current",
    ],
    capture=True,
)

head = run(
    [
        "git",
        "log",
        "-1",
        "--oneline",
    ],
    capture=True,
)

print(
    "Branch:",
    branch.stdout.strip()
    if branch.returncode == 0
    else "UNKNOWN",
)

print(
    "HEAD:",
    head.stdout.strip()
    if head.returncode == 0
    else "UNKNOWN",
)


# =========================================================
# 2) Git status
# =========================================================

section("2) GIT WORKTREE STATUS")

status = run(
    [
        "git",
        "status",
        "--short",
    ],
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


tracked_changes = [
    line
    for line in status_lines
    if not line.startswith("??")
]

untracked_changes = [
    line
    for line in status_lines
    if line.startswith("??")
]

staged_changes = [
    line
    for line in status_lines
    if (
        len(line) >= 2
        and line[0] not in {
            " ",
            "?",
        }
    )
]

print()
print(
    f"Tracked changes ....... "
    f"{len(tracked_changes)}"
)

print(
    f"Untracked files ....... "
    f"{len(untracked_changes)}"
)

print(
    f"Staged changes ........ "
    f"{len(staged_changes)}"
)


# =========================================================
# 3) Frontend lint
# =========================================================

section("3) FRONTEND LINT")

if "lint" not in scripts:
    print("❌ لا يوجد lint script")
    lint_passed = False
else:
    lint = run(
        [
            "npm",
            "run",
            "lint",
        ],
        cwd=FRONTEND,
    )

    lint_passed = (
        lint.returncode == 0
    )

    print()

    if lint_passed:
        print("✅ Frontend lint passed")
    else:
        print("❌ Frontend lint failed")


# =========================================================
# 4) Frontend build
# =========================================================

section("4) FRONTEND PRODUCTION BUILD")

build = run(
    [
        "npm",
        "run",
        "build",
    ],
    cwd=FRONTEND,
)

build_passed = (
    build.returncode == 0
)

print()

if build_passed:
    print("✅ Frontend production build passed")
else:
    print("❌ Frontend production build failed")


# =========================================================
# 5) Dist inventory
# =========================================================

section("5) FRONTEND DIST INVENTORY")

assets = FRONTEND / "dist/assets"

js_assets = []
css_assets = []

if assets.exists():
    js_assets = sorted(
        (
            path.stat().st_size,
            path.name,
        )
        for path in assets.glob("*.js")
    )

    css_assets = sorted(
        (
            path.stat().st_size,
            path.name,
        )
        for path in assets.glob("*.css")
    )

    print(
        f"JavaScript chunks ..... "
        f"{len(js_assets)}"
    )

    print(
        f"CSS assets ............ "
        f"{len(css_assets)}"
    )

    if js_assets:
        largest_js_size, largest_js_name = max(
            js_assets,
            key=lambda item: item[0],
        )

        print(
            f"Largest JS ............ "
            f"{largest_js_size / 1024:.2f} KB "
            f"({largest_js_name})"
        )
    else:
        largest_js_size = 0

        print(
            "❌ لا توجد JavaScript assets"
        )
else:
    largest_js_size = 0

    print("❌ dist/assets غير موجود")


# =========================================================
# 6) Backend syntax
# =========================================================

section("6) BACKEND PYTHON SYNTAX")

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

backend_compile_passed = (
    compile_result.returncode == 0
)

if backend_compile_passed:
    print(
        "✅ Backend Python compile passed"
    )
else:
    print(
        "❌ Backend Python compile failed"
    )


# =========================================================
# 7) Backend tests
# =========================================================

section("7) BACKEND REGRESSION TESTS")

backend_tests = sorted(
    path
    for path in BACKEND.rglob(
        "test_*.py"
    )
    if path.is_file()
)

print(
    f"Backend test files .... "
    f"{len(backend_tests)}"
)

for path in backend_tests:
    print(
        f"  {relative(path)}"
    )


pytest_version = run(
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
    pytest_version.returncode == 0
)

backend_tests_passed = False
backend_tests_skipped = False

if not backend_tests:
    print()
    print(
        "⚠️ لا توجد اختبارات Backend"
    )

    backend_tests_skipped = True

elif not pytest_available:
    print()
    print(
        "⚠️ pytest غير مثبت؛ "
        "لم يتم تشغيل الاختبارات"
    )

    backend_tests_skipped = True

else:
    print()
    print("تشغيل pytest...")
    print()

    test_result = run(
        [
            sys.executable,
            "-m",
            "pytest",
            "-q",
        ],
        cwd=BACKEND,
    )

    backend_tests_passed = (
        test_result.returncode == 0
    )

    print()

    if backend_tests_passed:
        print(
            "✅ Backend regression tests passed"
        )
    else:
        print(
            "❌ Backend regression tests failed"
        )


# =========================================================
# 8) Sensitive file status
# =========================================================

section("8) ENVIRONMENT & SENSITIVE FILE STATUS")

sensitive_candidates = [
    ROOT / ".env",
    FRONTEND / ".env",
    BACKEND / ".env",
    ROOT / ".env.production",
    FRONTEND / ".env.production",
    BACKEND / ".env.production",
]

sensitive_issues = []

for path in sensitive_candidates:
    if not path.exists():
        continue

    tracked = run(
        [
            "git",
            "ls-files",
            "--error-unmatch",
            relative(path),
        ],
        capture=True,
    ).returncode == 0

    print(
        f"{'❌ TRACKED' if tracked else '✅ LOCAL'} "
        f"{relative(path)}"
    )

    if tracked:
        sensitive_issues.append(
            relative(path)
        )

example_env = ROOT / ".env.example"

if example_env.exists():
    print(
        "✅ .env.example موجود"
    )
else:
    print(
        "⚠️ .env.example غير موجود"
    )


# =========================================================
# 9) Backup / temporary files
# =========================================================

section("9) BACKUP & TEMPORARY FILE CHECK")

patterns = [
    "*.bak",
    "*.backup",
    "*.old",
    "*.orig",
    "*.tmp",
    "*~",
    "*.before-*",
]

temporary_files = []

for pattern in patterns:
    temporary_files.extend(
        path
        for path in ROOT.rglob(pattern)
        if (
            path.is_file()
            and ".git" not in path.parts
            and "node_modules" not in path.parts
            and "dist" not in path.parts
        )
    )

temporary_files = sorted(
    set(temporary_files)
)

if temporary_files:
    for path in temporary_files:
        print(
            f"⚠️ {relative(path)}"
        )
else:
    print(
        "✅ لا توجد ملفات Backup أو Temporary"
    )


# =========================================================
# 10) Debug inventory
# =========================================================

section("10) DEBUG STATEMENT CHECK")

source_suffixes = {
    ".js",
    ".jsx",
    ".ts",
    ".tsx",
    ".py",
}

debug_hits = []

for base in (
    FRONTEND / "src",
    BACKEND / "app",
):
    if not base.exists():
        continue

    for path in base.rglob("*"):
        if (
            not path.is_file()
            or path.suffix
            not in source_suffixes
            or "__pycache__"
            in path.parts
        ):
            continue

        text = path.read_text(
            encoding="utf-8",
            errors="ignore",
        )

        for number, line in enumerate(
            text.splitlines(),
            start=1,
        ):
            stripped = line.strip()

            if (
                "debugger;" in stripped
                or "console.log(" in stripped
                or "console.debug(" in stripped
            ):
                debug_hits.append(
                    (
                        path,
                        number,
                        stripped,
                    )
                )

if debug_hits:
    for path, line, content in debug_hits:
        print(
            f"⚠️ {relative(path)}:"
            f"{line} {content[:120]}"
        )
else:
    print(
        "✅ لا توجد Debug statements أساسية"
    )


# =========================================================
# 11) Git whitespace
# =========================================================

section("11) GIT WHITESPACE CHECK")

git_check = run(
    [
        "git",
        "diff",
        "--check",
    ],
)

git_check_passed = (
    git_check.returncode == 0
)

if git_check_passed:
    print(
        "✅ git diff --check passed"
    )
else:
    print(
        "❌ git diff --check failed"
    )


# =========================================================
# 12) Required release commits
# =========================================================

section("12) RELEASE COMMIT INVENTORY")

required_commits = {
    "SSTable responsive":
        "2bc4844",
    "Route splitting":
        "5fbf6eb",
    "Vendor splitting":
        "cfb9e26",
    "Route loading":
        "2e34eed",
    "Error boundary":
        "57b3efb",
    "Lint cleanup":
        "eb8132d",
}

commit_checks = []

for label, commit in required_commits.items():
    result = run(
        [
            "git",
            "cat-file",
            "-e",
            f"{commit}^{{commit}}",
        ],
        capture=True,
    )

    exists = (
        result.returncode == 0
    )

    commit_checks.append(
        exists
    )

    print(
        f"{'✅' if exists else '❌'} "
        f"{label}: {commit}"
    )


# =========================================================
# 13) Final release gate
# =========================================================

section(
    " Sprint 1.6.2-D3.5-H3 "
    "— FINAL RELEASE GATE"
)

hard_failures = []
release_notes = []


if not lint_passed:
    hard_failures.append(
        "Frontend lint failed"
    )

if not build_passed:
    hard_failures.append(
        "Frontend build failed"
    )

if not backend_compile_passed:
    hard_failures.append(
        "Backend syntax check failed"
    )

if (
    backend_tests
    and pytest_available
    and not backend_tests_passed
):
    hard_failures.append(
        "Backend tests failed"
    )

if sensitive_issues:
    hard_failures.append(
        "Sensitive environment files "
        "are tracked by Git"
    )

if not git_check_passed:
    hard_failures.append(
        "Git whitespace check failed"
    )

if not all(commit_checks):
    hard_failures.append(
        "Required release commits missing"
    )

if largest_js_size > 300 * 1024:
    hard_failures.append(
        "Largest JavaScript chunk "
        "exceeds 300 KB"
    )


if tracked_changes:
    release_notes.append(
        f"Working tree has "
        f"{len(tracked_changes)} tracked change(s)"
    )

if untracked_changes:
    release_notes.append(
        f"Working tree has "
        f"{len(untracked_changes)} untracked file(s)"
    )

if temporary_files:
    release_notes.append(
        f"Temporary files found: "
        f"{len(temporary_files)}"
    )

if debug_hits:
    release_notes.append(
        f"Debug statements found: "
        f"{len(debug_hits)}"
    )

if backend_tests_skipped:
    release_notes.append(
        "Backend tests were not executed"
    )


print(
    f"Frontend lint ......... "
    f"{'PASS' if lint_passed else 'FAIL'}"
)

print(
    f"Frontend build ........ "
    f"{'PASS' if build_passed else 'FAIL'}"
)

print(
    f"Backend compile ....... "
    f"{'PASS' if backend_compile_passed else 'FAIL'}"
)

print(
    f"Backend tests ......... "
    f"{'PASS' if backend_tests_passed else 'SKIPPED'}"
)

print(
    f"Git whitespace ........ "
    f"{'PASS' if git_check_passed else 'FAIL'}"
)

print(
    f"Sensitive files ....... "
    f"{'PASS' if not sensitive_issues else 'FAIL'}"
)

print(
    f"Required commits ...... "
    f"{'PASS' if all(commit_checks) else 'FAIL'}"
)

print(
    f"Largest JS chunk ...... "
    f"{largest_js_size / 1024:.2f} KB"
)

print()


if hard_failures:
    print("❌ RELEASE GATE FAILED")

    for failure in hard_failures:
        print(
            f"  - {failure}"
        )

    if release_notes:
        print()
        print("ملاحظات إضافية:")

        for note in release_notes:
            print(
                f"  - {note}"
            )

    print()
    print(
        "❌ Sprint 1.6.2-D3.5-H3 "
        "غير مكتمل"
    )

    sys.exit(1)


if release_notes:
    print(
        "⚠️ RELEASE GATE PASSED "
        "WITH NOTES"
    )

    for note in release_notes:
        print(
            f"  - {note}"
        )

    print()
    print(
        "✅ الفحوصات التقنية ناجحة، "
        "لكن يجب ترتيب Working Tree "
        "قبل إنشاء Release Candidate."
    )
else:
    print(
        "🎉 RELEASE GATE PASSED"
    )

    print(
        "✅ Working tree clean"
    )

    print(
        "✅ المشروع جاهز لإنشاء "
        "Release Candidate"
    )


print()
print(
    "✅ Sprint 1.6.2-D3.5-H3 "
    "— Final Release Readiness مكتمل"
)

print("=" * 96)
