# GitHub Projects 단일 보드 설정 ("AI Board")

여러 레포의 작업을 한 보드에서 본다. 한 번만 설정하면 된다.
`gh`(GitHub CLI)가 이 PC에 아직 없어서 1~2단계가 먼저 필요하다.

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

## 3. 보드 생성
```bash
~/ai-workflow/bin/ai-board setup
```
- 개인 계정 아래에 "AI Board" 프로젝트(기본 비공개)를 만들고, `검토필요도`(낮음/중간/높음) 필드를 추가한다.
- 보드 번호는 `~/ai-workflow/.board` 에 저장된다.
- **공개로 바꾸지 말 것.** 회사 작업 제목이 보드에 들어갈 수 있다.

## 4. Status 옵션 이름 변경 (웹, 1분, 1회)
`gh` 로는 기본 Status 옵션을 바꿀 수 없어서 웹에서 한다.
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
- `ai-board` 는 gh 가 없는 환경에서 작성해 아직 실제로 실행해 보지 못했다. 설치·인증 후 `ai-board setup` 과 `move` 를 한 번 시험하고, 안 맞는 부분이 있으면 알려 달라.
