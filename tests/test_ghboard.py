import unittest
from unittest import mock

import helpers
import aiwf
import ghboard


def setup_board():
    helpers.fresh_state()
    aiwf.save_profiles({"profiles": {"default": {"login": "me", "repo": "me/work"}}})
    ghboard.use("default")
    aiwf.save_json(ghboard.BOARD, {"repo": "me/work", "project_id": "P", "status_field": "F",
                                   "status_options": {n: f"opt-{n}" for n in ghboard.COLUMNS}, "url": "https://x/board"})


class QueueTest(unittest.TestCase):
    def setUp(self):
        setup_board()

    def test_enqueue_merges(self):
        ghboard.enqueue("s1", status="AI작업중", body=True)
        ghboard.enqueue("s1", status="검토대기", comments=["a"])
        ghboard.enqueue("s1", comments=["b"])
        q = aiwf.load_json(ghboard._qfile("s1"), {})
        self.assertEqual(q["status"], "검토대기")          # 상태는 마지막 값
        self.assertEqual(q["comments"], ["a", "b"])        # 코멘트는 이어 붙음
        self.assertTrue(q["body"])

    def test_cancel_tentative_only_removes_tentative(self):
        ghboard.enqueue("t", create=True, tentative=True, delay=20)
        ghboard.enqueue("n", create=True, status="AI작업중")
        ghboard.cancel_tentative("t")
        ghboard.cancel_tentative("n")
        self.assertFalse(ghboard._qfile("t").exists())
        self.assertTrue(ghboard._qfile("n").exists())

    def test_status_change_releases_delayed_body(self):
        ghboard.enqueue("s", body=True, delay=60)
        self.assertGreater(aiwf.load_json(ghboard._qfile("s"), {})["not_before"], 0)
        ghboard.enqueue("s", status="검토대기")
        self.assertNotIn("not_before", aiwf.load_json(ghboard._qfile("s"), {}))


class CardTest(unittest.TestCase):
    def setUp(self):
        setup_board()
        ghboard.save_card(7, item="I7", sids=["s1"], project="shop", url="https://x/7", status="AI작업중", title="t")

    def test_card_of_skips_completed(self):
        self.assertEqual(ghboard.card_of("s1"), 7)
        ghboard.save_card(7, status="완료")
        self.assertIsNone(ghboard.card_of("s1"))

    def test_comment_and_title_are_redacted(self):
        secret = "ghp_abcdefghijklmnopqrstuvwxyz0123456789"
        with mock.patch.object(ghboard, "rest") as rest:
            ghboard.comment(7, f"토큰 {secret}")
            ghboard.rename(7, f"제목 {secret}")
            ghboard.update_body(7, f"본문 TOKEN=abcd1234efgh")
        sent = " ".join(str(c.args[2]) for c in rest.call_args_list)
        self.assertNotIn(secret, sent)
        self.assertNotIn("abcd1234efgh", sent)


class SyncTest(unittest.TestCase):
    def setUp(self):
        setup_board()
        ghboard.save_card(1, sids=["a"], status="검토대기")
        ghboard.save_card(2, sids=["b"], status="AI작업중")
        ghboard.save_card(3, sids=["c"], status="검토대기")
        ghboard.save_card(4, sids=["d"], status="판단필요")

    def board(self, nodes):
        return {"node": {"items": {"pageInfo": {"hasNextPage": False, "endCursor": None}, "nodes": nodes}}}

    def node(self, num, status, state="OPEN"):
        return {"fieldValueByName": {"name": status}, "content": {"number": num, "state": state}}

    def test_sync_applies_web_changes(self):
        data = self.board([self.node(1, "완료", "CLOSED"),       # 웹에서 닫음
                           self.node(2, "AI작업중"),              # 같음
                           self.node(3, "판단필요"),              # 웹에서 옮김
                           self.node(99, "완료")])                # 모르는 카드는 무시
        with mock.patch.object(ghboard, "graphql", return_value=data):
            changed = ghboard.sync_from_board()
        self.assertEqual(changed, 2)
        cards = ghboard.cards()
        self.assertEqual((cards["1"]["status"], cards["2"]["status"], cards["3"]["status"]), ("완료", "AI작업중", "판단필요"))
        self.assertNotIn("99", cards)

    def test_closed_issue_wins_over_column(self):
        with mock.patch.object(ghboard, "graphql", return_value=self.board([self.node(4, "판단필요", "CLOSED")])):
            ghboard.sync_from_board()
        self.assertEqual(ghboard.cards()["4"]["status"], "완료")

    def test_sessions_with_pending_work_are_left_alone(self):
        ghboard.enqueue("a", status="AI작업중")       # 카드 1 의 세션이 아직 보낼 작업이 있다
        with mock.patch.object(ghboard, "graphql", return_value=self.board([self.node(1, "완료", "CLOSED")])):
            self.assertEqual(ghboard.sync_from_board(), 0)
        self.assertEqual(ghboard.cards()["1"]["status"], "검토대기")

    def test_records_synced_time(self):
        with mock.patch.object(ghboard, "graphql", return_value=self.board([])):
            ghboard.sync_from_board()
        self.assertGreater(ghboard.conf()["synced_t"], 0)


class DateFieldTest(unittest.TestCase):
    def setUp(self):
        setup_board()
        aiwf.save_json(ghboard.BOARD, {**ghboard.conf(), "date_field": "FD"})
        ghboard.save_card(7, item="ITEM")

    def dates(self, fn):
        with mock.patch.object(ghboard, "graphql") as g, mock.patch.object(ghboard, "today", return_value="2026-11-24"):
            fn()
        return [(c.kwargs["f"], c.kwargs["d"]) for c in g.call_args_list]

    def test_date_is_recorded_only_once(self):
        self.assertEqual(self.dates(lambda: ghboard.set_start(7)), [("FD", "2026-11-24")])
        self.assertEqual(self.dates(lambda: ghboard.set_start(7)), [])

    def test_no_field_no_call(self):
        aiwf.save_json(ghboard.BOARD, {**ghboard.conf(), "date_field": None})
        self.assertEqual(self.dates(lambda: ghboard.set_start(7)), [])


if __name__ == "__main__":
    unittest.main()
