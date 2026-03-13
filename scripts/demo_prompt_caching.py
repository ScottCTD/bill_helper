# CALLING SPEC:
# - Purpose: run the `demo_prompt_caching` repository script.
# - Inputs: callers that import `scripts/demo_prompt_caching.py` and pass module-defined arguments or framework events.
# - Outputs: CLI-side workflow helpers and the `demo_prompt_caching` entrypoint.
# - Side effects: command-line execution and repository automation as implemented below.
"""Demonstrate LiteLLM prompt-caching cost savings on Bedrock Claude Sonnet.

This script sends a series of LLM calls that mirror a multi-turn ReAct agent
loop and prints a detailed cost breakdown showing the savings from prompt
caching vs. no caching.

Prerequisites:
    - AWS credentials configured for Bedrock access
    - ``pip install litellm`` (already in project deps)

Usage:
    uv run python scripts/demo_prompt_caching.py
"""

from __future__ import annotations

import os
import sys
import textwrap
import time
from typing import Any

import litellm

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

MODEL = "bedrock/us.anthropic.claude-sonnet-4-6"

# Claude Sonnet 4 pricing (per million tokens)
PRICE_INPUT_PER_MTOK = 3.00
PRICE_OUTPUT_PER_MTOK = 15.00
PRICE_CACHE_WRITE_PER_MTOK = 3.75
PRICE_CACHE_READ_PER_MTOK = 0.30


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _cost(
    input_tokens: int,
    output_tokens: int,
    cache_write_tokens: int,
    cache_read_tokens: int,
) -> float:
    uncached_input = input_tokens - cache_write_tokens - cache_read_tokens
    return (
        uncached_input * PRICE_INPUT_PER_MTOK / 1_000_000
        + cache_write_tokens * PRICE_CACHE_WRITE_PER_MTOK / 1_000_000
        + cache_read_tokens * PRICE_CACHE_READ_PER_MTOK / 1_000_000
        + output_tokens * PRICE_OUTPUT_PER_MTOK / 1_000_000
    )


def _no_cache_cost(input_tokens: int, output_tokens: int) -> float:
    return (
        input_tokens * PRICE_INPUT_PER_MTOK / 1_000_000
        + output_tokens * PRICE_OUTPUT_PER_MTOK / 1_000_000
    )


def _extract_usage(response: Any) -> dict[str, int]:
    u = response.usage
    prompt_details = getattr(u, "prompt_tokens_details", None) or {}

    cache_read = getattr(u, "cache_read_input_tokens", 0) or 0
    if not cache_read:
        cache_read = (
            getattr(prompt_details, "cached_tokens", 0)
            or (prompt_details.get("cached_tokens", 0) if isinstance(prompt_details, dict) else 0)
        ) or 0

    cache_write = getattr(u, "cache_creation_input_tokens", 0) or 0

    return {
        "input_tokens": getattr(u, "prompt_tokens", 0) or 0,
        "output_tokens": getattr(u, "completion_tokens", 0) or 0,
        "cache_write_tokens": cache_write,
        "cache_read_tokens": cache_read,
    }


def _print_usage(label: str, usage: dict[str, int]) -> None:
    actual = _cost(**usage)
    baseline = _no_cache_cost(usage["input_tokens"], usage["output_tokens"])
    saved = baseline - actual
    pct = (saved / baseline * 100) if baseline else 0

    print(f"\n  {label}")
    print(f"    input_tokens          = {usage['input_tokens']:>7,}")
    print(f"    output_tokens         = {usage['output_tokens']:>7,}")
    print(f"    cache_write_tokens    = {usage['cache_write_tokens']:>7,}")
    print(f"    cache_read_tokens     = {usage['cache_read_tokens']:>7,}")
    print(f"    cost (with caching)   = ${actual:>10.6f}")
    print(f"    cost (without caching)= ${baseline:>10.6f}")
    print(f"    savings               = ${saved:>10.6f}  ({pct:>5.1f}%)")


DEMO_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "list_entities",
            "description": "List all known merchant/payee entities.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_tags",
            "description": "List all known transaction category tags.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "propose_create_entry",
            "description": "Propose creating a new ledger entry.",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "amount": {"type": "number"},
                    "tag": {"type": "string"},
                    "entity": {"type": "string"},
                },
                "required": ["name", "amount"],
            },
        },
    },
]


