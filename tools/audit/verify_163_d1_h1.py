from pathlib import Path
import json
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request


ROOT = Path("/opt/ss4ts-noc")
FRONTEND = ROOT / "frontend"
BACKEND = ROOT / "backend"

EXPECTED_BRANCH = "sprint/1.6.3"

HTTP_TARGETS = [
    (
        "Frontend root",
        "http://127.0.0.1/",
        {200, 301, 302, 307, 308},
    ),
    (
       "Backend health",
       "http://127.0.0.1:8000/api/health",
       {200},
    ),
    (
        "Backend OpenAPI",
        "http://127.0.0.1:8000/openapi.json",
        {200},
    ),
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
    timeout=120,
):
    try:
        return subprocess.run(
            command,
            cwd=cwd,
            text=True,
            capture_output=capture,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return subprocess.CompletedProcess(
            command,
            124,
            stdout="",
            stderr="Command timed out",
        )


def request_url(url, timeout=8):
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent":
                "ss4ts-runtime-audit/1.0",
        },
    )

    started = time.perf_counter()

    try:
        with urllib.request.urlopen(
            request,
            timeout=timeout,
        ) as response:
            body = response.read()

            elapsed = (
                time.perf_counter()
                - started
            ) * 1000

            return {
                "status": response.status,
                "elapsed_ms": elapsed,
                "content_type":
                    response.headers.get(
                        "Content-Type",
                        "",
                    ),
                "body": body,
                "error": "",
            }

    except urllib.error.HTTPError as error:
        elapsed = (
            time.perf_counter()
            - started
        ) * 1000

        return {
            "status": error.code,
            "elapsed_ms": elapsed,
            "content_type":
                error.headers.get(
                    "Content-Type",
                    "",
                ),
            "body": error.read(2048),
            "error": str(error),
        }

    except Exception as error:
        elapsed = (
            time.perf_counter()
            - started
        ) * 1000

        return {
            "status": None,
            "elapsed_ms": elapsed,
            "content_type": "",
            "body": b"",
            "error": str(error),
        }


required = [
    ROOT,
    FRONTEND,
    BACKEND,
    FRONTEND / "package.json",
]

missing = [
    str(path)
    for path in required
    if not path.exists()
]

if missing:
    print("❌ عناصر مطلوبة غير موجودة:")

    for item in missing:
        print(f"  - {item}")

    sys.exit(1)


print("=" * 96)
print(
    " Sprint 1.6.3-D1-H1 "
    "— ENVIRONMENT & SERVICE BASELINE"
)
print("=" * 96)


hard_failures = []
notes = []


# =========================================================
# 1) Git context
# =========================================================

section("1) GIT CONTEXT")

branch_result = run(
    ["git", "branch", "--show-current"],
    capture=True,
)

branch = branch_result.stdout.strip()

print(f"Branch ................. {branch}")

if branch != EXPECTED_BRANCH:
    hard_failures.append(
        f"Expected branch "
        f"{EXPECTED_BRANCH}, found {branch}"
    )
else:
    print("✅ Correct sprint branch")


status_result = run(
    ["git", "status", "--short"],
    capture=True,
)

status_lines = [
    line
    for line in status_result.stdout.splitlines()
    if line.strip()
]

if status_lines:
    print("⚠️ Working tree changes:")

    for line in status_lines:
        print(f"  {line}")

    notes.append(
        f"Working tree has "
        f"{len(status_lines)} change(s)"
    )
else:
    print("✅ Working tree clean")


tracking_result = run(
    [
        "git",
        "status",
        "--branch",
        "--short",
    ],
    capture=True,
)

if tracking_result.stdout.strip():
    print()
    print(tracking_result.stdout.rstrip())


# =========================================================
# 2) Runtime tool availability
# =========================================================

section("2) RUNTIME TOOL AVAILABILITY")

tools = [
    "docker",
    "curl",
    "node",
    "npm",
    "python3",
]

tool_status = {}

for tool in tools:
    path = shutil.which(tool)
    available = path is not None
    tool_status[tool] = available

    print(
        f"{'✅' if available else '❌'} "
        f"{tool:<10} "
        f"{path or 'NOT FOUND'}"
    )

if not tool_status["docker"]:
    hard_failures.append(
        "Docker command is unavailable"
    )


# =========================================================
# 3) Docker service
# =========================================================

section("3) DOCKER ENGINE STATUS")

docker_info = run(
    [
        "docker",
        "info",
        "--format",
        "{{json .ServerVersion}}",
    ],
    capture=True,
)

docker_ready = (
    docker_info.returncode == 0
)

if docker_ready:
    print(
        "✅ Docker engine ready: "
        f"{docker_info.stdout.strip()}"
    )
else:
    print("❌ Docker engine unavailable")

    if docker_info.stderr:
        print(docker_info.stderr.rstrip())

    hard_failures.append(
        "Docker engine is not ready"
    )


