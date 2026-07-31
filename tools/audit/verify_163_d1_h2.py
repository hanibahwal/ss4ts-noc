from __future__ import annotations

from pathlib import Path
import json
import statistics
import subprocess
import sys
import time
import urllib.error
import urllib.request


ROOT = Path("/opt/ss4ts-noc")
BACKEND = ROOT / "backend"

BASE_URL = "http://127.0.0.1:8000"
FRONTEND_URL = "http://127.0.0.1:5173"

SLOW_THRESHOLD_MS = 500.0
REQUEST_REPEATS = 3
LOG_LOOKBACK = "30m"


def section(title: str) -> None:
    print()
    print("=" * 96)
    print(title)
    print("=" * 96)


def run(
    command: list[str],
    *,
    cwd: Path = ROOT,
    capture: bool = True,
    timeout: int = 120,
) -> subprocess.CompletedProcess:
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


def http_request(
    url: str,
    *,
    timeout: int = 10,
) -> dict:
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "ss4ts-runtime-audit/1.1",
            "Accept": "application/json,text/html,*/*",
        },
    )

    started = time.perf_counter()

    try:
        with urllib.request.urlopen(
            request,
            timeout=timeout,
        ) as response:
            body = response.read()
            elapsed_ms = (
                time.perf_counter() - started
            ) * 1000

            return {
                "ok": True,
                "status": response.status,
                "elapsed_ms": elapsed_ms,
                "content_type":
                    response.headers.get(
                        "Content-Type",
                        "",
                    ),
                "body": body,
                "error": "",
            }

    except urllib.error.HTTPError as error:
        elapsed_ms = (
            time.perf_counter() - started
        ) * 1000

        return {
            "ok": False,
            "status": error.code,
            "elapsed_ms": elapsed_ms,
            "content_type":
                error.headers.get(
                    "Content-Type",
                    "",
                ),
            "body": error.read(),
            "error": str(error),
        }

    except Exception as error:
        elapsed_ms = (
            time.perf_counter() - started
        ) * 1000

        return {
            "ok": False,
            "status": None,
            "elapsed_ms": elapsed_ms,
            "content_type": "",
            "body": b"",
            "error": str(error),
        }


def parse_json(result: dict):
    try:
        return json.loads(
            result["body"].decode(
                "utf-8",
                errors="replace",
            )
        )
    except Exception:
        return None


print("=" * 96)
print(
    " Sprint 1.6.3-D1-H2 "
    "— RUNTIME ENDPOINT & LOG HARDENING"
)
print("=" * 96)

hard_failures: list[str] = []
notes: list[str] = []


# =========================================================
# 1) Git baseline
# =========================================================

section("1) GIT BASELINE")

branch = run(
    ["git", "branch", "--show-current"],
).stdout.strip()

status = run(
    ["git", "status", "--short"],
).stdout.splitlines()

print(f"Branch ................. {branch}")
print(
    "Working tree .......... "
    f"{'CLEAN' if not status else 'DIRTY'}"
)

if branch != "sprint/1.6.3":
    hard_failures.append(
        f"Unexpected branch: {branch}"
    )

if status:
    for line in status:
        print(f"  {line}")

    notes.append(
        f"Working tree has {len(status)} change(s)"
    )


# =========================================================
# 2) OpenAPI inventory
# =========================================================

section("2) OPENAPI INVENTORY")

openapi_result = http_request(
    f"{BASE_URL}/openapi.json"
)

openapi = parse_json(openapi_result)

if (
    openapi_result["status"] != 200
    or not isinstance(openapi, dict)
):
    print("❌ OpenAPI unavailable or invalid")

    hard_failures.append(
        "OpenAPI inventory failed"
    )

    paths = {}
else:
    paths = openapi.get("paths", {})

    print(
        f"API title .............. "
        f"{openapi.get('info', {}).get('title', '-')}"
    )

    print(
        f"API version ............ "
        f"{openapi.get('info', {}).get('version', '-')}"
    )

    print(
        f"Path count ............. {len(paths)}"
    )

    for path in sorted(paths):
        methods = ", ".join(
            key.upper()
            for key in paths[path]
            if key.lower() in {
                "get",
                "post",
                "put",
                "patch",
                "delete",
            }
        )

        print(f"{methods:<18} {path}")


# =========================================================
# 3) Safe endpoint selection
# =========================================================

section("3) SAFE GET ENDPOINT INVENTORY")

safe_get_paths = []

for path, operations in paths.items():
    if "get" not in operations:
        continue

    if "{" in path:
        continue

    safe_get_paths.append(path)

safe_get_paths = sorted(set(safe_get_paths))

for path in safe_get_paths:
    print(path)

