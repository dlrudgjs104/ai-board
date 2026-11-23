import importlib.machinery
import importlib.util
import json
import os
import subprocess
import sys
import time
import unittest
from unittest import mock

import helpers
import aiwf
import ghboard

SECRET = "ghp_abcdefghijklmnopqrstuvwxyz0123456789"


def load_hook():
    loader = importlib.machinery.SourceFileLoader("ai_hook", str(helpers.ROOT / "bin" / "ai-hook"))
    spec = importlib.util.spec_from_loader("ai_hook", loader)
    mod = importlib.util.module_from_spec(spec)
    loader.exec_module(mod)
    return mod


class PruneSessionsTest(unittest.TestCase):
    def test_only_old_sessions_removed(self):
        helpers.fresh_state()
        aiwf.ensure_dirs()
        old, new = aiwf.session_file("old"), aiwf.session_file("new")
        aiwf.save_json(old, {"id": "old"})
        aiwf.save_json(new, {"id": "new"})
        t = time.time() - 40 * 86400
        os.utime(old, (t, t))
        aiwf.prune_sessions(30)
        self.assertFalse(old.exists())
        self.assertTrue(new.exists())


class ArchivePaginationTest(unittest.TestCase):
    def test_walks_all_pages(self):
        helpers.fresh_state()
        aiwf.save_profiles({"profiles": {"default": {"login": "me", "repo": "me/work"}}})
        ghboard.use("default")
        aiwf.save_json(ghboard.BOARD, {"repo": "me/work", "project_id": "P"})
        old = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() - 30 * 86400))
        recent = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() - 1 * 86400))
        mk = lambda i, closed: {"id": i, "isArchived": False, "fieldValueByName": {"name": "완료"}, "content": {"number": 1, "closedAt": closed}}
        pages = [{"node": {"items": {"pageInfo": {"hasNextPage": True, "endCursor": "c1"}, "nodes": [mk("A", recent)]}}},
                 {"node": {"items": {"pageInfo": {"hasNextPage": False, "endCursor": None}, "nodes": [mk("B", old)]}}}]
        archived = []

        def fake_graphql(query, **v):
            if "archiveProjectV2Item" in query:
                archived.append(v["i"])
                return {}
            return pages.pop(0)

        with mock.patch.object(ghboard, "graphql", fake_graphql):
            n = ghboard.archive_done(14)
        self.assertEqual((n, archived), (1, ["B"]))        # 둘째 페이지의 오래된 카드까지 처리


class FetchThrottleTest(unittest.TestCase):
    def test_fetched_recently(self):
        repo = helpers.TMP / "fetchrepo"
        repo.mkdir(exist_ok=True)
        subprocess.run(["git", "init", "-q", str(repo)], check=True)
        hook = load_hook()
        self.assertFalse(hook.fetched_recently(str(repo)))          # fetch 한 적 없음
        fh = repo / ".git" / "FETCH_HEAD"
        fh.write_text("")
        self.assertTrue(hook.fetched_recently(str(repo)))
        t = time.time() - 3600
        os.utime(fh, (t, t))
        self.assertFalse(hook.fetched_recently(str(repo)))          # 1시간 전이면 다시 fetch


class OnOffCommandTest(unittest.TestCase):
    def run_cli(self, *args, run="r1"):
        env = {**os.environ, "AI_BOARD_STATE": os.environ["AI_BOARD_STATE"], "AI_BOARD_MODE": "work"}
        if run:
            env["AI_BOARD_RUN"] = run
        else:
            env.pop("AI_BOARD_RUN", None)
        return subprocess.run([sys.executable, str(helpers.ROOT / "bin" / "ai-board"), *args], capture_output=True, text=True, env=env)

    def setUp(self):
        helpers.fresh_state()

    def test_off_then_on_restores_launch_mode(self):
        self.assertEqual(self.run_cli("off").returncode, 0)
        self.assertEqual(aiwf.effective_mode(aiwf.load_json(aiwf.run_file("r1"), {})), "off")
        self.assertEqual(self.run_cli("off").returncode, 0)           # 두 번 꺼도 prev 가 off 로 덮이지 않는다
        r = self.run_cli("on")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(aiwf.load_json(aiwf.run_file("r1"), {})["mode"], "work")

    def test_requires_launcher_session(self):
        r = self.run_cli("off", run=None)
        self.assertNotEqual(r.returncode, 0)

    def test_removed_commands_are_gone(self):
        for cmd in ("list", "task", "close", "title", "flush", "archive", "sync", "search", "digest", "notify", "skip", "personal", "work", "now",
                    "init", "check", "worker", "register"):
            self.assertNotEqual(self.run_cli(cmd).returncode, 0, cmd)


