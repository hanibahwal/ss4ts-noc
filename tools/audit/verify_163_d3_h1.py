from __future__ import annotations

from pathlib import Path
import ast
import re
import subprocess
import sys


ROOT = Path("/opt/ss4ts-noc")
BACKEND = ROOT / "backend"

FILES = [
    BACKEND / "app/models/decision.py",
    BACKEND / "app/models/prediction.py",
    BACKEND / "app/services/decision_engine.py",
    BACKEND / "app/services/ai_engine.py",
    BACKEND / "app/api/v1/decision_intelligence.py",
    BACKEND / "app/models/knowledge_graph.py",
    BACKEND / "app/services/knowledge_graph_query.py",
]

EXPECTED_BRANCH = "sprint/1.6.3"


def section(title: str) -> None:
    print()
    print("=" * 100)
    print(title)
    print("=" * 100)


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


def source(path: Path) -> str:
    return path.read_text(
        encoding="utf-8",
        errors="ignore",
    )


def parse(path: Path) -> ast.Module | None:
    try:
        return ast.parse(source(path))
    except SyntaxError:
        return None


def class_names(path: Path) -> list[str]:
    tree = parse(path)

    if tree is None:
        return []

    return [
        node.name
        for node in tree.body
        if isinstance(node, ast.ClassDef)
    ]


def function_names(path: Path) -> list[str]:
    tree = parse(path)

    if tree is None:
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


missing = [
    relative(path)
    for path in FILES
    if not path.exists()
]

if missing:
    print("❌ ملفات مطلوبة غير موجودة:")

    for item in missing:
        print(f"  - {item}")

    sys.exit(1)


print("=" * 100)
print(
    " Sprint 1.6.3-D3-H1 "
    "— DECISION & IMPACT INTELLIGENCE BASELINE"
)
print("=" * 100)

failures: list[str] = []
notes: list[str] = []


# ---------------------------------------------------------------------
# 1) Git context
# ---------------------------------------------------------------------

section("1) GIT CONTEXT")

branch = run(
    ["git", "branch", "--show-current"],
).stdout.strip()

status = [
    line
    for line in run(
        ["git", "status", "--short"],
    ).stdout.splitlines()
    if line.strip()
]

print(f"Branch ................. {branch}")
print(
    "Working tree .......... "
    f"{'CLEAN' if not status else 'DIRTY'}"
)

for line in status:
    print(f"  {line}")

if branch != EXPECTED_BRANCH:
    failures.append(
        f"Expected {EXPECTED_BRANCH}, found {branch}"
    )

if status:
    notes.append(
        f"Working tree contains {len(status)} change(s)"
    )


# ---------------------------------------------------------------------
# 2) Domain inventory
# ---------------------------------------------------------------------

section("2) DECISION DOMAIN INVENTORY")

for path in FILES:
    classes = class_names(path)
    functions = function_names(path)

    print(relative(path))
    print(f"  classes .............. {len(classes)}")
    print(f"  functions ............ {len(functions)}")

    for name in classes:
        print(f"    class {name}")


# ---------------------------------------------------------------------
# 3) Recommendation terminology
# ---------------------------------------------------------------------

section("3) RECOMMENDATION TERMINOLOGY")

terms = [
    "recommendation",
    "recommended_action",
    "action",
    "decision",
    "severity",
    "priority",
    "confidence",
    "impact",
    "blast_radius",
    "root_cause",
    "affected",
    "evidence",
    "reason",
    "remediation",
    "rollback",
]

combined = "\n".join(
    source(path).lower()
    for path in FILES
)

for term in terms:
    count = len(
        re.findall(
            rf"\b{re.escape(term)}\b",
            combined,
        )
    )

    print(
        f"{'✅' if count else '—'} "
        f"{term:<24} occurrences={count}"
    )


# ---------------------------------------------------------------------
# 4) Existing enums and dataclasses
# ---------------------------------------------------------------------

section("4) ENUM & DATACLASS CONTRACTS")

for path in FILES[:2]:
    tree = parse(path)

    if tree is None:
        continue

    print(relative(path))

    for node in tree.body:
        if not isinstance(node, ast.ClassDef):
            continue

        bases = []

        for base in node.bases:
            try:
                bases.append(ast.unparse(base))
            except Exception:
                pass

        decorators = []

        for decorator in node.decorator_list:
            try:
                decorators.append(
                    ast.unparse(decorator)
                )
            except Exception:
                pass

        if (
            any("Enum" in item for item in bases)
            or any(
                "dataclass" in item
                for item in decorators
            )
        ):
            print(
                f"  {node.name:<36} "
                f"bases={bases} "
                f"decorators={decorators}"
            )


# ---------------------------------------------------------------------
# 5) Knowledge Graph integration gap
# ---------------------------------------------------------------------

section("5) KNOWLEDGE GRAPH INTEGRATION GAP")

integration_terms = {
    "KnowledgeNode":
        "knowledgenode",
    "KnowledgeEdge":
        "knowledgeedge",
    "GraphSnapshot":
        "graphsnapshot",
    "KnowledgeGraphQuery":
        "knowledgegraphquery",
    "blast_radius":
        "blast_radius",
    "impact_paths":
        "impact_paths",
    "affected_nodes":
        "affected_nodes",
    "source_node_id":
        "source_node_id",
}

decision_sources = "\n".join(
    source(path).lower()
    for path in FILES[:5]
)

