from __future__ import annotations

from pathlib import Path
import ast
import json
import re
import subprocess
import sys
import urllib.error
import urllib.request


ROOT = Path("/opt/ss4ts-noc")
BACKEND = ROOT / "backend"
FRONTEND = ROOT / "frontend"

EXPECTED_BRANCH = "sprint/1.6.3"

MODEL_DIR = BACKEND / "app/models"
SERVICE_DIR = BACKEND / "app/services"
API_DIR = BACKEND / "app/api/v1"
TEST_DIR = BACKEND / "tests"

OPENAPI_URL = "http://127.0.0.1:8000/openapi.json"

TARGET_ENTITIES = {
    "site",
    "tower",
    "device",
    "router",
    "link",
    "interface",
    "customer",
    "vlan",
    "route",
    "relationship",
    "topology",
}

TARGET_RELATIONS = {
    "contains",
    "connected_to",
    "depends_on",
    "serves",
    "uplink_of",
    "downlink_of",
    "member_of",
    "located_at",
    "backed_up_by",
    "impacts",
}


def section(title: str) -> None:
    print()
    print("=" * 98)
    print(title)
    print("=" * 98)


def run(
    command: list[str],
    *,
    cwd: Path = ROOT,
    timeout: int = 180,
) -> subprocess.CompletedProcess:
    try:
        return subprocess.run(
            command,
            cwd=cwd,
            text=True,
            capture_output=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return subprocess.CompletedProcess(
            command,
            124,
            stdout="",
            stderr="Command timed out",
        )


def relative(path: Path) -> str:
    return str(path.relative_to(ROOT))


def read_text(path: Path) -> str:
    return path.read_text(
        encoding="utf-8",
        errors="ignore",
    )


def python_files(base: Path) -> list[Path]:
    if not base.exists():
        return []

    return sorted(
        path
        for path in base.rglob("*.py")
        if (
            path.is_file()
            and "__pycache__" not in path.parts
        )
    )


def request_json(url: str) -> dict | None:
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/json",
            "User-Agent": "ss4ts-knowledge-graph-audit/1.0",
        },
    )

    try:
        with urllib.request.urlopen(
            request,
            timeout=10,
        ) as response:
            return json.loads(
                response.read().decode(
                    "utf-8",
                    errors="replace",
                )
            )

    except (
        urllib.error.URLError,
        urllib.error.HTTPError,
        json.JSONDecodeError,
        TimeoutError,
    ):
        return None


def extract_classes(path: Path) -> list[str]:
    try:
        tree = ast.parse(read_text(path))
    except SyntaxError:
        return []

    return [
        node.name
        for node in ast.walk(tree)
        if isinstance(node, ast.ClassDef)
    ]


def extract_functions(path: Path) -> list[str]:
    try:
        tree = ast.parse(read_text(path))
    except SyntaxError:
        return []

    return [
        node.name
        for node in ast.walk(tree)
        if isinstance(
            node,
            (
                ast.FunctionDef,
                ast.AsyncFunctionDef,
            ),
        )
    ]


required_paths = [
    ROOT,
    BACKEND,
    FRONTEND,
    MODEL_DIR,
    SERVICE_DIR,
    API_DIR,
]

missing = [
    str(path)
    for path in required_paths
    if not path.exists()
]

if missing:
    print("❌ عناصر مطلوبة غير موجودة:")

    for item in missing:
        print(f"  - {item}")

    sys.exit(1)


print("=" * 98)
print(
    " Sprint 1.6.3-D2-H1 "
    "— NETWORK KNOWLEDGE GRAPH BASELINE"
)
print("=" * 98)

hard_failures: list[str] = []
notes: list[str] = []


# =========================================================
# 1) Git context
# =========================================================

section("1) GIT CONTEXT")

branch = run(
    ["git", "branch", "--show-current"],
).stdout.strip()

status_lines = [
    line
    for line in run(
        ["git", "status", "--short"],
    ).stdout.splitlines()
    if line.strip()
]

print(f"Branch ................. {branch}")
print(
    "Working tree .......... "
    f"{'CLEAN' if not status_lines else 'DIRTY'}"
)

