"""기록(작업 일지·카드·코멘트)에 올라가기 전에 시크릿을 가린다.

규칙 문서의 "시크릿은 기록에 쓰지 않는다" 를 AI 의 기억이 아니라 코드로 보장하기 위한 안전망이다.
알려진 토큰 형식, PEM 개인키, KEY=값 형태의 대입, URL 안의 비밀번호, Authorization 헤더를 `***` 로 바꾼다.
완벽한 탐지는 아니므로(임의의 문자열 비밀번호는 못 잡는다) 요청에 비밀번호를 직접 쓰지 않는 것이 먼저다.
같은 글에 여러 번 적용해도 결과가 같다(idempotent).
"""
import re

MASK = "***"

# 형식이 뚜렷한 토큰: 통째로 가린다
_TOKENS = [
    r"gh[pousr]_[A-Za-z0-9]{20,}",                      # GitHub
    r"github_pat_[A-Za-z0-9_]{20,}",
    r"sk-[A-Za-z0-9][A-Za-z0-9_-]{16,}",                # Anthropic · OpenAI 등
    r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b",                   # AWS 액세스 키 ID
    r"xox[abprs]-[A-Za-z0-9-]{10,}",                    # Slack
    r"AIza[0-9A-Za-z_-]{35}",                           # Google API 키
    r"\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}",   # JWT
    r"glpat-[A-Za-z0-9_-]{20,}",                        # GitLab
    r"npm_[A-Za-z0-9]{30,}",                            # npm
]
_TOKEN_RE = re.compile("|".join(f"(?:{p})" for p in _TOKENS))

# PEM 블록 (끝줄이 잘렸으면 시작줄 뒤 전부)
_PEM_RE = re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?(?:-----END [A-Z ]*PRIVATE KEY-----|\Z)", re.S)

# Authorization: Bearer xxx
_BEARER_RE = re.compile(r"(?i)\b(Bearer|Basic)\s+[A-Za-z0-9._~+/=-]{12,}")

# https://user:비밀번호@host
_URLCRED_RE = re.compile(r"(?<=://)([^\s/:@]+):([^\s/@]+)@")

# 이름에 비밀 단어가 들어간 대입: PASSWORD=..., api_key: "...", --token xxx
_WORD = r"(?:PASSWORD|PASSWD|SECRET|TOKEN(?!S)|API[_-]?KEY|ACCESS[_-]?KEY|PRIVATE[_-]?KEY|CREDENTIAL)"
_ASSIGN_RE = re.compile(
    r"(?i)(\b[A-Za-z0-9_.-]*" + _WORD + r"[A-Za-z0-9_.-]*[\"']?\s*[=:]\s*)([\"']?)([^\s\"'`,;&)]{4,})(\2)")
_FLAG_RE = re.compile(r"(?i)(--?" + r"(?:password|passwd|token|secret|api-?key|access-?key)" + r"[ =])([^\s\"'`-][^\s\"'`]*)")


def _keep(value: str) -> bool:
    """값이 이미 가려졌거나 변수 참조·자리표시자라서 가릴 필요가 없는가."""
    return (value.startswith(("$", "<", "{", "%", "*", "(", "[")) or set(value) <= set("*.x#-_")
            or value.lower() in ("true", "false", "null", "none", "required", "string", "empty", "redacted"))


def _assign(m):
    return m.group(0) if _keep(m.group(3)) else f"{m.group(1)}{m.group(2)}{MASK}{m.group(4)}"


def _flag(m):
    return m.group(0) if _keep(m.group(2)) else f"{m.group(1)}{MASK}"


def redact(text):
    """text 안의 시크릿으로 보이는 부분을 *** 로 바꿔 돌려준다. 문자열이 아니면 그대로 돌려준다."""
    if not isinstance(text, str) or not text:
        return text
    text = _PEM_RE.sub(f"-----BEGIN PRIVATE KEY----- {MASK} -----END PRIVATE KEY-----", text)
    text = _TOKEN_RE.sub(MASK, text)
    text = _BEARER_RE.sub(lambda m: f"{m.group(1)} {MASK}", text)
    text = _URLCRED_RE.sub(lambda m: f"{m.group(1)}:{MASK}@", text)
    text = _ASSIGN_RE.sub(_assign, text)
    text = _FLAG_RE.sub(_flag, text)
    return text
