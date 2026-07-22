#!/usr/bin/env python3
"""Send a single chat-completion request directly to the configured AIP endpoint."""

from __future__ import annotations

import argparse
import json
import os
import ssl
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


AGENT_DIR = Path(__file__).resolve().parents[1]
ENV_FILE = AGENT_DIR / ".env"
DEFAULT_BASE_URL = "https://models.k8s.aip.mitre.org/v1"
DEFAULT_MODEL = "gpt-oss-120b"
DEFAULT_SYSTEM_PROMPT = "You are a helpful assistant."


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("prompt", nargs="*", help="Message sent to the model.")
    parser.add_argument("--system", default=DEFAULT_SYSTEM_PROMPT, help="System prompt.")
    parser.add_argument("--model", help="Override MODEL_ID from .env.")
    parser.add_argument("--timeout", type=float, default=60, help="Request timeout in seconds.")
    return parser.parse_args()


def load_env_file(path: Path) -> None:
    """Load simple KEY=VALUE pairs without overriding values already in the shell."""
    if not path.is_file():
        raise FileNotFoundError(f"Agent environment file does not exist: {path}")
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip().removeprefix("export ").strip()
        value = value.strip().strip('"').strip("'")
        if key:
            os.environ.setdefault(key, value)


def configure_tls() -> ssl.SSLContext:
    """Return the TLS context configured in the agent environment."""
    ca_bundle = os.getenv("LOCAL_CA_BUNDLE") or os.getenv("AIP_CA_BUNDLE")
    if ca_bundle:
        certificate = Path(ca_bundle).expanduser()
        if not certificate.is_file():
            raise EnvironmentError(f"TLS CA bundle does not exist: {certificate}")
        return ssl.create_default_context(cafile=str(certificate))
    if os.getenv("LOCAL_VERIFY_SSL", "true").lower() in {"0", "false", "no"}:
        return ssl._create_unverified_context()
    return ssl.create_default_context()


def require_api_key() -> str:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise EnvironmentError(f"OPENAI_API_KEY is not set in {ENV_FILE}")
    if not api_key.startswith("sk-"):
        raise EnvironmentError("OPENAI_API_KEY must start with 'sk-' for the AIP endpoint")
    return api_key


def main() -> None:
    args = parse_args()
    load_env_file(ENV_FILE)

    prompt = " ".join(args.prompt).strip() or "What is deep learning?"
    api_key = require_api_key()
    base_url = os.getenv("BASE_URL", DEFAULT_BASE_URL)
    model = args.model or os.getenv("MODEL_ID", DEFAULT_MODEL)
    verify = configure_tls()

    request = Request(
        f"{base_url.rstrip('/')}/chat/completions",
        data=json.dumps({
            "model": model,
            "messages": [
                {"role": "system", "content": args.system},
                {"role": "user", "content": prompt},
            ],
        }).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urlopen(request, timeout=args.timeout, context=verify) as response:
            payload = json.load(response)
    except HTTPError as error:
        if error.code == 401:
            raise EnvironmentError("The AIP endpoint rejected OPENAI_API_KEY") from error
        raise RuntimeError(f"AIP request failed with HTTP {error.code}") from error
    except URLError as error:
        raise ConnectionError(f"Unable to reach the AIP endpoint: {error.reason}") from error

    choices = payload.get("choices", [])
    content = choices[0].get("message", {}).get("content") if choices else None
    print(content or "(The model returned no text.)")


if __name__ == "__main__":
    main()
