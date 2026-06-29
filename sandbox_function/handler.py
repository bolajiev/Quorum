"""
Alibaba Cloud Function Compute handler.
Receives: { code: str, tests: [{id, input, expected_output}] }
Returns:  { passed: bool, failures: [...] }

This file is the "proof of Alibaba Cloud deployment" artifact —
invoking it IS an Alibaba Cloud API call.
"""
import json
import os
import resource
import subprocess
import sys
import textwrap

TIMEOUT_SECS = int(os.environ.get("SANDBOX_TIMEOUT_SECS", "8"))
MEM_LIMIT_BYTES = 256 * 1024 * 1024


def _preexec():
    resource.setrlimit(resource.RLIMIT_CPU, (TIMEOUT_SECS, TIMEOUT_SECS))
    resource.setrlimit(resource.RLIMIT_AS, (MEM_LIMIT_BYTES, MEM_LIMIT_BYTES))


def _run_test(solution_code: str, test: dict) -> dict | None:
    """Returns failure dict or None on pass."""
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
except Exception:
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
    try:
        proc = subprocess.run(
            [sys.executable, "-c", wrapper],
            capture_output=True, text=True,
            timeout=TIMEOUT_SECS, preexec_fn=_preexec,
            env={"PATH": "/usr/bin:/bin"},
        )
        if proc.returncode == 0:
            return None
        return {
            "test_id": test["id"],
            "expected": str(test["expected_output"]).strip(),
            "actual": proc.stdout.strip() or proc.stderr.strip(),
            "traceback": (proc.stdout + proc.stderr)[:500],
        }
    except subprocess.TimeoutExpired:
        return {
            "test_id": test["id"],
            "expected": str(test["expected_output"]).strip(),
            "actual": "TIMEOUT",
            "traceback": f"Exceeded {TIMEOUT_SECS}s",
        }


def handler(event, context):
    """Alibaba Cloud FC entry point."""
    try:
        body = json.loads(event) if isinstance(event, (str, bytes)) else event
        code = body["code"]
        tests = body["tests"]
    except (json.JSONDecodeError, KeyError) as e:
        return json.dumps({"error": f"Bad request: {e}"})

    failures = [f for t in tests if (f := _run_test(code, t)) is not None]
    return json.dumps({"passed": len(failures) == 0, "failures": failures})
