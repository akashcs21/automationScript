"""JIGYASA LAB — Meta Graph API Facebook Page Reels publisher.

Implements the official two-stage video_reels upload flow:
  1. POST /{PAGE_ID}/video_reels?upload_phase=START   -> video_id + upload_url
  2. POST {upload_url} with binary video               -> upload complete
  3. POST /{PAGE_ID}/video_reels?upload_phase=FINISH   -> post_id
     with is_ai_generated=true and description
Never retries an uncertain publish (avoids duplicate Reels). Never logs tokens.
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any

import requests

from config import FB_PAGE_ACCESS_TOKEN, FB_PAGE_ID, GRAPH_API_VERSION, GRAPH_BASE_URL
from logger import logger, log_event, redact

GRAPH_VIDEO_BASE = f"https://graph-video.facebook.com/{GRAPH_API_VERSION}"


class PublishError(RuntimeError):
    """Raised when publishing cannot be completed safely."""


class _GraphResponse:
    def __init__(self, resp: requests.Response) -> None:
        self.status_code = resp.status_code
        self.text = resp.text
        try:
            self.json = resp.json()
        except ValueError:
            self.json = {}
        self.error = self.json.get("error", {}) if isinstance(self.json, dict) else {}


def _is_retryable_transient(error_code: int | str | None, http_status: int) -> bool:
    """Rate limits and temporary 5xx are the only safe transient errors."""
    if http_status in (429, 500, 502, 503, 504):
        return True
    if error_code in (4, 613, 803):  # rate limit / throttling
        return True
    return False


def _is_fatal_auth(error_code: int | str | None) -> bool:
    return error_code in (190, 102, 200, 190)  # invalid/expired token, permissions


class FacebookPublisher:
    def __init__(self, page_id: str | None = None,
                 access_token: str | None = None) -> None:
        self.page_id = page_id or FB_PAGE_ID
        self.access_token = access_token or FB_PAGE_ACCESS_TOKEN
        if not self.page_id:
            raise PublishError("FB_PAGE_ID is not set — cannot publish to Facebook.")
        if not self.access_token:
            raise PublishError("FB_PAGE_ACCESS_TOKEN is not set — cannot publish to Facebook.")

    # ---------------------------------------------------------------- stage 1
    def start_upload(self, file_size: int, description: str) -> dict[str, Any]:
        """Stage 1: initialize the resumable upload session."""
        url = f"{GRAPH_BASE_URL}/{self.page_id}/video_reels"
        params = {
            "upload_phase": "START",
            "access_token": self.access_token,
        }
        # Some app-scoped setups accept the description at FINISH; START mainly
        # needs the file size hint when provided by the SDK. Keep it minimal.
        logger.info("Stage 1: starting video_reels upload session (page=%s)",
                    self.page_id)
        resp = _GraphResponse(requests.post(url, params=params, timeout=60))
        if resp.status_code != 200 or not resp.json.get("video_id"):
            self._raise_on_error(resp, "upload START")
        video_id = resp.json["video_id"]
        upload_url = resp.json.get("upload_url")
        if not upload_url:
            raise PublishError(f"START response missing upload_url: {resp.text}")
        log_event("upload_started", video_id=video_id,
                  token=redact(self.access_token))
        return {"video_id": video_id, "upload_url": upload_url}

    # ---------------------------------------------------------------- stage 2
    def upload_binary(self, upload_url: str, video_path: Path) -> None:
        """Stage 2: upload the MP4 binary to the returned upload URL."""
        size = video_path.stat().st_size
        logger.info("Stage 2: uploading %s (%.1f MB)", video_path.name,
                    size / 1024 / 1024)
        headers = {
            "Authorization": f"OAuth {self.access_token}",
            "offset": "0",
            "file_size": str(size),
            "Content-Type": "video/mp4",
        }
        with video_path.open("rb") as f:
            resp = _GraphResponse(requests.post(upload_url, headers=headers,
                                                data=f, timeout=600))
        if resp.status_code not in (200, 201, 202) and not resp.json.get("success", True):
            # Some upload_url endpoints return empty 200 OK on success.
            if resp.status_code >= 400:
                self._raise_on_error(resp, "binary upload")
        log_event("binary_uploaded", video_path=str(video_path), size_bytes=size)

    # ---------------------------------------------------------------- stage 3
    def finish_upload(self, video_id: str, description: str,
                      is_ai_generated: bool = True) -> dict[str, Any]:
        """Stage 3: finalize and publish the Reel."""
        url = f"{GRAPH_BASE_URL}/{self.page_id}/video_reels"
        params = {
            "upload_phase": "FINISH",
            "video_id": video_id,
            "description": description,
            "is_ai_generated": "true" if is_ai_generated else "false",
            "access_token": self.access_token,
        }
        logger.info("Stage 3: finishing upload & publishing video_id=%s", video_id)
        resp = _GraphResponse(requests.post(url, params=params, timeout=120))
        if resp.status_code != 200:
            self._raise_on_error(resp, "upload FINISH")
        result = resp.json
        log_event("upload_finished", video_id=video_id, response_keys=list(result.keys()))
        return result

    # ---------------------------------------------------------------- helpers
    def _raise_on_error(self, resp: _GraphResponse, phase: str) -> None:
        err = resp.error
        code = err.get("code")
        message = err.get("message", resp.text[:300])
        error_subcode = err.get("error_subcode")
        detail = (f"HTTP {resp.status_code} | code={code} | subcode={error_subcode} | "
                  f"message={message}")
        logger.error("Publish %s failed: %s", phase, detail)
        raise PublishError(f"Meta Graph API {phase} failed: {detail}")

    def publish_reel(self, video_path: Path, description: str) -> dict[str, Any]:
        """Run the full two-stage flow. Never blindly retries an uncertain step.

        Returns a record dict with video_id / post_id / status for the log.
        """
        record: dict[str, Any] = {
            "video_path": str(video_path),
            "video_id": None,
            "post_id": None,
            "status": "failed",
            "error": None,
            "published_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }

        try:
            started = self.start_upload(file_size=video_path.stat().st_size,
                                        description=description)
            record["video_id"] = started["video_id"]

            self.upload_binary(started["upload_url"], video_path)

            finished = self.finish_upload(started["video_id"], description)
            record["post_id"] = finished.get("post_id") or finished.get("id")
            record["status"] = "published"
            log_event("reel_published", video_id=record["video_id"],
                      post_id=record["post_id"])
            return record

        except PublishError as exc:
            record["error"] = str(exc)
            log_event("publish_failed", video_id=record["video_id"], error=str(exc))
            raise
        except Exception as exc:  # network, timeouts — uncertain state
            record["error"] = f"{type(exc).__name__}: {exc}"
            log_event("publish_uncertain", video_id=record["video_id"], error=str(exc))
            raise PublishError(
                f"Uncertain publish state (no blind retry): {exc}"
            ) from exc

    def check_token(self) -> dict[str, Any]:
        """Diagnostic: validate the page token without publishing."""
        url = f"{GRAPH_BASE_URL}/me"
        resp = _GraphResponse(requests.get(url, params={"access_token": self.access_token},
                                           timeout=30))
        if resp.status_code != 200:
            self._raise_on_error(resp, "token check")
        return resp.json
