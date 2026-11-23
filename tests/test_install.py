"""install.sh --uninstall [--purge] 검증. 실제 gh 와 ~/.ai-board 를 건드리지 않도록 가짜 gh, 임시 HOME·상태 폴더만 쓴다."""
import json
import os
import signal
import subprocess
import sys
import textwrap
import time
import unittest
from pathlib import Path

import helpers

INSTALL = helpers.ROOT / "install.sh"
STUB_GH = textwrap.dedent("""\\
    #!/usr/bin/env bash
    echo "$@" >> "$GH_STUB_LOG"
    # gh auth token --user NAME → 로그인돼 있는 계정만 성공
    if [[ "$1 $2 $3" == "auth token --user" ]]; then [[ "$4" == "fakeuser" || "$4" == "otheruser" ]] && { echo tok; exit 0; }; exit 1; fi
    exit 0
""")


class InstallUninstallTest(unittest.TestCase):
    def setUp(self):
        self.root = Path(helpers.fresh_state()).parent / f"inst-{time.time_ns()}"
        self.home, self.bin = self.root / "home", self.root / "bin"
        self.state = self.home / ".ai-board"
        stub = self.root / "stub"
        for d in (self.home, self.bin, stub, self.state / "records" / "shop", self.state / "sessions",
                  self.state / "profiles" / "default" / "queue"):
            d.mkdir(parents=True, exist_ok=True)
        (stub / "gh").write_text(STUB_GH)
        (stub / "gh").chmod(0o755)
        self.log = self.root / "gh.log"
        self.log.write_text("")
        (self.state / "profiles.json").write_text(json.dumps({"profiles": {"default": {"login": "fakeuser", "repo": "fakeuser/work"}}}))
        (self.state / "events.jsonl").write_text("{}\n")
        (self.state / "records" / "shop" / "a.md").write_text("# 일지")
        (self.state / "sessions" / "s1.json").write_text("{}")
        (self.state / "profiles" / "default" / "queue" / "q1.json").write_text("{}")
        for c in ("ai-board", "claude-personal", "claude-work", "claude-lite"):
            (self.bin / c).symlink_to(helpers.ROOT / "bin" / c)
        self.env = {**os.environ, "HOME": str(self.home), "AI_BOARD_STATE": str(self.state), "AI_BOARD_BIN": str(self.bin),
                    "PATH": f"{stub}:{os.environ['PATH']}", "GH_STUB_LOG": str(self.log)}
        self.procs = []

    def tearDown(self):
        for p in self.procs:
            p.kill()

    def run_install(self, *args, env=None):
        return subprocess.run(["bash", str(INSTALL), *args], capture_output=True, text=True, env=env or self.env,
                              stdin=subprocess.DEVNULL, timeout=60)

    def gh_calls(self):
        return self.log.read_text().splitlines()

    def links(self):
        return sorted(p.name for p in self.bin.iterdir())

    # ------------------------------------------------------------ 기본 제거 (예전 동작 유지)
    def test_plain_uninstall_removes_links_only(self):
        r = self.run_install("--uninstall")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.links(), [])
        self.assertTrue((self.state / "profiles.json").exists())       # 연결·기록은 그대로
        self.assertIn("--purge", r.stdout)                             # 더 지우는 방법을 안내
        self.assertEqual(self.gh_calls(), [])

    # ------------------------------------------------------------ dry-run
    def test_dry_run_deletes_nothing(self):
        r = self.run_install("--uninstall", "--purge", "--dry-run", "-y")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(len(self.links()), 4)
        self.assertTrue((self.state / "records" / "shop" / "a.md").exists())
        self.assertFalse([c for c in self.gh_calls() if "logout" in c])
        for expect in ("fakeuser", "대기열 1건", "작업 일지 1개", "dry-run"):
            self.assertIn(expect, r.stdout)

    # ------------------------------------------------------------ 실제 삭제
    def test_purge_removes_state_links_and_logs_out_only_connected_account(self):
        r = self.run_install("--uninstall", "--purge", "-y")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertFalse(self.state.exists())
        self.assertEqual(self.links(), [])
        logouts = [c for c in self.gh_calls() if c.startswith("auth logout")]
        self.assertEqual(logouts, ["auth logout -h github.com -u fakeuser"])      # 다른 계정은 로그아웃하지 않는다
        self.assertTrue(self.home.exists())                                       # 홈은 멀쩡

    def test_keep_records_preserves_journals_only(self):
        r = self.run_install("--uninstall", "--purge", "--keep-records", "-y")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual([p.name for p in self.state.iterdir()], ["records"])
        self.assertTrue((self.state / "records" / "shop" / "a.md").exists())

    def test_purge_without_login_in_gh_skips_logout(self):
        (self.state / "profiles.json").write_text(json.dumps({"profiles": {"default": {"login": "ghost", "repo": "ghost/work"}}}))
        r = self.run_install("--uninstall", "--purge", "-y")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertFalse(self.state.exists())
        self.assertFalse([c for c in self.gh_calls() if "logout" in c])

    def test_purge_when_nothing_is_installed(self):
        import shutil
        shutil.rmtree(self.state)
        r = self.run_install("--uninstall", "--purge", "-y")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("상태 폴더가 없습니다", r.stdout)

    # ------------------------------------------------------------ 확인 절차·안전장치
    def test_non_interactive_without_yes_cancels(self):
        r = self.run_install("--uninstall", "--purge")             # stdin 이 터미널이 아니고 -y 도 없다
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("취소", r.stdout)
        self.assertTrue((self.state / "profiles.json").exists())
        self.assertFalse([c for c in self.gh_calls() if "logout" in c])

    def test_refuses_home_directory(self):
        sentinel = self.home / "important.txt"
        sentinel.write_text("keep")
        r = self.run_install("--uninstall", "--purge", "-y", env={**self.env, "AI_BOARD_STATE": str(self.home)})
        self.assertNotEqual(r.returncode, 0)
        self.assertTrue(sentinel.exists())

    def test_refuses_home_even_if_it_looks_like_a_state_dir(self):
        """홈에 records/ 폴더가 있어 '상태 폴더처럼 보여도' 홈 자체는 지우지 않는다 (표식 검사와 별개의 안전장치)."""
        (self.home / "records").mkdir()
        (self.home / "records" / "mine.md").write_text("keep")
        sentinel = self.home / "important.txt"
        sentinel.write_text("keep")
        r = self.run_install("--uninstall", "--purge", "-y", env={**self.env, "AI_BOARD_STATE": str(self.home)})
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("위험", r.stdout)
        self.assertTrue(sentinel.exists() and (self.home / "records" / "mine.md").exists())

    def test_refuses_root_and_unrelated_directory(self):
        r = self.run_install("--uninstall", "--purge", "-y", env={**self.env, "AI_BOARD_STATE": "/"})
        self.assertNotEqual(r.returncode, 0)
        other = self.root / "docs"
        other.mkdir()
        (other / "thesis.txt").write_text("keep")
        r = self.run_install("--uninstall", "--purge", "-y", env={**self.env, "AI_BOARD_STATE": str(other)})
        self.assertNotEqual(r.returncode, 0)
        self.assertTrue((other / "thesis.txt").exists())

    def test_flags_require_uninstall(self):
        for flag in ("--purge", "--keep-records", "--dry-run"):
            self.assertEqual(self.run_install(flag).returncode, 2, flag)
        self.assertEqual(self.run_install("--uninstall", "--keep-records").returncode, 2)

    # ------------------------------------------------------------ 전송기 종료
    def spawn_lock_holder(self, lock):
        code = f"import fcntl,time; f=open({str(lock)!r},'w'); fcntl.flock(f, fcntl.LOCK_EX); time.sleep(60)"
        p = subprocess.Popen([sys.executable, "-c", code])
        self.procs.append(p)
        time.sleep(0.5)
        return p

    def test_stops_only_the_worker_of_this_state(self):
        mine = self.spawn_lock_holder(self.state / "worker.lock")
        other_dir = self.root / "other-state"
        other_dir.mkdir()
        theirs = self.spawn_lock_holder(other_dir / "worker.lock")
        r = self.run_install("--uninstall", "--purge", "-y")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        time.sleep(0.5)
        self.assertIsNotNone(mine.poll(), "이 상태 폴더의 전송기가 종료되지 않음")
        self.assertIsNone(theirs.poll(), "다른 상태 폴더의 전송기까지 종료됨")


if __name__ == "__main__":
    unittest.main()
