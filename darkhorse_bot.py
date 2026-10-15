#!/usr/bin/env python3
"""
Dark Horse Genesis Automation Bot (https://genesis.dhorse.fun/mine)
Features:
- Multi-account management via /opt/dark-horse/accounts.json
- Per-account Tor circuit stream isolation (rotating exit IPs)
- Automated daily check-in (POST /api/checkin)
- Automated mining reward claim (POST /api/mining/claim) with threshold validation
- Live status reporting & CLI account manager
"""

import os
import sys
import json
import time
import argparse
from datetime import datetime, timezone
from pathlib import Path
import httpx

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.environ.get("DHORSE_DATA_DIR", BASE_DIR)
ACCOUNTS_FILE = os.path.join(DATA_DIR, "accounts.json")

TOR_HOST = os.environ.get("TOR_PROXY_HOST", "127.0.0.1")
TOR_PORT = int(os.environ.get("TOR_PROXY_PORT", "9050"))
MIN_CLAIM_THRESHOLD = float(os.environ.get("MIN_CLAIM_THRESHOLD", "1.0"))


def load_accounts() -> list:
    if not os.path.exists(ACCOUNTS_FILE):
        return []
    with open(ACCOUNTS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_accounts(accounts: list) -> None:
    with open(ACCOUNTS_FILE, "w", encoding="utf-8") as f:
        json.dump(accounts, f, indent=2)


def get_client(acc: dict) -> httpx.Client:
    tor_user = acc.get("torUserId") or f"tor_dhorse_{acc.get('handle', 'default')}"
    acc["torUserId"] = tor_user
    proxy = f"socks5://{tor_user}:torpass123@{TOR_HOST}:{TOR_PORT}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Origin": "https://genesis.dhorse.fun",
        "Referer": "https://genesis.dhorse.fun/mine",
    }
    client = httpx.Client(proxy=proxy, headers=headers, timeout=25.0)
    cookie_val = acc.get("sessionCookie")
    if cookie_val:
        client.cookies.set("genesis_session", cookie_val, domain="genesis.dhorse.fun")
    return client


