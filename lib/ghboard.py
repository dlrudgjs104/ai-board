"""GitHub Projects 보드 연동: 세션 카드 생성·이동·보고를 대기열에 모아 전송기 하나가 순서대로 보낸다.

한도에 걸리지 않게 하는 방법
- 보드·필드·컬럼 ID 는 설정 때 한 번 받아 board.json 에 저장 → 컬럼 이동 = GraphQL 1번
- 모든 세션의 변경은 queue/<세션ID>.json 에 합쳐진다 (상태는 마지막 값만, 본문은 '바뀜' 표시만)
- 전송기(ai-board worker)는 컴퓨터에 하나만 돌고, 호출 사이에 간격을 두며, 카드 본문은 1분에 한 번까지만 고친다
- 한도·일시 오류는 기다렸다 다시 보낸다 (대기열에 남아 있으므로 잃지 않음)
"""
import fcntl
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

import aiwf

BOARD = aiwf.STATE / "board.json"      # 보드·필드·옵션 ID
CARDS = aiwf.STATE / "cards.json"      # 이슈 번호 → {item, sid, project, status, title, url, body_t}
QUEUE = aiwf.STATE / "queue"
QLOCK = aiwf.STATE / "queue.lock"
WLOCK = aiwf.STATE / "worker.lock"

COLUMNS = ["Backlog", "AI작업중", "판단필요", "검토대기", "완료"]
COLUMN_DESC = {"Backlog": ("GRAY", "시작 전"), "AI작업중": ("YELLOW", "AI가 진행 중"), "판단필요": ("RED", "사람 결정·승인 대기"),
               "검토대기": ("GREEN", "AI 답변 완료, 사람 검토 대기"), "완료": ("PURPLE", "확인 끝 (이슈 닫힘)")}
CALL_GAP = 0.7          # 호출 사이 최소 간격(초)
BODY_GAP = 60           # 같은 카드 본문 수정 최소 간격(초)


class GitHubError(RuntimeError):
    pass


# ---------------------------------------------------------------- 저수준 호출
_last_call = [0.0]


def _pace():
    wait = CALL_GAP - (time.time() - _last_call[0])
    if wait > 0:
        time.sleep(wait)
    _last_call[0] = time.time()


def rest(method, endpoint, payload=None):
    _pace()
    cmd = ["gh", "api", "--method", method, endpoint]
    if payload is not None:
        cmd += ["--input", "-"]
    r = subprocess.run(cmd, input=json.dumps(payload) if payload is not None else None, capture_output=True, text=True)
    if r.returncode != 0:
        raise GitHubError(r.stderr.strip()[:300] or r.stdout.strip()[:300])
    return json.loads(r.stdout) if r.stdout.strip() else {}


def graphql(query, **variables):
    _pace()
    payload = {"query": query, "variables": variables}
    r = subprocess.run(["gh", "api", "graphql", "--input", "-"], input=json.dumps(payload), capture_output=True, text=True)
    try:
        data = json.loads(r.stdout) if r.stdout.strip() else {}
    except ValueError:
        data = {}
    if r.returncode != 0 or data.get("errors"):
        msg = "; ".join(e.get("message", "") for e in data.get("errors", [])) or r.stderr.strip()
        raise GitHubError(msg[:300])
    return data.get("data", {})


def is_retryable(e):
    return bool(re.search(r"rate limit|secondary|abuse|timeout|502|503|504|temporar", str(e), re.I))


# ---------------------------------------------------------------- 설정
def conf():
    return aiwf.load_json(BOARD, {})


def configured():
    c = conf()
    return bool(c.get("project_id") and c.get("repo") and c.get("status_field"))


def load_board_ids(owner, number):
    """보드 ID, Status·검토필요도 필드와 옵션 ID 를 읽어 온다."""
    q = """query($login:String!,$n:Int!){ %s(login:$login){ projectV2(number:$n){ id url title
          fields(first:50){ nodes{ ... on ProjectV2SingleSelectField{ id name options{ id name } } } } } } }"""
    for kind in ("user", "organization"):
        try:
            d = graphql(q % kind, login=owner, n=number)
        except GitHubError as e:
            if is_retryable(e):
                raise
            continue
        p = (d.get(kind) or {}).get("projectV2")
        if p:
            fields = {f["name"]: f for f in p["fields"]["nodes"] if f}
            return p, fields
    raise GitHubError(f"보드를 찾지 못했습니다: {owner} #{number}")


