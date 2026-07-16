"""SMTP backend that records the result of every Django email delivery."""

from __future__ import annotations

from django.core.mail.backends.smtp import EmailBackend

from .metrics import record_email_delivery


class TrackingEmailBackend(EmailBackend):
    """Keep Django SMTP behavior while emitting a durable delivery metric."""

    def _send(self, email_message):
        recipients = email_message.recipients()
        try:
            sent = super()._send(email_message)
        except Exception as exc:
            record_email_delivery(
                subject=email_message.subject,
                recipient_count=len(recipients),
                success=False,
                provider='django_smtp',
                error_message=str(exc),
            )
            raise

        record_email_delivery(
            subject=email_message.subject,
            recipient_count=len(recipients),
            success=bool(sent),
            provider='django_smtp',
            error_message='' if sent else 'SMTP backend did not accept the message',
        )
        return sent
