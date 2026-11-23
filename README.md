# ai-workflow

여러 프로젝트를 여러 Claude Code 세션으로 동시에 개발할 때, 모든 작업이 **GitHub Projects 보드 하나**에 카드로 실시간 정리되고, 세션이 끊겨도 다음 날 바로 이어서 일하게 해 주는 도구 모음.

```
 ┌ 터미널 1: ~/shop     $ claude-personal ─┐
 ├ 터미널 2: ~/blog     $ claude-personal ─┼─ 훅이 자동 기록 ─▶ 대기열 ─▶ 전송기 1개 ─▶ GitHub Projects "AI Board"
 └ 터미널 3: ~/company  $ claude-work     ─┘                                          Backlog · AI작업중 · 판단필요 · 검토대기 · 완료
          각 프로젝트 docs/STATUS.md (AI가 갱신) ─▶ 다음 세션 시작 때 자동으로 이어받음
```

| 하고 싶은 것 | 하는 법 |
|---|---|
| 일을 시킨다 | 프로젝트 폴더에서 `claude-personal` (회사 일은 `claude-work`) 로 시작해서 평소처럼 요청 |
| 진행 상황을 본다 | 보드(`ai-board`)에서 세션마다 카드 하나. 작업이 시작되면 **AI작업중**, 카드 본문에 요청·수정 파일·커밋이 쌓임 |
| 끝난 걸 안다 | 답변이 끝나면 카드가 **검토대기**로 가고 마지막 답변이 **✅ 작업 보고** 코멘트로 붙음. 결정이 필요하면 **판단필요** + **❓** 코멘트. 휴대폰 GitHub 앱으로 알림 |
| 확인을 끝낸다 | 이슈를 닫거나 "확인 완료 처리해줘" → **완료**. personal 모드에서 "커밋하고 푸시해줘" 까지 하면 제목이 `요청 요약 > 수정된 내용` 으로 바뀌고 자동으로 **완료** |
| 다음 날 이어서 한다 | 같은 폴더에서 `claude-personal` → 지난 상황(STATUS 🔴🟡⚪, 이 프로젝트 카드, 최근 세션)이 자동으로 들어감. 같은 세션을 이어 열면(`--resume`) 같은 카드가 이어짐 |
| 할 일을 미리 적어 둔다 | 보드에서 직접 카드 추가 또는 `ai-board task "할 일"` → 나중에 세션에서 `#12 진행해줘` 하면 그 카드로 연결 |
| 여러 프로젝트를 동시에 | 터미널마다 다른 프로젝트에서 세션을 켜면 보드 한 곳에 모두 나옴. 프로젝트별 보기는 라벨 필터 탭 |

- **원하는 세션에서만 켜진다.** `claude-personal` / `claude-work` / `claude-lite` 로 시작한 세션에만 규칙과 기록이 적용된다. 그냥 `claude` 는 평소와 같고 `~/.claude` 설정은 건드리지 않는다.
- **정확하다.** 카드 생성·이동·보고는 Claude Code 훅이 세션 이벤트(작업 시작, 질문, 답변 끝)를 보고 자동으로 한다. AI가 규칙을 잊어도 빠지지 않는다. 파일을 바꾸고 STATUS.md 를 안 고치면 훅이 되돌려 고치게 한다.
- **API 한도에 걸리지 않는다.** 모든 세션의 변경은 로컬 대기열에서 합쳐져 전송기 하나가 순서대로 보낸다. 컬럼 이동은 호출 1번, 카드 본문은 1분에 한 번까지. GitHub 가 잠시 막혀도 대기열에 남았다가 보내진다.
- **간단한 질문 세션은 보드에 안 올라간다.** 파일 수정·커밋·질문·1분 넘는 작업이 있을 때만 카드가 생긴다.

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
| 4. GitHub 보드 | GitHub CLI 설치·로그인(+`project` 권한), 그 뒤 `ai-board init` 마법사: 계정 선택 → 기록 레포(이름 지정, 있으면 연결·없으면 비공개 생성) → 보드(있으면 재사용·없으면 생성) | GitHub 계정 |

```bash
./install.sh --board      # 보드 연동까지 바로
./install.sh --no-board   # 보드 없이 (STATUS.md 와 이어받기만)
./install.sh --check      # 바꾸지 않고 점검만
./install.sh --uninstall  # 명령 링크만 제거
```

보드의 컬럼, "이슈 닫힘 ↔ 완료" 자동화, 완료 카드 자동 보관까지 설치 때 자동으로 설정된다. 자세한 계정·권한·알림 설정은 [docs/github-setup.md](docs/github-setup.md).

---

## 사용법

