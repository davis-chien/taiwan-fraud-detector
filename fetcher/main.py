from __future__ import annotations

from typing import Any, Dict

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from pipeline.scraper import fetch_page
from pipeline.unshortener import unshorten_url
from pipeline.enricher import get_domain_info
from pipeline.validator import validate_url

app = FastAPI(title="Taiwan Fraud Detector — Fetcher Worker")


class URLRequest(BaseModel):
    url: str


class HostRequest(BaseModel):
    hostname: str


@app.get("/health")
def health() -> Dict[str, str]:
    return {"status": "ok"}


@app.post("/unshorten")
def unshorten(req: URLRequest) -> Dict[str, Any]:
    resolved_url, changed, status, chain = unshorten_url(req.url)
    return {
        "resolved_url": resolved_url,
        "changed": changed,
        "status": status,
        "chain": chain,
    }


@app.post("/fetch")
def fetch(req: URLRequest) -> Dict[str, Any]:
    valid, reason = validate_url(req.url)
    if not valid:
        raise HTTPException(status_code=400, detail=reason)
    return fetch_page(req.url)


@app.post("/enrich")
def enrich(req: HostRequest) -> Dict[str, Any]:
    return get_domain_info(req.hostname)