integration_present = {}

for label, token in integration_terms.items():
    present = token in decision_sources
    integration_present[label] = present

    print(
        f"{'✅' if present else '❌'} "
        f"{label}"
    )


# ---------------------------------------------------------------------
# 6) Duplication risk
# ---------------------------------------------------------------------

section("6) RECOMMENDATION MODEL DUPLICATION RISK")

candidate_names = [
    "Recommendation",
    "Decision",
    "DecisionRecommendation",
    "RecommendedAction",
    "ActionRecommendation",
    "Remediation",
]

all_classes = {
    name
    for path in FILES
    for name in class_names(path)
}

for name in candidate_names:
    present = name in all_classes

    print(
        f"{'⚠️ EXISTS' if present else '✅ FREE  '} "
        f"{name}"
    )

if "Recommendation" in all_classes:
    notes.append(
        "Recommendation class already exists; "
        "do not create a duplicate model"
    )


# ---------------------------------------------------------------------
# 7) Required target contract
# ---------------------------------------------------------------------

section("7) PROPOSED IMPACT DECISION CONTRACT")

required_fields = [
    "decision_id",
    "source_node_id",
    "affected_node_ids",
    "severity",
    "priority",
    "confidence",
    "summary",
    "root_cause",
    "recommended_actions",
    "evidence",
    "impact_paths",
    "backup_available",
    "requires_approval",
    "generated_at",
    "metadata",
]

for field in required_fields:
    present = re.search(
        rf"\b{re.escape(field)}\b",
        combined,
    ) is not None

    print(
        f"{'✅' if present else '❌'} "
        f"{field}"
    )


# ---------------------------------------------------------------------
# 8) Existing API routes
# ---------------------------------------------------------------------

section("8) DECISION API ROUTES")

api_text = source(
    BACKEND
    / "app/api/v1/decision_intelligence.py"
)

route_pattern = re.compile(
    r"@\w+\.(get|post|put|patch|delete)\("
    r"\s*[\"']([^\"']+)[\"']",
    re.I,
)

routes = route_pattern.findall(api_text)

for method, path in routes:
    print(f"{method.upper():<8} {path}")

print(f"\nRoutes ................. {len(routes)}")


# ---------------------------------------------------------------------
# 9) Quality gate
# ---------------------------------------------------------------------

section("9) QUALITY GATE")

python = BACKEND / ".venv/bin/python"

compile_result = run([
    str(python),
    "-m",
    "compileall",
    "-q",
    "backend/app",
])

compile_passed = compile_result.returncode == 0

print(
    f"{'✅' if compile_passed else '❌'} "
    "Backend compile"
)

if not compile_passed:
    failures.append("Backend compile failed")


tests_result = run([
    str(python),
    "-m",
    "pytest",
    "-q",
    "backend/tests",
])

tests_passed = tests_result.returncode == 0

print(
    f"{'✅' if tests_passed else '❌'} "
    "Backend tests"
)

if not tests_passed:
    print(tests_result.stdout)
    print(tests_result.stderr)
    failures.append("Backend tests failed")


whitespace_result = run(
    ["git", "diff", "--check"]
)

whitespace_passed = (
    whitespace_result.returncode == 0
)

print(
    f"{'✅' if whitespace_passed else '❌'} "
    "Git whitespace"
)

if not whitespace_passed:
    failures.append(
        "Git whitespace check failed"
    )


# ---------------------------------------------------------------------
# 10) Recommended implementation
# ---------------------------------------------------------------------

section("10) RECOMMENDED IMPLEMENTATION ORDER")

plan = [
    (
        "D3-H2",
        "Impact decision domain extension",
        "Extend existing decision models instead of duplicating them.",
    ),
    (
        "D3-H3",
        "Impact analysis service",
        "Combine graph blast radius, paths, metrics and device health.",
    ),
    (
        "D3-H4",
        "Root-cause ranking",
        "Rank probable causes using evidence and dependency direction.",
    ),
    (
        "D3-H5",
        "Recommendation generation",
        "Generate prioritized and approval-aware remediation actions.",
    ),
    (
        "D3-H6",
        "Decision API integration",
        "Expose impact decisions through the existing API family.",
    ),
]

for sprint, title, description in plan:
    print(f"{sprint} — {title}")
    print(f"  {description}")


# ---------------------------------------------------------------------
# 11) Final result
# ---------------------------------------------------------------------

section(" Sprint 1.6.3-D3-H1 — BASELINE RESULT")

print(
    f"Existing classes ....... {len(all_classes)}"
)

print(
    f"Decision API routes .... {len(routes)}"
)

print(
    "Graph integration ...... "
    f"{sum(integration_present.values())}/"
    f"{len(integration_present)}"
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
    f"Git whitespace ......... "
    f"{'PASS' if whitespace_passed else 'FAIL'}"
)

print()

if failures:
    print("❌ DECISION INTELLIGENCE BASELINE FAILED")

    for item in failures:
        print(f"  - {item}")

    sys.exit(1)

if notes:
    print("⚠️ BASELINE PASSED WITH NOTES")

    for item in notes:
        print(f"  - {item}")
else:
    print("🎉 DECISION INTELLIGENCE BASELINE PASSED")

print()
print(
    "✅ Sprint 1.6.3-D3-H1 "
    "— Decision & Impact Intelligence Baseline مكتمل"
)
print("=" * 100)
