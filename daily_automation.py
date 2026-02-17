#!/usr/bin/env python3
"""
Daily Newsletter Automation Script
===================================
Runs the full daily workflow:
1. Collect yesterday's newsletter data from TinyEmail and Beehiiv APIs
2. Store in Supabase
3. Export combined CSV matching Google Sheets format (both TinyEmail and Beehiiv)
4. Email the report to specified recipients

Usage:
    python daily_automation.py                           # Run full workflow
    python daily_automation.py --email user@example.com  # Specify recipient
    python daily_automation.py --no-email                # Skip email
    python daily_automation.py --date 2026-02-17         # Specific date

Automation (cron):
    # Run daily at 8am
    0 8 * * * cd /path/to/newsletter-collector && .venv/bin/python daily_automation.py

Environment Variables Required:
    - SUPABASE_URL, SUPABASE_KEY
    - TINYEMAIL_API_KEY
    - BEEHIIV_API_KEY_GROUP1, BEEHIIV_API_KEY_GROUP2
    - SMTP_SERVER, SMTP_PORT, SMTP_USERNAME, SMTP_PASSWORD, FROM_EMAIL (for email)
"""

import os
import sys
import argparse
import subprocess
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()


def run_collection(target_date: str) -> bool:
    """
    Run the data collection for a specific date.

    Args:
        target_date: Date to collect (YYYY-MM-DD)

    Returns:
        True if successful
    """
    print(f"\n{'='*60}")
    print(f"STEP 1: Collecting newsletter data for {target_date}")
    print('='*60)

    try:
        result = subprocess.run(
            [
                sys.executable, "collector_main.py",
                "--start-date", target_date,
                "--end-date", target_date
            ],
            capture_output=True,
            text=True,
            timeout=600  # 10 minute timeout
        )

        if result.returncode == 0:
            print("Data collection completed successfully")
            print(result.stdout[-2000:] if len(result.stdout) > 2000 else result.stdout)
            return True
        else:
            print(f"Data collection failed with code {result.returncode}")
            print(result.stderr)
            return False

    except subprocess.TimeoutExpired:
        print("Data collection timed out after 10 minutes")
        return False
    except Exception as e:
        print(f"Error running collection: {e}")
        return False


def run_export(target_date: str, email: str = None) -> str:
    """
    Run the CSV export for a specific date.

    Args:
        target_date: Date to export (YYYY-MM-DD)
        email: Optional email address to send report to

    Returns:
        Path to exported CSV file, or None if failed
    """
    print(f"\n{'='*60}")
    print(f"STEP 2: Exporting data to CSV")
    print('='*60)

    try:
        cmd = [
            sys.executable, "daily_export.py",
            "--date", target_date
        ]

        if email:
            cmd.extend(["--email", email])

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=120
        )

        if result.returncode == 0:
            print("Export completed successfully")
            print(result.stdout)

            # Extract output path from stdout
            for line in result.stdout.split('\n'):
                if 'Exported to:' in line:
                    return line.split('Exported to:')[1].strip()
            return None
        else:
            print(f"Export failed with code {result.returncode}")
            print(result.stderr)
            return None

    except subprocess.TimeoutExpired:
        print("Export timed out after 2 minutes")
        return None
    except Exception as e:
        print(f"Error running export: {e}")
        return None


def main():
    """Main entry point for daily automation."""
    parser = argparse.ArgumentParser(
        description="Run daily newsletter data collection and export"
    )
    parser.add_argument(
        '--date',
        type=str,
        help='Date to process (YYYY-MM-DD), defaults to yesterday'
    )
    parser.add_argument(
        '--email',
        type=str,
        default=os.getenv('REPORT_EMAIL'),
        help='Email address to send report (or set REPORT_EMAIL env var)'
    )
    parser.add_argument(
        '--no-email',
        action='store_true',
        help='Skip sending email'
    )
    parser.add_argument(
        '--export-only',
        action='store_true',
        help='Skip collection, only export existing data'
    )

    args = parser.parse_args()

    # Determine target date
    if args.date:
        target_date = args.date
    else:
        yesterday = datetime.now() - timedelta(days=1)
        target_date = yesterday.strftime("%Y-%m-%d")

    print("="*60)
    print(" DAILY NEWSLETTER AUTOMATION")
    print("="*60)
    print(f"Date: {target_date}")
    print(f"Email: {args.email if args.email and not args.no_email else 'Disabled'}")
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # Step 1: Collection (unless --export-only)
    if not args.export_only:
        if not run_collection(target_date):
            print("\nCollection failed. Continuing with export anyway...")

    # Step 2: Export
    email_to = args.email if not args.no_email else None
    output_path = run_export(target_date, email_to)

    # Summary
    print(f"\n{'='*60}")
    print(" SUMMARY")
    print('='*60)

    if output_path:
        print(f"CSV exported: {output_path}")
        if email_to:
            print(f"Report sent to: {email_to}")
        print("\nDone!")
        return 0
    else:
        print("Export failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())
