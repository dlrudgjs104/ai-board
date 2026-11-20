# ai-workflow

여러 프로젝트를 AI로 개발할 때 쓰는 **작업 규칙, 템플릿, 보조 명령** 모음.
배경과 분석은 [docs/ai-era-repo-and-visibility-guide.md](docs/ai-era-repo-and-visibility-guide.md).

## 세션을 시작하는 법 (모드 선택)

| 명령 | 모드 | 적용되는 규칙 | 언제 |
|---|---|---|---|
| `claude` | personal(기본) | `~/.claude/CLAUDE.md` 가 core + review-gate + personal 을 읽게 함 | 평소 개인 프로젝트 |
| `claude-personal` | personal | core + review-gate + github-board + personal (시스템 프롬프트로 확실히 주입) | 개인 프로젝트, 규칙을 확실히 적용 |
| `claude-work` | work | core + review-gate + github-board + work | 회사 작업. 브랜치 + PR, main 직접 금지, 개인 규칙 무시 |
| `claude-lite` | lite | lite 만 | 규약 없이 가볍게. 간단한 작업·질문 |
| `claude-lite -d 문서.md` | lite + 지정 문서 | lite + 그 문서의 지시 | "이 문서만 읽고 이렇게 작업해" |

- `-d 문서.md` 는 모든 모드에서 쓸 수 있다. 그 세션에서 가장 먼저 읽고 우선 따를 문서를 지정한다.
- 나머지 인자는 `claude` 에 그대로 전달된다. 예: `claude-work --resume`, `claude-lite -d ~/notes/task.md`
- 회사 작업 규칙은 `claude-work` 로 시작한 세션에만 적용된다. 일반 `claude` 와 `claude-personal` 에는 적용되지 않는다.
- 모드별 규칙 파일은 `rules/` 에서 직접 고치면 다음 세션부터 반영된다.

## 구성

```
ai-workflow/
├─ rules/
│   ├─ core.md          세션 시작/종료 절차, STATUS 갱신, 완료 조건, 시크릿  (personal, work)
│   ├─ review-gate.md   위험도 분류(높음/중간/낮음), 요약 표준 형식         (personal, work)
│   ├─ github-board.md  GitHub Projects 보드 연동 규칙                     (personal, work)
│   ├─ personal.md      main 직접, 커밋 전 묻기, push는 요청 시
│   ├─ work.md          브랜치 + PR, 병합은 사람, worktree, 회사 정보 보호
│   └─ lite.md          문서 규약 생략, 지정 문서만
├─ templates/           STATUS.md, plan.md, adr.md, CLAUDE.project.md
├─ bin/                 claude-personal|work|lite, ai-init, ai-status, ai-board
├─ github-projects/SETUP.md   보드 설정 절차
└─ docs/                분석 문서
```

`~/.claude/CLAUDE.md` 는 진입점이다. `[AI-MODE: …]` 블록이 없는 세션(그냥 `claude`)을 personal 기본 모드로 취급한다.
`bin/` 의 명령은 `~/.local/bin` 에 심볼릭 링크되어 어디서든 실행된다.

## 일상 흐름

1. 아침: `ai-status` (또는 `ai-status -r`) 로 🔴 판단 필요 → 🟢 검토 대기 확인. GitHub 보드를 설정했다면 보드에서도 확인
2. 프로젝트에서 `claude-personal` / `claude-work` 로 작업 시작. AI가 STATUS.md 를 읽고 이어서 한다
3. 작업이 끝나면 AI가 STATUS.md/worklog 를 갱신하고 "끝난 것 / 검토 필요도 / 내 판단 필요" 를 보고한다
4. 높음 항목부터 검토하고, 확인한 🟢 항목은 정리한다

## 새 프로젝트/기존 프로젝트에 적용

```bash
ai-init -n ~/myproject    # 무엇을 만들지 미리 보기
ai-init ~/myproject       # docs/STATUS.md, decisions/, plans/, CLAUDE.md(없을 때만) 생성. 기존 파일은 덮어쓰지 않음
```

## GitHub Projects 보드

[github-projects/SETUP.md](github-projects/SETUP.md) 참고. `gh` 설치와 인증 이후 `ai-board setup`.

## 주의
- 이 폴더에는 시크릿을 넣지 않는다. `.board`(보드 번호) 정도만 로컬 설정이다.
- 개인 프로젝트 메모리(`~/.claude/projects/*/memory`)의 git 규칙(main 직접, 브랜치 금지)은 personal 용이다. work 모드는 이를 명시적으로 무시한다.