def _call(
    messages: list[dict[str, Any]],
    *,
    injection_points: list[dict[str, Any]] | None = None,
    max_tokens: int = 64,
) -> tuple[Any, dict[str, int]]:
    kwargs: dict[str, Any] = {
        "model": MODEL,
        "messages": messages,
        "max_tokens": max_tokens,
        # Always pass tools so the prompt prefix stays identical across calls.
        # (Anthropic bakes tool schemas into the prompt; omitting them changes
        # the prefix and breaks cache continuity.)
        "tools": DEMO_TOOLS,
        "tool_choice": "auto",
    }
    if injection_points:
        kwargs["cache_control_injection_points"] = injection_points
    response = litellm.completion(**kwargs)
    return response, _extract_usage(response)


LONG_INSTRUCTIONS = textwrap.dedent("""\
    You are an expert personal-finance billing assistant that helps users
    categorize, reconcile, and track every transaction across credit cards,
    bank accounts, and investment portfolios.

    Core responsibilities:
    1. Parse and normalize transaction descriptions from bank statements,
       credit card bills, receipts, and invoices.
    2. Categorize each transaction into a canonical tag taxonomy including
       but not limited to: groceries, dining, transportation, utilities,
       entertainment, healthcare, insurance, subscriptions, education,
       charitable donations, business expenses, and miscellaneous.
    3. Detect and flag potential duplicate entries across data sources.
    4. Reconcile balances between accounts and highlight discrepancies.
    5. Generate monthly and quarterly spending summaries with trend analysis.
    6. Identify unusual spending patterns and potential fraud indicators.
    7. Track recurring bills and subscriptions, alerting on price changes.
    8. Maintain an entity registry of merchants, payees, and institutions
       with normalized names and categories.
    9. Handle multi-currency transactions with appropriate conversion notes.
    10. Provide tax-relevant categorization for deductible expenses.

    Detailed category definitions:
    - GROCERIES: Purchases from supermarkets, farmers markets, and grocery
      delivery services including Instacart, FreshDirect, Walmart Grocery,
      Whole Foods Market, Costco (food items), No Frills, Metro, Loblaws,
      T&T Supermarket, and Farm Boy. Includes bulk purchases, meal-kit
      delivery services like HelloFresh and Goodfood, and specialty food
      stores. Does not include prepared meals or restaurant takeout.
    - DINING: Restaurant meals, takeout orders, food delivery (DoorDash,
      UberEats, Fantuan, SkipTheDishes), coffee shops (Starbucks, Tim
      Hortons, Second Cup), bars, pubs, breweries, catering services, and
      workplace cafeteria charges. Includes tips and service charges.
    - TRANSPORTATION: Gas stations (Shell, Esso, Petro-Canada, Costco Gas),
      public transit (TTC, Presto, Compass Card), rideshare (Uber, Lyft),
      parking (Green P, Impark), highway tolls (407 ETR), car maintenance
      (oil changes, tire rotations, brake service), vehicle insurance, car
      washes, and auto-parts purchases (Canadian Tire, AutoZone).
    - UTILITIES: Electricity (Toronto Hydro, BC Hydro, Hydro One), natural
      gas (Enbridge), water and sewer, trash collection, internet service
      (Bell, Rogers, Telus), mobile phone plans, cable television, and
      streaming services (Netflix, Disney+, Spotify, Apple Music, YouTube
      Premium, Crave, Amazon Prime Video).
    - ENTERTAINMENT: Movies (Cineplex, TIFF), concerts, sporting events
      (NHL, NBA, MLB tickets), amusement parks (Canada's Wonderland),
      gaming (Steam, PlayStation, Xbox, Nintendo), hobbies, recreational
      activities, museum and gallery admissions, zoo and aquarium visits,
      escape rooms, bowling, and mini-golf.
    - HEALTHCARE: Doctor visits (copays, specialist referrals), prescription
      medications, dental work (cleanings, fillings, orthodontics), vision
      care (eye exams, glasses, contacts), mental health services (therapy,
      counseling), gym memberships (GoodLife, YMCA, CrossFit), health
      supplements, physiotherapy, chiropractic care, massage therapy, and
      medical devices.
    - INSURANCE: Health insurance premiums, auto insurance (monthly or
      annual), home and tenant insurance, life insurance, disability
      insurance, travel insurance, pet insurance, and umbrella policies.
      Includes both premium payments and deductible charges.
    - SUBSCRIPTIONS: Software services (Microsoft 365, Adobe Creative Cloud,
      iCloud, Google One, Dropbox, 1Password, VPN services), news
      publications (Globe and Mail, New York Times, The Athletic), membership
      clubs (Costco, Amazon Prime, CAA), meal kits, and any other recurring
      digital or physical subscription service.
    - EDUCATION: Tuition payments, textbooks and course materials, online
      courses (Coursera, Udemy, LinkedIn Learning), professional
      certifications, conference registration fees, workshop fees, tutoring
      services, student loan payments, and school supply purchases.
    - CHARITABLE: Donations to registered non-profits, religious
      organizations, hospitals and medical research foundations, universities
      and schools, environmental organizations, crowdfunding charitable
      campaigns (GoFundMe for medical/disaster relief), political
      contributions, and United Way payroll deductions.
    - BUSINESS: Office supplies (Staples, Amazon Business), professional
      services (legal, accounting, consulting), advertising and marketing,
      business travel (flights, hotels, meals), client entertainment, SaaS
      tools (Slack, Notion, Figma, GitHub), contractor and freelancer
      payments, coworking space fees (WeWork, Regus), domain registrations
      and hosting, and professional association dues.
    - PERSONAL_CARE: Haircuts and salon services, spa treatments, cosmetics
      and skincare products (Sephora, Shoppers Drug Mart beauty), personal
      grooming tools, and dry cleaning or laundry services.
    - HOME: Furniture (IKEA, Structube, West Elm), home improvement (Home
      Depot, Rona, Home Hardware), appliances, cleaning supplies, gardening
      supplies, pest control, home security systems, and property taxes.
    - CLOTHING: Apparel purchases (H&M, Zara, Uniqlo, Gap, Aritzia), shoes,
      accessories, athletic wear (lululemon, Nike), alterations and tailoring,
      and seasonal wardrobe updates.
    - TRAVEL: Flights (Air Canada, WestJet, Porter), hotels and Airbnb,
      vacation packages, travel insurance, luggage, travel accessories,
      airport parking, currency exchange fees, and international roaming
      charges.
    - PETS: Veterinary visits, pet food and treats, grooming, pet insurance,
      boarding and daycare, pet supplies (PetSmart, Pet Valu), and adoption
      fees.
    - GIFTS: Birthday presents, holiday gifts, wedding gifts, baby shower
      gifts, gift cards, flowers (1-800-Flowers), and charitable donations
      made as gifts.

    Entity normalization rules:
    - Strip location suffixes: "IKEA TORONTO DOWNTOWN" -> "IKEA"
    - Normalize abbreviations: "SBUX" -> "Starbucks", "MCD" -> "McDonald's"
    - Remove transaction codes: "FARM BOY #29 TORONTO ON" -> "Farm Boy"
    - Collapse payment processors: "SQ *LOCALCAFE" -> "Local Cafe"
    - Handle international merchants with local naming conventions.
    - Recognize chain store numbering: "SHOPPERS DRUG MART #1234" -> "Shoppers Drug Mart"
    - Handle payment intermediaries: "PAYPAL *SPOTIFY" -> "Spotify"
    - Normalize online marketplace sellers: "AMZN MKTP US*ABC123" -> "Amazon"
    - Map regional brand names: "LOBLAW GREAT FOOD" -> "Loblaws"
    - Handle franchise variations: "SUBWAY 12345" -> "Subway"

    Transaction parsing rules:
    - Extract date, amount, currency, merchant, and description.
    - Identify debit vs credit transactions.
    - Parse memo fields for additional context.
    - Handle pending vs posted transaction states.
    - Recognize and flag reversed or refunded transactions.
    - Detect foreign currency transactions and note the exchange rate.
    - Identify recurring patterns (same merchant, similar amount, regular interval).
    - Parse multi-line transaction descriptions from PDF statements.
    - Handle split tender transactions (part cash, part card).
    - Recognize loyalty point redemptions and their cash-equivalent value.

    Output format requirements:
    - Always produce structured JSON when proposing changes.
    - Include confidence scores for categorization decisions.
    - Provide reasoning for ambiguous categorizations.
    - Flag items needing human review with clear explanations.
    - Maintain audit trail of all proposed changes.
    - Use ISO 8601 date format (YYYY-MM-DD) for all dates.
    - Include original merchant name alongside the normalized version.
    - Report amounts with exactly two decimal places.

    Additional context and constraints:
    - Respect user privacy: never store or log raw financial data.
    - Operate in the user's configured timezone for all date handling.
    - Support both imperial and metric currency formatting.
    - Handle fiscal year boundaries that differ from calendar years.
    - Apply consistent rounding rules (banker's rounding to 2 decimals).
    - When in doubt about a categorization, prefer the more specific tag.
    - For split transactions, allocate proportionally to relevant categories.
    - Maintain backward compatibility with previously categorized entries.
    - Canadian dollar (CAD) is the default currency unless specified otherwise.
    - HST (13%) is the default sales tax rate for Ontario transactions.
    - Track GST/HST amounts separately when identifiable on receipts.
    - Flag transactions over $500 for additional review.
    - Identify potential subscription price increases by comparing to history.
    - Group related transactions (e.g., flight + hotel + meals for same trip).
    - Detect and separate personal vs business expenses for mixed-use cards.
    - Handle pre-authorized debits and automatic bill payments distinctly.
    - Recognize payroll deposits and classify them as income correctly.
    - Track investment-related transactions separately (TFSA, RRSP, FHSA).
    - Maintain a running tally of total monthly spending per category.

    Ambiguity resolution guidelines:
    - Costco purchases: classify as GROCERIES unless the receipt shows
      electronics, clothing, or other non-food items.
    - Amazon purchases: classify as SHOPPING by default; re-classify if the
      user provides order details showing a specific category.
    - Walmart purchases: use GROCERIES for Walmart Supercentre, SHOPPING for
      general Walmart unless clarified by the user.
    - Gas station convenience store purchases under $20: classify as
      TRANSPORTATION (fuel top-up assumed) unless description says otherwise.
    - Restaurant charges on weekdays between 11:00-14:00 near the user's
      workplace: suggest BUSINESS (potential client lunch) and flag for review.
    - Pharmacy purchases: classify as HEALTHCARE for prescriptions, PERSONAL_CARE
      for cosmetics and toiletries, based on merchant sub-category if available.
""")


