from __future__ import annotations

import json

from ..config import get_settings
from ..db import session_scope
from ..models import AppSettingsRow, utcnow
from ..schemas import UserSettings, UserSettingsPublic

MASK = "••••••••"


def load_user_settings() -> UserSettings:
    with session_scope() as s:
        row = s.get(AppSettingsRow, 1)
        data = json.loads(row.data) if row else {}
    us = UserSettings(**{k: v for k, v in data.items() if k in UserSettings.model_fields})
    env = get_settings()
    # .env cookies act as defaults when none were saved from the UI.
    if not us.fb_c_user and env.fb_c_user:
        us.fb_c_user = env.fb_c_user
    if not us.fb_xs and env.fb_xs:
        us.fb_xs = env.fb_xs
    if not us.ebay_client_id and env.ebay_client_id:
        us.ebay_client_id = env.ebay_client_id
    if not us.ebay_client_secret and env.ebay_client_secret:
        us.ebay_client_secret = env.ebay_client_secret
    return us


def save_user_settings(new: UserSettings) -> UserSettings:
    current = load_user_settings()
    data = new.model_dump()
    # Masked values coming back from the UI mean "unchanged".
    for k in ("fb_c_user", "fb_xs", "ebay_client_secret"):
        if data.get(k) == MASK:
            data[k] = getattr(current, k)
    for k in ("ebay_client_id", "ebay_client_secret", "fb_c_user", "fb_xs"):
        data[k] = (data.get(k) or "").strip()
    with session_scope() as s:
        row = s.get(AppSettingsRow, 1) or AppSettingsRow(id=1)
        row.data = json.dumps(data)
        row.updated_at = utcnow()
        s.add(row)
        s.commit()
    return UserSettings(**data)


def public_view(us: UserSettings) -> UserSettingsPublic:
    d = us.model_dump()
    d["fb_cookie_configured"] = bool(us.fb_c_user and us.fb_xs)
    d["fb_c_user"] = MASK if us.fb_c_user else ""
    d["fb_xs"] = MASK if us.fb_xs else ""
    d["ebay_api_configured"] = bool(us.ebay_client_id and us.ebay_client_secret)
    d["ebay_client_secret"] = MASK if us.ebay_client_secret else ""
    return UserSettingsPublic(**d)
