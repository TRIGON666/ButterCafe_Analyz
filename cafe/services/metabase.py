import base64
import hashlib
import hmac
import json
import time
from urllib import parse

from django.conf import settings


def _b64url_encode(payload):
    return base64.urlsafe_b64encode(payload).rstrip(b'=').decode('ascii')


def _json_b64url(payload):
    data = json.dumps(payload, separators=(',', ':'), ensure_ascii=False).encode('utf-8')
    return _b64url_encode(data)


def _sign_hs256(message, secret):
    signature = hmac.new(secret.encode('utf-8'), message.encode('ascii'), hashlib.sha256).digest()
    return _b64url_encode(signature)


def build_static_embed_token(resource_type, resource_id, params=None, expires_in_minutes=60):
    header = {'alg': 'HS256', 'typ': 'JWT'}
    payload = {
        'resource': {resource_type: int(resource_id)},
        'params': params or {},
        'exp': int(time.time()) + expires_in_minutes * 60,
    }
    signing_input = f'{_json_b64url(header)}.{_json_b64url(payload)}'
    signature = _sign_hs256(signing_input, settings.METABASE_EMBED_SECRET)
    return f'{signing_input}.{signature}'


def configured_missing_settings():
    missing = []
    if not settings.METABASE_URL:
        missing.append('METABASE_URL')
    if not settings.METABASE_DASHBOARD_ID:
        missing.append('METABASE_DASHBOARD_ID')
    if not settings.METABASE_EMBED_SECRET:
        missing.append('METABASE_EMBED_SECRET')
    return missing


def build_dashboard_embed_url(params=None):
    missing = configured_missing_settings()
    if missing:
        return None

    token = build_static_embed_token('dashboard', settings.METABASE_DASHBOARD_ID, params=params)
    query = parse.urlencode(
        {
            'bordered': 'true',
            'titled': 'true',
            'theme': settings.METABASE_EMBED_THEME,
        }
    )
    return f'{settings.METABASE_URL.rstrip("/")}/embed/dashboard/{token}#{query}'
