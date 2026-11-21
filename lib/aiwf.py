"""ai-workflow 공용 모듈: 경로, 프로젝트 식별, STATUS.md 해석, 세션 상태 저장소.

상태 저장소(기본 ~/.ai-workflow, AI_WORKFLOW_STATE 로 변경 가능)
  sessions/<세션ID>.json   세션별 현재 상태 (훅이 갱신, 대시보드가 읽음)
  events.jsonl             모든 세션의 활동 기록 (한 줄 = 한 이벤트)
  projects.json            알려진 프로젝트 목록 {경로: {name, path, seen}}
  board.json · cards.json · queue/   GitHub 보드 설정, 카드 기록, 보낼 작업 (lib/ghboard.py)
"""
import json
import os
import re
import subprocess
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STATE = Path(os.environ.get("AI_WORKFLOW_STATE") or Path.home() / ".ai-workflow")
SESSIONS = STATE / "sessions"
EVENTS = STATE / "events.jsonl"
PROJECTS = STATE / "projects.json"

SECTIONS = [("🔴", "판단 필요"), ("🟡", "진행 중"), ("🟢", "완료 · 검토 대기"), ("⚪", "예정")]


def now() -> float:
    return time.time()


def ensure_dirs():
    SESSIONS.mkdir(parents=True, exist_ok=True)


def load_json(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


def save_json(path: Path, data):
    """임시 파일에 쓴 뒤 바꿔치기해서, 읽는 쪽이 반쯤 쓴 파일을 보지 않게 한다."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=".tmp-")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    os.replace(tmp, path)


def append_event(ev: dict):
    ensure_dirs()
    with open(EVENTS, "a", encoding="utf-8") as f:
        f.write(json.dumps(ev, ensure_ascii=False) + "\n")


def read_events(limit=80):
    """파일 끝 200KB 만 읽어 최근 이벤트를 돌려준다 (기록이 쌓여도 느려지지 않게)."""
    try:
        with open(EVENTS, "rb") as f:
            f.seek(0, 2)
            size = f.tell()
            f.seek(max(0, size - 200_000))
            lines = f.read().decode("utf-8", "replace").splitlines()
    except OSError:
        return []
    if size > 200_000:
        lines = lines[1:]   # 잘린 첫 줄 버림
    out = []
    for line in lines[-limit:]:
        try:
            out.append(json.loads(line))
        except ValueError:
            pass
    return out


# ---------------------------------------------------------------- 프로젝트
def git_root(cwd: str) -> str:
    try:
        r = subprocess.run(["git", "-C", cwd, "rev-parse", "--show-toplevel"],
                           capture_output=True, text=True, timeout=3)
        if r.returncode == 0 and r.stdout.strip():
            return r.stdout.strip()
    except (OSError, subprocess.TimeoutExpired):
        pass
    return cwd


def project_of(cwd: str):
    """작업 폴더 → (프로젝트 이름, 프로젝트 경로). 이름은 git 레포 폴더 이름, AI_PROJECT 로 바꿀 수 있다."""
    path = git_root(cwd)
    return os.environ.get("AI_PROJECT") or Path(path).name, path


def register_project(name: str, path: str):
    projects = load_json(PROJECTS, {})
    p = projects.get(path, {})
    p.update({"name": name, "path": path, "seen": now()})
    projects[path] = p
    save_json(PROJECTS, projects)


def status_path(project_path: str) -> Path:
    return Path(project_path) / "docs" / "STATUS.md"


# ---------------------------------------------------------------- STATUS.md
def parse_status(path: Path):
    """STATUS.md → {updated, sections: {이모지: [{text, sub: [...]}]}}. 없으면 None."""
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    m = re.search(r"^최종 갱신:\s*(.+)$", text, re.M)
    sections = {e: [] for e, _ in SECTIONS}
    cur = None
    for line in text.splitlines():
        h = re.match(r"^##\s+(\S+)", line)
        if h:
            cur = h.group(1) if h.group(1) in sections else None
            continue
        if not cur:
            continue
        top = re.match(r"^-\s+(\[[ xX]\]\s*)?(.*)$", line)
        sub = re.match(r"^\s{2,}-\s+(.*)$", line)
        if top:
            item = top.group(2).strip()
            if item and item != "(없음)":
                sections[cur].append({"text": item, "sub": []})
        elif sub and sections[cur]:
            sections[cur][-1]["sub"].append(sub.group(1).strip())
    return {"updated": m.group(1).strip() if m else None, "sections": sections, "mtime": path.stat().st_mtime}


# ---------------------------------------------------------------- 세션
def session_file(sid: str) -> Path:
    return SESSIONS / f"{sid}.json"


def read_sessions():
    out = []
    if SESSIONS.is_dir():
        for f in SESSIONS.glob("*.json"):
            s = load_json(f, None)
            if s:
                out.append(s)
    return out


def live_state(s: dict) -> str:
    """세션 상태를 사람이 보는 상태로: working | needs_you | replied | idle | stale | ended"""
    st = s.get("state", "idle")
    if st == "ended":
        return "ended"
    age = now() - s.get("last_activity", 0)
    if st == "working" and age > 15 * 60:
        return "stale"      # 15분 넘게 소식 없음: 끊겼거나 멈췄을 수 있음
    if age > 12 * 3600:
        return "stale"
    return st


def short_lines(text: str, n: int) -> str:
    """줄바꿈은 살리고 길이만 자른다."""
    text = (text or "").strip()
    return text if len(text) <= n else text[: n - 1] + "…"


def short(text: str, n: int) -> str:
    text = " ".join((text or "").split())
    return text if len(text) <= n else text[: n - 1] + "…"
