#!/usr/bin/env bash
# ai-workflow 설치/점검/제거 (WSL Ubuntu·Debian 기준, 일반 Linux·macOS 도 대부분 동작)
#
#   ./install.sh              명령 설치 + 필요한 것 점검. GitHub 보드 연동은 물어본 뒤 진행
#   ./install.sh --board      GitHub 보드 연동까지 바로 진행 (gh 설치, 로그인, 권한, 보드 생성/연결)
#   ./install.sh --reconnect  이미 연결돼 있어도 기록 레포·보드를 다시 고름 (계정을 바꿨을 때 등)
#   ./install.sh --no-board   보드 연동은 묻지 않고 건너뜀
#   ./install.sh --check      아무것도 바꾸지 않고 상태만 점검
#   ./install.sh --uninstall  ~/.local/bin 에 만든 링크 제거 (레포와 프로젝트 문서는 그대로)
#   ./install.sh --uninstall --purge   위 + 연결 정보·세션·작업 일지(~/.ai-workflow) 삭제, 이 도구가 연결한
#                             gh 계정 로그아웃, 전송기 종료. GitHub 의 레포·보드·카드는 지우지 않는다. 확인을 묻는다
#       --keep-records        --purge 때 작업 일지는 남긴다
#       --dry-run             아무것도 지우지 않고 무엇을 지울지만 보여 준다
#   -y                        모든 질문에 '예'
#
# 이 스크립트는 ~/.claude 설정을 바꾸지 않는다. 워크플로우는 claude-personal / claude-work / claude-lite
# 로 시작한 세션에만 적용되고, 그냥 claude 로 시작한 세션은 영향이 없다.
set -euo pipefail

ROOT="$(cd "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")" && pwd)"
BIN_DIR="${AI_WORKFLOW_BIN:-$HOME/.local/bin}"
CMDS=(claude-personal claude-work claude-lite ai-board)

mode=install; board=ask; yes=0; reconnect=0; purge=0; keep=0; dry=0
for a in "$@"; do
  case "$a" in
    --board) board=yes ;;
    --reconnect) board=yes; reconnect=1 ;;
    --no-board) board=no ;;
    --check) mode=check ;;
    --uninstall) mode=uninstall ;;
    --purge) purge=1 ;;
    --keep-records) keep=1 ;;
    --dry-run) dry=1 ;;
    -y|--yes) yes=1 ;;
    -h|--help) sed -n '2,17p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) echo "알 수 없는 옵션: $a (도움말: ./install.sh -h)" >&2; exit 2 ;;
  esac
done

ok()   { printf '  \033[32m✔\033[0m %s\n' "$*"; }
warn() { printf '  \033[33m!\033[0m %s\n' "$*"; }
bad()  { printf '  \033[31m✘\033[0m %s\n' "$*"; }
step() { printf '\n\033[1m%s\033[0m\n' "$*"; }
ask()  { # ask "질문" → 0(예)/1(아니오)
  [[ $yes == 1 ]] && return 0
  [[ -t 0 ]] || return 1
  local r
  while true; do   # y/n 이외의 입력은 다시 묻는다 (엔터는 기본값 N)
    read -r -p "  ? $1 [y/N] " r || return 1      # 입력이 끊기면(EOF) 아니오
    case "${r,,}" in
      y|yes|예|네) return 0 ;;
      ""|n|no|아니오|아니) return 1 ;;
      *) echo "    y 또는 n 으로 입력해 주세요." ;;
    esac
  done
}
has()  { command -v "$1" >/dev/null 2>&1; }

# ---------------------------------------------------------------- uninstall
if [[ $mode != uninstall && ( $purge == 1 || $keep == 1 || $dry == 1 ) ]]; then
  echo "--purge / --keep-records / --dry-run 은 --uninstall 과 함께 씁니다 (예: ./install.sh --uninstall --purge)" >&2; exit 2
fi
if [[ $mode == uninstall && $purge == 0 && $keep == 1 ]]; then
  echo "--keep-records 는 --purge 와 함께 씁니다" >&2; exit 2
fi

