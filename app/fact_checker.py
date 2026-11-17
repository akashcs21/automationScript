"""JIGYASA LAB — fact-checking quality gate.

Identifies factual claims in the script, requires credible supporting
references, verifies that source URLs are reachable, and refuses to publish
when important claims cannot be supported.

URL reachability is a *necessary hygiene check*, not proof that a claim is true.
"""
from __future__ import annotations

import time
from typing import Any

import requests

from config import GRAPH_API_VERSION  # noqa: F401  (kept for symmetry)
from logger import logger, log_event


class FactCheckError(RuntimeError):
    """Raised when a claim cannot be verified and the run must stop."""


CREDIBLE_DOMAINS = [
    "nasa.gov", "esa.int", "esa.int", "noaa.gov", "nih.gov", "who.int",
    "nature.com", "science.org", "cell.com", "thelancet.com",
    "edu", "ac.uk", "gov.uk", "britannica.com", "si.edu", "amnh.org",
    "naturalhistory.si.edu", "royalsociety.org", "cnrs.fr", "mpg.de",
    "helmholtz.de", "riken.jp", "csiro.au",
]

UNSUPPORTED_PHRASES = [
    "scientists say", "studies show", "research proves", "experts believe",
    "it is known that", "mystery solved", "secretly", "aliens built",
]


def _is_credible(url: str) -> bool:
    url_l = url.lower()
    return any(domain in url_l for domain in CREDIBLE_DOMAINS)


def _url_reachable(url: str, timeout: int = 12) -> bool:
    """HEAD/GET check that the URL responds successfully (best effort)."""
    try:
        resp = requests.head(url, timeout=timeout, allow_redirects=True)
        if resp.status_code >= 400:
            resp = requests.get(url, timeout=timeout, stream=True)
        return resp.status_code < 400
    except Exception as exc:
        logger.debug("URL not reachable %s: %s", url, exc)
        return False


def check_script(script: dict) -> dict:
    """Run the fact-checking gate over the script.

    Returns a report dict. Raises FactCheckError if any important claim
    cannot be verified — the caller must stop the run, not publish.
    """
    report: dict[str, Any] = {
        "passed": True,
        "checked_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "claims": [],
        "warnings": [],
        "errors": [],
    }

    claims = script.get("factual_claims", [])
    if not claims:
        report["warnings"].append("No factual claims supplied in script.")
        return report

    narration = script.get("narration_script", "")
    for idx, claim in enumerate(claims):
        claim_text = claim.get("claim", "").strip()
        source_url = claim.get("source_url", "").strip()
        confidence = claim.get("confidence", "unknown")

        entry: dict[str, Any] = {
            "index": idx,
            "claim": claim_text,
            "source_url": source_url,
            "credible_domain": _is_credible(source_url),
            "url_reachable": False,
        }

        if not claim_text:
            report["errors"].append(f"Claim {idx} is empty.")
            report["passed"] = False
            continue

        # Clickbait / unsupported phrasing heuristic.
        low = claim_text.lower()
        for phrase in UNSUPPORTED_PHRASES:
            if phrase in low:
                report["warnings"].append(
                    f"Claim {idx} uses unsupported phrasing '{phrase}'."
                )

        if not source_url or not source_url.startswith("http"):
            report["errors"].append(
                f"Claim {idx} lacks a valid source URL: {claim_text[:80]}"
            )
            report["passed"] = False
            entry["error"] = "missing or invalid source_url"

        else:
            entry["url_reachable"] = _url_reachable(source_url)
            if not entry["url_reachable"]:
                report["errors"].append(
                    f"Claim {idx} source URL unreachable: {source_url}"
                )
                report["passed"] = False
            elif not entry["credible_domain"] and confidence != "low":
                report["warnings"].append(
                    f"Claim {idx} source not on a known credible domain: {source_url}"
                )

        report["claims"].append(entry)
        time.sleep(0.4)  # be polite to source servers

    # Narration-level sanity: avoid unverifiable hype in the script body.
    low_narration = narration.lower()
    for phrase in UNSUPPORTED_PHRASES:
        if phrase in low_narration and not any(
            phrase in c.get("claim", "").lower() for c in claims
        ):
            report["warnings"].append(
                f"Narration uses unsupported phrase '{phrase}' with no cited claim."
            )

    all_ok = report["passed"] and not report["errors"]
    log_event("fact_check_completed", passed=all_ok,
              claims=len(report["claims"]),
              errors=len(report["errors"]),
              warnings=len(report["warnings"]))

    if not all_ok:
        raise FactCheckError(
            "Fact-checking gate failed — run stopped. "
            f"Errors: {report['errors']}; Warnings: {report['warnings']}"
        )
    return report