# ---------------------------------------------------------------------------
# Example 1: System-prompt caching across repeated calls
# ---------------------------------------------------------------------------


def example_system_prompt_caching() -> None:
    print("=" * 72)
    print("EXAMPLE 1 — System-Prompt Caching (Basics)")
    print("=" * 72)
    print(textwrap.dedent("""\
        How it works:
          Anthropic caches content up to each cache-control breakpoint.
          On subsequent requests the provider checks whether the prefix
          up to any breakpoint matches a previously cached prefix.
          A match is a "cache read" (90% cheaper than normal input).
          A miss writes the prefix to cache ("cache write", 25% surcharge).

        This example sends two identical requests with a long system prompt.
        The first call writes the cache; the second reads it.
    """))

    system_msg: dict[str, Any] = {"role": "system", "content": LONG_INSTRUCTIONS}
    injection = [{"location": "message", "role": "system"}]

    # Call 1 — cache write
    print("  Call 1 (cache WRITE — first time seeing this prefix) ...")
    _, u1 = _call(
        [system_msg, {"role": "user", "content": "What categories do you support?"}],
        injection_points=injection,
    )
    _print_usage("Call 1 (cache write)", u1)

    # Small pause so the cache is available
    time.sleep(2)

    # Call 2 — cache read (same system prefix)
    print("\n  Call 2 (cache READ — identical prefix) ...")
    _, u2 = _call(
        [system_msg, {"role": "user", "content": "How do you handle dining transactions?"}],
        injection_points=injection,
    )
    _print_usage("Call 2 (cache read)", u2)

    print()


