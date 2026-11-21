# ai-workflow

여러 프로젝트를 여러 Claude Code 세션으로 동시에 개발할 때, **무엇이 진행 중이고 · 무엇이 끝났고 · 어디서 내 판단이 필요한지**를 한 화면에서 실시간으로 보고, 세션이 끊겨도 다음 날 바로 이어서 일하게 해 주는 도구 모음.

```
 ┌ 터미널 1: ~/shop     $ claude-personal ─┐
 ├ 터미널 2: ~/blog     $ claude-personal ─┼─ 훅이 자동 기록 ─▶ ~/.ai-workflow ─▶ ai-board (브라우저, 2초마다 갱신, 알림)
 └ 터미널 3: ~/company  $ claude-work     ─┘                        │
          각 프로젝트 docs/STATUS.md (AI가 갱신, git 으로 보관) ──────┴─▶ (선택) GitHub 현황 이슈 — 밖에서 보기·모바일 알림
```

| 하고 싶은 것 | 하는 법 |
|---|---|
| 일을 시킨다 | 프로젝트 폴더에서 `claude-personal` (회사 일은 `claude-work`) 로 시작해서 평소처럼 요청 |
| 진행 상황을 실시간으로 본다 | `ai-board` → 브라우저 보드. 세션마다 **작업 중 / 나를 기다림 / 답변 완료**, 지금 하는 일, 수정 파일, 커밋 |
| 끝난 걸 바로 안다 | 보드의 🔔 알림 켜기 → 답변 완료·확인 필요 때 바탕화면 알림. GitHub 연동 시 휴대폰 알림 |
| 다음 날 이어서 한다 | 같은 폴더에서 `claude-personal` → 지난 상황 요약(🔴 판단 필요·🟡 진행 중·⚪ 예정·최근 세션)이 자동으로 들어가 바로 이어서 일함 |
| 남은 일을 본다 / 미리 적어 둔다 | 보드의 프로젝트 카드, 또는 `ai-board task "할 일"` |
| 여러 프로젝트를 동시에 | 터미널마다 다른 프로젝트에서 세션을 켜면 보드 한 화면에 모두 나옴. 같은 프로젝트에 세션이 겹치면 AI에게 자동으로 알려 줌 |

- **원하는 세션에서만 켜진다.** `claude-personal` / `claude-work` / `claude-lite` 로 시작한 세션에만 규칙과 기록이 적용된다. 그냥 `claude` 는 평소와 같고, `~/.claude` 설정은 건드리지 않는다.
- **정확하다.** 세션 활동은 Claude Code 훅이 자동으로 기록해서 AI가 잊어도 빠지지 않는다. 작업 현황(STATUS.md)은 AI가 시작·막힘·완료 때마다 고치고, 파일을 바꾸고도 안 고치면 훅이 되돌려 고치게 한다.
- **API 한도에 걸리지 않는다.** 실시간 정보는 모두 내 PC 안에서 처리한다. GitHub 는 바뀐 내용이 있을 때만 프로젝트당 이슈 하나를 고친다.

---

## 설치 (WSL Ubuntu 기준, 약 5분)

```bash
git clone https://github.com/dlrudgjs104/ai-workflow.git ~/ai-workflow
cd ~/ai-workflow
./install.sh
```

`install.sh` 는 하나씩 점검하고, 없는 것은 **물어본 뒤** 설치하거나 방법을 알려 준다.

| 단계 | 내용 | 필요한 것 |
|---|---|---|
| 1. 기본 도구 | git, python3, curl, git 사용자 이름·메일 | 없으면 `sudo apt install` |
| 2. Claude Code | 없으면 공식 설치 스크립트로 설치 | Claude 계정(Pro/Max/Team/Enterprise) 또는 Console API 키. 처음 `claude` 실행 때 로그인 |
| 3. 명령 등록 | `~/.local/bin` 에 명령 링크, PATH 확인 | 없음 |
| 4. GitHub 현황 이슈 (선택) | GitHub CLI 설치·로그인, 비공개 추적 레포(기본 `<내계정>/work`) 확인·생성 | GitHub 계정 |

```bash
./install.sh --board      # GitHub 연동까지 바로
./install.sh --no-board   # GitHub 없이 (나중에 --board 로 다시)
./install.sh --check      # 바꾸지 않고 점검만
./install.sh --uninstall  # 명령 링크만 제거
```

GitHub 연동에 필요한 계정·권한과 휴대폰 알림 설정은 [docs/github-setup.md](docs/github-setup.md).

---

## 사용법

