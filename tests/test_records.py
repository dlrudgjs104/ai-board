import os
import time
import unittest

import helpers
import records


class RecordsTest(unittest.TestCase):
    def setUp(self):
        self.root = helpers.fresh_state() / "records"
        (self.root / "shop").mkdir(parents=True)
        (self.root / "blog").mkdir(parents=True)
        (self.root / "shop" / "2026-01-02_x.md").write_text("# a\n결정: 캐시를 끈다\n끝", encoding="utf-8")
        (self.root / "blog" / "2026-01-01_y.md").write_text("캐시 이야기\n", encoding="utf-8")

    def test_search_case_insensitive_and_project_filter(self):
        self.assertEqual(len(records.search("캐시", root=self.root)), 2)
        hits = records.search("캐시", project="shop", root=self.root)
        self.assertEqual([(h[0], h[1]) for h in hits], [("shop/2026-01-02_x.md", 2)])
        self.assertEqual(records.search("", root=self.root), [])
        self.assertEqual(records.search("없는말", root=self.root), [])

    def test_search_limit(self):
        self.assertEqual(len(records.search("캐시", root=self.root, limit=1)), 1)

    def test_digest(self):
        now = time.time()
        s = {"project": "shop", "journal": [
            {"t": now - 100, "request": "로그인 고쳐줘", "decisions": ["세션 쿠키 사용"], "commits": ["abc fix"], "files": ["a.py"], "done_t": now},
            {"t": now - 10 * 86400, "request": "오래된 일"}]}
        out = records.digest(1, now=now, sessions=[s])
        self.assertIn("[shop]", out)
        self.assertIn("로그인 고쳐줘", out)
        self.assertIn("결정: 세션 쿠키 사용", out)
        self.assertNotIn("오래된 일", out)
        self.assertIn("없습니다", records.digest(1, now=now, sessions=[]))

    def test_prune_dry_run_then_delete(self):
        old = self.root / "shop" / "2026-01-02_x.md"
        t = time.time() - 200 * 86400
        os.utime(old, (t, t))
        found = records.prune(90, dry_run=True, root=self.root)
        self.assertEqual(found, [old])
        self.assertTrue(old.exists())                      # 기본은 지우지 않는다
        records.prune(90, dry_run=False, root=self.root)
        self.assertFalse(old.exists())
        self.assertFalse((self.root / "shop").exists())    # 빈 폴더 정리
        self.assertTrue((self.root / "blog" / "2026-01-01_y.md").exists())


if __name__ == "__main__":
    unittest.main()
