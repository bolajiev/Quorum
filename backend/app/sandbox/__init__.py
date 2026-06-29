import os

if os.environ.get("FC_ENDPOINT") and os.environ.get("FC_FUNCTION_NAME"):
    from app.sandbox.fc_client import run_tests
else:
    from app.sandbox.local_subprocess import run_tests, SandboxResult  # noqa: F401
