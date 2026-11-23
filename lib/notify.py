"""판단필요 카드가 생기면 푸시 알림(ntfy)을 보낸다. 기본은 꺼져 있고, 사용자가 주소를 등록해야 켜진다.

- 설정: ~/.ai-workflow/notify.json  {"ntfy": "https://ntfy.sh/내토픽"}   (ai-board notify <주소> 로 등록)
- 외부 서비스로 나가는 내용은 최소로 한다: 프로젝트 이름, 카드 번호, 카드 링크만. 요청·답변 본문은 보내지 않는다.
- 알림 실패는 조용히 넘어간다 (카드 이동을 막지 않는다).
"""
import json
import urllib.error
import urllib.parse
import urllib.request

import aiwf

CONF = aiwf.STATE / "notify.json"


def get_url():
    return (aiwf.load_json(CONF, {}) or {}).get("ntfy") or ""


def set_url(url: str):
    """주소를 등록한다. 빈 문자열이면 끈다. 잘못된 주소는 ValueError."""
    url = (url or "").strip()
    if url:
        p = urllib.parse.urlparse(url)
        if p.scheme not in ("http", "https") or not p.netloc or not p.path.strip("/"):
            raise ValueError("https://서버/토픽 형태의 주소가 필요합니다 (예: https://ntfy.sh/my-topic)")
    aiwf.save_json(CONF, {"ntfy": url} if url else {})


def _payload(url, title, message, click=None):
    p = urllib.parse.urlparse(url)
    body = {"topic": p.path.strip("/").split("/")[0], "title": title, "message": message}
    if click:
        body["click"] = click
    return f"{p.scheme}://{p.netloc}", body


def send(title, message, click=None, url=None, timeout=5):
    """알림을 보낸다. 보냈으면 True. 꺼져 있거나 실패하면 False (예외를 내지 않는다)."""
    url = url if url is not None else get_url()
    if not url:
        return False
    base, body = _payload(url, title, message, click)
    req = urllib.request.Request(base, data=json.dumps(body).encode("utf-8"), headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return 200 <= r.status < 300
    except (urllib.error.URLError, OSError, ValueError):
        return False


def needs_you(project, num, url=None):
    """카드 #num 이 사람의 판단을 기다린다는 알림."""
    return send(f"판단 필요 · {project}", f"카드 #{num} 이(가) 확인을 기다립니다.", click=url)