class SetupEntryPointsTest(unittest.TestCase):
    """ai-board 밖으로 옮긴 내부 진입점(설정 마법사 check, 전송기 실행 코드)이 동작하는지."""

    def test_boardsetup_check_without_config(self):
        state = helpers.fresh_state()
        env = {**os.environ, "AI_BOARD_STATE": str(state)}
        r = subprocess.run([sys.executable, str(helpers.ROOT / "lib" / "boardsetup.py"), "check"], capture_output=True, text=True, env=env)
        self.assertEqual(r.returncode, 1, r.stderr)
        self.assertTrue(r.stdout.startswith("MISSING"), r.stdout)

    def test_boardsetup_help_lists_options(self):
        r = subprocess.run([sys.executable, str(helpers.ROOT / "lib" / "boardsetup.py"), "--help"], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        for opt in ("--repo", "--board", "--board-title", "--reset-columns", "check"):
            self.assertIn(opt, r.stdout)

    def test_worker_code_imports_from_lib(self):
        """전송기를 띄우는 코드가 다른 폴더에서도 ghboard 를 import 할 수 있다 (실제 전송 루프는 돌리지 않는다)."""
        code = ghboard.WORKER_CODE.replace("ghboard.worker()", "print(callable(ghboard.worker))")
        r = subprocess.run([sys.executable, "-c", code, str(helpers.ROOT / "lib")], capture_output=True, text=True, cwd="/",
                           env={**os.environ, "AI_BOARD_STATE": os.environ["AI_BOARD_STATE"]})
        self.assertEqual((r.returncode, r.stdout.strip()), (0, "True"), r.stderr)

    def test_spawn_worker_uses_worker_code(self):
        helpers.fresh_state()
        aiwf.save_profiles({"profiles": {"default": {"login": "me", "repo": "me/work"}}})
        ghboard.use("default")
        aiwf.save_json(ghboard.BOARD, {"repo": "me/work", "project_id": "P", "status_field": "F"})
        with mock.patch.object(ghboard.subprocess, "Popen") as popen:
            ghboard.spawn_worker()
        args = popen.call_args.args[0]
        self.assertEqual(args[1:3], ["-c", ghboard.WORKER_CODE])
        self.assertTrue(args[3].endswith("lib"))


class LocalStateMaskedTest(unittest.TestCase):
    """카드·일지뿐 아니라 로컬 상태(세션·이벤트)에도 시크릿이 남지 않아야 한다 (다음 세션 시작 요약에 다시 쓰이므로)."""

    def test_session_and_events_have_no_secret(self):
        state = helpers.fresh_state()
        repo = helpers.TMP / "maskrepo"
        repo.mkdir(exist_ok=True)
        subprocess.run(["git", "init", "-q", str(repo)], check=True)
        env = {**os.environ, "AI_BOARD_STATE": str(state), "AI_BOARD_MODE": "personal"}
        env.pop("AI_BOARD_RUN", None)

        def fire(event, **extra):
            d = {"hook_event_name": event, "session_id": "mask-1234", "cwd": str(repo), **extra}
            subprocess.run([sys.executable, str(helpers.ROOT / "bin" / "ai-hook")], input=json.dumps(d), text=True, capture_output=True, env=env)

        fire("SessionStart", source="startup")
        fire("UserPromptSubmit", prompt=f"이 토큰으로 해줘 {SECRET}")
        fire("PostToolUse", tool_name="Bash", tool_input={"command": f"curl -H 'X: {SECRET}' http://x"}, tool_response="")
        fire("Stop", last_assistant_message=f"쓰지 않았습니다 {SECRET}")
        for f in list(state.rglob("*.json")) + list(state.rglob("*.jsonl")) + list(state.rglob("*.md")):
            self.assertNotIn(SECRET, f.read_text(encoding="utf-8"), str(f))


if __name__ == "__main__":
    unittest.main()
