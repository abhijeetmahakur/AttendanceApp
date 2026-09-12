"""File storage for leave-request attachments.

Uses S3-compatible cloud storage (Cloudflare R2, AWS S3, Backblaze B2,
MinIO - anything reachable via the S3 API) when configured, falling back
to local disk otherwise, so the app still works end to end without cloud
credentials - the same graceful-degradation pattern as mailer.py and
whatsapp.py.

Local disk is fine for local development, but most hosting platforms only
guarantee a persistent filesystem if you explicitly attach (and usually
pay for) a disk volume - free/ephemeral tiers wipe local files on every
redeploy or restart. Cloud storage avoids that regardless of which host
this app ends up running on.
"""

import os

from flask import current_app


def is_configured():
    cfg = current_app.config
    return bool(cfg.get("S3_BUCKET") and cfg.get("S3_ACCESS_KEY_ID") and cfg.get("S3_SECRET_ACCESS_KEY"))


def _client():
    import boto3

    cfg = current_app.config
    return boto3.client(
        "s3",
        endpoint_url=cfg.get("S3_ENDPOINT_URL") or None,
        aws_access_key_id=cfg["S3_ACCESS_KEY_ID"],
        aws_secret_access_key=cfg["S3_SECRET_ACCESS_KEY"],
        region_name=cfg.get("S3_REGION") or "auto",
    )


def save(file_storage, key):
    """Saves an uploaded file under `key` (a relative path/identifier, e.g.
    "leave_attachments/<student_id>/<uuid>.pdf")."""
    if is_configured():
        _client().upload_fileobj(file_storage, current_app.config["S3_BUCKET"], key)
        return

    abs_path = os.path.join(current_app.config["UPLOAD_FOLDER"], key)
    os.makedirs(os.path.dirname(abs_path), exist_ok=True)
    file_storage.save(abs_path)


def open_stream(key):
    """Returns a (file-like object, content_length_or_None) for `key`.
    Raises FileNotFoundError if it doesn't exist in local-disk mode, or
    botocore's ClientError (404) in cloud-storage mode - callers should
    catch broadly and turn either into a 404 response."""
    if is_configured():
        obj = _client().get_object(Bucket=current_app.config["S3_BUCKET"], Key=key)
        return obj["Body"], obj.get("ContentLength")

    abs_path = os.path.join(current_app.config["UPLOAD_FOLDER"], key)
    return open(abs_path, "rb"), os.path.getsize(abs_path)