### 0) 초기 설정과 계정(프로필) — 계정마다 1회
```bash
ai-board init                                   # 마법사: 계정 → 기록 레포 이름 → 보드 → (선택) 적용할 폴더
ai-board init --name company --account 회사계정 --repo ai-log --board-title "Dept Board" --link ~/company -y
ai-board profiles                               # 연결된 계정·레포·보드와 폴더 연결 확인
ai-board link company ~/company                 # 이 폴더 아래 프로젝트는 company 프로필 사용
ai-board default personal                       # 연결 규칙이 없는 폴더는 personal
```
- **프로필 = 계정 + 기록 레포 + 보드.** 회사 계정과 개인 계정을 따로 운영하려면 계정마다 `gh auth login` 후 `ai-board init` 을 한 번씩 한다. 프로필마다 카드 번호·대기열이 따로라 섞이지 않는다.
- **기존 것은 연결한다.** 레포가 이미 있으면 그대로 연결하고(README 는 건드리지 않고 `AI-WORKFLOW.md` 만 추가), 같은 이름의 보드가 있으면 재사용한다. 이름은 `--repo`, `--board-title`, `--board 번호` 로 자유롭게 정한다.
- **새로 만든 레포에는 `README.md` 로 작동 방식 설명서가 들어간다** (카드·일지·보드 흐름·명령). 갱신은 `ai-board init --readme`.
- 어느 프로필을 쓸지는 `-P 이름` > 폴더 연결(`link`) > 기본 프로필 순서로 정해진다. 프로젝트 레포에는 아무 파일도 만들지 않는다 (설정은 `~/.ai-workflow/profiles.json`).
- 예전 단일 보드 설정은 첫 실행 때 자동으로 프로필 `default` 로 옮겨진다.

### 작업 일지 (요청 · 결정 · 반영)
세션마다 일지 md 하나가 자동으로 쌓인다: 요청한 사항 → 결정한 사항 → 반영된 사항(수정 파일·커밋) → 결과 보고.
- 로컬: `~/.ai-workflow/records/<프로젝트>/날짜_시각_세션.md` (보드를 안 써도 항상 남음)
- 기록 레포: 같은 파일이 `records/<프로젝트>/` 로 올라간다. 파일 이름은 `날짜_시각초_세션ID8자리-임의값.md` 로, 같은 프로젝트의 다른 기능을 여러 세션·여러 PC 에서 동시에 해도 덮어쓰지 않는다 (같은 이름이 다른 세션 것이면 `-2` 를 붙임).
- 결정 사항은 AI가 답변 끝 보고의 `### 결정 사항` 목록과 AskUserQuestion 답변에서 가져온다. `off`·`skip` 한 요청은 기록되지 않는다.

### 1) 프로젝트 준비 (프로젝트당 1회, 선택)
```bash
ai-init ~/myproject       # docs/STATUS.md, docs/decisions/, docs/plans/, CLAUDE.md(없을 때만) 생성
```
기존 파일은 덮어쓰지 않는다 (`-n` 은 미리 보기). `CLAUDE.md` 에 실행·테스트 명령과 고위험 영역을 적어 두면 AI가 그 기준으로 일한다.

### 2) 세션 시작

| 명령 | 언제 | 규칙 |
|---|---|---|
| `claude-personal` | 혼자 하는 프로젝트 | main 직접 작업, 커밋 전 확인, push 는 요청 시 |
| `claude-work` | 회사·협업 | 브랜치 + PR 까지만, 병합은 사람. 보고에 회사 내부 정보 안 씀 |
| `claude-lite` | 가볍게 (문서 규약 없이) | 보드·STATUS 를 건드리지 않음 |
| `claude-* -d 문서.md` | "이 문서를 먼저 읽고 그대로 해" | 위 규칙 + 지정 문서 |
| `claude` | 워크플로우 없이 | 평소 그대로 |

나머지 인자는 `claude` 에 그대로 간다. 예: `claude-personal --resume`, `claude-work --continue`

### 세션 중 켜고 끄기 · 모드 전환
시작한 뒤에도 바꿀 수 있다. 세션 안에서는 앞에 `!` 를 붙여 실행한다 (예: `! ai-board off`). Claude 에게 "기록 꺼줘" 라고 해도 된다.

| 명령 | 효과 |
|---|---|
| `ai-board off` | 이 세션의 기록을 끈다. 카드·보고·STATUS 강제·요청 내용 저장이 모두 멈춘다 (일반 claude 처럼) |
| `ai-board on` | 다시 켠다 (끄기 전 모드로) |
| `ai-board skip` | **다음 요청 한 건만** 기록에서 제외하고 자동으로 원래대로. 간단한 질문 하나만 빼고 싶을 때 |
| `ai-board personal` / `work` | 모드 전환. 바뀐 모드의 규칙이 다음 요청부터 적용되고, 보드에는 **새 카드**가 만들어진다 (완료 조건이 달라서) |
| `ai-board now` | 현재 모드 확인 |

