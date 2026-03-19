"""
Inbound email webhook for Resend.

When someone emails the ingestion address, Resend sends us metadata.
We then call the Resend API to download attachments.
"""

import logging
import httpx
from fastapi import APIRouter, Request, Response

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

router = APIRouter()


@router.post("/webhooks/resend/inbound")
async def resend_inbound_webhook(request: Request):
    """Receive inbound email notifications from Resend."""
    body = await request.json()

    event_type = body.get("type")
    if event_type != "email.received":
        return Response(status_code=200)

    data = body.get("data", {})
    email_id = data.get("email_id")
    sender = data.get("from")
    to = data.get("to", [])
    subject = data.get("subject")
    attachments = data.get("attachments", [])

    logger.info(
        f"Inbound email received: id={email_id}, from={sender}, "
        f"to={to}, subject={subject}, attachments={len(attachments)}"
    )

    # Download each attachment via Resend API
    for att in attachments:
        att_id = att.get("id")
        filename = att.get("filename")
        content_type = att.get("content_type")
        logger.info(f"  Attachment: {filename} ({content_type}), id={att_id}")

        # Fetch attachment content
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"https://api.resend.com/emails/{email_id}/attachments/{att_id}",
                headers={"Authorization": f"Bearer {settings.RESEND_API_KEY}"},
            )
            if resp.status_code == 200:
                content = resp.content
                logger.info(f"  Downloaded {filename}: {len(content)} bytes")
                # TODO (M2): Feed into ingestion pipeline
            else:
                logger.error(f"  Failed to download {filename}: {resp.status_code}")

    return {
        "status": "received",
        "email_id": email_id,
        "attachments_count": len(attachments),
    }