# ---------------------------------------------------------------------------
# Example 2: Multi-turn ReAct loop with incremental caching
# ---------------------------------------------------------------------------


def example_react_loop_caching() -> None:
    print("=" * 72)
    print("EXAMPLE 2 — Multi-Turn ReAct Loop (Incremental Caching)")
    print("=" * 72)
    print(textwrap.dedent("""\
        In a ReAct agent loop each LLM call appends an assistant response
        and tool results, then calls the model again.  The entire prefix
        up to the previous call's last message is unchanged.

        Optimal strategy — three breakpoints per call:
          1. System message          (long-lived prefix, always cached)
          2. Boundary message        (= previous call's last msg → cache READ)
          3. Last message            (current last msg → cache WRITE for next)

        This example simulates a 4-step loop:
          Initial call  →  tool iter 1  →  tool iter 2  →  new user turn
    """))

    system_msg: dict[str, Any] = {"role": "system", "content": LONG_INSTRUCTIONS}
    messages: list[dict[str, Any]] = [
        system_msg,
        {"role": "user", "content": "I uploaded my January credit card statement. Can you categorize the transactions?"},
    ]

    cumulative_savings = 0.0
    cumulative_actual = 0.0
    cumulative_baseline = 0.0

    def _step(label: str, injection: list[dict[str, Any]]) -> None:
        nonlocal cumulative_savings, cumulative_actual, cumulative_baseline
        print(f"\n  {label} ({len(messages)} messages) ...")
        _, usage = _call(messages, injection_points=injection)
        _print_usage(label, usage)
        actual = _cost(**usage)
        baseline = _no_cache_cost(usage["input_tokens"], usage["output_tokens"])
        cumulative_actual += actual
        cumulative_baseline += baseline
        cumulative_savings += baseline - actual

    # --- Step 1: Initial call [system, user] ---
    _step(
        "Step 1 — Initial call",
        [
            {"location": "message", "role": "system"},
            {"location": "message", "index": -1},
        ],
    )
    time.sleep(2)

    # Simulate assistant response with tool call + tool result
    messages.append({
        "role": "assistant",
        "content": "I'll start by checking your existing categories and entities.",
        "tool_calls": [{"id": "tc1", "type": "function", "function": {"name": "list_entities", "arguments": "{}"}}],
    })
    messages.append({
        "role": "tool", "tool_call_id": "tc1", "name": "list_entities",
        "content": '{"entities": ["Starbucks", "Amazon", "Netflix", "Uber", "Farm Boy", "Hydro One"]}',
    })

    # --- Step 2: Tool loop iter 1 [system, user, assistant(tc), tool] ---
    # Boundary = user (index 1, i.e. -3). Last = tool (index -1).
    _step(
        "Step 2 — Tool loop iter 1",
        [
            {"location": "message", "role": "system"},
            {"location": "message", "index": -3},
            {"location": "message", "index": -1},
        ],
    )
    time.sleep(2)

    messages.append({
        "role": "assistant",
        "content": "Found existing entities. Now let me check tags.",
        "tool_calls": [{"id": "tc2", "type": "function", "function": {"name": "list_tags", "arguments": "{}"}}],
    })
    messages.append({
        "role": "tool", "tool_call_id": "tc2", "name": "list_tags",
        "content": '{"tags": ["groceries", "dining", "transportation", "utilities", "subscriptions"]}',
    })

    # --- Step 3: Tool loop iter 2 [system, user, a(tc), t, a(tc), t] ---
    # Boundary = first tool result (index 3, i.e. -3). Last = -1.
    _step(
        "Step 3 — Tool loop iter 2",
        [
            {"location": "message", "role": "system"},
            {"location": "message", "index": -3},
            {"location": "message", "index": -1},
        ],
    )
    time.sleep(2)

    # Simulate final assistant response (no tool calls) completing turn 1,
    # then a new user message starting turn 2.
    messages.append({"role": "assistant", "content": "I've categorized all 15 transactions from your January statement."})
    # For the new turn, only keep: system + user1 + final_assistant + user2
    # (matching how build_llm_messages works — intermediate tool turns are not persisted)
    messages_turn2: list[dict[str, Any]] = [
        system_msg,
        {"role": "user", "content": "I uploaded my January credit card statement. Can you categorize the transactions?"},
        {"role": "assistant", "content": "I've categorized all 15 transactions from your January statement."},
        {"role": "user", "content": "Great, now can you also process my February bank statement?"},
    ]
    messages.clear()
    messages.extend(messages_turn2)

    # --- Step 4: New user turn [system, user1, assistant1, user2] ---
    # Second-to-last user = user1 (index 1, i.e. -3). Last = user2 (-1).
    _step(
        "Step 4 — New user turn",
        [
            {"location": "message", "role": "system"},
            {"location": "message", "index": -3},
            {"location": "message", "index": -1},
        ],
    )

    print(f"\n  {'─' * 56}")
    print(f"  Cumulative cost (with caching)    = ${cumulative_actual:.6f}")
    print(f"  Cumulative cost (without caching) = ${cumulative_baseline:.6f}")
    print(f"  Total savings                     = ${cumulative_savings:.6f}  "
          f"({cumulative_savings / cumulative_baseline * 100:.1f}%)")
    print()


