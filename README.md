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
| 4. GitHub 보드 | GitHub CLI 설치·로그인(+`project` 권한), 비공개 추적 레포(기본 `<내계정>/work`) 확인·생성, 보드 생성·컬럼·레포 연결 | GitHub 계정 |

```bash
./install.sh --board      # 보드 연동까지 바로
./install.sh --no-board   # 보드 없이 (STATUS.md 와 이어받기만)
./install.sh --check      # 바꾸지 않고 점검만
./install.sh --uninstall  # 명령 링크만 제거
```

보드의 컬럼, "이슈 닫힘 ↔ 완료" 자동화, 완료 카드 자동 보관까지 설치 때 자동으로 설정된다. 자세한 계정·권한·알림 설정은 [docs/github-setup.md](docs/github-setup.md).

---

## 사용법

### 1) 프로젝트 준비 (프로젝트당 1회)
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
│   ├─ ai-board          보드 열기·목록·할 일 카드·설정·대기열 전송기
│   ├─ ai-init           프로젝트 문서 뼈대 생성
│   └─ ai-status         STATUS.md 들만 빠르게 모아 보기
├─ lib/
│   ├─ aiwf.py           공용 (기록 저장소, STATUS.md 해석)
│   └─ ghboard.py        GitHub 보드 연동 (대기열, 전송기, 카드 생성·이동·보고)
├─ rules/                세션에 주입되는 규칙 (고치면 다음 세션부터 반영)
│   ├─ core.md           세션 시작/종료 절차, 완료 조건, 시크릿
│   ├─ review-gate.md    위험도(검토 필요도) 분류, 요약 형식
│   ├─ board.md          보드에 정확히 보이도록 AI가 지킬 것 (보고 형식, 질문으로 끝내기, STATUS 갱신)
│   └─ personal.md · work.md · lite.md
├─ templates/            STATUS.md, plan.md, adr.md, CLAUDE.project.md
└─ docs/                 github-setup.md, 배경 분석
```

로컬 기록은 `~/.ai-workflow/` (세션 상태, 활동 기록, 보드 설정·카드·대기열)에 쌓인다.

## 주의
- 추적 레포와 보드는 비공개로 둔다. 요청 원문, 수정 파일 목록, 마지막 답변이 카드에 올라간다.
- 이 레포에는 시크릿을 넣지 않는다. GitHub 토큰은 GitHub CLI 가 따로 보관한다.
- 훅을 잠시 끄려면 `AI_WORKFLOW_HOOKS=0 claude-personal`.
- 사람이 웹에서 카드를 옮기거나 닫은 것은 `ai-board list` 의 로컬 기록에 바로 반영되지 않는다. 정확한 현황은 보드에서 본다.
