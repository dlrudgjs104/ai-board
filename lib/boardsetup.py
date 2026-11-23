"""초기 설정 마법사: GitHub 계정 → 기록 레포 → 보드. install.sh 가 호출한다 (다시 연결: ./install.sh --reconnect).

  python3 lib/boardsetup.py [--repo 이름] [--board 번호|--board-title 제목] [--create-repo] [--reset-columns] [--readme] [-y]
  python3 lib/boardsetup.py check      기록 레포가 GitHub 에 실제로 있는지 점검 (종료코드 0 정상 · 1 없음 · 2 확인 못 함)

계정은 하나만 쓴다: 로그인된 계정 중 고르거나 다른 계정을 새로 로그인한다 (--account 로 지정).
- 기록 레포: 기존 레포 이름을 물어보고, 없으면 `work`(비공개)를 기본으로 만든다. 카드는 이 레포의 이슈로 쌓인다.
- 보드: 기존 보드를 고르고, 없으면 `ai-board` 를 새로 만든다.
- 설명서는 README.md 로 올린다 (직접 쓴 README 가 있으면 건드리지 않고 AI-BOARD.md 로)
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
DEFAULT_BOARD = "ai-board"


def say(*a):
    """들여쓰기 2칸으로 출력 (install.sh 와 같은 모양). 줄 앞의 공백은 그대로 살린다."""
    print("  " + " ".join(str(x) for x in a))


def ok(msg):
    print(f"  \033[32m✔\033[0m {msg}")


def warn(msg):
    print(f"  \033[33m!\033[0m {msg}")


def note(msg):
    print(f"    \033[2m{msg}\033[0m")


def head(msg):
    print(f"\n\033[1m{msg}\033[0m")


def interactive(opts):
    return sys.stdin.isatty() and not opts.get("yes")


def ask(opts, prompt, default=None, valid=None, hint=""):
    """한 줄 입력. valid(값) 이 False 면 hint 를 보여 주고 다시 묻는다. 엔터는 기본값, 입력이 끊기면(EOF) 기본값."""
    if not interactive(opts):
        return default
    while True:
        try:
            s = input(f"  ? {prompt}" + (f" [{default}]" if default else "") + ": ").strip()
        except EOFError:
            return default
        s = s or default
        if valid is None or valid(s):
            return s
        note(hint or "올바른 값이 아닙니다.")


def confirm(opts, prompt, default=True):
    """예/아니오. y·yes·예·네 / n·no·아니오·아니 만 받고, 그 밖의 입력은 다시 묻는다. 엔터는 기본값."""
    if not interactive(opts):
        return default if opts.get("yes") else False
    while True:
        try:
            s = input(f"  ? {prompt} [{'Y/n' if default else 'y/N'}] ").strip().lower()
        except EOFError:
            return default
        if not s:
            return default
        if s in ("y", "yes", "예", "네"):
            return True
        if s in ("n", "no", "아니오", "아니"):
            return False
        note("y 또는 n 으로 입력해 주세요.")


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


def login_new_account():
    """브라우저 인증으로 gh 에 계정을 하나 더 로그인시킨다. 새로 생긴 계정 이름을 돌려준다 (실패 시 None)."""
    before = set(accounts())
    note("표시되는 코드를 https://github.com/login/device 에 입력하고, 쓰려는 GitHub 계정으로 승인하세요.")
    note("브라우저가 열리지 않으면 주소를 직접 열고, 다른 계정으로 로그인돼 있으면 시크릿 창을 쓰세요.")
    subprocess.run(["gh", "auth", "login", "-h", "github.com", "-p", "https", "-w", "-s", "project"])
    new = [x for x in accounts() if x not in before]
    if new:
        return new[-1]
    r = subprocess.run(["gh", "api", "user", "-q", ".login"], capture_output=True, text=True)   # 같은 계정을 다시 인증한 경우
    return r.stdout.strip() or None


def active_account():
    r = subprocess.run(["gh", "api", "user", "-q", ".login"], capture_output=True, text=True)
    return r.stdout.strip() if r.returncode == 0 else ""


def current_account(opts):
    """연동할 GitHub 계정 하나를 정한다.
    --account 로 지정하면 그 계정. 대화형이면 로그인된 계정 목록에서 고르거나 다른 계정을 새로 로그인한다.
    비대화형이면 gh 의 활성 계정. 로그인이 하나도 없으면 대화형일 때 바로 로그인시킨다."""
    accs = accounts()
    want = opts.get("account")
    if want:
        if want not in accs:
            raise SystemExit(f"{want} 계정이 gh 에 로그인되어 있지 않습니다. 먼저: gh auth login -h github.com -s project  (로그인된 계정: {', '.join(accs) or '없음'})")
        login = want
    elif not accs:
        if not interactive(opts):
            raise SystemExit("GitHub 에 로그인되어 있지 않습니다. 먼저: gh auth login -h github.com -s project")
        say("GitHub 로그인이 필요합니다.")
        login = login_new_account()
        if not login or not accounts():
            raise SystemExit("로그인하지 못했습니다. 직접 실행: gh auth login -h github.com -s project")
    else:
        act = active_account()
        if not act:
            raise SystemExit("로그인 계정을 확인하지 못했습니다. gh auth status 로 상태를 확인하세요.")
        login = act
        if interactive(opts):
            while True:
                accs = accounts()
                say("연동할 GitHub 계정을 고르세요 (기록 레포와 보드가 이 계정에 만들어집니다)")
                for i, x in enumerate(accs, 1):
                    say(f"  {i}) {x}" + ("   ← 현재 로그인" if x == act else ""))
                say(f"  {len(accs) + 1}) 다른 계정으로 새로 로그인")
                dflt = str(accs.index(act) + 1) if act in accs else "1"
                n = ask(opts, "번호", dflt, valid=lambda v: v.isdigit() and 1 <= int(v) <= len(accs) + 1, hint="목록의 번호를 입력해 주세요.")
                if int(n) <= len(accs):
                    login = accs[int(n) - 1]
                    break
                new = login_new_account()
                if new:
                    login = new
                    break
                warn("로그인하지 못했습니다. 다시 고르세요.")
        elif len(accs) > 1:
            note("로그인된 계정이 여럿이라 현재 계정을 씁니다 (다른 계정은 --account <이름>)")
    others = [x for x in accounts() if x != login]
    ok(f"GitHub 계정: {login}")
    if others:
        note(f"다른 로그인 계정({', '.join(others)})은 사용하지 않습니다")
    return login


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


README_MARK = "<!-- ai-board:readme -->"


def readme_target(repo, force=False):
    """설명서를 README.md 로 올릴 수 있는지 정한다 → (파일 이름, 덮어써도 되는지, 이유).
    README.md 가 없거나, 이 도구가 만든 것이거나, 레포 생성 때 자동으로 생긴 짧은 것이면 README.md 를 쓴다.
    직접 쓴 README 가 있으면 건드리지 않고 AI-BOARD.md 로 비켜 간다 (--readme 로 강제 덮어쓰기)."""
    try:
        cur = ghboard.rest("GET", f"repos/{repo}/contents/README.md")
    except GitHubError as e:
        if "Not Found" in str(e) or "404" in str(e):
            return "README.md", True, "새로 만듦"
        raise
    old = base64.b64decode(cur.get("content") or "").decode("utf-8", "replace")
    if force:
        return "README.md", True, "강제 덮어쓰기"
    if README_MARK in old:
        return "README.md", True, "이 도구가 만든 설명서를 갱신"
    if len(old.strip()) < 300:
        return "README.md", True, "비어 있던(자동 생성된) README 를 대체"
    return "AI-BOARD.md", False, "직접 쓴 README 가 있어 건드리지 않음"


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
        ok("컬럼 설정: " + " · ".join(ghboard.COLUMNS))
    elif missing:
        warn(f"보드에 없는 컬럼: {', '.join(missing)} (웹에서 Status 옵션에 추가하거나 --reset-columns)")
    if "검토필요도" not in fields:
        gh(login, "project", "field-create", str(number), "--owner", owner, "--name", "검토필요도",
           "--data-type", "SINGLE_SELECT", "--single-select-options", "낮음,중간,높음")
        ok("필드 추가: 검토필요도 (낮음/중간/높음)")
    if gh(login, "project", "link", str(number), "--owner", owner, "--repo", repo).returncode == 0:
        ok(f"보드를 {repo} 레포의 Projects 탭에 연결")


def run_init(opts: dict) -> str:
    """연결 정보를 만들거나 갱신한다. opts: repo create_repo board board_title reset_columns yes readme"""
    if subprocess.run(["which", "gh"], capture_output=True).returncode != 0:
        raise SystemExit("GitHub CLI(gh) 가 없습니다. ./install.sh --board 로 설치하세요.")
    conf = aiwf.profiles_conf()
    head("GitHub 기록 설정")
    login = current_account(opts)
    sc = scopes(login)
    if sc is not None and "project" not in sc and interactive(opts):
        warn(f"{login} 계정에 보드용 project 권한이 없어 추가합니다 (브라우저 인증).")
        subprocess.run(["gh", "auth", "refresh", "-h", "github.com", "-u", login, "-s", "project"])
        sc = scopes(login)
        ghboard._tokens.pop(login, None)
    if sc is not None and "project" not in sc:
        raise SystemExit(f"{login} 계정에 project 권한이 없습니다 (보드에 필요).\n"
                         f"  gh auth refresh -h github.com -u {login} -s project")
    ghboard.PROFILE.update(name=None, login=login)
    name = aiwf.SLOT
    if name in conf["profiles"]:
        old = conf["profiles"][name]
        note(f"현재 연결: 레포 {old.get('repo')} · 보드 #{old.get('board')} → 다시 고릅니다")

    # 1) 기록 레포: 기존 레포 이름을 묻고, 비우면 work 를 기본으로 (없으면 비공개로 생성)
    repo = opts.get("repo")
    if not repo:
        head("기록 레포")
        note("작업 카드(이슈)와 일지가 쌓이는 비공개 레포입니다.")
        note(f"기존 레포를 쓰려면 이름을 입력하고, 엔터를 누르면 '{DEFAULT_REPO}' 를 사용합니다 (없으면 새로 만듦).")
        repo = ask(opts, "레포 이름", "") or DEFAULT_REPO
    repo = repo if "/" in repo else f"{login}/{repo}"
    owner, rname = repo.split("/", 1)
    try:
        info = ghboard.rest("GET", f"repos/{repo}")
        ok(f"기록 레포: {repo} ({'비공개' if info.get('private') else '공개'}, 기존 레포에 연결)")
        if not info.get("private"):
            warn("공개 레포입니다. 요청 원문과 일지가 공개되므로 비공개 레포를 권합니다.")
        if info.get("has_issues") is False:   # 카드는 이슈라서 꺼져 있으면 켠다
            ghboard.rest("PATCH", f"repos/{repo}", {"has_issues": True})
            ok("이슈 기능이 꺼져 있어 켰습니다 (카드가 이슈로 만들어집니다)")
    except GitHubError as e:
        if "Not Found" not in str(e) and "404" not in str(e):
            raise SystemExit(f"기록 레포를 확인하지 못했습니다: {e}")
        if not (opts.get("create_repo") or rname == DEFAULT_REPO and not interactive(opts)
                or confirm(opts, f"{repo} 레포가 없습니다. 비공개로 만들까요?")):
            raise SystemExit(f"기록 레포 {repo} 가 없습니다. 만들려면: python3 {aiwf.ROOT}/lib/boardsetup.py --repo {repo} --create-repo")
        ghboard.rest("POST", "user/repos" if owner == login else f"orgs/{owner}/repos",
                     {"name": rname, "private": True, "auto_init": True, "has_issues": True,
                      "description": "AI 작업 기록 (ai-board): 카드·작업 일지"})
        ok(f"기록 레포 생성: {repo} (비공개)")

    # 2) 보드: 기존 보드를 고르거나, 없으면 ai-board 를 새로 만든다
    boards = list_boards(owner, login)
    number, title, fresh = opts.get("board"), opts.get("board_title"), False
    if number:
        match = [b for b in boards if b["number"] == int(number)]
        title = match[0]["title"] if match else title
    elif not title:
        same = [b for b in boards if b["title"] == DEFAULT_BOARD]
        if boards and interactive(opts):
            head("보드")
            for b in boards:
                say(f"  #{b['number']}  {b['title']}")
            note(f"번호를 입력하면 그 보드를 연결하고, 새 이름을 입력하면 새로 만듭니다.")
            note(f"엔터를 누르면 {'#' + str(same[0]['number']) + ' 를 사용' if same else repr(DEFAULT_BOARD) + ' 를 새로 만듦'}합니다.")
            nums = {b["number"] for b in boards}
            ans = ask(opts, "보드 번호 또는 새 이름", f"#{same[0]['number']}" if same else DEFAULT_BOARD,
                      valid=lambda v: bool(v) and (not re.fullmatch(r"#?\d+", v) or int(v.lstrip("#")) in nums),
                      hint="목록에 있는 번호나, 새 보드 이름(숫자만은 불가)을 입력하세요.")
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
            ok(f"같은 이름의 보드를 재사용합니다: #{number} {title}")
    if not number:
        r = gh(login, "project", "create", "--owner", owner, "--title", title or DEFAULT_BOARD, "--format", "json", "-q", ".number")
        if r.returncode != 0:
            raise SystemExit(f"보드를 만들지 못했습니다 (project 권한 필요): {r.stderr.strip()}")
        number, fresh = int(r.stdout.strip()), True
        ok(f"보드 생성: #{number} {title or DEFAULT_BOARD}")
    else:
        ok(f"보드 사용: #{number}" + (f" {title}" if title else ""))

    # 3) 저장 → 보드 ID 저장 → 컬럼 맞춤
    conf["profiles"] = {name: {"login": login, "owner": owner, "repo": repo, "board": int(number), "board_title": title or ""}}
    aiwf.save_profiles(conf)
    ghboard.use(name)
    ensure_layout(owner, number, repo, login, fresh, opts.get("reset_columns"))
    data = ghboard.save_board(owner, int(number), repo)
    c = ghboard.conf()
    c["title"] = title or DEFAULT_BOARD
    aiwf.save_json(ghboard.BOARD, c)
    conf["profiles"][name]["board_title"] = c["title"]
    aiwf.save_profiles(conf)

    # 4) 기록 레포 설명서: 레포에 들어가자마자 보이도록 README.md 로. 직접 쓴 README 가 있으면 AI-BOARD.md 로 비켜 간다
    text = render_readme({"login": login, "repo": repo, "board_url": data["url"], "board_title": c["title"]})
    try:
        target, is_new, why = readme_target(repo, force=bool(opts.get("readme")))
        put_file(repo, target, text, "docs: ai-board 설명서", overwrite=True)
        ok(f"설명서: {repo}/{target} ({why})" + ("" if is_new else "  ※ README.md 로 바꾸려면 --readme"))
    except GitHubError as e:
        warn(f"설명서를 올리지 못했습니다: {str(e)[:120]}")

    head("설정 완료")
    say(f"계정  {login}")
    say(f"레포  {repo}")
    say(f"보드  {data['url']}")
    note("자동 설정: 이슈를 닫으면 '완료', 완료 14일 뒤 카드 보관")
    note("프로젝트별 탭은 웹에서 필터 label:proj:<이름> 으로 저장하면 됩니다")
    return name


def check() -> int:
    """기록 레포가 GitHub 에 실제로 있는지 본다 (install.sh 가 호출). 출력: 'OK|MISSING|UNKNOWN <계정> <레포>'"""
    d = aiwf.profiles_conf()["profiles"]
    if not d:
        print("MISSING  (설정 없음) → ./install.sh --board")
        return 1
    name, p = next(iter(d.items()))
    ghboard.use(name)
    try:
        ghboard.rest("GET", f"repos/{p.get('repo')}")
        print(f"OK       {p.get('login')} {p.get('repo')}")
        return 0
    except GitHubError as e:
        if "Not Found" in str(e) or "404" in str(e):
            print(f"MISSING  {p.get('login')} {p.get('repo')}")
            return 1
        print(f"UNKNOWN  {p.get('login')} {p.get('repo')}  ({str(e)[:80]})")
        return 2


def main(argv=None) -> int:
    import argparse
    ap = argparse.ArgumentParser(prog="boardsetup", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("action", nargs="?", choices=["check"], help="check: 기록 레포 점검만")
    ap.add_argument("--account", help="연동할 GitHub 계정 (gh 에 로그인된 계정). 없으면 목록에서 고르거나 새로 로그인")
    ap.add_argument("--repo", help="기록 레포 (이름 또는 owner/이름). 있으면 연결, 없으면 비공개 생성 (기본 work)")
    ap.add_argument("--create-repo", action="store_true")
    ap.add_argument("--board", type=int, help="기존 보드 번호")
    ap.add_argument("--board-title", help="보드 이름 (같은 이름이 있으면 재사용, 없으면 새로 만듦)")
    ap.add_argument("--reset-columns", action="store_true")
    ap.add_argument("--yes", "-y", action="store_true", help="묻지 않고 기본값")
    ap.add_argument("--readme", action="store_true", help="레포 설명서를 최신으로 덮어쓰기")
    a = ap.parse_args(argv)
    if a.action == "check":
        return check()
    try:
        run_init({"account": a.account, "repo": a.repo, "create_repo": a.create_repo, "board": a.board, "board_title": a.board_title,
                  "reset_columns": a.reset_columns, "yes": a.yes, "readme": a.readme})
    except GitHubError as e:
        print(f"설정 중 GitHub 오류: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
