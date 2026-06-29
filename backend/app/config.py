import os
import pathlib
from dotenv import load_dotenv

# Walk up from this file to find the repo-root .env
_here = pathlib.Path(__file__).resolve()
for _p in [_here.parent, _here.parent.parent, _here.parent.parent.parent]:
    if (_p / ".env").exists():
        load_dotenv(_p / ".env")
        break

QWEN_API_KEY = os.environ.get("QWEN_API_KEY", "")
QWEN_BASE_URL = os.environ.get(
    "QWEN_BASE_URL",
    "https://dashscope-intl.aliyuncs.com/compatible-mode/v1",
)

MODEL_CODER = "qwen-max"          # qwen3.7-max — best coding model
MODEL_CRITIC = "qwen-plus"        # qwen3.7-plus — balanced
MODEL_PLANNER = "qwen-turbo"      # qwen3.6-flash — cheap/fast
MODEL_BASELINE = "qwen-plus"      # same as Critic for fair comparison

MAX_CODER_ATTEMPTS = 4
MAX_REPLAN_COUNT = 2
SANDBOX_TIMEOUT_SECS = 8
