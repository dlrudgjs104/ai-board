"""초기 설정 마법사: GitHub 계정 → 기록 레포 → 보드 → 프로필 저장. `ai-board init` 이 호출한다.

프로필 = 계정 하나 + 기록 레포 하나 + 보드 하나. 회사 계정과 개인 계정을 따로 운영하려면 프로필을 둘 만든다.
- 계정: gh 에 로그인된 계정 중에서 고른다 (계정 추가는 gh auth login)
- 레포·보드: 이름은 자유. 이미 있으면 새로 만들지 않고 연결한다 (기존 AI Board 재사용)
- 새로 만든 레포에는 작동 방식을 설명하는 README.md 를 넣는다 (기존 레포는 건드리지 않고 AI-WORKFLOW.md 만 추가)
"""
import base64
import json
import re
import subprocess
import sys
import urllib.parse

import aiwf
import ghboard
from ghboard import GitHubError

DEFAULT_REPO = "work"
DEFAULT_BOARD = "AI Board"


def say(*a):
    print(*a)


def interactive(opts):
    return sys.stdin.isatty() and not opts.get("yes")


def ask(opts, prompt, default=None):
    if not interactive(opts):
        return default
    s = input(f"  ? {prompt}" + (f" [{default}]" if default else "") + ": ").strip()
    return s or default


def confirm(opts, prompt, default=True):
    if not interactive(opts):
        return default if opts.get("yes") else False
    s = input(f"  ? {prompt} [{'Y/n' if default else 'y/N'}] ").strip().lower()
    return default if not s else s.startswith("y")


def gh(login, *args, inp=None):
    return subprocess.run(["gh", *args], input=inp, capture_output=True, text=True, env=ghboard.gh_env(login))


def accounts():
    """gh 에 로그인된 github.com 계정 이름들."""
    r = subprocess.run(["gh", "auth", "status", "-h", "github.com"], capture_output=True, text=True)
    return list(dict.fromkeys(re.findall(r"account (\S+)", r.stdout + r.stderr)))


def scopes(login):
    r = gh(login, "api", "-i", "user")
    m = re.search(r"^x-oauth-scopes:\s*(.*)$", r.stdout, re.I | re.M)
    return [x.strip() for x in m.group(1).split(",") if x.strip()] if m else None   # None: 확인 불가(세분화 토큰 등)


def pick_account(opts):
    accs = accounts()
    if not accs:
        raise SystemExit("GitHub 에 로그인된 계정이 없습니다. 먼저: gh auth login -h github.com -s project")
    want = opts.get("account")
    if want:
        if want not in accs:
            raise SystemExit(f"{want} 계정은 gh 에 로그인되어 있지 않습니다 (로그인된 계정: {', '.join(accs)}).\n"
                             f"  추가하려면: gh auth login -h github.com -s project   (브라우저에서 해당 계정으로 승인)")
        return want
    if len(accs) == 1:
        say(f"계정: {accs[0]}")
        return accs[0]
    if not interactive(opts):
        raise SystemExit(f"로그인된 계정이 여럿입니다({', '.join(accs)}). --account 로 고르세요.")
    say("로그인된 GitHub 계정:")
    for i, a in enumerate(accs, 1):
        say(f"   {i}) {a}")
    say("   (다른 계정을 쓰려면 이 마법사를 끝낸 뒤 gh auth login 으로 추가하고 다시 실행)")
    n = ask(opts, "사용할 계정 번호", "1")
    try:
        return accs[int(n) - 1]
    except (ValueError, IndexError):
        raise SystemExit("올바른 번호가 아닙니다")


def put_file(repo, path, text, message, overwrite=True):
    """기록 레포에 파일을 만든다. 이미 있으면 overwrite 일 때만 덮어쓴다. 만들었으면 True."""
    url = f"repos/{repo}/contents/{urllib.parse.quote(path)}"
    body = {"message": message, "content": base64.b64encode(text.encode("utf-8")).decode()}
    try:
        body["sha"] = ghboard.rest("GET", url).get("sha")
        if not overwrite:
            return False
    except GitHubError as e:
        if "Not Found" not in str(e) and "404" not in str(e):
            raise
    ghboard.rest("PUT", url, body)
    return True


def render_readme(info: dict) -> str:
    text = (aiwf.ROOT / "templates" / "RECORDS_README.md").read_text(encoding="utf-8")
    for k, v in info.items():
        text = text.replace("{{" + k + "}}", str(v))
    return text


def list_boards(owner, login):
    r = gh(login, "project", "list", "--owner", owner, "--format", "json", "--limit", "100")
    if r.returncode != 0:
        raise GitHubError(f"보드 목록을 읽지 못했습니다 (project 권한 필요: gh auth refresh -h github.com -s project): {r.stderr.strip()[:200]}")
    return [p for p in json.loads(r.stdout or "{}").get("projects", []) if not p.get("closed")]


