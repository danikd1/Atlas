# -*- coding: utf-8 -*-
"""Отправка email через RuSender API."""

import logging
import os
import uuid

import httpx

logger = logging.getLogger(__name__)

RUSENDER_API_KEY = os.environ.get("RUSENDER_API_KEY", "")
RUSENDER_FROM_EMAIL = os.environ.get("RUSENDER_FROM_EMAIL", "noreply@atlas-reader.pro")
RUSENDER_FROM_NAME = os.environ.get("RUSENDER_FROM_NAME", "Atlas Reader")

RUSENDER_API_URL = "https://api.rusender.ru/api/v1/external-mails/send"


def send_password_reset_code(to_email: str, code: str) -> bool:
    """Отправляет письмо с кодом сброса пароля. Возвращает True при успехе."""
    if not RUSENDER_API_KEY:
        logger.error("RUSENDER_API_KEY не задан — письмо не отправлено")
        return False

    html = f"""
    <div style="font-family: sans-serif; max-width: 480px; margin: 0 auto; padding: 32px;">
      <h2 style="color: #1e293b; margin-bottom: 8px;">Сброс пароля</h2>
      <p style="color: #475569; margin-bottom: 24px;">
        Вы запросили сброс пароля для вашего аккаунта Atlas Reader.
      </p>
      <div style="background: #f1f5f9; border-radius: 12px; padding: 24px; text-align: center; margin-bottom: 24px;">
        <p style="color: #64748b; font-size: 14px; margin: 0 0 8px 0;">Ваш код подтверждения</p>
        <p style="font-size: 36px; font-weight: 700; letter-spacing: 8px; color: #1e293b; margin: 0;">
          {code}
        </p>
      </div>
      <p style="color: #94a3b8; font-size: 13px;">
        Код действителен 15 минут. Если вы не запрашивали сброс пароля — проигнорируйте это письмо.
      </p>
    </div>
    """

    payload = {
        "idempotencyKey": str(uuid.uuid4()),
        "mail": {
            "to": {"email": to_email},
            "from": {"email": RUSENDER_FROM_EMAIL, "name": RUSENDER_FROM_NAME},
            "subject": f"{code} — код сброса пароля Atlas Reader",
            "html": html,
        },
    }

    try:
        response = httpx.post(
            RUSENDER_API_URL,
            json=payload,
            headers={"Content-Type": "application/json", "X-Api-Key": RUSENDER_API_KEY},
            timeout=10,
        )
        response.raise_for_status()
        logger.info("Письмо с кодом сброса отправлено на %s", to_email)
        return True
    except Exception as e:
        logger.error("Ошибка отправки письма на %s: %s", to_email, e)
        return False
