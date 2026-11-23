"""전송기의 핵심 흐름(process, worker)을 가짜 GitHub 로 검증한다: 카드 생성·이동·연결·닫힘 처리·재시도."""
import time
import unittest
from unittest import mock

import helpers
import aiwf
import ghboard
from ghboard import GitHubError


class _StopWorker(Exception):
    pass


class FakeGitHub:
    """rest/graphql 호출을 기록하고 그럴듯한 응답을 돌려준다."""

    def __init__(self):
        self.calls = []
        self.next_issue = 10
        self.issue_state = {}          # 번호 → open|closed (없으면 open)

    def rest(self, method, endpoint, payload=None):
        self.calls.append((method, endpoint, payload))
        if method == "POST" and endpoint.endswith("/issues"):
            n, self.next_issue = self.next_issue, self.next_issue + 1
            return {"number": n, "node_id": f"N{n}", "html_url": f"https://x/{n}", "title": payload["title"]}
        if method == "GET" and "/issues/" in endpoint:
            n = int(endpoint.rsplit("/", 1)[1])
            return {"number": n, "node_id": f"N{n}", "html_url": f"https://x/{n}", "title": f"issue {n}",
                    "state": self.issue_state.get(n, "open")}
        return {}

    def graphql(self, query, **v):
        self.calls.append(("GQL", query.split("{")[0].strip()[:40] + " " + " ".join(sorted(v)), v))
        if "addProjectV2ItemById" in query:
            return {"addProjectV2ItemById": {"item": {"id": f"ITEM-{v['c']}"}}}
        return {}

    def endpoints(self, method):
        return [e for m, e, _ in self.calls if m == method]

    def status_sets(self):
        return [v["o"] for m, _, v in self.calls if m == "GQL" and "o" in v]


def make_session(sid="s1", project="shop", **extra):
    s = {"id": sid, "project": project, "path": "/p", "mode": "personal", "state": "working",
         "request": "로그인 고쳐줘", "requests": [{"t": time.time(), "text": "로그인 고쳐줘"}], "files": [], "commits": []}
    s.update(extra)
    aiwf.save_json(aiwf.session_file(sid), s)
    return s


