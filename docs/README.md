# 문서 구조 안내

| 용도 | 권장 위치 | 비고 |
|------|-----------|------|
| **PRD** (제품·기능 요구사항) | `docs/prd/` | 예: `AICRM_prd.md`, 버전별 `prd-v1.0.md` |
| **개발표준** (사람이 읽는 규정·가이드) | `docs/standards/` | 온보딩, 감사, 팀 합의용 Markdown 등. |
| **에디터/AI 규칙** (Cursor 등) | `standards/*.mdc` + `.cursor/rules/` | `.mdc`는 `alwaysApply`, `globs` 등 메타를 둘 수 있습니다. |

샘플 파일은 각 폴더에 `sample-*.md`로 두었습니다. 실제 프로젝트에서는 이름을 바꿔 확장하세요.