def process_account(acc: dict, quiet: bool = False) -> dict:
    handle = acc.get("handle", "unknown")
    log = (lambda msg: sys.stderr.write(msg + "\n")) if quiet else print

    log(f"\n==================================================")
    log(f">>> Processing Account: @{handle}")
    log(f"==================================================")

    claimed_amount = 0.0
    checkin_now = False

    client = get_client(acc)
    try:
        # 1. Tor Exit IP check
        try:
            ip = client.get("https://api.ipify.org?format=json").json().get("ip")
            acc["torExitIp"] = ip
            log(f"  Tor Exit IP: {ip}")
        except Exception as e:
            log(f"  Tor IP check error: {e}")

        # 2. Verify Session & Profile
        r_me = client.get("https://genesis.dhorse.fun/api/me")
        if r_me.status_code == 401 or "NOT_SIGNED_IN" in r_me.text:
            log(f"  FAILED: Session expired for @{handle}. Please update sessionCookie.")
            acc["sessionStatus"] = "expired"
            return {
                "handle": handle,
                "status": "expired",
                "tier": acc.get("tier", "user"),
                "points": acc.get("points", 0),
                "claimed": 0.0,
                "claimable": acc.get("claimable", 0.0),
                "streak": acc.get("checkinDays", 0),
                "checkin_now": False,
            }

        if r_me.status_code != 200:
            log(f"  Warning: GET /api/me returned {r_me.status_code}: {r_me.text[:80]}")
            return {
                "handle": handle,
                "status": "error",
                "tier": acc.get("tier", "user"),
                "points": acc.get("points", 0),
                "claimed": 0.0,
                "claimable": acc.get("claimable", 0.0),
                "streak": acc.get("checkinDays", 0),
                "checkin_now": False,
            }

        me = r_me.json()
        acc["sessionStatus"] = "active"
        acc["handle"] = me.get("handle", handle)
        acc["points"] = me.get("points", 0)
        acc["tier"] = me.get("tier", "user")
        acc["walletAddress"] = me.get("walletAddress", "")
        acc["checkinToday"] = me.get("checkinToday", False)
        acc["checkinDays"] = me.get("checkinDays", 0)

        log(f"  Profile: Tier={acc['tier']} | Points={acc['points']} | Streak={acc['checkinDays']} days")

        # 3. Daily Check-in
        if not acc["checkinToday"]:
            log("  Performing Daily Check-in...")
            r_checkin = client.post("https://genesis.dhorse.fun/api/checkin", json={})
            if r_checkin.status_code == 200:
                c_data = r_checkin.json()
                acc["checkinToday"] = True
                acc["checkinDays"] = c_data.get("checkinDays", acc["checkinDays"] + 1)
                checkin_now = True
                log(f"  Check-in SUCCESS: Day {acc['checkinDays']} claimed!")
            else:
                log(f"  Check-in error: {r_checkin.status_code} {r_checkin.text}")
        else:
            log(f"  Check-in already completed today (Day {acc['checkinDays']}).")

        # 4. Mining Status & Claim
        r_mstatus = client.get("https://genesis.dhorse.fun/api/mining/status")
        if r_mstatus.status_code == 200:
            m_data = r_mstatus.json()
            claimable = float(m_data.get("claimable", 0.0))
            claimed_total = float(m_data.get("claimed", 0.0))
            daily_rate = float(m_data.get("dailyRate", 0.0))
            eff_power = m_data.get("effectivePower", 0)

            acc["claimable"] = round(claimable, 4)
            acc["claimed"] = round(claimed_total, 4)
            acc["dailyRate"] = daily_rate
            acc["effectivePower"] = eff_power

            log(
                f"  Mining: Power={eff_power} | DailyRate={daily_rate}/day | "
                f"Claimable={claimable:.4f} | Total Claimed={claimed_total:.4f}"
            )

            # Check threshold for claim
            if claimable >= MIN_CLAIM_THRESHOLD:
                log(f"  Claimable reward ({claimable:.4f}) reached threshold ({MIN_CLAIM_THRESHOLD}). Claiming...")
                r_claim = client.post("https://genesis.dhorse.fun/api/mining/claim", json={})
                if r_claim.status_code == 200:
                    claim_res = r_claim.json()
                    claimed_val = claim_res.get("claimed", claimable)
                    try:
                        claimed_amount = float(claimed_val)
                    except Exception:
                        claimed_amount = float(claimable)
                    log(f"  Mining Claim SUCCESS: +{claimed_amount} points!")
                    # Refresh profile
                    r_me_updated = client.get("https://genesis.dhorse.fun/api/me")
                    if r_me_updated.status_code == 200:
                        acc["points"] = r_me_updated.json().get("points", acc["points"])
                elif r_claim.status_code == 409:
                    log(f"  Server notice: Claim queued/waiting for next epoch threshold.")
                else:
                    log(f"  Mining claim error: {r_claim.status_code} {r_claim.text}")
            else:
                log(
                    f"  Mining claimable is {claimable:.4f} (under {MIN_CLAIM_THRESHOLD} threshold). "
                    f"Will claim automatically when ready."
                )

        acc["lastRunAt"] = datetime.now(timezone.utc).isoformat()
        log(f"  Account @{acc['handle']} update completed.")

    except Exception as e:
        log(f"  Error processing @{handle}: {e}")
    finally:
        client.close()

    return {
        "handle": acc.get("handle", handle),
        "status": acc.get("sessionStatus", "active"),
        "tier": acc.get("tier", "user"),
        "points": acc.get("points", 0),
        "claimed": claimed_amount,
        "claimable": acc.get("claimable", 0.0),
        "streak": acc.get("checkinDays", 0),
        "checkin_now": checkin_now,
    }