# 연결 정보·세션·작업 일지를 지우고, 이 도구가 연결한 gh 계정만 로그아웃한다 (설치를 처음부터 다시 시험할 때 쓴다).
# 지우지 않는 것: GitHub 의 기록 레포·보드·카드, 다른 gh 계정, ~/.git-credentials (이 도구가 만든 것이 아니다)
purge_all() {
  local state login="" n_rec=0 n_ses=0 n_q=0
  state="${AI_WORKFLOW_STATE:-$HOME/.ai-workflow}"
  state="$(readlink -f "$state" 2>/dev/null || echo "$state")"
  step "연결 정보·기록 삭제 (--purge)"
  # 안전장치: 엉뚱한 폴더(홈, /)를 지우지 않고, ai-workflow 상태 폴더처럼 생긴 곳만 지운다
  if [[ -z "$state" || "$state" == "/" || "$state" == "$(readlink -f "$HOME")" ]]; then
    bad "상태 폴더 경로가 위험합니다 ($state). 중단합니다"; exit 1
  fi
  if [[ ! -d "$state" ]]; then ok "지울 상태 폴더가 없습니다 ($state)"; return 0; fi
  if [[ ! -e "$state/profiles.json" && ! -d "$state/sessions" && ! -d "$state/records" && ! -e "$state/events.jsonl" ]]; then
    bad "ai-workflow 상태 폴더로 보이지 않아 중단합니다 ($state)"; exit 1
  fi
  if [[ -f "$state/profiles.json" ]] && has python3; then
    login="$(python3 - "$state/profiles.json" <<'PY' 2>/dev/null || true
import json, sys
try:
    d = json.load(open(sys.argv[1]))["profiles"]
    print(next(iter(d.values())).get("login") or "")
except Exception:
    pass
PY
)"
  fi
  n_rec="$(find "$state/records" -name '*.md' 2>/dev/null | wc -l)"
  n_ses="$(find "$state/sessions" -name '*.json' 2>/dev/null | wc -l)"
  n_q="$(find "$state"/profiles -path '*/queue/*.json' 2>/dev/null | wc -l)"

  echo "  지울 것:"
  echo "    - 상태 폴더 $state  (세션 ${n_ses}개, 대기열 ${n_q}건$([[ $keep == 1 ]] && echo ", 작업 일지 ${n_rec}개는 남김" || echo ", 작업 일지 ${n_rec}개"))"
  echo "    - 전송기(백그라운드 프로세스) 종료"
  if [[ -n "$login" ]] && has gh && gh auth token --user "$login" >/dev/null 2>&1; then
    echo "    - GitHub 로그인 해제: $login  (gh auth logout, 이 계정만)"
  else
    login=""
  fi
  echo "  지우지 않는 것: GitHub 의 기록 레포·보드·카드, 다른 gh 계정, ~/.git-credentials"
  [[ "$n_q" -gt 0 ]] && warn "아직 GitHub 로 보내지 않은 대기열 ${n_q}건이 사라집니다."
  [[ $keep == 0 && "$n_rec" -gt 0 ]] && warn "로컬 작업 일지 ${n_rec}개를 지웁니다. 기록 레포에 올라가지 않은 것은 복구할 수 없습니다 (남기려면 --keep-records)."
  warn "열려 있는 claude-personal / claude-work 세션이 있으면 먼저 종료하세요."

  if [[ $dry == 1 ]]; then echo; ok "(dry-run) 실제로는 아무것도 지우지 않았습니다"; return 0; fi
  if ! ask "위 내용을 삭제할까요? 되돌릴 수 없습니다."; then warn "취소했습니다. 아무것도 지우지 않았습니다"; exit 0; fi

  # 전송기는 상태 폴더의 worker.lock 을 잡고 있다. 그 잠금을 쥔 프로세스만 종료한다 (다른 상태 폴더의 전송기는 건드리지 않음)
  killed="$(python3 - "$state/worker.lock" <<'PY' 2>/dev/null || echo 0
import os, signal, sys
lock, n = os.path.realpath(sys.argv[1]), 0
try:
    for pid in (p for p in os.listdir("/proc") if p.isdigit() and int(p) != os.getpid()):
        try:
            if any(os.path.realpath(f"/proc/{pid}/fd/{fd}") == lock for fd in os.listdir(f"/proc/{pid}/fd")):
                os.kill(int(pid), signal.SIGTERM)
                n += 1
        except OSError:
            pass
except OSError:
    pass
