# 프로젝트 이름

## 작업 모드
이 레포는 `~/ai-workflow` 의 규칙을 따른다 (`claude-personal` / `claude-work` / `claude-lite` 로 실행).
- 개인 프로젝트: main 직접 작업 (personal)
- 협업/회사 프로젝트: 브랜치 + PR (work) ← 해당하면 이 줄만 남기고 위 줄을 지운다

## 구조
- `frontend/` : (스택, 실행 명령)
- `backend/` : (스택, 실행 명령)
- `docs/` : STATUS.md, worklog.md, decisions/, plans/, spec/

## 로컬 실행
- 백엔드: (명령, 포트)
- 프론트: (명령, 포트)

## 테스트·검증 명령 (완료 조건)
- (예: ./gradlew test, npm run lint, npm run build)

## 이 프로젝트의 고위험 영역 (항상 사람 확인)
- (예: 결제 모듈, DB 마이그레이션, 배포 스크립트)

## 문서 갱신 규칙
- 작업 종료마다 docs/STATUS.md 와 docs/worklog.md 갱신