if not safe_get_paths:
    hard_failures.append(
        "No safe GET endpoints discovered"
    )


# =========================================================
# 4) Runtime endpoint tests
# =========================================================

section("4) RUNTIME ENDPOINT TESTS")

endpoint_results = []

for path in safe_get_paths:
    samples = []

    final_result = None

    for _ in range(REQUEST_REPEATS):
        result = http_request(
            f"{BASE_URL}{path}"
        )

        final_result = result
        samples.append(result["elapsed_ms"])

    assert final_result is not None

    median_ms = statistics.median(samples)

    passed = (
        final_result["status"] is not None
        and 200 <= final_result["status"] < 400
    )

    json_payload = parse_json(final_result)

    json_valid = (
        json_payload is not None
        or "application/json"
        not in final_result["content_type"]
    )

    slow = median_ms > SLOW_THRESHOLD_MS

    print(
        f"{'✅' if passed and json_valid else '❌'} "
        f"{path:<50} "
        f"status={final_result['status']} "
        f"median={median_ms:.1f}ms "
        f"{'SLOW' if slow else ''}"
    )

    endpoint_results.append({
        "path": path,
        "passed": passed,
        "json_valid": json_valid,
        "median_ms": median_ms,
        "status": final_result["status"],
    })

    if not passed:
        notes.append(
            f"Endpoint failed: {path} "
            f"status={final_result['status']}"
        )

    if not json_valid:
        hard_failures.append(
            f"Invalid JSON response: {path}"
        )

    if slow:
        notes.append(
            f"Slow endpoint: {path} "
            f"{median_ms:.1f}ms"
        )


# =========================================================
# 5) Required runtime endpoints
# =========================================================

section("5) REQUIRED ENDPOINTS")

required_paths = [
    "/api/health",
    "/api/v1/health",
    "/api/v1/dashboard",
]

for path in required_paths:
    present = path in paths

    print(
        f"{'✅' if present else '❌'} "
        f"{path}"
    )

    if not present:
        hard_failures.append(
            f"Required endpoint missing: {path}"
        )


# =========================================================
# 6) Frontend runtime
# =========================================================

section("6) FRONTEND RUNTIME")

frontend_result = http_request(
    FRONTEND_URL
)

frontend_passed = (
    frontend_result["status"] == 200
    and b"<html" in
    frontend_result["body"].lower()
)

print(
    f"{'✅' if frontend_passed else '❌'} "
    f"Frontend status={frontend_result['status']} "
    f"time={frontend_result['elapsed_ms']:.1f}ms"
)

if not frontend_passed:
    hard_failures.append(
        "Frontend runtime failed"
    )


# =========================================================
# 7) Docker resource inventory
# =========================================================

section("7) CONTAINER RESOURCE INVENTORY")

docker_stats = run(
    [
        "docker",
        "stats",
        "--no-stream",
        "--format",
        (
            "{{.Name}}|"
            "{{.CPUPerc}}|"
            "{{.MemUsage}}|"
            "{{.MemPerc}}|"
            "{{.PIDs}}"
        ),
    ],
)

if docker_stats.returncode != 0:
    print("❌ Unable to read docker stats")
    hard_failures.append(
        "Docker stats unavailable"
    )
else:
    for line in docker_stats.stdout.splitlines():
        if line.strip():
            print(line)


# =========================================================
# 8) Restart counts
# =========================================================

section("8) CONTAINER RESTART COUNTS")

container_names = run(
    [
        "docker",
        "ps",
        "--format",
        "{{.Names}}",
    ],
).stdout.splitlines()

restart_issues = []

for name in container_names:
    name = name.strip()

    if not name:
        continue

    result = run(
        [
            "docker",
            "inspect",
            name,
            "--format",
            (
                "{{.RestartCount}}|"
                "{{.State.Status}}|"
                "{{if .State.Health}}"
                "{{.State.Health.Status}}"
                "{{else}}none{{end}}"
            ),
        ],
    )

    value = result.stdout.strip()
    print(f"{name:<32} {value}")

    parts = value.split("|")

    if len(parts) >= 2:
        try:
            restart_count = int(parts[0])
        except ValueError:
            restart_count = -1

        if restart_count > 0:
            restart_issues.append(
                (name, restart_count)
            )

if restart_issues:
    notes.append(
        "Containers with restarts: "
        + ", ".join(
            f"{name}={count}"
            for name, count in restart_issues
        )
    )


# =========================================================
# 9) Classified log scan
# =========================================================

section("9) CLASSIFIED LOG SCAN")

ignore_patterns = [
    "pluginsautoupdate",
    "flag evaluation succeeded",
    "unable to gather disk name",
    "no such file or directory",
    "terminating connection due to administrator command",
]