def save_board(owner, number, repo):
    p, fields = load_board_ids(owner, number)
    st = fields.get("Status")
    if not st:
        raise GitHubError("보드에 Status 필드가 없습니다")
    data = {"owner": owner, "number": number, "repo": repo, "project_id": p["id"], "url": p["url"],
            "status_field": st["id"], "status_options": {o["name"]: o["id"] for o in st["options"]}}
    rv = fields.get("검토필요도")
    if rv:
        data["review_field"] = rv["id"]
        data["review_options"] = {o["name"]: o["id"] for o in rv["options"]}
    aiwf.save_json(BOARD, data)
    return data


# ---------------------------------------------------------------- 카드 조작 (전송기 안에서만 호출)
def cards():
    return aiwf.load_json(CARDS, {})


def save_card(num, **fields):
    allc = cards()
    c = allc.get(str(num), {})
    c.update(fields)
    allc[str(num)] = c
    aiwf.save_json(CARDS, allc)
    return c


def add_to_board(node_id):
    c = conf()
    d = graphql("mutation($p:ID!,$c:ID!){addProjectV2ItemById(input:{projectId:$p,contentId:$c}){item{id}}}",
                p=c["project_id"], c=node_id)
    return d["addProjectV2ItemById"]["item"]["id"]


def set_option(item_id, field, option_id):
    c = conf()
    graphql("""mutation($p:ID!,$i:ID!,$f:ID!,$o:String!){updateProjectV2ItemFieldValue(input:{projectId:$p,itemId:$i,
               fieldId:$f,value:{singleSelectOptionId:$o}}){projectV2Item{id}}}""",
            p=c["project_id"], i=item_id, f=field, o=option_id)


def set_status(num, status):
    c, card = conf(), cards().get(str(num), {})
    if card.get("status") == status:
        return
    opt = c["status_options"].get(status)
    if not opt:
        raise GitHubError(f"보드에 '{status}' 컬럼이 없습니다 (ai-board setup 으로 다시 맞추세요)")
    set_option(card["item"], c["status_field"], opt)
    save_card(num, status=status)


def set_review(num, level):
    c, card = conf(), cards().get(str(num), {})
    if not c.get("review_field") or card.get("review") == level or level not in c.get("review_options", {}):
        return
    set_option(card["item"], c["review_field"], c["review_options"][level])
    save_card(num, review=level)


def ensure_labels(repo, project):
    c = conf()
    done = set(c.get("labels", []))
    for name, color, desc in (("ai-card", "5319e7", "ai-workflow 세션 카드"), (f"proj:{project}", "1d76db", f"프로젝트 {project}")):
        if name in done:
            continue
        try:
            rest("POST", f"repos/{repo}/labels", {"name": name, "color": color, "description": desc})
        except GitHubError:
            pass    # 이미 있음
        done.add(name)
    c["labels"] = sorted(done)
    aiwf.save_json(BOARD, c)


def create_card(project, title, body, status="AI작업중", sid=""):
    c = conf()
    ensure_labels(c["repo"], project)
    it = rest("POST", f"repos/{c['repo']}/issues", {"title": f"[{project}] {title}", "body": body,
                                                    "labels": ["ai-card", f"proj:{project}"]})
    item = add_to_board(it["node_id"])
    save_card(it["number"], item=item, sids=[sid], project=project, url=it["html_url"], title=it["title"],
              status=None, body_t=time.time(), created=time.time())
    set_status(it["number"], status)
    return it["number"]


def bind_card(num, sid, project):
    """이미 있는 이슈(보드에 미리 만든 카드 등)를 이 세션의 카드로 쓴다."""
    c = conf()
    it = rest("GET", f"repos/{c['repo']}/issues/{num}")
    item = add_to_board(it["node_id"])      # 이미 보드에 있으면 기존 항목 ID 가 돌아온다
    prev = cards().get(str(num), {})
    save_card(num, item=item, sids=list(dict.fromkeys((prev.get("sids") or []) + [sid])), project=project,
              url=it["html_url"], title=it["title"], status=prev.get("status"))
    return num


