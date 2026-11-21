# GitHub 보드 설정 (AI Board)

모든 프로젝트·세션의 작업 카드는 **추적 레포 하나**(예: `<내계정>/work`, 비공개)의 이슈로 만들어지고, 그 레포에 연결된 **GitHub Projects 보드 "AI Board"** 에서 본다.

```
claude-personal / claude-work 세션 ─ 훅 ─▶ 로컬 대기열 ─▶ 전송기 1개 ─▶ 추적 레포 이슈 + AI Board
 (여러 프로젝트, 여러 세션 동시에)            (변경 합치기)   (순서대로·간격 두고)   Backlog · AI작업중 · 판단필요 · 검토대기 · 완료
```
- 작업 레포(회사·조직 레포 포함)에는 아무것도 만들지 않는다. 작업 레포 권한이 없어도 된다.
- 보드·필드·컬럼 ID 는 설정 때 한 번 받아 두므로 컬럼 이동은 API 호출 1번이다. 모든 세션의 변경은 전송기 하나가 순서대로 보내고, 카드 본문은 1분에 한 번까지만 고친다. 세션 여러 개가 동시에 일해도 GitHub API 한도(시간당 5000)에 한참 못 미친다.
- GitHub 가 잠시 막혀도 작업은 로컬 대기열에 남았다가 풀리면 보내진다.

## 필요한 계정·권한
| 항목 | 왜 | 받는 법 / 확인 |
|---|---|---|
| GitHub 계정 | 보드·추적 레포가 GitHub 에 있다 | https://github.com/signup |
| GitHub CLI 로그인 | 카드 생성·이동·코멘트 | `gh auth login -s project` → `gh auth status` |
| `project` 권한 | Projects 보드 읽기·쓰기. 기본 로그인에는 없다 | `gh auth status` 의 Token scopes 에 `'project'`. 없으면 `gh auth refresh -h github.com -s project` |
| 추적 레포 (비공개) | 카드(이슈)가 모이는 곳 | `ai-board setup <내계정>/work --create` 가 만든다. 직접 만들려면 GitHub 웹 → New repository → **Private** |
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

## 3. 추적 레포 + 보드
```bash
ai-board setup <내계정>/work --create      # 레포가 없으면 비공개로 만들고, 보드 생성·컬럼·검토필요도·레포 연결까지
ai-board setup <owner>/<repo> --board 3    # 이미 있는 보드(팀 보드 등)를 쓸 때
ai-board status                            # 로그인·보드·대기열·최근 오류
```

## 4. 웹에서 1회 (1분)
1. 보드 오른쪽 위 `⋯` → **Workflows** → *Item closed* 를 켜고 Status 를 **완료** 로 → 이슈를 닫으면 카드가 완료로 간다.
2. 보기를 **Board** 레이아웃으로 둔다 (Status 기준 칸반).
3. 프로젝트별 탭: 새 보기(View) → 필터에 `label:proj:trendist` → Save. 프로젝트마다 하나씩.
4. 카드에 `검토필요도`, `Labels` 필드를 보이게 하면 우선순위가 한눈에 보인다.

## 5. 알림 받기
- 휴대폰에 GitHub 모바일 앱을 깔고 로그인하면 카드에 달리는 **❓ 확인이 필요합니다 / ✅ 작업 보고** 코멘트가 푸시로 온다.
- 추적 레포 **Watch → All Activity** 로 두면 메일·앱 알림이 확실하다.
