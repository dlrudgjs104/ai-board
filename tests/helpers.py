"""테스트 공통: 실제 ~/.ai-board 를 건드리지 않도록 상태 폴더를 임시 폴더로 돌리고 lib 를 import 경로에 넣는다.
각 테스트 파일은 다른 모듈보다 먼저 `import helpers` 해야 한다 (aiwf.STATE 가 import 때 정해지므로)."""
import atexit
import os
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TMP = Path(tempfile.mkdtemp(prefix="aiwf-test-"))
os.environ["AI_BOARD_STATE"] = str(TMP / "state")
os.environ.pop("AI_BOARD_RUN", None)
sys.path.insert(0, str(ROOT / "lib"))
atexit.register(shutil.rmtree, TMP, ignore_errors=True)


def fresh_state():
    """상태 폴더를 비우고 다시 만든다 (테스트마다 호출)."""
    state = Path(os.environ["AI_BOARD_STATE"])
    shutil.rmtree(state, ignore_errors=True)
    state.mkdir(parents=True)
    return state