def update_body(num, body):
    c = conf()
    rest("PATCH", f"repos/{c['repo']}/issues/{num}", {"body": body})
    save_card(num, body_t=time.time())


def comment(num, text):
    c = conf()
    rest("POST", f"repos/{c['repo']}/issues/{num}/comments", {"body": text})


# ---------------------------------------------------------------- 카드 본문
def render_body(s):
    t = lambda x: time.strftime("%m-%d %H:%M", time.localtime(x or 0))
    live = {"working": "⚙ AI 작업 중", "needs_you": "🔔 사람 확인 대기", "replied": "✅ 답변 완료", "idle": "· 대기",
            "ended": "■ 세션 종료"}.get(s.get("state"), s.get("state"))
    lines = [f"> 🤖 ai-workflow 자동 기록 · 프로젝트 **{s.get('project')}** · 모드 {s.get('mode')} · 세션 `{s.get('id', '')[:8]}`"
             f"{' · 브랜치 `' + s['branch'] + '`' if s.get('branch') else ''}", "",
             f"**현재:** {live} (마지막 활동 {t(s.get('last_activity'))})", "", "### 요청"]
    for r in (s.get("requests") or [])[-15:]:
        lines.append(f"- {t(r['t'])} {aiwf.short(r['text'], 300)}")
    files = s.get("files") or []
    if files:
        lines += ["", f"### 수정한 파일 ({len(files)})"] + [f"- `{f}`" for f in files[-30:]]
        if len(files) > 30:
            lines.append(f"- … 외 {len(files) - 30}개")
    if s.get("commits"):
        lines += ["", "### 커밋"] + [f"- `{c}`" for c in s["commits"][-15:]]
    if s.get("summary"):
        lines += ["", "### 마지막 답변", "", "\n".join("> " + l for l in aiwf.short_lines(s["summary"], 1500).splitlines())]
    lines += ["", "---", f"이어서 열기: `cd {s.get('path')} && claude-{s.get('mode') or 'personal'} --resume {s.get('id')}`",
              "확인이 끝나면 이슈를 닫으세요 → 보드에서 **완료**로 이동"]
    return "\n".join(lines)


# ---------------------------------------------------------------- 대기열
def _qfile(sid):
    return QUEUE / f"{sid}.json"


def enqueue(sid, **ops):
    """세션의 보드 작업을 대기열에 합친다. status/review 는 마지막 값, comments 는 이어 붙임, 나머지는 True 면 켜짐."""
    QUEUE.mkdir(parents=True, exist_ok=True)
    with open(QLOCK, "w") as lk:
        fcntl.flock(lk, fcntl.LOCK_EX)
        q = aiwf.load_json(_qfile(sid), {"sid": sid, "comments": []})
        for k, v in ops.items():
            if v is None:
                continue
            if k == "comments":
                q["comments"] = q.get("comments", []) + list(v)
            else:
                q[k] = v
        # 상태 변경·코멘트·카드 생성은 미뤄 둔 본문 수정을 기다리지 않고 바로 보낸다
        if any(ops.get(k) for k in ("status", "review", "create", "bind", "comments", "final")):
            q.pop("not_before", None)
        q["t"] = time.time()
        aiwf.save_json(_qfile(sid), q)


def _take(path):
    with open(QLOCK, "w") as lk:
        fcntl.flock(lk, fcntl.LOCK_EX)
        q = aiwf.load_json(path, None)
        path.unlink(missing_ok=True)
        return q