- 적용은 **다음 요청부터**다. 작업 중간에 `off` 하면 열려 있던 카드는 검토대기로 정리된다.
- 모드별 규칙(`personal.md`, `work.md`)은 시스템 프롬프트가 아니라 훅이 요청마다 넣어 준다 (처음·전환 직후엔 전문, 평소엔 한 줄 요약). 그래서 중간에 바꿀 수 있다.
- 상태는 런처 실행 단위(`~/.ai-workflow/runs/`)로 저장되므로 `/clear` 해도 유지되고, `claude-personal` 을 새로 시작하면 시작 모드로 돌아간다.
- `claude-lite` 세션은 `off` / `on` / `skip` 만 된다. 회사 내용이 민감한 요청은 `work` 에서도 `skip` 을 권한다.

### 3) 보드
```bash
ai-board                                   # 보드를 브라우저로 열기
ai-board list                              # 터미널에서: 실행 중인 세션 + 컬럼별 카드
ai-board task "로그인 화면 다크 모드" -p shop  # Backlog 카드 추가 (나중에 "#번호 진행해줘")
ai-board status                            # 로그인·보드·대기열·최근 오류 점검
ai-board flush                             # 남은 보드 작업을 지금 보내기
```

### 매일 흐름
1. 출근: 보드에서 **판단필요 → 검토대기**(검토필요도 높음부터) 순서로 본다
2. 일 맡기기: 해당 프로젝트 폴더에서 `claude-personal` → 요청 (미리 만든 카드면 `#번호 진행해줘`). 다른 프로젝트도 다른 터미널에서 동시에
3. 진행 중: 보드에서 카드 상태 확인. 판단필요로 오면 그 세션으로 가서 답한다
4. 검토: 카드의 ✅ 작업 보고를 보고 확인이 끝나면 이슈를 닫는다 → 완료
5. 다음 날: 같은 폴더에서 `claude-personal` 하면 어제 상황이 자동으로 이어진다. 끊긴 세션을 그대로 열려면 카드 본문 맨 아래의 **이어서 열기** 명령

---

## 구성

```
ai-workflow/
├─ install.sh            설치·점검·제거
├─ bin/
│   ├─ claude-personal   모드 런처 (claude-work·claude-lite 는 링크). 규칙 주입 + 훅 연결
│   ├─ ai-hook           Claude Code 훅: 활동 기록, 보드 작업 대기열에 넣기, 시작 요약 주입, STATUS 갱신 확인
│   ├─ ai-board          보드 열기·목록·할 일 카드·설정·대기열 전송기, 세션 중 off/on/skip/personal/work
│   ├─ ai-init           프로젝트 문서 뼈대 생성
│   └─ ai-status         STATUS.md 들만 빠르게 모아 보기
├─ lib/
│   ├─ aiwf.py           공용 (기록 저장소, STATUS.md 해석, 프로필·실행 모드 상태)
│   ├─ boardsetup.py     초기 설정 마법사 (계정·기록 레포·보드·프로필)
│   ├─ journal.py        작업 일지 (요청·결정·반영 md 생성, 기록 레포 업로드)
│   └─ ghboard.py        GitHub 보드 연동 (대기열, 전송기, 카드 생성·이동·보고)
├─ rules/                주입되는 규칙 (core·review-gate·board 는 시작 때, personal·work 는 훅이 요청마다. 고치면 다음 세션부터 반영)
│   ├─ core.md           세션 시작/종료 절차, 완료 조건, 시크릿
│   ├─ review-gate.md    위험도(검토 필요도) 분류, 요약 형식
│   ├─ board.md          보드에 정확히 보이도록 AI가 지킬 것 (보고 형식, 질문으로 끝내기, STATUS 갱신)
│   └─ personal.md · work.md · lite.md
├─ templates/            STATUS.md, plan.md, adr.md, CLAUDE.project.md, RECORDS_README.md(기록 레포 설명서)
└─ docs/                 github-setup.md, 배경 분석
```

로컬 기록은 `~/.ai-workflow/` (세션 상태, 활동 기록, 작업 일지, 프로필, 프로필별 보드 설정·카드·대기열)에 쌓인다.

## 주의
- 기록 레포와 보드는 비공개로 둔다. 요청 원문, 수정 파일 목록, 마지막 답변이 카드에 올라간다.
- 이 레포에는 시크릿을 넣지 않는다. GitHub 토큰은 GitHub CLI 가 따로 보관한다.
- 훅을 잠시 끄려면 `AI_WORKFLOW_HOOKS=0 claude-personal`.
- 사람이 웹에서 카드를 옮기거나 닫은 것은 `ai-board list` 의 로컬 기록에 바로 반영되지 않는다. 정확한 현황은 보드에서 본다.
