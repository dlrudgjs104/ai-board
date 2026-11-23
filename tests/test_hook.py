"""bin/ai-hook 을 실제 프로세스로 돌려 보는 통합 테스트 (보드 미설정 상태: GitHub 호출 없음).
Stop 훅이 NameError 로 조용히 죽던 버그(변수 changed 미정의)의 재발 방지가 핵심이다."""
import json
import os
import subprocess
import sys
import unittest
from pathlib import Path

import helpers
import aiwf

HOOK = helpers.ROOT / "bin" / "ai-hook"
SECRET = "ghp_abcdefghijklmnopqrstuvwxyz0123456789"


class HookFlowTest(unittest.TestCase):
    def setUp(self):
        self.state = helpers.fresh_state()
        self.repo = helpers.TMP / "proj"
        self.repo.mkdir(exist_ok=True)
        subprocess.run(["git", "init", "-q", str(self.repo)], check=True)
        self.env = {**os.environ, "AI_BOARD_STATE": str(self.state), "AI_BOARD_MODE": "personal", "AI_BOARD_HOOKS": "1"}
        self.env.pop("AI_BOARD_RUN", None)

    def fire(self, event, **extra):
        data = {"hook_event_name": event, "session_id": "sess-1234-abcd", "cwd": str(self.repo), **extra}
        return subprocess.run([sys.executable, str(HOOK)], input=json.dumps(data), capture_output=True, text=True, env=self.env)

    def hook_errors(self):
        ev = self.state / "events.jsonl"
        if not ev.exists():
            return []
        return [json.loads(l) for l in ev.read_text(encoding="utf-8").splitlines() if '"HookError"' in l]

    def test_full_turn_without_hook_errors(self):
        self.assertEqual(self.fire("SessionStart", source="startup").returncode, 0)
        r = self.fire("UserPromptSubmit", prompt=f"로그인 고쳐줘 TOKEN=abcd1234efgh")
        self.assertIn("ai-board 현재 모드: personal", r.stdout)
        self.fire("PostToolUse", tool_name="Edit", tool_input={"file_path": str(self.repo / "a.py")}, tool_response={})
        self.fire("Stop", last_assistant_message=f"고쳤습니다. {SECRET} 는 쓰지 않았습니다.\n검토 필요도: 낮음")
        self.assertEqual(self.hook_errors(), [], "훅이 예외로 중단됨")
        s = aiwf.load_json(aiwf.session_file("sess-1234-abcd"), {})
        self.assertEqual(s.get("state"), "replied")
        self.assertIn("a.py", s.get("files", []))

    def test_journal_written_and_masked(self):
        self.fire("SessionStart", source="startup")
        self.fire("UserPromptSubmit", prompt="요청 TOKEN=abcd1234efgh")
        self.fire("Stop", last_assistant_message=f"보고 {SECRET}")
        mds = list((self.state / "records").rglob("*.md"))
        self.assertEqual(len(mds), 1)
        text = mds[0].read_text(encoding="utf-8")
        self.assertIn("요청", text)
        self.assertNotIn(SECRET, text)
        self.assertNotIn("abcd1234efgh", text)

    def test_stop_marks_question_as_needs_you(self):
        self.fire("SessionStart", source="startup")
        self.fire("UserPromptSubmit", prompt="뭐든")
        self.fire("Stop", last_assistant_message="이렇게 할까요?")
        self.assertEqual(self.hook_errors(), [])
        self.assertEqual(aiwf.load_json(aiwf.session_file("sess-1234-abcd"), {}).get("state"), "needs_you")

    def test_off_mode_records_nothing(self):
        (self.state / "runs").mkdir(parents=True, exist_ok=True)
        self.env["AI_BOARD_RUN"] = "r1"
        aiwf.save_json(self.state / "runs" / "r1.json", {"mode": "off"})
        self.fire("UserPromptSubmit", prompt="비밀 요청")
        self.fire("Stop", last_assistant_message="답")
        self.assertFalse(list((self.state / "records").rglob("*.md")) if (self.state / "records").exists() else [])


if __name__ == "__main__":
    unittest.main()
