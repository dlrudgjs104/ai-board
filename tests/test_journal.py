import json
import unittest

import helpers
import journal


class ParseDecisionsTest(unittest.TestCase):
    def test_heading_list(self):
        msg = "끝난 것\n\n### 결정 사항\n- A 방식으로 한다\n- B 는 하지 않는다\n\n### 검토 필요도: 낮음"
        self.assertEqual(journal.parse_decisions(msg), ["A 방식으로 한다", "B 는 하지 않는다"])

    def test_inline(self):
        self.assertEqual(journal.parse_decisions("결정 사항: 단일 계정만 쓴다"), ["단일 계정만 쓴다"])

    def test_none_and_empty(self):
        self.assertEqual(journal.parse_decisions(""), [])
        self.assertEqual(journal.parse_decisions("### 결정 사항\n- (없음)"), [])
        self.assertEqual(journal.parse_decisions("그냥 답변입니다"), [])

    def test_duplicates_removed(self):
        self.assertEqual(journal.parse_decisions("### 결정 사항\n- 같은 것\n- 같은 것"), ["같은 것"])


class PathTest(unittest.TestCase):
    def test_safe(self):
        self.assertEqual(journal.safe("my proj/x"), "my_proj_x")
        self.assertEqual(journal.safe(""), "unknown")

    def test_rel_path_has_session_and_jid(self):
        s = {"id": "abcdef12-0000", "jid": "a1b2c3", "project": "shop", "started": 0}
        p = journal.rel_path(s)
        self.assertTrue(p.startswith("records/shop/") and p.endswith("_abcdef12-a1b2c3.md"), p)
        self.assertTrue(journal.rel_path(s, 2).endswith("-a1b2c3-2.md"))


SECRET = "ghp_abcdefghijklmnopqrstuvwxyz0123456789"


class RedactionInJournalTest(unittest.TestCase):
    def setUp(self):
        helpers.fresh_state()
        self.s = {"id": "s1", "jid": "j1", "project": "p", "path": "/p", "started": 1000}

    def test_request_decision_report_are_masked(self):
        journal.new_turn(self.s, f"이 토큰으로 해줘 {SECRET}", "personal")
        journal.add_decision(self.s, f"토큰 {SECRET} 사용")
        journal.finish_turn(self.s, f"완료. TOKEN=abcd1234efgh 를 썼다\n### 결정 사항\n- 키 {SECRET} 로 한다")
        md = journal.render(self.s)
        self.assertNotIn(SECRET, md)
        self.assertNotIn("abcd1234efgh", md)

    def test_transcript_steps_are_masked(self):
        tpath = helpers.TMP / "t.jsonl"
        rows = [{"type": "assistant", "timestamp": "2026-01-01T00:00:10Z", "message": {"content": [
            {"type": "tool_use", "name": "Bash", "input": {"command": f"curl -H 'Authorization: Bearer {SECRET}' x"}},
            {"type": "text", "text": f"토큰 {SECRET} 확인"}]}}]
        tpath.write_text("\n".join(json.dumps(r) for r in rows), encoding="utf-8")
        steps = journal.collect_steps(tpath, 0)
        self.assertEqual(len(steps), 2)
        self.assertTrue(all(SECRET not in st["v"] for st in steps))

    def test_render_final_net_catches_late_secrets(self):
        journal.new_turn(self.s, "요청", "personal")
        journal.cur(self.s)["files"].append(f"notes-{SECRET}.txt")     # 파일 이름처럼 개별 처리 밖으로 들어온 값
        self.assertNotIn(SECRET, journal.render(self.s))

    def test_write_local_creates_file(self):
        journal.new_turn(self.s, "요청", "personal")
        journal.finish_turn(self.s, "보고")
        path = journal.write_local(self.s)
        self.assertTrue(path.exists())
        self.assertIn("보고", path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