# =========================================================
# 4) Compose inventory
# =========================================================

section("4) COMPOSE INVENTORY")

compose_candidates = [
    ROOT / "compose.yml",
    ROOT / "compose.yaml",
    ROOT / "docker-compose.yml",
    ROOT / "docker-compose.yaml",
]

compose_file = next(
    (
        path
        for path in compose_candidates
        if path.exists()
    ),
    None,
)

if compose_file:
    print(
        "Compose file ........... "
        f"{compose_file.name}"
    )

    config_check = run(
        [
            "docker",
            "compose",
            "-f",
            str(compose_file),
            "config",
            "--quiet",
        ],
        capture=True,
    )

    if config_check.returncode == 0:
        print("✅ Compose configuration valid")
    else:
        print("❌ Compose configuration invalid")
        print(config_check.stderr.rstrip())

        hard_failures.append(
            "Docker Compose configuration invalid"
        )
else:
    print("⚠️ No root Compose file found")
    notes.append(
        "No root Docker Compose file found"
    )


# =========================================================
# 5) Running containers
# =========================================================

section("5) RUNNING CONTAINERS")

if docker_ready:
    containers = run(
        [
            "docker",
            "ps",
            "--format",
            (
                "{{.Names}}\t"
                "{{.Status}}\t"
                "{{.Ports}}"
            ),
        ],
        capture=True,
    )

    rows = [
        line
        for line in
        containers.stdout.splitlines()
        if line.strip()
    ]

    if rows:
        for row in rows:
            print(row)
    else:
        print("⚠️ No running containers")
        notes.append("No running containers")
else:
    print("— Docker unavailable")


# =========================================================
# 6) Container health
# =========================================================

section("6) CONTAINER HEALTH")

unhealthy = []
restarting = []

if docker_ready:
    inspect = run(
        [
            "docker",
            "ps",
            "-q",
        ],
        capture=True,
    )

    container_ids = [
        item.strip()
        for item in
        inspect.stdout.splitlines()
        if item.strip()
    ]

    if not container_ids:
        print("— No containers to inspect")

    for container_id in container_ids:
        result = run(
            [
                "docker",
                "inspect",
                container_id,
                "--format",
                (
                    "{{.Name}}|"
                    "{{.State.Status}}|"
                    "{{if .State.Health}}"
                    "{{.State.Health.Status}}"
                    "{{else}}none{{end}}"
                ),
            ],
            capture=True,
        )

        value = result.stdout.strip()
        print(value)

        parts = value.split("|")

        if len(parts) >= 3:
            name = parts[0]
            state = parts[1]
            health = parts[2]

            if health == "unhealthy":
                unhealthy.append(name)

            if state == "restarting":
                restarting.append(name)

if unhealthy:
    hard_failures.append(
        "Unhealthy containers: "
        + ", ".join(unhealthy)
    )

if restarting:
    hard_failures.append(
        "Restarting containers: "
        + ", ".join(restarting)
    )


# =========================================================
# 7) HTTP smoke test
# =========================================================

section("7) HTTP SMOKE TEST")

http_results = []

for label, url, accepted in HTTP_TARGETS:
    result = request_url(url)

    status = result["status"]
    elapsed = result["elapsed_ms"]

    passed = status in accepted

    print(
        f"{'✅' if passed else '❌'} "
        f"{label:<22} "
        f"status={status} "
        f"time={elapsed:.1f}ms "
        f"type={result['content_type'] or '-'}"
    )

    if result["error"] and not passed:
        print(
            f"   Error: {result['error']}"
        )

    http_results.append(
        (
            label,
            passed,
            status,
        )
    )

    if not passed:
        notes.append(
            f"{label} smoke test failed "
            f"with status {status}"
        )


# =========================================================
# 8) Backend OpenAPI inspection
# =========================================================

section("8) BACKEND OPENAPI INSPECTION")

openapi_result = request_url(
    "http://127.0.0.1:8000/openapi.json"
)

openapi_valid = False

if openapi_result["status"] == 200:
    try:
        document = json.loads(
            openapi_result["body"].decode(
                "utf-8",
                errors="replace",
            )
        )

        paths = document.get("paths", {})
        title = (
            document.get("info", {})
            .get("title", "")
        )

        print(f"API title .............. {title}")
        print(
            f"OpenAPI paths .......... "
            f"{len(paths)}"
        )

        expected_markers = [
          "/api/health",
          "/api/v1",
             ]

        path_names = list(paths)

        for marker in expected_markers:
            present = any(
                marker in path
                for path in path_names
            )

            print(
                f"{'✅' if present else '—'} "
                f"Path marker: {marker}"
            )

        openapi_valid = True

    except Exception as error:
        print(
            "❌ Invalid OpenAPI JSON: "
            f"{error}"
        )
else:
    print(
        "⚠️ OpenAPI endpoint unavailable"
    )

if not openapi_valid:
    notes.append(
        "OpenAPI runtime inspection incomplete"
    )


