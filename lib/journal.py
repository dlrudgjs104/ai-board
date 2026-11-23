"""작업 일지: 요청한 사항 · 결정한 사항 · 반영된 사항을 세션마다 md 하나로 남긴다 (증적·재활용용).

- 훅이 세션 기록(s["journal"] = 턴 목록)을 쌓고, 답변이 끝날 때마다 로컬 md 를 다시 쓴다
    ~/.ai-workflow/records/<프로젝트>/<날짜>_<시각>_<세션8자리>.md   (로컬 사본은 보드 설정과 무관하게 항상 남는다)
- 프로필(계정·기록 레포)이 있으면 같은 파일을 기록 레포의 records/<프로젝트>/ 아래에 올린다 (전송기가 처리)
  세션마다 파일이 따로이고 쓰는 PC 도 하나라서, 여러 PC 에서 작업해도 충돌하지 않는다
- 꺼짐(off)·건너뛰기(skip) 요청은 기록하지 않는다 (훅이 호출하지 않음)
"""
import base64
import datetime
import json
import re
import secrets
import socket
import time
import urllib.parse
from pathlib import Path

import aiwf
from redact import redact

RECORDS = aiwf.STATE / "records"
FULL = 100_000     # 증적용이라 요청·답변은 사실상 자르지 않는다 (비정상적으로 긴 것만 방어)


def _t(x):
    return time.strftime("%H:%M", time.localtime(x or 0))


def safe(name: str) -> str:
    return re.sub(r"[\\/:*?\"<>|\s]+", "_", name or "unknown").strip("._") or "unknown"


def new_jid() -> str:
    """세션 생성 때 한 번 정하는 임의 값. 파일 이름에 섞어 같은 프로젝트의 동시 세션·여러 PC 가 서로 덮어쓰지 않게 한다."""
    return secrets.token_hex(3)


def marker(s: dict) -> str:
    return f"<!-- ai-workflow session={s.get('id', '')} jid={s.get('jid', '')} -->"


def rel_path(s: dict, n: int = 1) -> str:
    """records/<프로젝트>/<날짜_시각초>_<세션ID 앞 8자리>-<임의값>.md  (n>1 이면 -n 을 더 붙임: 극히 드문 이름 충돌 회피)"""
    started = s.get("started") or aiwf.now()
    stamp = time.strftime("%Y-%m-%d_%H%M%S", time.localtime(started))
    rnd = f"-{s['jid']}" if s.get("jid") else ""
    extra = f"-{n}" if n > 1 else ""
    return f"records/{safe(s.get('project'))}/{stamp}_{s.get('id', '')[:8]}{rnd}{extra}.md"


# ---------------------------------------------------------------- 쌓기 (훅에서 호출)
def turns(s: dict) -> list:
    return s.setdefault("journal", [])


def new_turn(s: dict, text: str, mode: str):
    turns(s).append({"t": aiwf.now(), "mode": mode, "request": redact((text or "").strip()[:FULL]),
                     "decisions": [], "files": [], "commits": [], "report": ""})
    del s["journal"][:-200]


def cur(s: dict):
    t = turns(s)
    return t[-1] if t else None


def add_file(s: dict, fp: str):
    c = cur(s)
    if c is not None and fp not in c["files"]:
        c["files"].append(fp)


def add_commit(s: dict, commit: str):
    c = cur(s)
    if c is not None and commit not in c["commits"]:
        c["commits"].append(commit)


def add_decision(s: dict, text: str):
    c = cur(s)
    text = redact(aiwf.short(text, 400))
    if c is not None and text and text not in c["decisions"]:
        c["decisions"].append(text)


def parse_decisions(msg: str) -> list:
    """답변 끝 보고에서 '결정 사항' 을 뽑는다: '결정 사항:' 줄, 또는 '### 결정 사항' 아래 목록."""
    out, lines, i = [], (msg or "").splitlines(), 0
    while i < len(lines):
        line = lines[i].strip()
        m = re.match(r"^[-*#>\s]*\**\s*결정\s*(?:한\s*)?(?:사항)?\s*\**\s*[:：]?\s*\**\s*(.*)$", line)
        if m and (line.startswith(("#", "*", "-", ">")) or "결정" in line[:6]):
            if m.group(1):
                out.append(m.group(1).strip("* "))
            j = i + 1
            while j < len(lines) and lines[j].strip() and not lines[j].lstrip().startswith("#"):
                b = re.match(r"^\s*[-*•]\s+(.*)$", lines[j])
                if b:
                    out.append(b.group(1).strip("* "))
                elif not m.group(1):
                    break
                j += 1
            i = j
        else:
            i += 1
    return [d for d in dict.fromkeys(out) if d and d != "(없음)" and d != "없음"][:20]


TOOL_KEYS = ("command", "file_path", "pattern", "path", "url", "query", "description", "prompt", "skill", "notebook_path")


def _iso(ts) -> float:
    try:
        return datetime.datetime.fromisoformat(str(ts).replace("Z", "+00:00")).timestamp()
    except ValueError:
        return 0.0


def _tool_line(b: dict) -> str:
    name, inp = b.get("name", "?"), b.get("input") or {}
    if name == "AskUserQuestion":
        qs = [q.get("question", "") for q in inp.get("questions") or []]
        return f"{name}: " + " / ".join(aiwf.short(q, 160) for q in qs)
    for k in TOOL_KEYS:
        if inp.get(k):
            return f"{name}: {aiwf.short(str(inp[k]), 300)}"
    return f"{name}: {aiwf.short(json.dumps(inp, ensure_ascii=False), 200)}" if inp else name