warning_patterns = [
    "rate-overlimit",
    "statuscode\":429",
    "too many requests",
]

critical_patterns = [
    "traceback",
    "panic",
    "fatal",
    "segmentation fault",
    "out of memory",
    "oom killed",
    "unhandled exception",
]

classified = {
    "critical": [],
    "warning": [],
    "ignored": [],
}

for name in container_names:
    name = name.strip()

    if not name:
        continue

    logs = run(
        [
            "docker",
            "logs",
            "--since",
            LOG_LOOKBACK,
            "--tail",
            "500",
            name,
        ],
        timeout=45,
    )

    combined = (
        (logs.stdout or "")
        + "\n"
        + (logs.stderr or "")
    )

    for raw_line in combined.splitlines():
        line = raw_line.strip()

        if not line:
            continue

        lower = line.lower()

        if any(
            pattern in lower
            for pattern in ignore_patterns
        ):
            classified["ignored"].append(
                (name, line)
            )

            continue

        if any(
            pattern in lower
            for pattern in critical_patterns
        ):
            classified["critical"].append(
                (name, line)
            )

            continue

        if any(
            pattern in lower
            for pattern in warning_patterns
        ):
            classified["warning"].append(
                (name, line)
            )


print(
    f"Critical ............... "
    f"{len(classified['critical'])}"
)

print(
    f"Warnings ............... "
    f"{len(classified['warning'])}"
)

print(
    f"Ignored known noise .... "
    f"{len(classified['ignored'])}"
)

for category in (
    "critical",
    "warning",
):
    if classified[category]:
        print()
        print(f"[{category.upper()}]")

        for name, line in \
                classified[category][-15:]:
            print(
                f"{name}: {line[:220]}"
            )

if classified["critical"]:
    hard_failures.append(
        f"Critical log lines found: "
        f"{len(classified['critical'])}"
    )

if classified["warning"]:
    notes.append(
        f"Runtime warnings found: "
        f"{len(classified['warning'])}"
    )


# =========================================================
# 10) Quality checks
# =========================================================

section("10) QUALITY CHECKS")

tests = run(
    [
        str(BACKEND / ".venv/bin/python"),
        "-m",
        "pytest",
        "-q",
        "backend/tests",
    ],
    timeout=180,
)

tests_passed = tests.returncode == 0

print(
    f"{'✅' if tests_passed else '❌'} "
    "Backend tests"
)

if not tests_passed:
    hard_failures.append(
        "Backend tests failed"
    )


lint = run(
    [
        "npm",
        "run",
        "lint",
    ],
    cwd=ROOT / "frontend",
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
    cwd=ROOT / "frontend",
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


git_check = run(
    ["git", "diff", "--check"],
)

git_passed = git_check.returncode == 0

print(
    f"{'✅' if git_passed else '❌'} "
    "Git whitespace"
)

if not git_passed:
    hard_failures.append(
        "Git whitespace failed"
    )


# =========================================================
# 11) Final result
# =========================================================

section(
    " Sprint 1.6.3-D1-H2 "
    "— FINAL RESULT"
)

passed_endpoints = sum(
    1
    for item in endpoint_results
    if (
        item["passed"]
        and item["json_valid"]
    )
)

print(
    f"Endpoints .............. "
    f"{passed_endpoints}/"
    f"{len(endpoint_results)}"
)

print(
    f"Frontend runtime ....... "
    f"{'PASS' if frontend_passed else 'FAIL'}"
)

print(
    f"Critical logs .......... "
    f"{len(classified['critical'])}"
)

print(
    f"Runtime warnings ....... "
    f"{len(classified['warning'])}"
)

print(
    f"Backend tests .......... "
    f"{'PASS' if tests_passed else 'FAIL'}"
)

print(
    f"Frontend lint .......... "
    f"{'PASS' if lint_passed else 'FAIL'}"
)

print(
    f"Frontend build ......... "
    f"{'PASS' if build_passed else 'FAIL'}"
)

print(
    f"Git whitespace ......... "
    f"{'PASS' if git_passed else 'FAIL'}"
)

print()


if hard_failures:
    print("❌ RUNTIME HARDENING GATE FAILED")

    for item in hard_failures:
        print(f"  - {item}")

    if notes:
        print()
        print("ملاحظات:")

        for item in notes:
            print(f"  - {item}")

    sys.exit(1)


if notes:
    print("⚠️ RUNTIME GATE PASSED WITH NOTES")

    for item in notes:
        print(f"  - {item}")
else:
    print("🎉 RUNTIME GATE PASSED")


print()
print(
    "✅ Sprint 1.6.3-D1-H2 "
    "— Runtime Endpoint & Log Hardening مكتمل"
)

print("=" * 96)