if branch != EXPECTED_BRANCH:
    hard_failures.append(
        f"Expected branch {EXPECTED_BRANCH}, found {branch}"
    )

for line in status_lines:
    print(f"  {line}")

if status_lines:
    notes.append(
        f"Working tree has {len(status_lines)} change(s)"
    )


# =========================================================
# 2) Existing model inventory
# =========================================================

section("2) EXISTING MODEL INVENTORY")

model_files = python_files(MODEL_DIR)
all_model_classes: dict[str, list[str]] = {}

for path in model_files:
    classes = extract_classes(path)
    all_model_classes[relative(path)] = classes

    print(relative(path))

    if classes:
        for class_name in classes:
            print(f"  class {class_name}")
    else:
        print("  — no classes detected")

print()
print(
    f"Model files ............ {len(model_files)}"
)

print(
    "Model classes .......... "
    f"{sum(len(items) for items in all_model_classes.values())}"
)


# =========================================================
# 3) Existing services
# =========================================================

section("3) SERVICE INVENTORY")

service_files = python_files(SERVICE_DIR)

for path in service_files:
    functions = extract_functions(path)

    print(
        f"{relative(path):<58} "
        f"functions={len(functions)}"
    )

print(
    f"\nService files .......... {len(service_files)}"
)


# =========================================================
# 4) Existing APIs
# =========================================================

section("4) API SOURCE INVENTORY")

api_files = python_files(API_DIR)

route_decorator = re.compile(
    r"@\w+\.(get|post|put|patch|delete)\("
    r"\s*[\"']([^\"']+)[\"']",
    re.I,
)

source_routes: list[tuple[str, str, str]] = []

for path in api_files:
    text = read_text(path)

    matches = route_decorator.findall(text)

    print(
        f"{relative(path):<58} "
        f"routes={len(matches)}"
    )

    for method, route in matches:
        source_routes.append(
            (
                method.upper(),
                route,
                relative(path),
            )
        )

print(
    f"\nAPI files .............. {len(api_files)}"
)

print(
    f"Source routes .......... {len(source_routes)}"
)


# =========================================================
# 5) Runtime OpenAPI
# =========================================================

section("5) RUNTIME OPENAPI INVENTORY")

openapi = request_json(OPENAPI_URL)
runtime_paths: dict = {}

if not isinstance(openapi, dict):
    print("❌ OpenAPI runtime document unavailable")
    notes.append(
        "Runtime OpenAPI could not be inspected"
    )
else:
    runtime_paths = openapi.get("paths", {})

    print(
        "API title .............. "
        f"{openapi.get('info', {}).get('title', '-')}"
    )

    print(
        "API version ............ "
        f"{openapi.get('info', {}).get('version', '-')}"
    )

    print(
        f"Runtime paths .......... {len(runtime_paths)}"
    )

    for path in sorted(runtime_paths):
        methods = [
            method.upper()
            for method in runtime_paths[path]
            if method.lower() in {
                "get",
                "post",
                "put",
                "patch",
                "delete",
            }
        ]

        print(
            f"{','.join(methods):<18} {path}"
        )


# =========================================================
# 6) Knowledge graph terminology scan
# =========================================================

section("6) KNOWLEDGE GRAPH TERMINOLOGY SCAN")

search_roots = [
    BACKEND / "app",
    FRONTEND / "src",
]

source_suffixes = {
    ".py",
    ".js",
    ".jsx",
    ".ts",
    ".tsx",
    ".css",
}

entity_hits: dict[str, list[str]] = {
    item: []
    for item in sorted(TARGET_ENTITIES)
}

relation_hits: dict[str, list[str]] = {
    item: []
    for item in sorted(TARGET_RELATIONS)
}

for base in search_roots:
    if not base.exists():
        continue

    for path in base.rglob("*"):
        if (
            not path.is_file()
            or path.suffix not in source_suffixes
            or "__pycache__" in path.parts
        ):
            continue

        text = read_text(path).lower()
        path_name = relative(path)

        for term in entity_hits:
            if re.search(
                rf"\b{re.escape(term)}\b",
                text,
            ):
                entity_hits[term].append(path_name)

        for term in relation_hits:
            if re.search(
                rf"\b{re.escape(term)}\b",
                text,
            ):
                relation_hits[term].append(path_name)


