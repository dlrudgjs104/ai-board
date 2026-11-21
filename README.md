# ai-workflow

여러 프로젝트를 Claude Code로 개발할 때 쓰는 **작업 규칙, 템플릿, 보조 명령** 모음.
AI가 작업마다 진행 상황(`docs/STATUS.md`)과 검토 필요도를 남기고, 필요하면 GitHub Projects 보드 하나에 여러 레포의 작업을 모아 보여 준다.

- **원하는 세션에서만 켠다.** `claude-personal` / `claude-work` / `claude-lite` 로 시작한 세션에만 규칙이 들어가고, 그냥 `claude` 로 시작한 세션은 평소와 같다. `~/.claude` 설정은 건드리지 않는다.
- **기억은 파일에 남긴다.** STATUS, worklog, plans, ADR에 남은 내용을 다음 세션이 읽고 이어서 작업한다.
- **사람이 볼 양을 줄인다.** 변경마다 위험도(낮음/중간/높음)를 붙이고, 사람은 🔴 판단 필요와 높음부터 본다.

배경과 분석은 [docs/ai-era-repo-and-visibility-guide.md](docs/ai-era-repo-and-visibility-guide.md).

---

## 설치 (WSL Ubuntu 기준, 약 5분)

```bash
git clone https://github.com/dlrudgjs104/ai-workflow.git ~/ai-workflow
cd ~/ai-workflow
./install.sh
```

`install.sh` 는 다음을 확인하고, 없는 것은 **물어본 뒤** 설치하거나 설정 방법을 알려 준다.

| 단계 | 내용 | 필요한 것 |
|---|---|---|
| 1. 기본 도구 | git, python3, curl, git 사용자 이름·메일 | 없으면 `sudo apt install` |
| 2. Claude Code | 없으면 공식 설치 스크립트로 설치 | Claude 계정(Pro/Max/Team/Enterprise) 또는 Console API 키. 처음 `claude` 실행 시 로그인 |
| 3. 명령 등록 | `~/.local/bin` 에 명령 6개 링크, PATH 확인 | 없음 |
| 4. GitHub 보드 (선택) | gh 설치, 로그인, `project` 권한, 보드 생성 또는 팀 보드 연결 | GitHub 계정, sudo(gh 설치 시) |

옵션:

```bash
./install.sh --board      # GitHub 보드 연동까지 바로 진행
./install.sh --no-board   # 보드는 건너뜀 (나중에 --board 로 다시 실행)
./install.sh --check      # 아무것도 바꾸지 않고 상태만 점검
./install.sh --uninstall  # 등록한 명령 링크만 제거
```

다른 위치에 클론해도 된다. 규칙 문서 속 `~/ai-workflow` 경로는 실행할 때 실제 위치로 바뀐다.

### GitHub 계정·권한이 필요한 경우
보드 연동을 쓸 때만 필요하다. 쓰지 않으면 STATUS.md와 `ai-status` 만으로 모든 기능이 동작한다.

| 필요한 것 | 받는 방법 |
|---|---|
| GitHub 계정 | https://github.com/signup |
| gh 로그인 + `project` 권한 | `install.sh --board` 가 브라우저 인증을 띄운다. 직접 하려면 `gh auth login -s project` |
| 이슈를 만들 레포의 쓰기 권한 | 내 레포면 이미 있음. 남의 레포면 소유자에게 collaborator 초대 요청 |
| 팀 보드 접근 | 보드 소유자가 보드 Settings → Manage access 에서 추가해 준 뒤 `ai-board use <owner> <번호>` |

자세한 절차와 웹에서 하는 자동화 설정은 [github-projects/SETUP.md](github-projects/SETUP.md). 지금 상태는 `ai-board status` 로 확인한다.

---

## 사용법

### 1) 프로젝트 준비 (프로젝트당 1회)
```bash
ai-init -n ~/myproject    # 무엇을 만들지 미리 보기
ai-init ~/myproject       # docs/STATUS.md, docs/decisions/, docs/plans/, CLAUDE.md(없을 때만) 생성
```
기존 파일은 덮어쓰지 않는다. 만들어진 `CLAUDE.md` 에 실행·테스트 명령과 고위험 영역을 채워 두면 AI가 그 기준으로 일한다.

