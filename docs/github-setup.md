# GitHub 현황 이슈 설정 (선택)

실시간 보드(`ai-board`)는 GitHub 없이 내 PC 에서 동작한다. GitHub 연동은 **밖에서 보기와 알림**을 위한 선택 기능이다.

```
각 프로젝트의 docs/STATUS.md  ──(바뀌었을 때만, 최소 1분 간격)──▶  추적 레포 <내계정>/work (비공개)
   ↑ AI 세션이 갱신                                                   ├ [trendist] 현황     ← 본문 = STATUS.md
                                                                     ├ [coinsensor] 현황
                                                                     └ [eventor] 현황
                                                                       새 🔴 판단 필요 · 🟢 완료 → 코멘트 → GitHub 알림(메일·모바일 앱)
```
- 프로젝트당 이슈 **하나**만 쓰고 본문을 고친다. 일반 REST API 만 쓰므로 여러 세션이 동시에 일해도 API 한도에 걸리지 않는다.
- 작업 레포(회사·조직 레포 포함)에는 아무것도 만들지 않는다. 작업 레포 권한이 없어도 된다.
- 세션별 실시간 상태(작업 중·입력 대기 등)는 너무 자주 바뀌어서 GitHub 에 올리지 않고 로컬 보드에서만 본다.

## 필요한 계정·권한
| 항목 | 왜 | 받는 법 / 확인 |
|---|---|---|
| GitHub 계정 | 추적 레포가 GitHub 에 있다 | https://github.com/signup |
| GitHub CLI 로그인 | 현황 이슈 생성·갱신 | `gh auth login` → `gh auth status` |
| 추적 레포 (비공개) | 현황 이슈가 모이는 곳 | `ai-board setup <내계정>/work --create` 가 만든다. 직접 만들려면 GitHub 웹 → New repository → **Private** |
| (팀 공용) 추적 레포 쓰기 권한 | 여러 사람이 한 레포에 모을 때 | 레포 소유자가 Settings → Collaborators 에서 초대 → `ai-board setup <owner>/<repo>` |

토큰은 GitHub CLI 가 `~/.config/gh` 에 보관한다. 이 레포에는 저장되지 않는다.

## 1. GitHub CLI 설치 (WSL Ubuntu/Debian)
`./install.sh --board` 가 대신 해 준다. 직접 하려면:
```bash
sudo mkdir -p -m 755 /etc/apt/keyrings
curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg | sudo tee /etc/apt/keyrings/githubcli-archive-keyring.gpg >/dev/null
sudo chmod go+r /etc/apt/keyrings/githubcli-archive-keyring.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" | sudo tee /etc/apt/sources.list.d/github-cli.list >/dev/null
sudo apt update && sudo apt install gh -y
```

## 2. 로그인
```bash
gh auth login        # GitHub.com → HTTPS → 브라우저 인증, 본인 계정으로 승인
gh auth status       # Logged in 확인
```

## 3. 추적 레포 연결
```bash
ai-board setup <내계정>/work --create   # 없으면 비공개로 만들고 연결, 기존 프로젝트 현황을 바로 올림
ai-board status                         # 연결 상태·마지막 반영 시각·최근 오류
```
설정은 `~/ai-workflow/.board` 한 줄(`BOARD_REPO=…`)이고 gitignore 대상이다.

## 4. 알림 받기 (권장)
- 휴대폰에 **GitHub 모바일 앱**을 설치하고 로그인하면, 현황 이슈에 달리는 🔴/🟢 코멘트가 푸시로 온다.
- 추적 레포 오른쪽 위 **Watch → All Activity** 로 두면 메일·앱 알림이 확실히 온다.
- 레포 첫 화면에 현황 이슈를 고정(Pin issue, 최대 3개)해 두면 한눈에 보인다.

## 수동 명령
```bash
ai-board sync            # 지금 폴더 프로젝트를 바로 반영
ai-board sync --all      # 모든 프로젝트 반영
```
평소에는 훅이 Claude 응답이 끝날 때와 세션이 끝날 때 자동으로 반영한다.
