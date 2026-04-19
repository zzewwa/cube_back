import json
import logging
from urllib import error, parse, request

from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

logger = logging.getLogger(__name__)


def _normalize_proxy_url(raw_proxy):
    proxy = (raw_proxy or '').strip()
    if not proxy:
        return ''

    if proxy.startswith(('http://', 'https://', 'socks5://', 'socks5h://')):
        return proxy

    parts = proxy.split(':')
    if len(parts) == 4:
        host, port, username, password = parts
        username_q = parse.quote(username, safe='')
        password_q = parse.quote(password, safe='')
        return f'http://{username_q}:{password_q}@{host}:{port}'

    if len(parts) == 2:
        host, port = parts
        return f'http://{host}:{port}'

    return proxy


def _build_telegram_opener():
    proxy_url = _normalize_proxy_url(getattr(settings, 'TELEGRAM_PROXY_URL', ''))
    if not proxy_url:
        return request.build_opener()

    proxy_handler = request.ProxyHandler({'http': proxy_url, 'https': proxy_url})
    return request.build_opener(proxy_handler)


def _send_telegram_message(text):
    bot_token = (settings.TELEGRAM_BOT_TOKEN or "").strip()
    chat_id = (settings.TELEGRAM_CHAT_ID or "").strip()
    if not bot_token or not chat_id:
        logger.warning("Telegram alert skipped: TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID is empty")
        return False

    payload = {
        "chat_id": chat_id,
        "text": text,
        "disable_web_page_preview": True,
    }

    endpoint = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    raw_data = json.dumps(payload).encode("utf-8")
    req = request.Request(
        endpoint,
        data=raw_data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        opener = _build_telegram_opener()
        with opener.open(req, timeout=10) as response:
            status_ok = 200 <= response.status < 300
            if not status_ok:
                logger.error("Telegram alert failed with status %s", response.status)
            return status_ok
    except error.URLError:
        logger.exception("Telegram alert request failed")
        return False


def _send_webhook_message(text, payload):
    webhook_url = (getattr(settings, 'ALERT_WEBHOOK_URL', '') or '').strip()
    if not webhook_url:
        return False

    webhook_token = (getattr(settings, 'ALERT_WEBHOOK_BEARER_TOKEN', '') or '').strip()
    body = {
        'text': text,
        'status': payload.get('status', 'unknown'),
        'alerts': payload.get('alerts', []),
    }

    headers = {'Content-Type': 'application/json'}
    if webhook_token:
        headers['Authorization'] = f'Bearer {webhook_token}'

    req = request.Request(
        webhook_url,
        data=json.dumps(body).encode('utf-8'),
        headers=headers,
        method='POST',
    )

    try:
        with request.urlopen(req, timeout=10) as response:
            status_ok = 200 <= response.status < 300
            if not status_ok:
                logger.error('Alert webhook failed with status %s', response.status)
            return status_ok
    except error.URLError:
        logger.exception('Alert webhook request failed')
        return False


def _build_alert_text(payload):
    alerts = payload.get("alerts") or []
    if not alerts:
        return "MyCube alert: empty alert payload received"

    first = alerts[0]
    labels = first.get("labels") or {}
    annotations = first.get("annotations") or {}

    status = (payload.get("status") or first.get("status") or "unknown").upper()
    alert_name = labels.get("alertname", "MyCubeAlert")
    severity = labels.get("severity", "warning")
    summary = annotations.get("summary", "")
    description = annotations.get("description", "")
    instance = labels.get("instance", "")

    lines = [
        f"MyCube ALERT [{status}]",
        f"alert: {alert_name}",
        f"severity: {severity}",
    ]
    if instance:
        lines.append(f"instance: {instance}")
    if summary:
        lines.append(f"summary: {summary}")
    if description:
        lines.append(f"description: {description}")
    lines.append(f"alerts_total: {len(alerts)}")
    return "\n".join(lines)


@csrf_exempt
@require_POST
def alertmanager_webhook_view(request):
    token = request.GET.get("token", "")
    if token != settings.ALERTMANAGER_WEBHOOK_TOKEN:
        return JsonResponse({"ok": False, "error": "forbidden"}, status=403)

    try:
        payload = json.loads(request.body.decode("utf-8") or "{}")
    except (UnicodeDecodeError, json.JSONDecodeError):
        return JsonResponse({"ok": False, "error": "bad payload"}, status=400)

    text = _build_alert_text(payload)
    telegram_sent = _send_telegram_message(text)
    webhook_sent = _send_webhook_message(text, payload)
    return JsonResponse({"ok": telegram_sent or webhook_sent, "telegram": telegram_sent, "webhook": webhook_sent})