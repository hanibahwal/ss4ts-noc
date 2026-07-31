from pathlib import Path
import subprocess
import sys


ROOT = Path("/opt/ss4ts-noc")


def run(command, capture=True):
    return subprocess.run(
        command,
        cwd=ROOT,
        text=True,
        capture_output=capture,
    )


def section(title):
    print()
    print("=" * 94)
    print(title)
    print("=" * 94)


def git_status():
    result = run(
        ["git", "status", "--short"]
    )

    if result.returncode != 0:
        raise SystemExit(
            "❌ تعذر قراءة Git status"
        )

    return [
        line
        for line in result.stdout.splitlines()
        if line.strip()
    ]


def path_from_status(line):
    return line[3:].strip()


def print_group(title, entries):
    section(title)

    if not entries:
        print("— لا توجد ملفات")
        return

    for entry in entries:
        print(entry)


status_lines = git_status()

print("=" * 94)
print(
    " Sprint 1.6.2-D3.5-H4 "
    "— WORKING TREE CLASSIFICATION"
)
print("=" * 94)


groups = {
    "backend_core": [],
    "backend_decision": [],
    "backend_tests": [],
    "frontend_decision": [],
    "frontend_deployment": [],
    "frontend_other": [],
    "audit_scripts": [],
    "local_artifacts": [],
    "unclassified": [],
}


for line in status_lines:
    path = path_from_status(line)

    if path.startswith(
        "backend/tests/"
    ):
        groups["backend_tests"].append(
            line
        )

    elif path in {
        "backend/app/api/v1/ai.py",
        "backend/app/api/v1/decision_intelligence.py",
        "backend/app/models/decision.py",
        "backend/app/models/device.py",
        "backend/app/models/interface.py",
        "backend/app/models/prediction.py",
        "backend/app/models/traffic.py",
        "backend/app/services/ai_engine.py",
        "backend/app/services/decision_engine.py",
        "backend/app/services/domain_integration.py",
    }:
        groups["backend_decision"].append(
            line
        )

    elif path.startswith(
        "backend/"
    ):
        groups["backend_core"].append(
            line
        )

    elif path in {
        "frontend/src/components/device/DecisionIntelligenceCenter.jsx",
        "frontend/src/components/device/DecisionIntelligenceCenter.css",
        "frontend/src/services/api.js",
    }:
        groups["frontend_decision"].append(
            line
        )

    elif path in {
        "frontend/nginx.conf",
        "frontend/src/main.jsx",
    }:
        groups["frontend_deployment"].append(
            line
        )

    elif path.startswith(
        "frontend/"
    ):
        groups["frontend_other"].append(
            line
        )

    elif (
        path.startswith("verify_")
        and path.endswith(".py")
    ):
        groups["audit_scripts"].append(
            line
        )

    elif path in {
        "h44_output.txt",
    }:
        groups["local_artifacts"].append(
            line
        )

    else:
        groups["unclassified"].append(
            line
        )


print_group(
    "1) BACKEND CORE / EXISTING FILE MODIFICATIONS",
    groups["backend_core"],
)

print_group(
    "2) BACKEND DECISION INTELLIGENCE",
    groups["backend_decision"],
)

print_group(
    "3) BACKEND REGRESSION TESTS",
    groups["backend_tests"],
)

print_group(
    "4) FRONTEND DECISION INTELLIGENCE",
    groups["frontend_decision"],
)

print_group(
    "5) FRONTEND DEPLOYMENT",
    groups["frontend_deployment"],
)

print_group(
    "6) FRONTEND OTHER",
    groups["frontend_other"],
)

print_group(
    "7) AUDIT SCRIPTS",
    groups["audit_scripts"],
)

print_group(
    "8) LOCAL ARTIFACTS",
    groups["local_artifacts"],
)

print_group(
    "9) UNCLASSIFIED",
    groups["unclassified"],
)


section("10) DIFF STAT BY GROUP")

for group_name, entries in groups.items():
    paths = [
        path_from_status(line)
        for line in entries
    ]

    print()
    print(
        f"[{group_name}] "
        f"{len(paths)} file(s)"
    )

    if not paths:
        continue

    tracked_paths = [
        path
        for path in paths
        if not any(
            line.startswith("??")
            and path_from_status(line) == path
            for line in entries
        )
    ]

    if tracked_paths:
        result = run(
            [
                "git",
                "diff",
                "--stat",
                "--",
                *tracked_paths,
            ]
        )

        if result.stdout.strip():
            print(result.stdout.rstrip())

    untracked_paths = [
        path
        for line, path in zip(
            entries,
            paths,
        )
        if line.startswith("??")
    ]

    for path in untracked_paths:
        file_path = ROOT / path

        if file_path.is_file():
            size = file_path.stat().st_size

            print(
                f"UNTRACKED "
                f"{size:>9} bytes  "
                f"{path}"
            )
        elif file_path.is_dir():
            file_count = sum(
                1
                for item in file_path.rglob("*")
                if item.is_file()
            )

            print(
                f"UNTRACKED DIR "
                f"{file_count:>4} files  "
                f"{path}"
            )


section("11) STAGED FILE CHECK")

staged = run(
    [
        "git",
        "diff",
        "--cached",
        "--name-status",
    ]
)

if staged.stdout.strip():
    print(staged.stdout.rstrip())
else:
    print("✅ لا توجد ملفات في Staging Area")


section("12) WHITESPACE CHECK")

check = run(
    ["git", "diff", "--check"],
    capture=False,
)

if check.returncode != 0:
    print()
    print("❌ git diff --check فشل")
    sys.exit(check.returncode)

print("✅ git diff --check ناجح")


section("13) RECOMMENDED COMMIT PLAN")

plan = [
    (
        "feat(backend): add decision intelligence domain",
        groups["backend_decision"],
    ),
    (
        "test(backend): add decision intelligence regression tests",
        groups["backend_tests"],
    ),
    (
        "feat(backend): integrate traffic and router APIs",
        groups["backend_core"],
    ),
    (
        "feat(ui): integrate decision intelligence dashboard",
        groups["frontend_decision"],
    ),
    (
        "chore(deploy): harden frontend runtime configuration",
        groups["frontend_deployment"],
    ),
    (
        "refactor(ui): update dashboard presentation",
        groups["frontend_other"],
    ),
]

for message, entries in plan:
    print()

    print(
        f"{'✅' if entries else '—'} "
        f"{message}"
    )

    for line in entries:
        print(
            f"    {path_from_status(line)}"
        )


section("14) CLEANUP NOTES")

if groups["local_artifacts"]:
    print(
        "⚠️ ملفات local artifacts "
        "يفضل حذفها أو إضافتها إلى .gitignore"
    )

if groups["audit_scripts"]:
    print(
        "ℹ️ ملفات verify_*.py تحتاج قرارًا: "
        "إما Commit مستقل أو نقلها إلى tools/audit"
    )

if groups["unclassified"]:
    print(
        "⚠️ توجد ملفات غير مصنفة؛ "
        "لا تنشئ Commits قبل مراجعتها"
    )

print()
print(
    "✅ Sprint 1.6.2-D3.5-H4 "
    "— Classification Audit مكتمل"
)
