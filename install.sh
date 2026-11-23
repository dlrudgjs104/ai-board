#!/usr/bin/env bash
# ai-workflow 설치/점검/제거 (WSL Ubuntu·Debian 기준, 일반 Linux·macOS 도 대부분 동작)
#
#   ./install.sh              명령 설치 + 필요한 것 점검. GitHub 보드 연동은 물어본 뒤 진행
#   ./install.sh --board      GitHub 보드 연동까지 바로 진행 (gh 설치, 로그인, 권한, 보드 생성/연결)
#   ./install.sh --no-board   보드 연동은 묻지 않고 건너뜀
#   ./install.sh --check      아무것도 바꾸지 않고 상태만 점검
#   ./install.sh --uninstall  ~/.local/bin 에 만든 링크 제거 (레포와 프로젝트 문서는 그대로)
#   -y                        모든 질문에 '예'
#
# 이 스크립트는 ~/.claude 설정을 바꾸지 않는다. 워크플로우는 claude-personal / claude-work / claude-lite
# 로 시작한 세션에만 적용되고, 그냥 claude 로 시작한 세션은 영향이 없다.
set -euo pipefail

ROOT="$(cd "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")" && pwd)"
BIN_DIR="${AI_WORKFLOW_BIN:-$HOME/.local/bin}"
CMDS=(claude-personal claude-work claude-lite ai-status ai-init ai-board)

mode=install; board=ask; yes=0
for a in "$@"; do
  case "$a" in
    --board) board=yes ;;
    --no-board) board=no ;;
    --check) mode=check ;;
    --uninstall) mode=uninstall ;;
    -y|--yes) yes=1 ;;
    -h|--help) sed -n '2,13p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'; exit 0 ;;
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
if [[ $mode == uninstall ]]; then
  step "링크 제거 ($BIN_DIR)"
  for c in "${CMDS[@]}"; do
    l="$BIN_DIR/$c"
    if [[ -L "$l" && "$(readlink -f "$l")" == "$ROOT"/bin/* ]]; then rm "$l"; ok "삭제 $c"; else warn "건너뜀 $c (이 레포의 링크가 아님)"; fi
  done
  echo; echo "레포 폴더($ROOT)와 각 프로젝트의 docs/STATUS.md 는 그대로 남아 있습니다."
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

# ---------------------------------------------------------------- 4. GitHub 보드 (AI Board)
step "4. GitHub 보드 연동 (AI Board)"
if [[ $board == ask && $mode == install ]]; then
  echo "    여러 프로젝트·세션의 작업이 GitHub Projects 보드 하나에 카드로 실시간 정리됩니다."
  echo "    (작업 시작 → AI작업중, 질문 → 판단필요, 답변 끝 → 검토대기 + 보고 코멘트, 이슈 닫기 → 완료)"
  echo "    카드는 작업 레포가 아니라 비공개 기록 레포(기존 레포를 고르거나, 없으면 <내계정>/work 를 만듦)의 이슈로 쌓입니다."
  echo "    필요한 것: GitHub 계정 하나, GitHub CLI, 로그인 + project 권한 (보드는 기존 것을 고르거나, 없으면 AI Board 를 만듦)"
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
      if [[ -f "${AI_WORKFLOW_STATE:-$HOME/.ai-workflow}/profiles.json" || -f "${AI_WORKFLOW_STATE:-$HOME/.ai-workflow}/board.json" ]]; then
        # 파일만 남고 GitHub 의 기록 레포가 지워진 경우(재설치 때 흔함)를 잡아서 다시 만든다
        chk="$("$ROOT/bin/ai-board" check 2>/dev/null || true)"   # 레포가 없으면 종료코드 1 → set -e 로 멈추지 않게
        if grep -q '^OK' <<<"$chk"; then
          ok "연결됨: $(awk '{print $2" · "$3}' <<<"$chk")  (확인: ai-board status, 다시 고르기: ai-board init)"
        elif grep -q '^MISSING' <<<"$chk"; then
          warn "기록 레포가 GitHub 에 없습니다 ($(awk '{print $3}' <<<"$chk"))."
          if [[ $mode == install ]] && { [[ $yes == 1 || ! -t 0 ]] || ask "다시 설정할까요? (기존 레포를 고르거나 work 비공개 레포 생성, 보드는 있으면 재사용)"; }; then
            if [[ $yes == 1 || ! -t 0 ]]; then "$ROOT/bin/ai-board" init -y --create-repo || warn "설정 실패 → ai-board init"
            else "$ROOT/bin/ai-board" init || warn "설정을 마치지 못했습니다 → ai-board init"; fi
          else
            warn "나중에: ai-board init"
          fi
        else
          warn "기록 레포를 확인하지 못했습니다 (네트워크·권한?) → ai-board status"
        fi
      elif [[ $mode == install ]] && gh auth status 2>&1 | grep -q "'project'"; then
        # 기록 레포(기존 레포 연결, 없으면 work 비공개 생성) → 보드(기존 선택, 없으면 AI Board 생성) 를 물으며 설정한다
        if [[ $yes == 1 || ! -t 0 ]]; then "$ROOT/bin/ai-board" init -y --create-repo || warn "설정 실패 → ai-board init"
        else "$ROOT/bin/ai-board" init || warn "설정을 마치지 못했습니다 → ai-board init"; fi
      else
        warn "기록 레포·보드 미설정 → ai-board init"
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
    ai-board init                # 기록 레포·보드를 다시 고르기
    ai-init ~/myproject          # (선택) 프로젝트에 docs/STATUS.md 만들기. -n 은 미리 보기
  그냥 claude 로 시작한 세션에는 워크플로우가 적용되지 않습니다.
EOF
else
  cat <<EOF
  설치는 끝났지만 기록 레포·보드 설정이 아직 남았습니다. 명령은 모두 일반 터미널(WSL)에서 입력합니다.

  [1회] 계정 연결과 기록 레포·보드 설정
    gh auth login -s project     # GitHub 로그인 (아직 안 했다면)
    ai-board init                # 기록 레포(기존 것 또는 work 생성) → 보드(기존 것 또는 AI Board 생성). 질문에 답하면 끝

  [매번] 설정 후에는 프로젝트 폴더에서 시작
    cd ~/myproject
    claude-personal              # 열린 Claude 에게 평소대로 요청하면 됩니다

  GitHub 기록 없이 쓰려면 설정을 건너뛰어도 claude-personal 은 동작하고, 일지는 ~/.ai-workflow/records/ 에 남습니다.
  그냥 claude 로 시작한 세션에는 워크플로우가 적용되지 않습니다.
EOF
fi