print(n)
PY
)"
  [[ "${killed:-0}" -gt 0 ]] && ok "전송기 종료 (${killed}개)" || ok "실행 중인 전송기 없음"
  if [[ -n "$login" ]]; then
    gh auth logout -h github.com -u "$login" >/dev/null 2>&1 && ok "gh 로그아웃: $login" || warn "gh 로그아웃 실패: $login (직접: gh auth logout -h github.com -u $login)"
  fi
  if [[ $keep == 1 ]]; then
    find "$state" -mindepth 1 -maxdepth 1 ! -name records -exec rm -rf -- {} +
    ok "삭제: $state (records/ 는 남김)"
  else
    rm -rf -- "$state"
    ok "삭제: $state"
  fi
  echo
  echo "  다시 설치해 보려면: ./install.sh --board"
  echo "  GitHub 의 기록 레포·보드는 그대로라서, 마법사가 기존 것에 다시 연결합니다."
  echo "  레포·보드를 새로 만드는 과정까지 시험하려면 마법사에서 새 레포 이름을 입력하세요 (또는 GitHub 웹에서 지운 뒤 진행)."
}

if [[ $mode == uninstall ]]; then
  step "링크 제거 ($BIN_DIR)"
  for c in "${CMDS[@]}"; do
    l="$BIN_DIR/$c"
    if [[ -L "$l" && "$(readlink -f "$l")" == "$ROOT"/bin/* ]]; then
      if [[ $dry == 1 ]]; then ok "삭제 예정 $c"; else rm "$l"; ok "삭제 $c"; fi
    else warn "건너뜀 $c (이 레포의 링크가 아님)"; fi
  done
  if [[ $purge == 1 ]]; then
    purge_all
  else
    echo; echo "레포 폴더($ROOT)와 ~/.ai-workflow 의 기록은 그대로 남아 있습니다."
    echo "연결 정보·기록까지 지우려면: ./install.sh --uninstall --purge   (먼저 --dry-run 으로 확인 가능)"
  fi
  exit 0
fi

# ---------------------------------------------------------------- 1. 기본 도구
step "1. 기본 도구"
grep -qi microsoft /proc/version 2>/dev/null && ok "WSL 환경" || warn "WSL 이 아님 (Linux/macOS 에서도 대부분 동작)"
for t in git python3 curl; do has "$t" && ok "$t" || bad "$t 없음 → sudo apt install -y $t"; done
if has git; then
  n="$(git config --global user.name || true)"; e="$(git config --global user.email || true)"
  [[ -n "$n" && -n "$e" ]] && ok "git 사용자: $n <$e>" \
    || warn "git 사용자 정보 없음 → git config --global user.name \"이름\"; git config --global user.email \"메일\""
fi

# ---------------------------------------------------------------- 2. Claude Code
step "2. Claude Code"
if has claude; then
  ok "claude $(claude --version 2>/dev/null | head -1)"
elif [[ $mode == install ]] && ask "Claude Code 가 없습니다. 공식 설치 스크립트로 설치할까요? (curl -fsSL https://claude.ai/install.sh | bash)"; then
  curl -fsSL https://claude.ai/install.sh | bash
  export PATH="$HOME/.local/bin:$PATH"
  has claude && ok "claude 설치됨" || bad "설치 후에도 claude 를 찾지 못함. 새 터미널을 열고 다시 실행하세요"
else
  bad "claude 없음 → curl -fsSL https://claude.ai/install.sh | bash"
fi
has claude && echo "    처음 쓰는 경우: 터미널에서 claude 를 한 번 실행해 Claude 계정(Pro/Max/Team/Enterprise) 또는 Console API 키로 로그인하세요."

# ---------------------------------------------------------------- 3. 명령 등록
step "3. 명령 등록 ($BIN_DIR)"
if [[ $mode == install ]]; then
  mkdir -p "$BIN_DIR"
  chmod +x "$ROOT"/bin/ai-* "$ROOT"/bin/claude-personal "$ROOT/install.sh"
fi
for c in "${CMDS[@]}"; do
  l="$BIN_DIR/$c"; src="$ROOT/bin/$c"
  if [[ -L "$l" && "$(readlink -f "$l")" == "$(readlink -f "$src")" ]]; then ok "$c"
  elif [[ -e "$l" || -L "$l" ]]; then bad "$c: 같은 이름의 다른 파일이 있어 건드리지 않음 ($l)"
  elif [[ $mode == install ]]; then ln -s "$src" "$l"; ok "$c 등록"
  else warn "$c 미등록"; fi
done
case ":$PATH:" in
  *":$BIN_DIR:"*) ok "PATH 에 $BIN_DIR 포함" ;;
  *)
    if [[ $mode == install ]] && ask "$BIN_DIR 이 PATH 에 없습니다. ~/.bashrc 에 추가할까요?"; then
      printf '\n# ai-workflow\nexport PATH="%s:$PATH"\n' "$BIN_DIR" >> "$HOME/.bashrc"
      ok "~/.bashrc 에 추가함 (새 터미널부터 적용, 지금은: source ~/.bashrc)"
    elif grep -qs "^export PATH=\"$BIN_DIR:" "$HOME/.bashrc"; then
      warn "~/.bashrc 에는 추가돼 있음. 새 터미널을 열거나 source ~/.bashrc"
    else
      warn "PATH 에 $BIN_DIR 이 없음 → echo 'export PATH=\"$BIN_DIR:\$PATH\"' >> ~/.bashrc"
    fi ;;
esac

# ---------------------------------------------------------------- 4. GitHub 보드 (ai-board)
step "4. GitHub 보드 연동 (ai-board)"
if [[ $board == ask && $mode == install ]]; then
  echo "    여러 프로젝트·세션의 작업이 GitHub Projects 보드 하나에 카드로 실시간 정리됩니다."
  echo "    (작업 시작 → AI작업중, 질문 → 판단필요, 답변 끝 → 검토대기 + 보고 코멘트, 이슈 닫기 → 완료)"
  echo "    카드는 작업 레포가 아니라 비공개 기록 레포(기존 레포를 고르거나, 없으면 <내계정>/ai-board 를 만듦)의 이슈로 쌓입니다."
  echo "    필요한 것: GitHub 계정 하나, GitHub CLI, 로그인 + project 권한 (보드는 기존 것을 고르거나, 없으면 ai-board 를 만듦)"
  ask "지금 연동할까요?" && board=yes || board=no
fi

if [[ $mode == check || $board == yes ]]; then
  if ! has gh; then
    echo "    GitHub CLI: 터미널에서 GitHub 를 다루는 GitHub 공식 프로그램(명령 이름 gh). 설치는 누구나 같고, 계정 연결은 다음 로그인 단계에서 합니다."
    if [[ $mode == install ]] && has apt-get && ask "GitHub CLI 를 설치할까요? (GitHub 배포 저장소 cli.github.com 에서 apt 로 설치, sudo 비밀번호 필요)"; then
      sudo mkdir -p -m 755 /etc/apt/keyrings
      curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg | sudo tee /etc/apt/keyrings/githubcli-archive-keyring.gpg >/dev/null
      sudo chmod go+r /etc/apt/keyrings/githubcli-archive-keyring.gpg
      echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" \
        | sudo tee /etc/apt/sources.list.d/github-cli.list >/dev/null
      sudo apt-get update -qq && sudo apt-get install -y -qq gh
    fi
  fi
  if ! has gh; then
    bad "GitHub CLI 없음 → docs/github-setup.md 1단계 (https://cli.github.com)"
  else
    ok "GitHub CLI $(gh --version | head -1 | awk '{print $3}')"
    if ! gh auth status >/dev/null 2>&1 && [[ $mode == install ]] && ask "본인 GitHub 계정으로 로그인할까요? (브라우저 인증, 보드용 project 권한 포함)"; then
      echo "    표시되는 8자리 코드를 브라우저(https://github.com/login/device)에 입력하고, 본인 계정으로 승인하세요."
      gh auth login -h github.com -p https -w -s project || true
    fi
    if ! gh auth status >/dev/null 2>&1; then
      bad "GitHub 로그인 안 됨 → gh auth login -s project"
    else
      me="$(gh api user -q .login)"
      ok "로그인: $me"
      if ! gh auth status 2>&1 | grep -q "'project'"; then
        if [[ $mode == install ]] && ask "보드에 필요한 project 권한이 없습니다. 추가할까요? (브라우저 인증)"; then
          gh auth refresh -h github.com -s project || true
        fi
      fi
      gh auth status 2>&1 | grep -q "'project'" && ok "project 권한" || bad "project 권한 없음 → gh auth refresh -h github.com -s project"
      if [[ $reconnect == 0 ]] && [[ -f "${AI_WORKFLOW_STATE:-$HOME/.ai-workflow}/profiles.json" || -f "${AI_WORKFLOW_STATE:-$HOME/.ai-workflow}/board.json" ]]; then
        # 파일만 남고 GitHub 의 기록 레포가 지워진 경우(재설치 때 흔함)를 잡아서 다시 만든다
        chk="$(python3 "$ROOT/lib/boardsetup.py" check 2>/dev/null || true)"   # 레포가 없으면 종료코드 1 → set -e 로 멈추지 않게
        if grep -q '^OK' <<<"$chk"; then
          ok "연결됨: $(awk '{print $2" · "$3}' <<<"$chk")  (확인: ai-board status, 다시 고르기: ./install.sh --reconnect)"
        elif grep -q '^MISSING' <<<"$chk"; then
          warn "기록 레포가 GitHub 에 없습니다 ($(awk '{print $3}' <<<"$chk"))."
          if [[ $mode == install ]] && { [[ $yes == 1 || ! -t 0 ]] || ask "다시 설정할까요? (기존 레포를 고르거나 ai-board 비공개 레포 생성, 보드는 있으면 재사용)"; }; then
            if [[ $yes == 1 || ! -t 0 ]]; then python3 "$ROOT/lib/boardsetup.py" -y --create-repo || warn "설정 실패 → ./install.sh --reconnect"
            else python3 "$ROOT/lib/boardsetup.py" || warn "설정을 마치지 못했습니다 → ./install.sh --reconnect"; fi
          else
            warn "나중에: ./install.sh --reconnect"
          fi
        else
          warn "기록 레포를 확인하지 못했습니다 (네트워크·권한?) → ai-board status"
        fi
      elif [[ $mode == install ]] && gh auth status 2>&1 | grep -q "'project'"; then
        # 기록 레포(기존 레포 연결, 없으면 ai-board 비공개 생성) → 보드(기존 선택, 없으면 ai-board 생성) 를 물으며 설정한다
        if [[ $yes == 1 || ! -t 0 ]]; then python3 "$ROOT/lib/boardsetup.py" -y --create-repo || warn "설정 실패 → ./install.sh --reconnect"
        else python3 "$ROOT/lib/boardsetup.py" || warn "설정을 마치지 못했습니다 → ./install.sh --reconnect"; fi
      else
        warn "기록 레포·보드 미설정 → ./install.sh --board"
      fi
    fi
  fi
else
  warn "건너뜀. 나중에: ./install.sh --board"
fi

# ---------------------------------------------------------------- 마무리
step "완료"
STATE_DIR="${AI_WORKFLOW_STATE:-$HOME/.ai-workflow}"
if [[ -f "$STATE_DIR/profiles.json" || -f "$STATE_DIR/board.json" ]]; then
  cat <<EOF
  설치와 계정 설정이 끝났습니다. 명령은 모두 일반 터미널(WSL)에서 입력합니다. Claude 안에서 따로 설정할 것은 없습니다.

  [매번] 작업할 프로젝트 폴더에서 시작
    cd ~/myproject
    claude-personal              # 개인 프로젝트 (회사 프로젝트는 claude-work)
    → 열린 Claude 에게 "myproject 파악해줘" 처럼 평소대로 요청하면 됩니다.

  [필요할 때] 터미널에서
    ai-board                     # 기록 보드 열기
    ai-board status              # 연결된 계정·기록 레포·보드 확인
    ./install.sh --reconnect     # 기록 레포·보드를 다시 고르기 (이 레포 폴더에서)
  그냥 claude 로 시작한 세션에는 워크플로우가 적용되지 않습니다.
EOF
else
  cat <<EOF
  설치는 끝났지만 기록 레포·보드 설정이 아직 남았습니다. 명령은 모두 일반 터미널(WSL)에서 입력합니다.

  [1회] 계정 연결과 기록 레포·보드 설정
    gh auth login -s project     # GitHub 로그인 (아직 안 했다면)
    ./install.sh --board         # 기록 레포(기존 것 또는 ai-board 생성) → 보드(기존 것 또는 ai-board 생성). 질문에 답하면 끝

  [매번] 설정 후에는 프로젝트 폴더에서 시작
    cd ~/myproject
    claude-personal              # 열린 Claude 에게 평소대로 요청하면 됩니다

  GitHub 기록 없이 쓰려면 설정을 건너뛰어도 claude-personal 은 동작하고, 일지는 ~/.ai-workflow/records/ 에 남습니다.
  그냥 claude 로 시작한 세션에는 워크플로우가 적용되지 않습니다.
EOF
fi