class ProcessTest(unittest.TestCase):
    def setUp(self):
        helpers.fresh_state()
        aiwf.save_profiles({"profiles": {"default": {"login": "me", "repo": "me/work"}}})
        ghboard.use("default")
        aiwf.save_json(ghboard.BOARD, {"repo": "me/work", "project_id": "P", "status_field": "F",
                                       "status_options": {n: f"opt-{n}" for n in ghboard.COLUMNS}, "url": "https://x/board",
                                       "labels": ["ai-card", "proj:shop"]})
        self.gh = FakeGitHub()
        for name in ("rest", "graphql"):
            p = mock.patch.object(ghboard, name, getattr(self.gh, name))
            p.start()
            self.addCleanup(p.stop)
        make_session()

    def test_create_card_then_status(self):
        left = ghboard.process({"sid": "s1", "create": True, "status": "AI작업중", "title": "로그인 고쳐줘", "body": True})
        self.assertIsNone(left)
        issue = [p for m, e, p in self.gh.calls if m == "POST" and e.endswith("/issues")][0]
        self.assertEqual(issue["title"], "[shop] 로그인 고쳐줘")
        card = ghboard.cards()["10"]
        self.assertEqual((card["status"], card["project"], card["sids"]), ("AI작업중", "shop", ["s1"]))
        self.assertEqual(self.gh.status_sets(), ["opt-AI작업중"])

    def test_no_card_and_no_create_sends_nothing(self):
        self.assertIsNone(ghboard.process({"sid": "s1", "status": "검토대기", "body": True}))
        self.assertEqual(self.gh.calls, [])

    def test_missing_session_is_dropped(self):
        self.assertIsNone(ghboard.process({"sid": "ghost", "create": True}))
        self.assertEqual(self.gh.calls, [])

    def test_existing_card_moves_comments_and_closes(self):
        ghboard.process({"sid": "s1", "create": True, "status": "AI작업중", "title": "t"})
        self.gh.calls.clear()
        ghboard.process({"sid": "s1", "status": "완료", "review": None, "comments": ["### ✅ 작업 보고\n끝"], "close": True, "final": True,
                         "body": True})
        self.assertEqual(self.gh.status_sets(), ["opt-완료"])
        self.assertEqual(len(self.gh.endpoints("POST")), 1)       # 코멘트 하나
        patches = [p for m, e, p in self.gh.calls if m == "PATCH"]
        self.assertIn({"state": "closed", "state_reason": "completed"}, patches)
        self.assertEqual(ghboard.cards()["10"]["status"], "완료")

    def test_closed_card_gets_new_card_for_fresh_request(self):
        ghboard.process({"sid": "s1", "create": True, "status": "검토대기", "title": "첫 요청"})
        self.gh.issue_state[10] = "closed"                       # 사람이 웹에서 닫음
        ghboard.process({"sid": "s1", "create": True, "fresh": True, "status": "AI작업중", "title": "다음 요청", "body": True})
        cards = ghboard.cards()
        self.assertEqual(cards["10"]["status"], "완료")           # 이전 카드는 다시 열지 않는다
        self.assertEqual(cards["11"]["status"], "AI작업중")
        self.assertEqual(ghboard.card_of("s1"), 11)

    def test_open_card_is_continued_not_duplicated(self):
        ghboard.process({"sid": "s1", "create": True, "status": "검토대기", "title": "첫 요청"})
        ghboard.process({"sid": "s1", "create": True, "fresh": True, "status": "AI작업중", "title": "이어서", "body": True})
        self.assertEqual(sorted(ghboard.cards()), ["10"])         # 열려 있으면 새 카드를 만들지 않는다
        self.assertEqual(ghboard.cards()["10"]["status"], "AI작업중")

    def test_bind_existing_issue(self):
        ghboard.process({"sid": "s1", "bind": 12, "status": "AI작업중", "body": True})
        self.assertEqual(ghboard.card_of("s1"), 12)
        self.assertEqual(ghboard.cards()["12"]["sids"], ["s1"])
        self.assertEqual([e for e in self.gh.endpoints("POST") if e.endswith("/issues")], [])   # 새 이슈는 만들지 않는다

    def test_body_updates_are_throttled_unless_final(self):
        ghboard.process({"sid": "s1", "create": True, "status": "AI작업중", "title": "t"})
        self.gh.calls.clear()
        left = ghboard.process({"sid": "s1", "body": True})       # 방금 본문을 썼으므로 미룬다
        self.assertEqual(self.gh.endpoints("PATCH"), [])
        self.assertTrue(left and left["not_before"] > time.time())
        ghboard.process({"sid": "s1", "body": True, "final": True})     # 마지막 보고는 기다리지 않는다
        self.assertEqual(len(self.gh.endpoints("PATCH")), 1)

    def test_rename_adds_project_prefix(self):
        ghboard.process({"sid": "s1", "create": True, "status": "AI작업중", "title": "t"})
        self.gh.calls.clear()
        ghboard.process({"sid": "s1", "rename": "요청 > 수정"})
        self.assertEqual([p for m, e, p in self.gh.calls if m == "PATCH"][0]["title"], "[shop] 요청 > 수정")


class WorkerTest(unittest.TestCase):
    def setUp(self):
        helpers.fresh_state()
        aiwf.save_profiles({"profiles": {"default": {"login": "me", "repo": "me/work"}}})
        ghboard.use("default")
        aiwf.save_json(ghboard.BOARD, {"repo": "me/work", "project_id": "P", "status_field": "F", "status_options": {}, "url": "u"})
        make_session()

    def test_retryable_error_keeps_work_in_queue(self):
        ghboard.enqueue("s1", status="검토대기", comments=["보고"])
        # 한도 오류 뒤 전송기는 "기다렸다 다시 보내려고" 대기 루프에 들어간다. 첫 대기에서 테스트를 빠져나온다
        with mock.patch.object(ghboard, "process", side_effect=GitHubError("API rate limit exceeded")), \
                mock.patch.object(ghboard.time, "sleep", side_effect=_StopWorker):
            with self.assertRaises(_StopWorker):
                ghboard.worker(foreground=True)
        q = aiwf.load_json(ghboard._qfile("s1"), None)
        self.assertIsNotNone(q, "한도 오류로 작업이 사라졌다")
        self.assertEqual(q["comments"], ["보고"])
        self.assertGreater(q["not_before"], time.time())          # 잠시 뒤에 다시 보낸다
        errs = [e for e in aiwf.read_events(50) if e.get("event") == "SyncError"]
        self.assertTrue(errs)

    def test_successful_send_empties_queue(self):
        ghboard.enqueue("s1", status="검토대기")
        with mock.patch.object(ghboard, "process", return_value=None) as p, mock.patch.object(ghboard.time, "sleep"):
            # 대기열이 비면 5초(foreground) 뒤 끝나므로, 시간을 앞당겨 바로 끝나게 한다
            real = time.time
            ticks = iter(range(10 ** 6))
            with mock.patch.object(ghboard.time, "time", lambda: real() + next(ticks) * 3):
                ghboard.worker(foreground=True)
        p.assert_called_once()
        self.assertFalse(ghboard._qfile("s1").exists())


if __name__ == "__main__":
    unittest.main()