### 2) 세션 시작 (모드 선택)

| 명령 | 적용 규칙 | 언제 |
|---|---|---|
| `claude` | 없음 (평소 그대로) | 워크플로우가 필요 없을 때 |
| `claude-personal` | core + review-gate + github-board + personal | 혼자 하는 프로젝트. main 직접 작업, 커밋 전 확인, push는 요청 시 |
| `claude-work` | core + review-gate + github-board + work | 회사·협업. 브랜치 + PR까지만, 병합은 사람이 함 |
| `claude-lite` | lite | 문서 규약 없이 가볍게 |
| `claude-* -d 문서.md` | 위 + 지정 문서 | "이 문서를 먼저 읽고 그대로 해" |

나머지 인자는 `claude` 에 그대로 넘어간다. 예: `claude-work --resume`, `claude-lite -d ~/notes/task.md`

### 3) 세션 안에서 일어나는 일
- 시작할 때: AI가 `CLAUDE.md` → `docs/STATUS.md` → 최근 worklog를 읽고, 🔴 항목이 있으면 먼저 알린다.
- 작업 중: 설계 결정은 `docs/decisions/`(ADR), 여러 세션에 걸친 일은 `docs/plans/` 체크리스트로 남긴다.
- 끝날 때: STATUS.md와 worklog를 갱신하고 **끝난 것 / 검토 필요도 / 내 판단이 필요한 것** 세 가지를 보고한다.
- 보드를 설정했다면 이슈 카드를 `AI작업중 → 판단필요 → 검토대기` 로 옮긴다. 보드 연동이 실패해도 작업은 계속한다.

### 4) 상태 보기
```bash
ai-status          # 모든 프로젝트의 🔴 → 🟡 → 🟢 요약 (~ 아래 4단계까지 검색)
ai-status -r       # 🔴 사람 판단 필요만
ai-status -p shop  # 이름에 shop 이 들어간 프로젝트만
ai-board list      # GitHub 보드 항목
```

### 매일 흐름
1. 아침에 `ai-status -r` 로 🔴부터 처리하고, 보드에서는 **판단필요 → 검토대기**(검토필요도 높음부터) 순서로 본다
2. 프로젝트 폴더에서 `claude-personal` 또는 `claude-work` 로 시작하면 AI가 STATUS를 읽고 이어서 한다
3. 끝나면 보고와 STATUS를 보고 높음 항목부터 검토한다. 확인한 🟢 항목은 지운다

---

## 구성

```
ai-workflow/
├─ install.sh            설치·점검·제거
├─ rules/                세션에 주입되는 규칙 (고치면 다음 세션부터 반영)
│   ├─ core.md           세션 시작/종료 절차, STATUS 갱신, 완료 조건, 시크릿
│   ├─ review-gate.md    위험도 분류, 요약 표준 형식
│   ├─ github-board.md   GitHub Projects 보드 연동
│   ├─ personal.md       개인: main 직접, 커밋 전 묻기
│   ├─ work.md           회사: 브랜치 + PR, worktree, 회사 정보 보호
│   └─ lite.md           문서 규약 생략
├─ templates/            STATUS.md, plan.md, adr.md, CLAUDE.project.md
├─ bin/                  claude-personal (claude-work·claude-lite 는 링크), ai-init, ai-status, ai-board
├─ github-projects/SETUP.md
└─ docs/                 배경 분석
```

## 규칙을 내 방식으로 바꾸기
- 포크하거나 클론한 뒤 `rules/*.md` 를 직접 고친다. 런처가 세션마다 파일을 새로 읽으므로 재설치는 필요 없다.
- 프로젝트별 예외는 그 프로젝트의 `CLAUDE.md` 에 적는다. 프로젝트 규칙이 공통 규칙보다 우선한다.

## 주의
- 이 레포에는 시크릿을 넣지 않는다. 로컬 설정은 `.board`(보드 소유자·번호) 하나이고 `.gitignore` 에 들어 있다.
- 보드를 공개로 바꾸지 않는다. 회사 작업 제목이 보드에 들어갈 수 있다.
- `claude-work` 는 개인 메모리나 personal 규칙의 "main 직접 커밋" 같은 지시를 무시하고 브랜치 + PR 규칙을 우선한다.
