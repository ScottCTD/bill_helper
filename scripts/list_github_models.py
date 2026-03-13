#!/usr/bin/env python3
# CALLING SPEC:
# - Purpose: run the `list_github_models` repository script.
# - Inputs: callers that import `scripts/list_github_models.py` and pass module-defined arguments or framework events.
# - Outputs: CLI-side workflow helpers and the `list_github_models` entrypoint.
# - Side effects: command-line execution and repository automation as implemented below.
"""
Check GitHub Models / GitHub Copilot model names for LiteLLM.

Usage:
  python check_github_litellm_models.py --mode github
  python check_github_litellm_models.py --mode copilot
  python check_github_litellm_models.py --mode both

Requirements:
  pip install requests litellm

Auth:
  - For --mode github:
      export GITHUB_API_KEY=ghp_...
  - For --mode copilot:
      no env var required by default; LiteLLM will trigger GitHub Copilot OAuth device flow on first use
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from typing import Iterable

import requests


def slugify_copilot_name(name: str) -> str:
    """
    Convert GitHub Copilot display name into a likely LiteLLM github_copilot slug.

    Examples:
      GPT-5.1-Codex        -> gpt-5.1-codex
      GPT-5 mini           -> gpt-5-mini
      Claude Opus 4.6      -> claude-opus-4.6
      Claude Opus 4.6 (fast mode) (preview) -> claude-opus-4.6-fast
      Gemini 3.1 Pro       -> gemini-3.1-pro
      Grok Code Fast 1     -> grok-code-fast-1
      Raptor mini          -> raptor-mini
      Goldeneye            -> goldeneye
    """
    s = name.strip().lower()

    # Handle the special Copilot label explicitly
    s = s.replace("(fast mode)", "fast")
    s = s.replace("(preview)", "")

    # Collapse spaces around punctuation
    s = re.sub(r"\s+", " ", s).strip()

    # Replace spaces with dashes
    s = s.replace(" ", "-")

    # Clean up accidental double dashes
    s = re.sub(r"-{2,}", "-", s).strip("-")
    return s


def get_github_models_catalog() -> list[dict]:
    api_key = os.getenv("GITHUB_API_KEY")
    if not api_key:
        raise RuntimeError("GITHUB_API_KEY is required for --mode github")

    url = "https://models.github.ai/catalog/models"
    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {api_key}",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    r = requests.get(url, headers=headers, timeout=30)
    r.raise_for_status()
    data = r.json()
    if not isinstance(data, list):
        raise RuntimeError(f"Unexpected catalog response: {type(data)!r}")
    return data


def github_litellm_name_from_catalog_id(model_id: str) -> str:
    """
    LiteLLM github provider docs say to use github/<any-model-on-github>
    and ignore the company prefix.

    Example:
      meta/llama-3.2-11b-vision-instruct -> github/llama-3.2-11b-vision-instruct
    """
    if "/" in model_id:
        return "github/" + model_id.split("/", 1)[1]
    return "github/" + model_id


def print_github_models() -> None:
    models = get_github_models_catalog()

    rows = []
    for m in models:
        model_id = m.get("id", "")
        name = m.get("name", "")
        publisher = m.get("publisher", "")
        litellm_name = github_litellm_name_from_catalog_id(model_id)
        rows.append(
            {
                "publisher": publisher,
                "display_name": name,
                "catalog_id": model_id,
                "litellm_model": litellm_name,
            }
        )

    rows.sort(key=lambda x: (x["publisher"].lower(), x["display_name"].lower()))

    print("# GitHub Models -> LiteLLM names")
    print("# Format: publisher | display_name | catalog_id | litellm_model")
    for row in rows:
        print(
            f'{row["publisher"]} | {row["display_name"]} | '
            f'{row["catalog_id"]} | {row["litellm_model"]}'
        )


def get_current_copilot_display_names() -> list[str]:
    """
    Based on the current GitHub Copilot supported models page.
    Keep this list easy to update when GitHub changes it.
    """
    return [
        "GPT-4.1",
        "GPT-5 mini",
        "GPT-5.1",
        "GPT-5.1-Codex",
        "GPT-5.1-Codex-Mini",
        "GPT-5.1-Codex-Max",
        "GPT-5.2",
        "GPT-5.2-Codex",
        "GPT-5.3-Codex",
        "GPT-5.4",
        "Claude Haiku 4.5",
        "Claude Opus 4.5",
        "Claude Opus 4.6",
        "Claude Opus 4.6 (fast mode) (preview)",
        "Claude Sonnet 4",
        "Claude Sonnet 4.5",
        "Claude Sonnet 4.6",
        "Gemini 2.5 Pro",
        "Gemini 3 Flash",
        "Gemini 3 Pro",
        "Gemini 3.1 Pro",
        "Grok Code Fast 1",
        "Raptor mini",
        "Goldeneye",
    ]


def print_copilot_candidates() -> list[str]:
    display_names = get_current_copilot_display_names()
    candidates = []

    print("# GitHub Copilot display name -> likely LiteLLM github_copilot model")
    for name in display_names:
        slug = slugify_copilot_name(name)
        litellm_name = f"github_copilot/{slug}"
        candidates.append(litellm_name)
        print(f"{name} -> {litellm_name}")

    print("\n# Extra LiteLLM-documented / observed examples")
    extras = [
        "github_copilot/gpt-4",
        "github_copilot/gpt-5.1-codex",
        "github_copilot/gpt-5.3-codex",
        "github_copilot/claude-opus-4.6-fast",
        "github_copilot/text-embedding-3-small",
        "github_copilot/text-embedding-ada-002",
    ]
    for x in extras:
        if x not in candidates:
            candidates.append(x)
        print(x)

    return candidates


def probe_copilot_models(models: Iterable[str]) -> None:
    try:
        import litellm
    except ImportError as e:
        raise RuntimeError("litellm is required for probing: pip install litellm") from e

    print("\n# Probing github_copilot models with tiny requests")
    print("# First run may open GitHub Copilot OAuth device flow via LiteLLM.\n")

    for model in models:
        try:
            if "codex" in model:
                # LiteLLM docs say Codex models are responses-only on github_copilot
                resp = litellm.responses(
                    model=model,
                    input="Reply with OK only.",
                    max_output_tokens=8,
                    timeout=60,
                )
                print(f"OK   {model}   [responses]")
            elif "embedding" in model:
                _ = litellm.embedding(
                    model=model,
                    input=["hello"],
                    timeout=60,
                )
                print(f"OK   {model}   [embedding]")
            else:
                _ = litellm.completion(
                    model=model,
                    messages=[{"role": "user", "content": "Reply with OK only."}],
                    max_tokens=8,
                    timeout=60,
                )
                print(f"OK   {model}   [chat]")
        except Exception as e:
            print(f"FAIL {model}   {type(e).__name__}: {e}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--mode",
        choices=["github", "copilot", "both"],
        required=True,
        help="Which model family to inspect.",
    )
    parser.add_argument(
        "--probe-copilot",
        action="store_true",
        help="Actually send tiny test calls to Copilot models through LiteLLM.",
    )
    args = parser.parse_args()

    if args.mode in ("github", "both"):
        print_github_models()
        print()

    if args.mode in ("copilot", "both"):
        candidates = print_copilot_candidates()
        if args.probe_copilot:
            probe_copilot_models(candidates)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())