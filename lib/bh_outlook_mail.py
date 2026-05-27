"""Envío COM (Outlook) en un solo módulo: HTML + adjunto opcional, reintentos con backoff y trazas."""
from __future__ import annotations

import logging
import os
import time
from typing import Optional

__all__ = [
    "send_html_mail_once",
    "send_html_mail_with_backoff",
]


def send_html_mail_once(
    outlook,
    *,
    to: str,
    cc: str = "",
    subject: str = "",
    html_body: str = "",
    attachment_path: Optional[str] = None,
) -> None:
    mail = outlook.CreateItem(0)
    mail.To = to
    mail.CC = cc or ""
    mail.Subject = subject
    mail.HTMLBody = html_body
    if attachment_path and os.path.isfile(attachment_path):
        mail.Attachments.Add(attachment_path)
    mail.Send()


def send_html_mail_with_backoff(
    outlook,
    *,
    to: str,
    cc: str = "",
    subject: str = "",
    html_body: str = "",
    attachment_path: Optional[str] = None,
    max_attempts: int = 3,
    base_delay_s: float = 2.0,
    backoff_factor: float = 1.5,
    log_context: str = "",
) -> bool:
    """
    Reintenta el envío con espera creciente entre intentos.
    Registra métricas ligeras en log: intento, espera, resultado.
    """
    ctx = log_context or to
    delay = float(base_delay_s)
    last_err: str | None = None
    for intento in range(1, max_attempts + 1):
        try:
            send_html_mail_once(
                outlook,
                to=to,
                cc=cc,
                subject=subject,
                html_body=html_body,
                attachment_path=attachment_path,
            )
            logging.info(
                "[bh-outlook] metric=outcome_send outcome=ok attempts=%s/%s delay_s=0 ctx=%s",
                intento,
                max_attempts,
                ctx,
            )
            return True
        except Exception as e:
            last_err = str(e)
            logging.warning(
                "[bh-outlook] metric=outcome_send outcome=retry attempts=%s/%s err=%s ctx=%s",
                intento,
                max_attempts,
                last_err,
                ctx,
            )
            if intento >= max_attempts:
                break
            logging.info(
                "[bh-outlook] metric=backoff_sleep sleep_s=%.2f next_attempt=%s ctx=%s",
                delay,
                intento + 1,
                ctx,
            )
            time.sleep(delay)
            delay *= backoff_factor
    logging.error(
        "[bh-outlook] metric=outcome_send outcome=fail attempts=%s err=%s ctx=%s",
        max_attempts,
        last_err,
        ctx,
    )
    return False