def ensure_layout(owner, number, repo, login, fresh, reset):
    """보드 컬럼·검토필요도 필드·레포 연결을 맞춘다. 기본 컬럼(Todo/In Progress/Done)은 ID 를 유지한 채 이름만 바꿔서
    GitHub 기본 자동화(닫으면 Done)가 그대로 '완료' 를 가리키게 한다."""
    p, fields = ghboard.load_board_ids(owner, int(number))
    st = fields.get("Status")
    have = {o["name"]: o["id"] for o in (st or {}).get("options", [])}
    missing = [c for c in ghboard.COLUMNS if c not in have]
    if missing and (fresh or reset or set(have) <= {"Todo", "In Progress", "Done"} | set(ghboard.COLUMNS)):
        keep = {"Backlog": have.get("Backlog") or have.get("Todo"), "AI작업중": have.get("AI작업중") or have.get("In Progress"),
                "완료": have.get("완료") or have.get("Done"), "판단필요": have.get("판단필요"), "검토대기": have.get("검토대기")}
        opts = [({"id": keep[c]} if keep.get(c) else {}) | {"name": c, "color": ghboard.COLUMN_DESC[c][0],
                                                          "description": ghboard.COLUMN_DESC[c][1]} for c in ghboard.COLUMNS]
        ghboard.graphql("mutation($f:ID!,$o:[ProjectV2SingleSelectFieldOptionInput!]){updateProjectV2Field("
                        "input:{fieldId:$f,singleSelectOptions:$o}){projectV2Field{__typename}}}", f=st["id"], o=opts)
        say("컬럼 설정: " + " / ".join(ghboard.COLUMNS))
    elif missing:
        say(f"  ! 보드에 없는 컬럼: {', '.join(missing)} — 웹에서 Status 옵션에 추가하거나 --reset-columns")
    if "검토필요도" not in fields:
        gh(login, "project", "field-create", str(number), "--owner", owner, "--name", "검토필요도",
           "--data-type", "SINGLE_SELECT", "--single-select-options", "낮음,중간,높음")
        say("필드 추가: 검토필요도 (낮음/중간/높음)")
    if gh(login, "project", "link", str(number), "--owner", owner, "--repo", repo).returncode == 0:
        say(f"보드를 {repo} 에 연결 (레포의 Projects 탭에 표시)")


