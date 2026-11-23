"""설치 마법사(run_init)가 기본으로 ai-board 레포·보드를 만들고, 이미 있는 work 레포·AI Board 보드는 건드리지 않는지 가짜 GitHub 로 검증."""
import json
import unittest
from types import SimpleNamespace
from unittest import mock

import helpers
import aiwf
import boardsetup
import ghboard
from ghboard import GitHubError


class FakeGitHub:
    def __init__(self, repos=None, boards=None):
        self.repos = set(repos or [])                   # 이미 있는 레포 (owner/name)
        self.boards = list(boards or [])                # 이미 있는 보드 [{"number","title"}]
        self.created_repos, self.created_boards, self.gh_calls = [], [], []

    # ghboard.rest
    def rest(self, method, endpoint, payload=None):
        if method == "GET" and endpoint.startswith("repos/") and "/contents/" not in endpoint:
            name = endpoint[len("repos/"):]
            if name in self.repos:
                return {"private": True, "has_issues": True}
            raise GitHubError("Not Found (HTTP 404)")
        if method == "POST" and endpoint == "user/repos":
            self.created_repos.append(payload["name"])
            self.repos.add(f"me/{payload['name']}")
            return {}
        if method == "GET" and "/contents/" in endpoint:
            raise GitHubError("Not Found (HTTP 404)")
        return {}

    # ghboard.graphql
    def graphql(self, query, **v):
        if "projectV2(number" in query:
            return {"user": {"projectV2": {"id": "P", "url": "https://x/board", "title": "t", "fields": {"nodes": [
                {"id": "F", "name": "Status", "options": [{"id": "1", "name": "Todo"}, {"id": "2", "name": "In Progress"},
                                                          {"id": "3", "name": "Done"}]},
                {"id": "R", "name": "검토필요도", "options": []}]}}}}
        return {}

    # boardsetup.gh  (gh CLI)
    def gh(self, login, *args, inp=None):
        self.gh_calls.append(args)
        ok = lambda out="": SimpleNamespace(returncode=0, stdout=out, stderr="")
        if args[:2] == ("project", "list"):
            return ok(json.dumps({"projects": [{**b, "closed": False} for b in self.boards]}))
        if args[:2] == ("project", "create"):
            title = args[args.index("--title") + 1]
            number = 100 + len(self.created_boards)
            self.created_boards.append(title)
            self.boards.append({"number": number, "title": title})
            return ok(str(number))
        return ok()


class WizardDefaultsTest(unittest.TestCase):
    def run_wizard(self, gh, **opts):
        helpers.fresh_state()
        patches = [mock.patch.object(ghboard, "rest", gh.rest), mock.patch.object(ghboard, "graphql", gh.graphql),
                   mock.patch.object(boardsetup, "gh", gh.gh), mock.patch.object(boardsetup, "current_account", lambda o: "me"),
                   mock.patch.object(boardsetup, "scopes", lambda l: ["repo", "project"]),
                   mock.patch.object(boardsetup.subprocess, "run", lambda *a, **k: SimpleNamespace(returncode=0, stdout="", stderr=""))]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)
        boardsetup.run_init({"yes": True, **opts})
        return aiwf.profiles_conf()["profiles"][aiwf.SLOT]

    def test_defaults_are_ai_board(self):
        self.assertEqual((boardsetup.DEFAULT_REPO, boardsetup.DEFAULT_BOARD), ("ai-board", "ai-board"))

    def test_fresh_install_creates_ai_board_repo_and_board(self):
        gh = FakeGitHub()
        conf = self.run_wizard(gh)
        self.assertEqual(gh.created_repos, ["ai-board"])
        self.assertEqual(gh.created_boards, ["ai-board"])
        self.assertEqual((conf["repo"], conf["board_title"]), ("me/ai-board", "ai-board"))

    def test_existing_work_repo_and_AI_Board_are_ignored(self):
        """기존 work 레포와 'AI Board' 보드가 있어도 연결하지 않고 ai-board 를 새로 만든다."""
        gh = FakeGitHub(repos={"me/work"}, boards=[{"number": 1, "title": "AI Board"}])
        conf = self.run_wizard(gh)
        self.assertEqual(gh.created_repos, ["ai-board"])
        self.assertEqual(gh.created_boards, ["ai-board"])
        self.assertEqual(conf["repo"], "me/ai-board")
        self.assertNotEqual(conf["board"], 1)                         # 옛 보드 #1 에 붙지 않았다
        self.assertEqual(ghboard.conf()["title"], "ai-board")

    def test_existing_ai_board_repo_and_board_are_reused(self):
        gh = FakeGitHub(repos={"me/ai-board"}, boards=[{"number": 5, "title": "ai-board"}])
        conf = self.run_wizard(gh)
        self.assertEqual((gh.created_repos, gh.created_boards), ([], []))   # 두 번째 실행은 새로 만들지 않는다
        self.assertEqual((conf["repo"], conf["board"]), ("me/ai-board", 5))

    def test_explicit_names_still_win(self):
        gh = FakeGitHub()
        conf = self.run_wizard(gh, repo="my-log", board_title="내 보드", create_repo=True)
        self.assertEqual((gh.created_repos, gh.created_boards), (["my-log"], ["내 보드"]))
        self.assertEqual(conf["repo"], "me/my-log")


if __name__ == "__main__":
    unittest.main()
