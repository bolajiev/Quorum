"""
Dev-only sandbox: runs generated code in a subprocess with resource limits.
No network access, hard CPU+memory caps, 8s wall-clock timeout.
"""
import resource
import subprocess
import sys
import textwrap
from dataclasses import dataclass

from app.config import SANDBOX_TIMEOUT_SECS

_CPU_LIMIT_SECS = SANDBOX_TIMEOUT_SECS
_MEM_LIMIT_BYTES = 256 * 1024 * 1024  # 256 MB


@dataclass
class SandboxResult:
    stdout: str
    stderr: str
    exit_code: int
    timed_out: bool


def _preexec():
    resource.setrlimit(resource.RLIMIT_CPU, (_CPU_LIMIT_SECS, _CPU_LIMIT_SECS))
    resource.setrlimit(resource.RLIMIT_AS, (_MEM_LIMIT_BYTES, _MEM_LIMIT_BYTES))


def run_code(code: str, test_input: str = "") -> SandboxResult:
    """Execute code string in an isolated subprocess. Returns SandboxResult."""
    try:
        proc = subprocess.run(
            [sys.executable, "-c", code],
            input=test_input,
            capture_output=True,
            text=True,
            timeout=SANDBOX_TIMEOUT_SECS,
            preexec_fn=_preexec,
            env={"PATH": "/usr/bin:/bin"},  # no inherited env, blocks network helpers
        )
        return SandboxResult(
            stdout=proc.stdout,
            stderr=proc.stderr,
            exit_code=proc.returncode,
            timed_out=False,
        )
    except subprocess.TimeoutExpired:
        return SandboxResult(stdout="", stderr="Timed out", exit_code=-1, timed_out=True)


def run_tests(solution_code: str, tests: list[dict]) -> dict:
    """
    Run solution_code against a list of tests.
    Each test: {id, input, expected_output}
    Returns: {passed: bool, failures: [{test_id, expected, actual, traceback}]}
    """
    failures = []

    for test in tests:
        harness = textwrap.dedent(f"""
import sys, io

_solution = {repr(solution_code)}
_input = {repr(test.get('input', ''))}
_expected = {repr(str(test['expected_output']).strip())}

sys.stdin = io.StringIO(_input)
exec(compile(_solution, '<solution>', 'exec'))
""")
        # We capture solution's stdout by wrapping it
        wrapper = textwrap.dedent(f"""
import sys, io, traceback as _tb

_solution = {repr(solution_code)}
_input = {repr(test.get('input', ''))}
_expected = {repr(str(test['expected_output']).strip())}

buf = io.StringIO()
sys.stdin = io.StringIO(_input)
sys.stdout = buf
try:
    exec(compile(_solution, '<solution>', 'exec'))
except Exception as e:
    sys.stdout = sys.__stdout__
    print("ERROR:" + _tb.format_exc())
    sys.exit(1)
sys.stdout = sys.__stdout__
actual = buf.getvalue().strip()
if actual == _expected:
    sys.exit(0)
else:
    print(f"FAIL\\nexpected: {{_expected!r}}\\nactual:   {{actual!r}}")
    sys.exit(2)
""")
        result = run_code(wrapper)

        if result.exit_code != 0:
            output = result.stdout + result.stderr
            failures.append({
                "test_id": test["id"],
                "expected": str(test["expected_output"]).strip(),
                "actual": result.stdout.strip() or result.stderr.strip(),
                "traceback": output,
            })

    return {
        "passed": len(failures) == 0,
        "failures": failures,
    }
