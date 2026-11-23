"""로컬 작업 일지(~/.ai-workflow/records)를 찾고, 하루 요약을 만들고, 오래된 것을 정리한다.

- search: 일지 안에서 키워드를 찾는다 ("지난달에 이거 왜 이렇게 결정했지")
- digest: 최근 며칠 동안의 요청·결정·커밋을 프로젝트별로 한 번에 본다
- prune:  오래된 로컬 일지를 지운다 (기록 레포에 올라간 사본은 그대로 둔다)
"""
import time
from pathlib import Path

import aiwf


def records_dir() -> Path:
    return aiwf.STATE / "records"


def search(query: str, project=None, limit=40, root=None):
    """일지 md 에서 query(대소문자 무시)가 들어 있는 줄을 찾는다. [(상대경로, 줄번호, 줄)] 최신 파일부터."""
    root = root or records_dir()
    q = (query or "").strip().lower()
    if not q or not root.is_dir():
        return []
    files = sorted((f for f in root.rglob("*.md") if not project or f.parent.name == project),
                   key=lambda f: f.name, reverse=True)
    hits = []
    for f in files:
        try:
            lines = f.read_text(encoding="utf-8").splitlines()
        except OSError:
            continue
        for n, line in enumerate(lines, 1):
            if q in line.lower():
                hits.append((str(f.relative_to(root)), n, line.strip()))
                if len(hits) >= limit:
                    return hits
    return hits


def digest(days: float = 1, now=None, sessions=None) -> str:
    """최근 days 일 동안의 요청을 프로젝트별로 정리한 글."""
    now = now or time.time()
    since = now - days * 86400
    sessions = aiwf.read_sessions() if sessions is None else sessions
    by_project = {}
    for s in sessions:
        for t in s.get("journal") or []:
            if (t.get("t") or 0) >= since:
                by_project.setdefault(s.get("project") or "?", []).append((t, s))
    if not by_project:
        return f"최근 {days:g}일 동안 기록된 작업이 없습니다."
    fmt = lambda x: time.strftime("%m-%d %H:%M", time.localtime(x))
    out = [f"■ 최근 {days:g}일 작업 요약 (요청 {sum(len(v) for v in by_project.values())}건 · 프로젝트 {len(by_project)}개)"]
    for proj in sorted(by_project):
        rows = sorted(by_project[proj], key=lambda ts: ts[0].get("t") or 0)
        out += ["", f"[{proj}]"]
        for t, s in rows:
            state = "완료" if t.get("done_t") else "진행 중/미완"
            out.append(f"  - {fmt(t['t'])} {aiwf.short(t.get('request') or '(내용 없음)', 80)}  ({state})")
            for d in t.get("decisions") or []:
                out.append(f"      결정: {aiwf.short(d, 110)}")
            for c in t.get("commits") or []:
                out.append(f"      커밋: {c}")
            if t.get("files"):
                out.append(f"      수정 파일 {len(t['files'])}개")
    return "\n".join(out)


def prune(days: int = 90, dry_run: bool = True, root=None, now=None):
    """수정한 지 days 일이 지난 일지를 찾아(dry_run 이면 목록만) 지운다. 지운(또는 지울) 파일 목록을 돌려준다."""
    root = root or records_dir()
    cutoff = (now or time.time()) - days * 86400
    old = []
    if root.is_dir():
        for f in root.rglob("*.md"):
            try:
                if f.stat().st_mtime < cutoff:
                    old.append(f)
            except OSError:
                pass
    if not dry_run:
        for f in old:
            try:
                f.unlink()
            except OSError:
                pass
        for d in sorted((p for p in root.rglob("*") if p.is_dir()), reverse=True):
            try:
                d.rmdir()       # 비어 있을 때만 지워진다
            except OSError:
                pass
    return sorted(old)
