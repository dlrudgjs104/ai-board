# GitHub Projects 단일 보드 설정 ("AI Board")

여러 레포의 작업을 한 보드에서 본다. 한 번만 설정하면 된다.

> **빠른 방법:** `./install.sh --board` 가 아래 1~3단계(gh 설치, 로그인, project 권한, 보드 생성/연결)를 물어보면서 진행한다.
> Status 옵션도 자동으로 바뀌므로, 웹에서는 5단계(레포 연결·자동화)와 보기 설정만 하면 된다. 진행 상태는 언제든 `ai-board status` 로 확인한다.

## 필요한 계정·권한
| 항목 | 왜 필요한가 | 확인 |
|---|---|---|
| GitHub 계정 | 이슈·보드가 GitHub 에 있다 | `gh api user -q .login` |
| gh 로그인 | 터미널에서 이슈 생성·보드 이동 | `gh auth status` |
| `project` 권한(scope) | Projects 보드 읽기·쓰기. 기본 로그인에는 없다 | `gh auth status` 의 Token scopes 에 `'project'` |
| 레포 쓰기 권한 | 이슈를 만들 레포. 남의 레포면 collaborator 초대 필요 | 레포 Settings → Collaborators |
| (팀 보드) 보드 접근 권한 | 조직/동료 보드에 붙을 때. 보드 소유자가 Settings → Manage access 에서 추가 | `ai-board use <owner> <번호>` 성공 여부 |

토큰은 gh 가 로컬에 보관하며 이 레포에 저장되지 않는다.

## 1. gh 설치 (WSL Ubuntu/Debian)
```bash
# 공식 apt 저장소 방식
sudo mkdir -p -m 755 /etc/apt/keyrings
curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg | sudo tee /etc/apt/keyrings/githubcli-archive-keyring.gpg >/dev/null
sudo chmod go+r /etc/apt/keyrings/githubcli-archive-keyring.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" | sudo tee /etc/apt/sources.list.d/github-cli.list >/dev/null
sudo apt update && sudo apt install gh -y
```

## 2. 인증 (project 권한 포함)
```bash
gh auth login                    # GitHub.com → HTTPS → 브라우저 인증
gh auth refresh -s project       # Projects 접근 권한(scope) 추가. 이걸 빼면 ai-board 가 실패한다
gh auth status                   # project 가 scopes 에 보여야 함
```
> 토큰은 gh 가 로컬에 보관한다. 레포에 올라가지 않는다.

## 3. 보드 생성 또는 연결
```bash
ai-board setup              # 내 계정에 새 보드
ai-board setup my-org       # 조직 아래에 새 보드 (조직에서 프로젝트 생성 권한 필요)
ai-board use my-org 3       # 팀이 이미 쓰는 보드에 연결 (주소 https://github.com/orgs/my-org/projects/3)
```
- 개인 계정 아래에 "AI Board" 프로젝트(기본 비공개)를 만들고, `검토필요도`(낮음/중간/높음) 필드를 추가한다.
- 보드 번호는 `~/ai-workflow/.board` 에 저장된다.
- **공개로 바꾸지 말 것.** 회사 작업 제목이 보드에 들어갈 수 있다.

## 4. Status 옵션 이름 (자동, 실패 시에만 웹에서)
`ai-board setup` 이 API로 아래 5개 옵션을 만든다. 실패했다고 나오거나 `ai-board use` 로 기존 보드에 붙었다면 웹에서 맞춘다.
1. GitHub → 프로필 → Projects → "AI Board" 열기
2. 우측 상단 `⋯` → Settings → Fields → **Status**
3. 옵션을 아래 5개로 맞춘다 (이름을 정확히, 공백 없이):

| 옵션 | 의미 |
|---|---|
| Backlog | 시작 전 |
| AI작업중 | AI가 진행 중 |
| 판단필요 | 사람 결정 대기 (가장 먼저 볼 컬럼) |
| 검토대기 | AI는 끝냈고 사람 검토 대기 |
| 완료 | 확인 끝 |

4. 보드 뷰를 `Board` 레이아웃(칸반)으로 두고, 그룹 기준을 Status로 한다. `Repository` 필드를 카드에 표시하면 어느 프로젝트인지 바로 보인다.

## 5. 레포 연결과 자동화 (웹)
- 보드 `⋯` → Settings → **Manage access / Linked repositories** 에서 사용할 레포를 연결한다 (`ai-board link owner/repo` 도 가능).
  - 연결은 **보드와 소유자가 같은 레포만** 된다. 개인 보드에 조직 레포를 연결할 수는 없지만, 조직 레포의 이슈를 카드로 올리는 것(`ai-board add`)은 문제없다.
- Settings → **Workflows** 에서 다음을 켜면 손이 덜 간다.
  - *Item added to project* → Status = Backlog
  - *Pull request merged* / *Item closed* → Status = 완료
  - *Auto-add to project*: 연결한 레포에서 새 이슈가 생기면 자동 추가

## 6. 사용
```bash
ai-board add owner/myproject "알림 기능 추가" "목표/완료 조건"   # 이슈 생성 + 보드 추가
ai-board move https://github.com/owner/myproject/issues/12 AI작업중
ai-board move https://github.com/owner/myproject/issues/12 판단필요
ai-board move https://github.com/owner/myproject/issues/12 검토대기
ai-board list
```
Claude 세션은 `rules/github-board.md` 에 따라 이 명령을 쓴다 (보드가 설정되어 있을 때만, 실패해도 작업은 막지 않는다).

## 7. 매일 보는 순서 (병목 방지)
1. 터미널: `ai-status -r` — 🔴(내 판단 필요)부터 확인
2. 보드: **판단필요 → 검토대기** 컬럼 순서로 처리. 검토대기는 `검토필요도`가 높음인 카드부터
3. 나머지(AI작업중, Backlog)는 훑어보기만

## 참고: 레포를 아직 GitHub에 올리지 않은 프로젝트
이슈·보드는 GitHub 레포가 있어야 쓸 수 있다. 로컬 전용 프로젝트는 `ai-status`(STATUS.md)만으로 먼저 운영하고, 레포를 만든 뒤 보드에 연결한다. (비공개 레포로 만들고 시크릿 커밋 금지 규칙을 지킬 것: `rules/core.md` 시크릿 절)

## 알려진 한계
- `ai-board use` 로 붙은 기존 보드는 Status 옵션을 바꾸지 않는다. 이름이 다르면 `ai-board move` 가 보드에 있는 옵션 목록을 보여 주며 실패한다.
- `ai-board move` 는 보드 항목을 최대 500개까지만 찾는다.