def format_report(results: list) -> str:
    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    lines = [
        "## Dark Horse Genesis Fleet",
        f"*{now_str}*",
        "",
        "| Account | Points | Claimed | Claimable | Streak | Status |",
        "|:--|--:|--:|--:|:--|:--|",
    ]
    total_points = 0
    total_claimed = 0.0
    for r in results:
        pts = r.get("points", 0)
        total_points += pts
        cl = r.get("claimed", 0.0)
        total_claimed += cl
        cl_str = f"+{cl:.0f}" if cl > 0 else "-"
        streak_str = f"Day {r.get('streak', 0)}" + (" ✓" if r.get("checkin_now") else "")
        status_str = "OK" if r.get("status") == "active" else "EXPIRED"
        lines.append(
            f"| @{r['handle']} | {pts:,} | {cl_str} | {r.get('claimable', 0.0):.2f} | {streak_str} | {status_str} |"
        )
    lines.append("")
    cl_total_str = f"+{total_claimed:.0f}" if total_claimed > 0 else "-"
    lines.append(
        f"**Total Accounts:** {len(results)} | **Total Points:** {total_points:,} | **Round Claimed:** {cl_total_str}"
    )
    return "\n".join(lines)


def run_all(report_mode: bool = False) -> None:
    accounts = load_accounts()
    if not accounts:
        if report_mode:
            print("## Dark Horse Genesis Fleet\n\nNo accounts found.")
        else:
            print(f"No accounts found in {ACCOUNTS_FILE}.")
        return

    results = []
    if not report_mode:
        print(f"Starting Dark Horse Genesis cycle for {len(accounts)} account(s)...")

    for acc in accounts:
        res = process_account(acc, quiet=report_mode)
        results.append(res)
        time.sleep(2.0)

    save_accounts(accounts)

    if report_mode:
        print(format_report(results))
    else:
        print("\nAll accounts processed successfully!")


def show_status() -> None:
    accounts = load_accounts()
    print(f"\nTotal Dark Horse Accounts: {len(accounts)}")
    print("=" * 95)
    print(f"{'No':<3} | {'Handle':<16} | {'Tier':<8} | {'Points':<8} | {'Claimable':<12} | {'Checkin':<10} | {'Tor Exit IP'}")
    print("-" * 95)
    for i, a in enumerate(accounts, 1):
        handle = a.get("handle", "-")
        tier = a.get("tier", "user")
        points = a.get("points", 0)
        claimable = a.get("claimable", 0.0)
        daily_rate = a.get("dailyRate", 25.0)
        checkin_str = f"Day {a.get('checkinDays', 0)}" + (" ✓" if a.get("checkinToday") else " ✗")
        ip = a.get("torExitIp", "unknown")
        claimable_str = f"{claimable:.2f} (+{daily_rate:.0f}/d)"
        print(f"{i:<3} | @{handle:<15} | {tier:<8} | {points:<8} | {claimable_str:<12} | {checkin_str:<10} | {ip}")
    print("=" * 95)


def add_account(handle: str, cookie: str) -> None:
    accounts = load_accounts()
    # Check if handle exists
    existing = [a for a in accounts if a.get("handle") == handle]
    if existing:
        existing[0]["sessionCookie"] = cookie
        print(f"Updated session cookie for existing account @{handle}.")
    else:
        new_acc = {
            "handle": handle,
            "sessionCookie": cookie,
            "torUserId": f"tor_dhorse_{int(time.time())}",
            "torExitIp": "pending",
            "walletAddress": "",
            "tier": "user",
            "points": 0,
            "claimable": 0.0,
            "claimed": 0.0,
            "checkinToday": False,
            "checkinDays": 0,
            "lastRunAt": None,
        }
        accounts.append(new_acc)
        print(f"Added new account @{handle} to {ACCOUNTS_FILE}.")

    save_accounts(accounts)


def main():
    parser = argparse.ArgumentParser(description="Dark Horse Genesis Automation Bot")
    parser.add_argument("action", choices=["run", "status", "add"], default="status", nargs="?")
    parser.add_argument("--handle", type=str, help="X (Twitter) handle for add action")
    parser.add_argument("--cookie", type=str, help="genesis_session cookie for add action")
    parser.add_argument("--report", action="store_true", help="Output summary report in Markdown format")
    args = parser.parse_args()

    if args.action == "add":
        if not args.handle or not args.cookie:
            print("Error: --handle and --cookie are required for 'add' action.")
            sys.exit(1)
        add_account(args.handle, args.cookie)
    elif args.action == "run":
        run_all(report_mode=args.report)
    else:
        show_status()


if __name__ == "__main__":
    main()