def _putback(q, delay, hold_new=False):
    """보내지 못한 작업을 대기열에 되돌린다. 그 사이 새로 들어온 값이 있으면 새 값이 우선한다.
    hold_new=False 면 새로 들어온 작업(상태 변경·코멘트)은 미루지 않는다 (본문만 미룰 때)."""
    sid = q["sid"]
    with open(QLOCK, "w") as lk:
        fcntl.flock(lk, fcntl.LOCK_EX)
        cur = aiwf.load_json(_qfile(sid), {})
        merged = dict(q)
        merged.update({k: v for k, v in cur.items() if k != "comments"})
        merged["comments"] = q.get("comments", []) + cur.get("comments", [])
        newer = any(k not in ("t", "title", "body", "comments", "not_before", "sid") for k in cur) or cur.get("comments")
        merged["not_before"] = 0 if (newer and not hold_new) else time.time() + delay
        aiwf.save_json(_qfile(sid), merged)


def card_of(sid):
    """세션의 카드 번호. 카드 정보는 전송기만 쓰는 cards.json 에 있다 (세션 파일과 동시에 고쳐지지 않게)."""
    for num, c in cards().items():
        if sid in (c.get("sids") or [c.get("sid")]):
            return int(num)
    return None


def spawn_worker():
    """전송기를 띄운다. 이미 돌고 있으면 새로 띄운 쪽은 바로 끝난다."""
    if not configured():
        return
    try:
        subprocess.Popen([sys.executable, str(aiwf.ROOT / "bin" / "ai-board"), "worker"], start_new_session=True,
                         stdout=subprocess.DEVNULL, stderr=open(aiwf.STATE / "worker.log", "a"), stdin=subprocess.DEVNULL)
    except OSError:
        pass


def process(q):
    """대기열 항목 하나를 보낸다. 보낼 수 없는 부분은 남겨서 돌려준다."""
    sid = q["sid"]
    s = aiwf.load_json(aiwf.session_file(sid), None)
    if not s:
        return None
    num = card_of(sid)
    if not num and q.get("bind"):
        num = bind_card(q["bind"], sid, s["project"])
    if not num and q.get("create"):
        num = create_card(s["project"], aiwf.short(q.get("title") or s.get("request") or "작업", 70), render_body(s),
                          status=q.get("status") or "AI작업중", sid=sid)
        q.pop("body", None)
    if not num:
        return None     # 카드가 생길 조건이 아직 안 됨
    if q.get("status"):
        set_status(num, q["status"])
    if q.get("review"):
        set_review(num, q["review"])
    left = {}
    if q.get("body"):
        wait = BODY_GAP - (time.time() - (cards().get(str(num), {}).get("body_t") or 0))
        if wait > 0 and not q.get("final"):
            left = {"sid": sid, "body": True, "comments": [], "not_before": time.time() + wait}
        else:
            update_body(num, render_body(s))
    for text in q.get("comments", []):
        comment(num, text)
    return left or None


def worker(foreground=False):
    aiwf.ensure_dirs()
    QUEUE.mkdir(parents=True, exist_ok=True)
    lock = open(WLOCK, "w")
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        return "이미 전송기가 돌고 있습니다"
    idle_since = time.time()
    backoff = 30
    while True:
        files = sorted(QUEUE.glob("*.json"), key=lambda p: p.stat().st_mtime)
        ready = [f for f in files if aiwf.load_json(f, {}).get("not_before", 0) <= time.time()]
        if not ready:
            if not files and time.time() - idle_since > (5 if foreground else 45):
                break
            time.sleep(2)
            continue
        idle_since = time.time()
        for f in ready:
            q = _take(f)
            if not q:
                continue
            try:
                left = process(q)
                backoff = 30
                if left:
                    _putback(left, left["not_before"] - time.time())
            except GitHubError as e:
                aiwf.append_event({"t": time.time(), "sid": q.get("sid"), "event": "SyncError", "detail": str(e)[:200]})
                if is_retryable(e):
                    _putback(q, backoff, hold_new=True)
                    backoff = min(backoff * 2, 900)
                    break
                # 되돌릴 수 없는 오류(권한, 잘못된 ID 등)는 버리고 기록만 남긴다
    lock.close()
    # 끝나는 사이에 들어온 작업이 있으면 이어서 처리
    if any(QUEUE.glob("*.json")) and not foreground:
        spawn_worker()
    return "대기열 비움"


def pending():
    return [aiwf.load_json(f, {}) for f in QUEUE.glob("*.json")] if QUEUE.is_dir() else []