# ---------------------------------------------------------------------------
# Example 3: No caching vs. caching side-by-side comparison
# ---------------------------------------------------------------------------


def example_comparison() -> None:
    print("=" * 72)
    print("EXAMPLE 3 — Side-by-Side: No Caching vs. Caching")
    print("=" * 72)
    print(textwrap.dedent("""\
        Sends the SAME sequence of three calls twice:
          A) Without cache_control_injection_points (baseline)
          B) With cache_control_injection_points (optimized)

        This isolates the cost impact of prompt caching.
    """))

    system_msg: dict[str, Any] = {"role": "system", "content": LONG_INSTRUCTIONS}
    queries = [
        "Categorize: FARM BOY #29 TORONTO ON $47.23",
        "Categorize: UBER *TRIP TORONTO $18.50",
        "Categorize: NETFLIX.COM $22.99",
    ]

    for variant, injection in [("A) NO caching", None), ("B) WITH caching", [{"location": "message", "role": "system"}, {"location": "message", "index": -1}])]:
        print(f"\n  ── {variant} ──")
        total_actual = 0.0
        total_baseline = 0.0
        for i, query in enumerate(queries, 1):
            _, usage = _call(
                [system_msg, {"role": "user", "content": query}],
                injection_points=injection,
            )
            actual = _cost(**usage)
            baseline = _no_cache_cost(usage["input_tokens"], usage["output_tokens"])
            total_actual += actual
            total_baseline += baseline
            read = usage["cache_read_tokens"]
            write = usage["cache_write_tokens"]
            print(f"    Call {i}: input={usage['input_tokens']:>5,}  "
                  f"cache_read={read:>5,}  cache_write={write:>5,}  "
                  f"cost=${actual:.6f}")
            if i < len(queries):
                time.sleep(2)
        saved = total_baseline - total_actual
        print(f"    Total cost: ${total_actual:.6f}  "
              f"(baseline: ${total_baseline:.6f}, saved: ${saved:.6f})")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> int:
    print(textwrap.dedent("""\

    ╔══════════════════════════════════════════════════════════════════════╗
    ║          Prompt Caching Demo  —  LiteLLM + Bedrock Claude          ║
    ╠══════════════════════════════════════════════════════════════════════╣
    ║                                                                    ║
    ║  Anthropic prompt caching lets you cache long prompt prefixes so   ║
    ║  subsequent requests reuse them at 90% lower cost.                 ║
    ║                                                                    ║
    ║  Pricing (Claude Sonnet 4, per million tokens):                    ║
    ║    Regular input       $3.00                                       ║
    ║    Cache WRITE         $3.75  (25% surcharge on first use)         ║
    ║    Cache READ          $0.30  (90% discount on reuse!)             ║
    ║    Output              $15.00                                      ║
    ║                                                                    ║
    ║  How it works:                                                     ║
    ║    1. You mark cache breakpoints in your messages.                 ║
    ║    2. Anthropic caches everything from the start up to each        ║
    ║       breakpoint.                                                  ║
    ║    3. On later calls, if the prefix up to a breakpoint matches     ║
    ║       a cached prefix exactly, those tokens are served from        ║
    ║       cache (cheap).                                               ║
    ║    4. LiteLLM's cache_control_injection_points auto-injects the    ║
    ║       breakpoints so you don't modify message content.             ║
    ║                                                                    ║
    ║  Minimum cacheable prefix: 2048 tokens for Sonnet models.          ║
    ║  Cache TTL: 5 minutes (refreshed on each read).                   ║
    ║                                                                    ║
    ╚══════════════════════════════════════════════════════════════════════╝
    """))

    if not litellm.utils.supports_prompt_caching(MODEL):
        print(f"WARNING: litellm reports {MODEL} does not support prompt caching.")
        print("Results may not show cache hits. Continuing anyway.\n")

    try:
        example_system_prompt_caching()
        example_react_loop_caching()
        example_comparison()
    except Exception as exc:
        print(f"\nERROR: {exc}", file=sys.stderr)
        print("Make sure AWS credentials are configured for Bedrock access.", file=sys.stderr)
        return 1

    print("\n" + "=" * 72)
    print("KEY TAKEAWAYS")
    print("=" * 72)
    print(textwrap.dedent("""\
        1. Cache breakpoints create "checkpoints" in your message prefix.
           Anthropic caches from the start up to each breakpoint.

        2. In a ReAct tool loop, place breakpoints at:
             • System message      — long, stable, always cached
             • Boundary message    — last msg from the previous LLM call
                                     (READs the previous call's cache)
             • Last message        — current end of context
                                     (WRITEs cache for the next call)

        3. For multi-turn conversations, place a breakpoint at the
           second-to-last user message to read the previous turn's cache.

        4. The first call pays a 25% surcharge (cache write).
           Every subsequent call with the same prefix saves ~90%.

        5. For a 10-step tool loop with a 2000-token system prompt,
           caching can reduce total input cost by 60-80%.
    """))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
