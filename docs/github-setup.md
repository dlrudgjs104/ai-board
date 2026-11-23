# GitHub 보드 설정 (AI Board)

모든 프로젝트·세션의 작업 카드는 **기록 레포 하나**(예: `<내계정>/work`, 비공개)의 이슈로 만들어지고, 그 레포에 연결된 **GitHub Projects 보드 "AI Board"** 에서 본다.

```
claude-personal / claude-work 세션 ─ 훅 ─▶ 로컬 대기열 ─▶ 전송기 1개 ─▶ 기록 레포 이슈 + AI Board
 (여러 프로젝트, 여러 세션 동시에)            (변경 합치기)   (순서대로·간격 두고)   Backlog · AI작업중 · 판단필요 · 검토대기 · 완료
```
- 작업 레포(회사·조직 레포 포함)에는 아무것도 만들지 않는다. 작업 레포 권한이 없어도 된다.
- 보드·필드·컬럼 ID 는 설정 때 한 번 받아 두므로 컬럼 이동은 API 호출 1번이다. 모든 세션의 변경은 전송기 하나가 순서대로 보내고, 카드 본문은 1분에 한 번까지만 고친다. 세션 여러 개가 동시에 일해도 GitHub API 한도(시간당 5000)에 한참 못 미친다.
- GitHub 가 잠시 막혀도 작업은 로컬 대기열에 남았다가 풀리면 보내진다.

## 필요한 계정·권한
| 항목 | 왜 | 받는 법 / 확인 |
|---|---|---|
| GitHub 계정 | 보드·기록 레포가 GitHub 에 있다 | https://github.com/signup |
| GitHub CLI 로그인 | 카드 생성·이동·코멘트 | `gh auth login -s project` → `gh auth status` |
| `project` 권한 | Projects 보드 읽기·쓰기. 기본 로그인에는 없다 | `gh auth status` 의 Token scopes 에 `'project'`. 없으면 `gh auth refresh -h github.com -s project` |
| 기록 레포 (비공개) | 카드(이슈)가 모이는 곳 | `ai-board init` 이 만든다. 직접 만들려면 GitHub 웹 → New repository → **Private** |
| (팀 공용) 쓰기 권한 | 여러 사람이 한 보드를 쓸 때 | 레포 소유자가 Settings → Collaborators, 보드 Settings → Manage access 에 추가 → `ai-board setup <owner>/<repo> --board <번호>` |

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

## 2. 로그인 (project 권한 포함)
```bash
gh auth login -s project     # GitHub.com → HTTPS → 브라우저 인증, 본인 계정으로 승인
gh auth status               # Token scopes 에 'project' 확인
```

## 3. 기록 레포 + 보드
계정은 로그인한 GitHub 계정 하나만 쓴다. 카드(이슈)와 작업 일지(`records/`)가 기록 레포에 쌓이고, 카드는 보드 하나에 모인다.
```bash
ai-board init                                 # 마법사: 기록 레포(기존 레포 이름, 엔터면 work 사용·생성) → 보드(번호로 선택, 엔터면 AI Board 사용·생성)
ai-board init --repo ai-log --board-title "내 보드"          # 이름 지정. 레포·보드가 이미 있으면 연결, 없으면 만듦
ai-board init --board 3 --repo owner/repo     # 이미 있는 보드(팀 보드 등)를 번호로 연결
ai-board status                               # 로그인·레포·보드·대기열·최근 오류
```
다른 GitHub 계정으로 바꾸려면 `gh auth login -h github.com -s project`(또는 `gh auth switch`)로 그 계정을 활성화한 뒤 `ai-board init` 을 다시 실행한다. 프로젝트 레포에는 아무 파일도 생기지 않는다.

설명서는 레포 첫 화면에 보이도록 `README.md` 로 올라간다. 새 레포나 비어 있는 README 는 대체하고, 직접 쓴 README 가 있으면 건드리지 않고 `AI-WORKFLOW.md` 로 올린다.

## 4. 자동으로 설정되는 것
- **이슈 닫힘 ↔ 완료:** `init` 이 새 보드의 기본 컬럼(Todo/In Progress/Done)을 ID 를 유지한 채 Backlog/AI작업중/완료 로 이름만 바꾼다. 그래서 GitHub 기본 자동화가 그대로 동작한다.
  - *Item closed*: 이슈를 닫으면 카드가 완료로
  - *Auto-close issue*: 카드를 완료로 옮기면 이슈가 닫힘
- **보관:** 완료된 지 14일 지난 카드는 전송기가 하루 한 번 보드에서 보관한다 (`ai-board archive --days N` 으로 직접도 가능). 이슈는 그대로 남는다.
- 선택: 보기(View)를 **Board** 레이아웃으로 두고, 프로젝트별 탭은 필터 `label:proj:trendist` 로 Save.

> 다른 방법으로 만든 기존 보드를 `--board` 로 연결할 때, 그 보드에서 Done 컬럼을 이미 지웠다면 *Item closed* 자동화가 완료를 가리키지 않을 수 있다. 그때는 보드 ⋯ → Workflows → Item closed 에서 Status 를 완료로 한 번 지정한다.

## 5. 알림 받기
- 휴대폰에 GitHub 모바일 앱을 깔고 로그인하면 카드에 달리는 **❓ 확인이 필요합니다 / ✅ 작업 보고** 코멘트가 푸시로 온다.
- 기록 레포 **Watch → All Activity** 로 두면 메일·앱 알림이 확실하다.