### 1) 프로젝트 준비 (프로젝트당 1회)
```bash
ai-init ~/myproject       # docs/STATUS.md, docs/decisions/, docs/plans/, CLAUDE.md(없을 때만) 생성, 보드에 등록
```
기존 파일은 덮어쓰지 않는다 (`-n` 은 미리 보기). 만들어진 `CLAUDE.md` 에 실행·테스트 명령과 고위험 영역을 적어 두면 AI가 그 기준으로 일한다.

### 2) 세션 시작

| 명령 | 언제 | 규칙 |
|---|---|---|
| `claude-personal` | 혼자 하는 프로젝트 | main 직접 작업, 커밋 전 확인, push 는 요청 시 |
| `claude-work` | 회사·협업 | 브랜치 + PR 까지만, 병합은 사람. 기록에 회사 내부 정보 안 씀 |
| `claude-lite` | 가볍게 (문서 규약 없이) | 보드에는 세션만 보이고 STATUS 는 안 건드림 |
| `claude-* -d 문서.md` | "이 문서를 먼저 읽고 그대로 해" | 위 규칙 + 지정 문서 |
| `claude` | 워크플로우 없이 | 평소 그대로 |

나머지 인자는 `claude` 에 그대로 간다. 예: `claude-personal --resume`, `claude-work --continue`

### 3) 보드
```bash
ai-board            # 브라우저로 열기 (WSL 이면 윈도우 브라우저)
ai-board list       # 터미널에서 한눈에
ai-board task "로그인 화면 다크 모드" -p shop   # 할 일 미리 적어 두기 (⚪ 예정)
ai-board status     # 설정·GitHub·오류 점검
```
보드에서 할 수 있는 것: 세션별 실시간 상태와 마지막 답변 요약, 프로젝트별 🔴 판단 필요 / 🟡 진행 중 / ⚪ 예정 / 🟢 완료, 할 일 추가, **이어서 열기·새 세션** 명령 복사, 최근 활동 기록, 브라우저 알림.

### 매일 흐름
1. 출근: `ai-board` → **지금 볼 것**(나를 기다림·최근 완료)과 🔴 판단 필요부터 처리
2. 일 맡기기: 해당 프로젝트 폴더에서 `claude-personal` → 요청. 다른 프로젝트도 다른 터미널에서 동시에
3. 진행 중: 보드에서 상태 확인. 🔔 알림이 오면 그 세션으로 가서 답한다
4. 끝: 🟢 완료 항목(검토 필요도 높음부터)을 확인하고, 확인한 줄은 STATUS 에서 지운다 (또는 AI에게 "확인했어, 정리해 줘")
5. 다음 날: 같은 폴더에서 `claude-personal` 하면 어제 상황이 자동으로 이어진다. 끊긴 세션을 그대로 열려면 보드의 **이어서 열기**

---

## 구성

```
ai-workflow/
├─ install.sh            설치·점검·제거
├─ bin/
│   ├─ claude-personal   모드 런처 (claude-work·claude-lite 는 링크). 규칙 주입 + 기록 훅 연결
│   ├─ ai-hook           Claude Code 훅: 세션 활동 기록, 시작 요약 주입, STATUS 갱신 확인, GitHub 반영 요청
│   ├─ ai-board          보드 서버·터미널 보기·할 일 추가·GitHub 동기화
│   ├─ ai-init           프로젝트 문서 뼈대 생성
│   └─ ai-status         STATUS.md 들만 빠르게 모아 보기
├─ lib/aiwf.py           공용 모듈 (상태 저장소, STATUS.md 해석)
├─ web/dashboard.html    보드 화면
├─ rules/                세션에 주입되는 규칙 (고치면 다음 세션부터 반영)
│   ├─ core.md           세션 시작/종료 절차, 완료 조건, 시크릿
│   ├─ review-gate.md    위험도(검토 필요도) 분류, 요약 형식
│   ├─ board.md          STATUS.md 를 언제 어떻게 고치는지 (보드 정확도)
│   └─ personal.md · work.md · lite.md
├─ templates/            STATUS.md, plan.md, adr.md, CLAUDE.project.md
└─ docs/                 github-setup.md, 배경 분석
```

로컬 기록은 `~/.ai-workflow/` (세션 상태, 활동 기록, 프로젝트 목록, GitHub 동기화 기록)에 쌓인다. 지워도 각 프로젝트의 STATUS.md 는 그대로다.

## 주의
- 이 레포에는 시크릿을 넣지 않는다. 로컬 설정은 `.board`(추적 레포 이름) 하나이고 `.gitignore` 에 들어 있다.
- 추적 레포는 비공개로 둔다. 작업 요청과 현황이 들어간다.
- 보드 서버는 `127.0.0.1` 에서만 열린다. 다른 기기에서 보려면 GitHub 현황 이슈를 쓴다.
- 기록 훅을 잠시 끄려면 `AI_WORKFLOW_HOOKS=0 claude-personal`.