def run_init(opts: dict) -> str:
    """프로필을 만들거나 갱신하고 이름을 돌려준다. opts: profile account repo create_repo board board_title
    reset_columns yes link readme"""
    if subprocess.run(["which", "gh"], capture_output=True).returncode != 0:
        raise SystemExit("GitHub CLI(gh) 가 없습니다. ./install.sh --board 로 설치하세요.")
    conf = aiwf.profiles_conf()
    say("== ai-workflow 초기 설정 ==")
    login = pick_account(opts)
    sc = scopes(login)
    if sc is not None and "project" not in sc:
        raise SystemExit(f"{login} 계정에 project 권한이 없습니다 (보드에 필요).\n"
                         f"  gh auth switch -h github.com -u {login} && gh auth refresh -h github.com -s project")
    ghboard.PROFILE.update(name=None, login=login)

    # 1) 프로필 이름
    first = not conf["profiles"]
    name = opts.get("profile") or ask(opts, "프로필 이름 (회사/개인 구분용)", "default" if first else login)
    name = re.sub(r"[^\w.-]+", "-", name or login).strip("-") or login
    if name in conf["profiles"]:
        say(f"프로필 '{name}' 이(가) 이미 있어 설정을 갱신합니다.")

    # 2) 기록 레포: 이름 자유, 있으면 연결, 없으면 비공개로 생성
    repo = opts.get("repo") or ask(opts, "기록 레포 이름 (카드·일지가 쌓일 비공개 레포)", DEFAULT_REPO)
    repo = repo if "/" in repo else f"{login}/{repo}"
    owner, rname = repo.split("/", 1)
    created = False
    try:
        info = ghboard.rest("GET", f"repos/{repo}")
        say(f"기록 레포: {repo} ({'비공개' if info.get('private') else '공개'}) — 기존 레포에 연결")
        if not info.get("private"):
            say("  ! 공개 레포입니다. 요청 원문과 일지가 공개되니 비공개 레포를 권합니다.")
    except GitHubError as e:
        if "Not Found" not in str(e) and "404" not in str(e):
            raise SystemExit(f"기록 레포를 확인하지 못했습니다: {e}")
        if not (opts.get("create_repo") or confirm(opts, f"{repo} 가 없습니다. 비공개 레포로 만들까요?")):
            raise SystemExit(f"기록 레포 {repo} 가 없습니다. 만들려면: ai-board init --repo {repo} --create-repo")
        ghboard.rest("POST", "user/repos" if owner == login else f"orgs/{owner}/repos",
                     {"name": rname, "private": True, "auto_init": True,
                      "description": "AI 작업 기록 (ai-workflow): 카드·작업 일지"})
        created = True
        say(f"기록 레포 생성: {repo} (비공개)")

    # 3) 보드: 번호나 제목으로 기존 보드 재사용, 없으면 새로 만든다
    boards = list_boards(owner, login)
    number, title, fresh = opts.get("board"), opts.get("board_title"), False
    if number:
        match = [b for b in boards if b["number"] == int(number)]
        title = match[0]["title"] if match else title
    elif not title:
        same = [b for b in boards if b["title"] == DEFAULT_BOARD]
        if boards and interactive(opts):
            say("보드 목록:")
            for b in boards:
                say(f"   #{b['number']}  {b['title']}")
            say("   (번호를 입력하면 그 보드를 연결, 새 이름을 입력하면 새로 만듦)")
            ans = ask(opts, "보드 번호 또는 새 보드 이름", f"#{same[0]['number']}" if same else DEFAULT_BOARD)
            if re.fullmatch(r"#?\d+", ans or ""):
                number = int(ans.lstrip("#"))
            else:
                title = ans
        elif same:
            number = same[0]["number"]
        else:
            title = DEFAULT_BOARD
    if not number and title:
        same = [b for b in boards if b["title"] == title]
        if same:
            number = same[0]["number"]
            say(f"같은 이름의 보드가 있어 재사용합니다: #{number} {title}")
    if not number:
        r = gh(login, "project", "create", "--owner", owner, "--title", title or DEFAULT_BOARD, "--format", "json", "-q", ".number")
        if r.returncode != 0:
            raise SystemExit(f"보드를 만들지 못했습니다 (project 권한 필요): {r.stderr.strip()}")
        number, fresh = int(r.stdout.strip()), True
        say(f"보드 생성: #{number} {title or DEFAULT_BOARD}")
    else:
        say(f"보드 사용: #{number}" + (f" {title}" if title else ""))

    # 4) 프로필 저장 → 보드 ID 저장 → 컬럼 맞춤
    conf["profiles"][name] = {"login": login, "owner": owner, "repo": repo, "board": int(number), "board_title": title or ""}
    if first or not conf["default"] or opts.get("make_default"):
        conf["default"] = name
    aiwf.save_profiles(conf)
    ghboard.use(name)
    ensure_layout(owner, number, repo, login, fresh, opts.get("reset_columns"))
    data = ghboard.save_board(owner, int(number), repo)
    c = ghboard.conf()
    c["title"] = title or DEFAULT_BOARD
    aiwf.save_json(ghboard.BOARD, c)
    conf["profiles"][name]["board_title"] = c["title"]
    aiwf.save_profiles(conf)

    # 5) 기록 레포 설명서: 새 레포는 README.md, 기존 레포는 건드리지 않고 AI-WORKFLOW.md (이미 있으면 그대로)
    text = render_readme({"profile": name, "login": login, "repo": repo, "board_url": data["url"], "board_title": c["title"]})
    try:
        target = "README.md" if created else "AI-WORKFLOW.md"
        wrote = put_file(repo, target, text, "docs: ai-workflow 설명서", overwrite=created or bool(opts.get("readme")))
        say(f"설명서: {repo}/{target}" + ("" if wrote else " (이미 있어 그대로 둠, 갱신은 --readme)"))
    except GitHubError as e:
        say(f"  ! 설명서를 올리지 못했습니다: {str(e)[:120]}")

    # 6) 폴더 연결 (선택)
    link = opts.get("link")
    if link is None and interactive(opts):
        link = ask(opts, f"이 프로필을 쓸 프로젝트(또는 상위) 폴더 — 엔터로 건너뜀 (나중에 ai-board link {name})", "")
    if link:
        add_rule(conf, link, name)
        aiwf.save_profiles(conf)
        say(f"연결: {link} 아래 프로젝트 → 프로필 {name}")

    say(f"\n프로필 '{name}' 준비 완료: 계정 {login} · 레포 {repo} · 보드 {data['url']}")
    say("자동 설정됨: 이슈 닫힘 ↔ 완료, 완료 14일 뒤 카드 보관. 웹에서 프로젝트별 탭은 필터 label:proj:<이름> 으로 저장")
    if len(conf["profiles"]) > 1:
        say("프로필이 여럿입니다. 프로젝트마다 쓸 프로필을 정하세요: ai-board link <프로필> [폴더]  (확인: ai-board profiles)")
    return name


def add_rule(conf, path, profile):
    import os
    p = os.path.abspath(os.path.expanduser(path))
    conf["rules"] = [r for r in conf["rules"] if os.path.abspath(os.path.expanduser(r["path"])) != p]
    conf["rules"].append({"path": p, "profile": profile})
