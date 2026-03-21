"""
Inbound email webhook for Resend.

When someone emails the ingestion address, Resend sends us metadata.
We then call the Resend Attachments API to get download URLs.
"""

import httpx
from fastapi import APIRouter, Request, Response

from app.config import get_settings
from app.services.ingestion import ingest_file

settings = get_settings()

router = APIRouter()


@router.post("/webhooks/resend/inbound")
async def resend_inbound_webhook(request: Request):
    """Receive inbound email notifications from Resend."""
    body = await request.json()
    print(f"Webhook received: {body.get('type')}")

    event_type = body.get("type")
    if event_type != "email.received":
        return Response(status_code=200)

    data = body.get("data", {})
    email_id = data.get("email_id")
    sender = data.get("from")
    to = data.get("to", [])
    subject = data.get("subject")
    attachments_meta = data.get("attachments", [])

    print(
        f"Inbound email: id={email_id}, from={sender}, "
        f"to={to}, subject={subject}, attachments={len(attachments_meta)}"
    )

    if not attachments_meta:
        print("  No attachments, skipping.")
        return {"status": "received", "email_id": email_id, "attachments_count": 0}

    # Step 1: Call Attachments API to get download URLs
    results = []
    skipped = []
    async with httpx.AsyncClient() as client:
        list_resp = await client.get(
            f"https://api.resend.com/emails/receiving/{email_id}/attachments",
            headers={"Authorization": f"Bearer {settings.RESEND_API_KEY}"},
        )

        print(f"  Attachments API response: {list_resp.status_code} {list_resp.text}")

        if list_resp.status_code != 200:
            return {"status": "error", "detail": "Failed to list attachments"}

        attachments = list_resp.json().get("data", [])

        # Step 2: Download each attachment via its download_url
        for att in attachments:
            filename = att.get("filename")
            download_url = att.get("download_url")
            content_type = att.get("content_type")
            print(f"  Attachment: {filename} ({content_type})")

            if download_url:
                dl_resp = await client.get(download_url)
                if dl_resp.status_code == 200:
                    content = dl_resp.content
                    print(f"  Downloaded {filename}: {len(content)} bytes")
                    extension = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
                    if extension not in {"csv", "tsv", "xlsx"}:
                        skipped.append(
                            {
                                "filename": filename,
                                "reason": f"Unsupported file type: .{extension}",
                            }
                        )
                        continue

                    result = await ingest_file(
                        file_bytes=content,
                        filename=filename,
                        method="email",
                    )
                    results.append(result.to_dict())
                else:
                    print(f"  Failed to download {filename}: {dl_resp.status_code}")
                    skipped.append(
                        {
                            "filename": filename,
                            "reason": f"Download failed: {dl_resp.status_code}",
                        }
                    )
            else:
                print(f"  No download URL for {filename}, skipping.")
                skipped.append(
                    {
                        "filename": filename,
                        "reason": "No download URL provided",
                    }
                )

    return {
        "status": "received",
        "email_id": email_id,
        "attachments_processed": len(results),
        "attachments_skipped": skipped,
        "results": results,
    }