def collect_steps(path, since: float) -> list:
    """대화 기록(transcript, jsonl)에서 since(epoch 초) 이후 이 요청에 대한 AI 의 모든 답변 글과 도구 호출을 순서대로 뽑는다.
    생각(thinking)·도구 결과 원문은 제외한다. 읽지 못하면 빈 목록."""
    out = []
    try:
        with open(path, encoding="utf-8") as f:
            for line in f:
                try:
                    d = json.loads(line)
                except ValueError:
                    continue
                if d.get("type") != "assistant" or d.get("isSidechain") or _iso(d.get("timestamp")) < since - 1:
                    continue
                cont = (d.get("message") or {}).get("content")
                for b in cont if isinstance(cont, list) else []:
                    if b.get("type") == "text" and (b.get("text") or "").strip():
                        out.append({"k": "text", "v": redact(b["text"].strip()[:FULL])})
                    elif b.get("type") == "tool_use":
                        out.append({"k": "tool", "v": redact(_tool_line(b))})
    except OSError:
        return []
    return out[-500:]


def finish_turn(s: dict, msg: str, transcript=None):
    c = cur(s)
    if c is None:
        return
    c["report"] = redact(aiwf.short_lines(msg or "", FULL))
    if transcript:
        steps = collect_steps(transcript, c.get("t") or 0)
        if steps and steps[-1]["k"] == "text" and steps[-1]["v"] == (msg or "").strip():
            steps.pop()          # 마지막 답변은 '결과 보고' 에 따로 실리므로 중복 제거
        c["steps"] = steps
    for d in parse_decisions(msg):
        add_decision(s, d)
    c["done_t"] = aiwf.now()


# ---------------------------------------------------------------- md 만들기
def render(s: dict) -> str:
    started = s.get("started") or aiwf.now()
    lines = [marker(s), "", f"# {s.get('project')} 작업 일지 — {time.strftime('%Y-%m-%d %H:%M', time.localtime(started))}", "",
             f"- 세션: `{s.get('id', '')[:8]}` · PC: `{socket.gethostname()}`"
             + (f" · 브랜치: `{s['branch']}`" if s.get("branch") else ""),
             f"- 경로: `{s.get('path')}`", "- 자동 기록 (ai-workflow). 요청 → 결정 → 반영 → 진행 과정(AI 답변·도구 호출 전체) → 결과 보고", ""]
    for n, t in enumerate(turns(s), 1):
        lines += [f"## {n}. {_t(t['t'])} 요청 · 모드 {t.get('mode')}", ""]
        lines += ["> " + l for l in (t.get("request") or "(내용 없음)").splitlines()] + [""]
        lines += ["**결정한 사항**"] + ([f"- {d}" for d in t["decisions"]] or ["- (기록된 결정 없음)"]) + [""]
        lines += ["**반영된 사항**"]
        if t["files"]:
            lines.append("- 수정 파일: " + ", ".join(f"`{f}`" for f in t["files"][:40]) + (" 외" if len(t["files"]) > 40 else ""))
        lines += [f"- 커밋: `{c}`" for c in t["commits"]]
        if not t["files"] and not t["commits"]:
            lines.append("- (파일 변경·커밋 없음)")
        lines.append("")
        if t.get("steps"):
            lines += ["**진행 과정 (AI 답변·도구 호출 전체)**", ""]
            for st in t["steps"]:
                if st["k"] == "tool":
                    lines.append(f"- 🔧 `{st['v'].replace(chr(10), ' ')}`")
                else:
                    lines += [""] + ["> " + l for l in st["v"].splitlines()] + [""]
            lines.append("")
        if t.get("report"):
            lines += ["**결과 보고**", ""] + ["> " + l for l in t["report"].splitlines()] + [""]
        elif not t.get("done_t"):
            lines += ["_(진행 중이거나 답변 전에 종료됨)_", ""]
    return redact("\n".join(lines))      # 마지막 안전망: 어떤 경로로 들어왔든 올라가기 직전에 한 번 더


def write_local(s: dict) -> Path:
    path = RECORDS / rel_path(s)[len("records/"):]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render(s), encoding="utf-8")
    return path


# ---------------------------------------------------------------- 기록 레포에 올리기 (전송기에서)
def push(s: dict, rest):
    """세션 일지를 기록 레포의 records/ 아래에 만들거나 갱신한다. rest 는 ghboard.rest.
    같은 이름의 파일이 이미 있는데 다른 세션의 것이면(마커가 다름) 덮어쓰지 않고 -2, -3 … 이름으로 올린다."""
    import ghboard
    repo = ghboard.conf().get("repo")
    if not repo or not turns(s):
        return
    text = render(s)
    body = {"message": f"journal: {s.get('project')} {s.get('id', '')[:8]}",
            "content": base64.b64encode(text.encode("utf-8")).decode()}
    for n in range(1, 20):
        path = urllib.parse.quote(rel_path(s, n))
        body.pop("sha", None)
        try:
            cur = rest("GET", f"repos/{repo}/contents/{path}")
        except ghboard.GitHubError as e:
            if "Not Found" not in str(e) and "404" not in str(e):
                raise
            cur = None
        if cur:
            old = base64.b64decode(cur.get("content") or "").decode("utf-8", "replace") if cur.get("content") else None
            if old is not None and marker(s) not in old:
                continue            # 다른 세션의 파일: 다음 이름으로
            body["sha"] = cur.get("sha")
        for attempt in (1, 2):
            try:
                rest("PUT", f"repos/{repo}/contents/{path}", body)
                return
            except ghboard.GitHubError as e:
                if attempt == 2 or not re.search(r"409|422|does not match|sha", str(e), re.I):
                    raise
                try:     # 그 사이 바뀜: sha 를 다시 받아 한 번 더
                    body["sha"] = rest("GET", f"repos/{repo}/contents/{path}").get("sha")
                except ghboard.GitHubError:
                    raise e