# =========================================================
# 9) Recent container errors
# =========================================================

section("9) RECENT CONTAINER ERROR SCAN")

error_markers = (
    "error",
    "exception",
    "traceback",
    "fatal",
    "panic",
    "unhealthy",
)

log_hits = []

if docker_ready:
    names_result = run(
        [
            "docker",
            "ps",
            "--format",
            "{{.Names}}",
        ],
        capture=True,
    )

    names = [
        line.strip()
        for line in
        names_result.stdout.splitlines()
        if line.strip()
    ]

    for name in names:
        logs = run(
            [
                "docker",
                "logs",
                "--tail",
                "120",
                name,
            ],
            capture=True,
            timeout=30,
        )

        combined = (
            (logs.stdout or "")
            + "\n"
            + (logs.stderr or "")
        )

        matches = [
            line.strip()
            for line in combined.splitlines()
            if any(
                marker in line.lower()
                for marker in error_markers
            )
        ]

        if matches:
            print()
            print(f"[{name}]")

            for line in matches[-12:]:
                print(
                    f"⚠️ {line[:220]}"
                )

                log_hits.append(
                    (name, line)
                )

if not log_hits:
    print(
        "✅ No obvious recent error markers"
    )
else:
    notes.append(
        f"Recent logs contain "
        f"{len(log_hits)} error-like line(s)"
    )


# =========================================================
# 10) Backend regression tests
# =========================================================

section("10) BACKEND REGRESSION TESTS")

venv_python = (
    BACKEND / ".venv/bin/python"
)

if venv_python.exists():
    tests = run(
        [
            str(venv_python),
            "-m",
            "pytest",
            "-q",
            "backend/tests",
        ],
        cwd=ROOT,
        timeout=180,
    )

    tests_passed = (
        tests.returncode == 0
    )

    if tests_passed:
        print("✅ Backend tests passed")
    else:
        print("❌ Backend tests failed")
        hard_failures.append(
            "Backend regression tests failed"
        )
else:
    tests_passed = False

    print(
        "❌ Backend virtual environment missing"
    )

    hard_failures.append(
        "Backend virtual environment missing"
    )


# =========================================================
# 11) Frontend quality checks
# =========================================================

section("11) FRONTEND QUALITY CHECKS")

lint = run(
    [
        "npm",
        "run",
        "lint",
    ],
    cwd=FRONTEND,
    timeout=180,
)

lint_passed = lint.returncode == 0

print(
    f"{'✅' if lint_passed else '❌'} "
    "Frontend lint"
)

if not lint_passed:
    hard_failures.append(
        "Frontend lint failed"
    )


build = run(
    [
        "npm",
        "run",
        "build",
    ],
    cwd=FRONTEND,
    timeout=300,
)

build_passed = build.returncode == 0

print(
    f"{'✅' if build_passed else '❌'} "
    "Frontend build"
)

if not build_passed:
    hard_failures.append(
        "Frontend build failed"
    )


# =========================================================
# 12) Git whitespace
# =========================================================

section("12) GIT WHITESPACE")

git_check = run(
    [
        "git",
        "diff",
        "--check",
    ],
)

git_passed = git_check.returncode == 0

print(
    f"{'✅' if git_passed else '❌'} "
    "git diff --check"
)

if not git_passed:
    hard_failures.append(
        "Git whitespace check failed"
    )


# =========================================================
# 13) Final gate
# =========================================================

section(
    " Sprint 1.6.3-D1-H1 "
    "— BASELINE RESULT"
)

print(
    f"Branch ................ "
    f"{'PASS' if branch == EXPECTED_BRANCH else 'FAIL'}"
)

print(
    f"Working tree .......... "
    f"{'CLEAN' if not status_lines else 'DIRTY'}"
)

print(
    f"Docker engine ......... "
    f"{'PASS' if docker_ready else 'FAIL'}"
)

print(
    f"Unhealthy containers .. "
    f"{len(unhealthy)}"
)

print(
    f"HTTP targets passed ... "
    f"{sum(1 for _, passed, _ in http_results if passed)}"
    f"/{len(http_results)}"
)

print(
    f"Backend tests ......... "
    f"{'PASS' if tests_passed else 'FAIL'}"
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
    f"Git whitespace ........ "
    f"{'PASS' if git_passed else 'FAIL'}"
)

print()


if hard_failures:
    print("❌ BASELINE GATE FAILED")

    for failure in hard_failures:
        print(f"  - {failure}")

    if notes:
        print()
        print("ملاحظات:")

        for note in notes:
            print(f"  - {note}")

    sys.exit(1)


if notes:
    print("⚠️ BASELINE PASSED WITH NOTES")

    for note in notes:
        print(f"  - {note}")
else:
    print("🎉 BASELINE PASSED")


print()
print(
    "✅ Sprint 1.6.3-D1-H1 "
    "— Environment & Service Baseline مكتمل"
)

print("=" * 96)
