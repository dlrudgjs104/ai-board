"""ai-board 공용 모듈: 경로, 프로젝트 식별, 세션 상태 저장소.

상태 저장소(기본 ~/.ai-board, AI_BOARD_STATE 로 변경 가능)
  sessions/<세션ID>.json   세션별 현재 상태 (훅이 갱신, 대시보드가 읽음)
  events.jsonl             모든 세션의 활동 기록 (한 줄 = 한 이벤트)
  projects.json            알려진 프로젝트 목록 {경로: {name, path, seen}}
  runs/<실행ID>.json       런처 실행별 모드 상태 (ai-board off|on 이 쓰고 훅이 읽음)
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
STATE = Path(os.environ.get("AI_BOARD_STATE") or Path.home() / ".ai-board")
SESSIONS = STATE / "sessions"
EVENTS = STATE / "events.jsonl"
PROJECTS = STATE / "projects.json"
PROFILES = STATE / "profiles.json"   # 연결 정보: GitHub 계정·기록 레포·보드
RUNS = STATE / "runs"       # 런처 실행 하나(= claude 프로세스 하나)마다 상태 파일: 모드 전환·끄기·건너뛰기


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


def is_repo(path: str) -> bool:
    return git_root(path) != path or (Path(path) / ".git").exists()


def project_of(cwd: str):
    """작업 폴더 → (프로젝트 이름, 프로젝트 경로). 이름은 git 레포 폴더 이름, AI_PROJECT 로 바꿀 수 있다."""
    path = git_root(cwd)
    return os.environ.get("AI_PROJECT") or Path(path).name, path


def _child_repos(base: str, depth: int = 2):
    """base 아래 depth 단계까지의 git 레포 폴더 (숨김·node_modules 등은 건너뜀). 레포 안으로는 더 들어가지 않는다."""
    out = []
    skip = {"node_modules", "venv", ".venv", "__pycache__", "build", "dist", "target"}
    def walk(d, left):
        try:
            names = sorted(os.listdir(d))
        except OSError:
            return
        for n in names:
            if n.startswith(".") or n in skip:
                continue
            p = os.path.join(d, n)
            if not os.path.isdir(p):
                continue
            if os.path.exists(os.path.join(p, ".git")):
                out.append((n, p))
            elif left > 1:
                walk(p, left - 1)
    walk(base, depth)
    return out


def project_in_text(text: str, base: str = None):
    """요청 글에 프로젝트 이름이 있으면 (이름, 경로). 이미 알려진 프로젝트 → base(시작 폴더) 아래의 git 레포 순으로 찾고,
    여러 개면 가장 먼저 나온 것. 처음 보는 프로젝트(폴더 이름만 말한 경우)도 base 아래에 있으면 찾아서 등록한다."""
    low = text.lower()
    best = None
    cands = [(p.get("name") or "", p["path"]) for p in load_json(PROJECTS, {}).values() if is_repo(p["path"])]
    if base:
        known = {path for _, path in cands}
        cands += [(n, p) for n, p in _child_repos(base) if p not in known]
    for name, path in cands:
        n = name.lower()
        if len(n) < 3:
            continue
        m = re.search(r"(?<![a-z0-9_-])" + re.escape(n) + r"(?![a-z0-9_-])", low)   # 뒤에 붙는 조사(랑, 에서)는 허용
        if m and (best is None or m.start() < best[0]):
            best = (m.start(), name, path)
    if best:
        register_project(best[1], best[2])
        return best[1], best[2]
    return None


def register_project(name: str, path: str):
    projects = load_json(PROJECTS, {})
    p = projects.get(path, {})
    p.update({"name": name, "path": path, "seen": now()})
    projects[path] = p
    save_json(PROJECTS, projects)


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


# ---------------------------------------------------------------- 실행(런처) 단위 모드 상태
MODES = ("personal", "work", "lite")


def run_id():
    """런처가 정해 준 이 claude 실행의 ID. 런처 밖에서 시작했으면 None."""
    return os.environ.get("AI_BOARD_RUN") or None


def run_file(rid=None) -> Path:
    return RUNS / f"{rid or run_id()}.json"


def run_state(rid=None) -> dict:
    """{mode: "off" 이거나 없음(없으면 시작 모드), prev: 끄기 전 모드, injected: 마지막으로 규칙을 넣어 준 모드}"""
    return load_json(run_file(rid), {}) if (rid or run_id()) else {}


def save_run_state(rs: dict, rid=None):
    if rid or run_id():     # 런처 밖에서 시작한 세션은 상태 파일이 없다
        save_json(run_file(rid), rs)


def launch_mode() -> str:
    m = os.environ.get("AI_BOARD_MODE", "personal")
    return m if m in MODES else "personal"


def effective_mode(rs=None) -> str:
    """지금 이 세션에 적용되는 모드: personal | work | lite | off."""
    rs = run_state() if rs is None else rs
    return rs.get("mode") or launch_mode()


def prune_runs(days=7):
    """오래된 실행 상태 파일 정리."""
    if RUNS.is_dir():
        for f in RUNS.glob("*.json"):
            try:
                if now() - f.stat().st_mtime > days * 86400:
                    f.unlink()
            except OSError:
                pass


def prune_sessions(days=30):
    """오래 손대지 않은 세션 상태 파일 정리 (시작 때 전부 읽으므로 쌓이면 느려진다). 작업 일지·카드는 그대로 남는다."""
    if SESSIONS.is_dir():
        for f in SESSIONS.glob("*.json"):
            try:
                if now() - f.stat().st_mtime > days * 86400:
                    f.unlink()
            except OSError:
                pass


# ---------------------------------------------------------------- 연결 정보 (GitHub 계정 하나 · 기록 레포 하나 · 보드 하나)
# profiles.json: {"profiles": {"default": {login, owner, repo, board, board_title}}}
# 계정은 하나만 쓴다. 'default' 한 칸에 board.json · cards.json · queue/ 가 STATE/profiles/default/ 로 저장된다.
# (예전 다중 프로필 구조와 파일 위치를 그대로 써서, 이미 설정된 사용자의 기록이 그대로 이어진다)
SLOT = "default"


def profile_dir(name: str) -> Path:
    return STATE / "profiles" / name


def _migrate_legacy():
    """예전 단일 보드 설정(STATE/board.json 등)을 'default' 칸으로 옮긴다."""
    old = STATE / "board.json"
    if PROFILES.exists() or not old.exists():
        return
    b = load_json(old, {})
    d = profile_dir(SLOT)
    d.mkdir(parents=True, exist_ok=True)
    for n in ("board.json", "cards.json", "queue"):
        if (STATE / n).exists():
            os.replace(STATE / n, d / n)
    save_json(PROFILES, {"profiles": {
        SLOT: {"login": b.get("owner"), "owner": b.get("owner"), "repo": b.get("repo"), "board": b.get("number")}}})


def profiles_conf() -> dict:
    _migrate_legacy()
    d = load_json(PROFILES, {})
    d.setdefault("profiles", {})
    return d


def save_profiles(d: dict):
    save_json(PROFILES, {"profiles": d.get("profiles", {})})


def resolve_profile(path=None):
    """연결 정보가 있으면 항상 그 하나('default'), 없으면 None. (path 는 예전 호출과의 호환용으로만 받는다)"""
    d = profiles_conf()["profiles"]
    if SLOT in d:
        return SLOT
    return next(iter(d), None)