print("Entity terminology:")

for term, files in entity_hits.items():
    print(
        f"{'✅' if files else '—'} "
        f"{term:<20} files={len(files)}"
    )

print()
print("Relationship terminology:")

for term, files in relation_hits.items():
    print(
        f"{'✅' if files else '—'} "
        f"{term:<20} files={len(files)}"
    )


# =========================================================
# 7) Existing topology capabilities
# =========================================================

section("7) TOPOLOGY & RELATIONSHIP CAPABILITY CHECK")

all_source_text = "\n".join(
    read_text(path).lower()
    for base in search_roots
    if base.exists()
    for path in base.rglob("*")
    if (
        path.is_file()
        and path.suffix in source_suffixes
        and "__pycache__" not in path.parts
    )
)

capabilities = {
    "Topology page/component":
        "topology" in all_source_text,
    "Graph node concept":
        re.search(
            r"\b(graphnode|graph_node|nodeid|node_id)\b",
            all_source_text,
        )
        is not None,
    "Graph edge concept":
        re.search(
            r"\b(graphedge|graph_edge|edgeid|edge_id)\b",
            all_source_text,
        )
        is not None,
    "Relationship model":
        re.search(
            r"class\s+\w*relationship\w*",
            all_source_text,
            re.I,
        )
        is not None,
    "Impact concept":
        "impact" in all_source_text,
    "Dependency concept":
        "dependency" in all_source_text
        or "depends_on" in all_source_text,
    "Parent-child concept":
        "parent_id" in all_source_text
        or "parentid" in all_source_text,
}

for label, present in capabilities.items():
    print(
        f"{'✅' if present else '❌'} "
        f"{label}"
    )


# =========================================================
# 8) Proposed domain contract
# =========================================================

section("8) PROPOSED KNOWLEDGE GRAPH DOMAIN CONTRACT")

proposed_files = [
    "backend/app/models/knowledge_graph.py",
    "backend/app/services/knowledge_graph.py",
    "backend/app/api/v1/knowledge_graph.py",
    "backend/tests/test_knowledge_graph.py",
    (
        "frontend/src/components/topology/"
        "KnowledgeGraphPanel.jsx"
    ),
    (
        "frontend/src/components/topology/"
        "KnowledgeGraphPanel.css"
    ),
]

for item in proposed_files:
    state = (
        "EXISTS"
        if (ROOT / item).exists()
        else "NEW"
    )

    print(
        f"{state:<8} {item}"
    )


proposed_entities = [
    "Site",
    "Tower",
    "Device",
    "Interface",
    "NetworkLink",
    "CustomerService",
    "KnowledgeNode",
    "KnowledgeEdge",
    "ImpactPath",
]

print()
print("Proposed entities:")

for entity in proposed_entities:
    print(f"  - {entity}")


proposed_relationships = [
    "CONTAINS",
    "LOCATED_AT",
    "CONNECTED_TO",
    "DEPENDS_ON",
    "SERVES",
    "BACKED_UP_BY",
    "UPLINK_OF",
    "DOWNLINK_OF",
    "IMPACTS",
]

print()
print("Proposed relationships:")

for relation in proposed_relationships:
    print(f"  - {relation}")


# =========================================================
# 9) Conflict scan
# =========================================================

section("9) NAMING & ROUTE CONFLICT SCAN")

proposed_route_prefix = "/api/v1/knowledge-graph"

route_conflict = any(
    path.startswith(proposed_route_prefix)
    for path in runtime_paths
)

print(
    f"{'❌' if route_conflict else '✅'} "
    f"Route prefix available: "
    f"{proposed_route_prefix}"
)

if route_conflict:
    hard_failures.append(
        "Knowledge Graph route prefix already exists"
    )


proposed_module_names = [
    MODEL_DIR / "knowledge_graph.py",
    SERVICE_DIR / "knowledge_graph.py",
    API_DIR / "knowledge_graph.py",
]

for path in proposed_module_names:
    print(
        f"{'⚠️ EXISTS' if path.exists() else '✅ FREE  '} "
        f"{relative(path)}"
    )


# =========================================================
# 10) Backend quality baseline
# =========================================================

