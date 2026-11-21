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
  local r; read -r -p "  ? $1 [y/N] " r; [[ "$r" =~ ^[Yy] ]]
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

# ---------------------------------------------------------------- 4. GitHub 보드 (선택)
step "4. GitHub Projects 보드 연동 (선택)"
if [[ $board == ask && $mode == install ]]; then
  echo "    여러 레포의 작업 상태를 GitHub Projects 칸반 하나에서 보는 기능입니다. 안 써도 나머지는 모두 동작합니다."
  echo "    필요한 것: GitHub 계정, GitHub CLI 설치, 본인 계정 로그인 + project 권한 (이슈를 만들 레포에 쓰기 권한)"
  ask "지금 연동할까요?" && board=yes || board=no
fi

if [[ $mode == check || $board == yes ]]; then
  # gh 설치
  if ! has gh; then
    echo "    GitHub CLI: 터미널에서 이슈·보드를 다루는 GitHub 공식 프로그램(명령 이름 gh). 설치는 누구나 같고, 계정 연결은 다음 로그인 단계에서 합니다."
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
    bad "GitHub CLI 없음 → github-projects/SETUP.md 1단계 (https://cli.github.com)"
  else
    ok "GitHub CLI $(gh --version | head -1 | awk '{print $3}')"
    # 로그인
    if ! gh auth status >/dev/null 2>&1; then
      if [[ $mode == install ]] && ask "본인 GitHub 계정으로 로그인할까요? (브라우저 인증, 보드용 project 권한 포함)"; then
        echo "    표시되는 8자리 코드를 브라우저(https://github.com/login/device)에 입력하고, 본인 계정으로 승인하세요."
        gh auth login -h github.com -p https -w -s project || true
      fi
    fi
    if gh auth status >/dev/null 2>&1; then
      ok "로그인: $(gh api user -q .login 2>/dev/null || echo '?')"
      # project 권한
      if ! gh auth status 2>&1 | grep -q "'project'"; then
        if [[ $mode == install ]] && ask "보드에 필요한 project 권한이 없습니다. 권한을 추가할까요? (브라우저 인증)"; then
          gh auth refresh -h github.com -s project || true
        fi
      fi
      gh auth status 2>&1 | grep -q "'project'" && ok "project 권한" || bad "project 권한 없음 → gh auth refresh -h github.com -s project"
    else
      bad "GitHub 로그인 안 됨 → gh auth login -s project"
    fi
    # 보드
    if [[ -f "$ROOT/.board" ]]; then
      ok "보드 설정됨 ($(tr '\n' ' ' < "$ROOT/.board"))"
    elif [[ $mode == install ]] && gh auth status 2>&1 | grep -q "'project'"; then
      echo "    1) 내 계정에 새 보드 만들기   2) 팀이 이미 쓰는 보드에 연결   3) 나중에"
      sel=3
      if [[ $yes == 1 ]]; then sel=1; elif [[ -t 0 ]]; then read -r -p "  ? 선택 [1/2/3] " sel; fi
      case "$sel" in
        1) "$ROOT/bin/ai-board" setup ;;
        2) read -r -p "  ? 보드 소유자(조직 또는 사용자 이름): " o; read -r -p "  ? 보드 번호(주소 .../projects/<번호>): " num
           "$ROOT/bin/ai-board" use "$o" "$num" ;;
        *) warn "보드는 나중에: ai-board setup  또는  ai-board use <owner> <번호>" ;;
      esac
    else
      warn "보드 미설정 → ai-board setup  또는  ai-board use <owner> <번호>"
    fi
  fi
else
  warn "건너뜀. 나중에: ./install.sh --board"
fi

# ---------------------------------------------------------------- 마무리
step "완료"
cat <<EOF
  사용법은 $ROOT/README.md 를 참고하세요. 바로 해 볼 것:
    ai-init -n ~/myproject       # 프로젝트에 만들 문서 미리 보기
    ai-init ~/myproject          # docs/STATUS.md 등 생성 (기존 파일은 덮어쓰지 않음)
    cd ~/myproject && claude-personal   # 워크플로우 적용 세션 시작
    ai-status                    # 모든 프로젝트 상태 요약
  그냥 claude 로 시작한 세션에는 워크플로우가 적용되지 않습니다.
EOF
