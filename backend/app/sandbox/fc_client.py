"""
Alibaba Cloud Function Compute sandbox client.
Invokes the quorum-sandbox FC function per code submission.
Each invocation is a fresh, isolated, auto-torn-down container.

Required env vars:
  FC_ENDPOINT       e.g. https://<account-id>.ap-southeast-1.fc.aliyuncs.com
  FC_FUNCTION_NAME  e.g. quorum-sandbox
  ALIBABA_CLOUD_ACCESS_KEY_ID
  ALIBABA_CLOUD_ACCESS_KEY_SECRET
"""
import hashlib
import hmac
import json
import os
import time
import urllib.error
import urllib.request
from base64 import b64encode
from datetime import datetime, timezone


def _sign(secret: str, string_to_sign: str) -> str:
    return b64encode(
        hmac.new(secret.encode(), string_to_sign.encode(), hashlib.sha256).digest()
    ).decode()


def _invoke(code: str, tests: list[dict]) -> dict:
    endpoint = os.environ["FC_ENDPOINT"].rstrip("/")
    fn_name = os.environ["FC_FUNCTION_NAME"]
    ak_id = os.environ["ALIBABA_CLOUD_ACCESS_KEY_ID"]
    ak_secret = os.environ["ALIBABA_CLOUD_ACCESS_KEY_SECRET"]

    url = f"{endpoint}/2023-03-30/functions/{fn_name}/invocations"
    payload = json.dumps({"code": code, "tests": tests}).encode()

    date = datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S GMT")
    content_md5 = b64encode(hashlib.md5(payload).digest()).decode()
    content_type = "application/json"

    string_to_sign = "\n".join([
        "POST", content_md5, content_type, date,
        f"x-fc-account-id:{ak_id}",
        f"/2023-03-30/functions/{fn_name}/invocations",
    ])
    signature = _sign(ak_secret, string_to_sign)

    req = urllib.request.Request(
        url,
        data=payload,
        headers={
            "Content-Type": content_type,
            "Content-MD5": content_md5,
            "Date": date,
            "X-Fc-Account-Id": ak_id,
            "Authorization": f"FC {ak_id}:{signature}",
        },
        method="POST",
    )

    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read())


def run_tests(solution_code: str, tests: list[dict]) -> dict:
    """Same interface as local_subprocess.run_tests."""
    try:
        return _invoke(solution_code, tests)
    except (urllib.error.URLError, KeyError, json.JSONDecodeError) as e:
        # Surface as a structured failure so the orchestrator handles it gracefully
        return {
            "passed": False,
            "failures": [{
                "test_id": "fc_invoke",
                "expected": "",
                "actual": f"FC invocation error: {e}",
                "traceback": str(e),
            }],
        }