section("10) BACKEND QUALITY BASELINE")

venv_python = BACKEND / ".venv/bin/python"

compile_result = run(
    [
        str(venv_python),
        "-m",
        "compileall",
        "-q",
        "backend/app",
    ],
)

compile_passed = (
    compile_result.returncode == 0
)

print(
    f"{'✅' if compile_passed else '❌'} "
    "Backend compile"
)

if not compile_passed:
    hard_failures.append(
        "Backend compile failed"
    )


test_result = run(
    [
        str(venv_python),
        "-m",
        "pytest",
        "-q",
        "backend/tests",
    ],
)

tests_passed = (
    test_result.returncode == 0
)

print(
    f"{'✅' if tests_passed else '❌'} "
    "Backend regression tests"
)

if not tests_passed:
    print(test_result.stdout)
    print(test_result.stderr)

    hard_failures.append(
        "Backend regression tests failed"
    )


# =========================================================
# 11) Frontend quality baseline
# =========================================================

section("11) FRONTEND QUALITY BASELINE")

lint_result = run(
    ["npm", "run", "lint"],
    cwd=FRONTEND,
)

lint_passed = (
    lint_result.returncode == 0
)

print(
    f"{'✅' if lint_passed else '❌'} "
    "Frontend lint"
)

if not lint_passed:
    hard_failures.append(
        "Frontend lint failed"
    )


build_result = run(
    ["npm", "run", "build"],
    cwd=FRONTEND,
    timeout=300,
)

build_passed = (
    build_result.returncode == 0
)

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
    ["git", "diff", "--check"],
)

git_passed = (
    git_check.returncode == 0
)

print(
    f"{'✅' if git_passed else '❌'} "
    "git diff --check"
)

if not git_passed:
    hard_failures.append(
        "Git whitespace check failed"
    )


# =========================================================
# 13) Recommended implementation slices
# =========================================================

section("13) RECOMMENDED IMPLEMENTATION SLICES")

implementation_plan = [
    (
        "D2-H2",
        "Knowledge Graph domain models",
        (
            "Define nodes, edges, relationship types, "
            "impact paths, and validation rules."
        ),
    ),
    (
        "D2-H3",
        "Graph construction service",
        (
            "Build a graph from devices, interfaces, "
            "links, and site metadata."
        ),
    ),
    (
        "D2-H4",
        "Knowledge Graph API",
        (
            "Expose graph, neighborhood, dependency, "
            "and impact endpoints."
        ),
    ),
    (
        "D2-H5",
        "Topology relationship UI",
        (
            "Render nodes, edges, details, filters, "
            "and impact navigation."
        ),
    ),
    (
        "D2-H6",
        "Root-cause and blast-radius engine",
        (
            "Traverse dependencies to determine probable "
            "root cause and affected services."
        ),
    ),
]

for sprint, title, description in implementation_plan:
    print(f"{sprint} — {title}")
    print(f"  {description}")


# =========================================================
# 14) Final result
# =========================================================

section(
    " Sprint 1.6.3-D2-H1 "
    "— BASELINE RESULT"
)

existing_entities = sum(
    1
    for files in entity_hits.values()
    if files
)

existing_relations = sum(
    1
    for files in relation_hits.values()
    if files
)

print(
    f"Existing entity terms .. "
    f"{existing_entities}/{len(entity_hits)}"
)

print(
    f"Existing relation terms  "
    f"{existing_relations}/{len(relation_hits)}"
)

print(
    f"Backend compile ........ "
    f"{'PASS' if compile_passed else 'FAIL'}"
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
    print("❌ KNOWLEDGE GRAPH BASELINE FAILED")

    for item in hard_failures:
        print(f"  - {item}")

    if notes:
        print()
        print("ملاحظات:")

        for item in notes:
            print(f"  - {item}")

    sys.exit(1)


if notes:
    print("⚠️ BASELINE PASSED WITH NOTES")

    for item in notes:
        print(f"  - {item}")
else:
    print("🎉 KNOWLEDGE GRAPH BASELINE PASSED")


print()
print(
    "✅ Sprint 1.6.3-D2-H1 "
    "— Network Knowledge Graph Baseline مكتمل"
)

print("=" * 98)
