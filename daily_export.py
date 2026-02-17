#!/usr/bin/env python3
"""
Daily Newsletter Export Script
==============================
Exports Beehiiv newsletter metrics from Supabase to CSV format
matching the Google Sheets "Recent Newsletter Performance - Beehiiv - Weekly Performance"

Usage:
    python daily_export.py                    # Export yesterday's data
    python daily_export.py --date 2026-02-17  # Export specific date
    python daily_export.py --range 2026-02-01 2026-02-17  # Export date range
    python daily_export.py --email recipient@example.com  # Export and email

Output: CSV file ready for Google Sheets upload
"""

import os
import argparse
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import csv
from io import StringIO
from dotenv import load_dotenv
from supabase import create_client, Client

load_dotenv()

# Beehiiv brands in the order they appear in Google Sheets
BEEHIIV_BRANDS = [
    "Keeping Up With America",
    "Americans Daily Digest",
    "Republicans Report",
    "News Stand",
    "News Flash"
]

# TinyEmail brands in the order they appear in Google Sheets
TINYEMAIL_BRANDS = [
    "American Conservative AM",
    "American Conservative PM",
    "Conservatives Daily AM",
    "Conservatives Daily PM",
    "Worldly Reports AM",
    "Worldly Reports PM",
    "Patriots Wire AM",
    "Patriots Wire PM"
]

# Column headers matching Google Sheets format
HEADERS = [
    "Date", "Brands", "Sends", "Delivered", "Opens", "Open Rate",
    "Unique Opens", "Unique Open Rate", "Clicks", "CTR",
    "Unique Clicks", "UCTR", "Brand List Size", "List Growth",
    "% Unsuscribe", "Unsuscribe", "Spam"
]


class NewsletterExporter:
    """Base exporter for newsletter data from Supabase to Google Sheets CSV format"""

    def __init__(self):
        supabase_url = os.getenv('SUPABASE_URL')
        supabase_key = os.getenv('SUPABASE_KEY')

        if not supabase_url or not supabase_key:
            raise ValueError("SUPABASE_URL and SUPABASE_KEY must be set in .env")

        self.client: Client = create_client(supabase_url, supabase_key)

    def fetch_data(self, start_date: str, end_date: str, platform: str) -> List[Dict]:
        """
        Fetch metrics from Supabase for date range and platform

        Args:
            start_date: YYYY-MM-DD format
            end_date: YYYY-MM-DD format
            platform: 'Beehiiv' or 'TinyEmail'

        Returns:
            List of metric records
        """
        try:
            result = self.client.table('newsletter_metrics')\
                .select('*')\
                .eq('platform', platform)\
                .gte('date', start_date)\
                .lte('date', end_date)\
                .order('date')\
                .order('brand')\
                .execute()

            return result.data
        except Exception as e:
            print(f"Error fetching data: {e}")
            return []

    def format_number(self, value: int, show_sign: bool = False) -> str:
        """Format number with thousands separator"""
        if value is None:
            return ""
        if show_sign and value != 0:
            return f"{value:+,}"
        return f"{value:,}"

    def format_percentage(self, value: float, decimal_places: int = 2) -> str:
        """Format as percentage string"""
        if value is None or value == 0:
            return ""
        return f"{value:.{decimal_places}f}%"

    def format_decimal(self, value: float, decimal_places: int = 4) -> str:
        """Format as decimal (for unsubscribe rate)"""
        if value is None or value == 0:
            return ""
        return f"{value:.{decimal_places}f}"

    def is_weekend(self, date_str: str) -> bool:
        """Check if date is Saturday or Sunday"""
        date = datetime.strptime(date_str, "%Y-%m-%d")
        return date.weekday() >= 5  # Saturday=5, Sunday=6

    def format_date_display(self, date_str: str) -> str:
        """Convert YYYY-MM-DD to M/D/YYYY format"""
        date = datetime.strptime(date_str, "%Y-%m-%d")
        return date.strftime("%-m/%-d/%Y")

    def generate_platform_csv(self, data: List[Dict], start_date: str, end_date: str,
                               platform: str, brands: List[str]) -> List[List[str]]:
        """
        Generate CSV rows for a specific platform

        Args:
            data: List of metric records from Supabase
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
            platform: Platform name for header
            brands: List of brand names in order

        Returns:
            List of CSV rows
        """
        rows = []

        # Write header rows (matching Google Sheets format)
        rows.append([""] * 17)  # Empty row
        rows.append(["", "", platform.upper()] + [""] * 14)  # Title row
        rows.append(HEADERS)

        # Group data by date
        data_by_date = {}
        for record in data:
            date = record['date']
            if date not in data_by_date:
                data_by_date[date] = {}
            data_by_date[date][record['brand']] = record

        # Generate all dates in range
        current = datetime.strptime(start_date, "%Y-%m-%d")
        end = datetime.strptime(end_date, "%Y-%m-%d")

        while current <= end:
            date_str = current.strftime("%Y-%m-%d")
            display_date = self.format_date_display(date_str)
            is_weekend = self.is_weekend(date_str)

            # Empty row before date
            rows.append([display_date] + [""] * 16)

            # Check if we have data for this date
            date_data = data_by_date.get(date_str, {})

            # Write row for each brand
            for i, brand in enumerate(brands):
                record = date_data.get(brand)

                if record and not is_weekend:
                    # Full data row
                    list_growth = record.get('list_growth', 0)
                    row = [
                        display_date if i == 0 else "",  # Date only on first row
                        brand,
                        self.format_number(record.get('sends', 0)),
                        self.format_percentage(record.get('delivered', 0)),
                        self.format_number(record.get('opens', 0)),
                        self.format_percentage(record.get('open_rate', 0)),
                        self.format_number(record.get('unique_opens', 0)),
                        self.format_percentage(record.get('unique_open_rate', 0)),
                        self.format_number(record.get('clicks', 0)),
                        self.format_percentage(record.get('ctr', 0)),
                        self.format_number(record.get('unique_clicks', 0)),
                        self.format_percentage(record.get('uctr', 0)),
                        self.format_number(record.get('brand_list_size', 0)),
                        self.format_number(list_growth, show_sign=True) if list_growth else "0",
                        self.format_decimal(record.get('unsubscribe_rate', 0)),
                        record.get('unsubscribes', "") if record.get('unsubscribes') else "",
                        record.get('spam_reports', "") if record.get('spam_reports') else ""
                    ]
                else:
                    # Weekend or no data - just show brand and list size
                    sends = record.get('sends', 0) if record else 0
                    row = [
                        display_date if i == 0 else "",
                        brand,
                        self.format_number(sends) if sends else "",
                        "", "", "", "", "", "", "", "", "",
                        self.format_number(sends) if sends else "",
                        "0" if is_weekend else "",
                        "", "", ""
                    ]

                rows.append(row)

            current += timedelta(days=1)

        return rows

    def generate_combined_csv(self, start_date: str, end_date: str) -> str:
        """
        Generate combined CSV with both TinyEmail and Beehiiv data

        Args:
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)

        Returns:
            CSV string
        """
        output = StringIO()
        writer = csv.writer(output)

        # Fetch TinyEmail data and generate rows
        print("Fetching TinyEmail data...")
        tinyemail_data = self.fetch_data(start_date, end_date, 'TinyEmail')
        print(f"Found {len(tinyemail_data)} TinyEmail records")
        tinyemail_rows = self.generate_platform_csv(
            tinyemail_data, start_date, end_date, "TINY EMAIL", TINYEMAIL_BRANDS
        )

        # Write TinyEmail rows
        for row in tinyemail_rows:
            writer.writerow(row)

        # Add separator rows between platforms
        writer.writerow([""] * 17)
        writer.writerow([""] * 17)

        # Fetch Beehiiv data and generate rows
        print("Fetching Beehiiv data...")
        beehiiv_data = self.fetch_data(start_date, end_date, 'Beehiiv')
        print(f"Found {len(beehiiv_data)} Beehiiv records")
        beehiiv_rows = self.generate_platform_csv(
            beehiiv_data, start_date, end_date, "BEEHIIV", BEEHIIV_BRANDS
        )

        # Write Beehiiv rows
        for row in beehiiv_rows:
            writer.writerow(row)

        return output.getvalue()

    def export_to_file(self, start_date: str, end_date: str,
                       output_path: Optional[str] = None,
                       platform: Optional[str] = None) -> str:
        """
        Export data to CSV file

        Args:
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
            output_path: Optional output path, defaults to exports/newsletter_YYYYMMDD.csv
            platform: Optional platform filter ('Beehiiv', 'TinyEmail', or None for both)

        Returns:
            Path to output file
        """
        print(f"Exporting newsletter data from {start_date} to {end_date}...")

        # Generate CSV based on platform
        if platform == 'Beehiiv':
            data = self.fetch_data(start_date, end_date, 'Beehiiv')
            print(f"Found {len(data)} Beehiiv records")
            output = StringIO()
            writer = csv.writer(output)
            rows = self.generate_platform_csv(data, start_date, end_date, "BEEHIIV", BEEHIIV_BRANDS)
            for row in rows:
                writer.writerow(row)
            csv_content = output.getvalue()
            prefix = "beehiiv"
        elif platform == 'TinyEmail':
            data = self.fetch_data(start_date, end_date, 'TinyEmail')
            print(f"Found {len(data)} TinyEmail records")
            output = StringIO()
            writer = csv.writer(output)
            rows = self.generate_platform_csv(data, start_date, end_date, "TINY EMAIL", TINYEMAIL_BRANDS)
            for row in rows:
                writer.writerow(row)
            csv_content = output.getvalue()
            prefix = "tinyemail"
        else:
            # Combined export (both platforms)
            csv_content = self.generate_combined_csv(start_date, end_date)
            prefix = "newsletter"

        # Determine output path
        if not output_path:
            os.makedirs("exports", exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = f"exports/{prefix}_{start_date}_to_{end_date}_{timestamp}.csv"

        # Write file
        with open(output_path, 'w', newline='', encoding='utf-8') as f:
            f.write(csv_content)

        print(f"Exported to: {output_path}")
        return output_path


# Keep alias for backwards compatibility
BeehiivExporter = NewsletterExporter


class EmailSender:
    """Send CSV reports via email"""

    def __init__(self):
        self.smtp_server = os.getenv('SMTP_SERVER', 'smtp.gmail.com')
        self.smtp_port = int(os.getenv('SMTP_PORT', '587'))
        self.smtp_username = os.getenv('SMTP_USERNAME')
        self.smtp_password = os.getenv('SMTP_PASSWORD')
        self.from_email = os.getenv('FROM_EMAIL', self.smtp_username)

        if not self.smtp_username or not self.smtp_password:
            raise ValueError("SMTP_USERNAME and SMTP_PASSWORD must be set in .env")

    def send_report(self, to_email: str, csv_path: str,
                    start_date: str, end_date: str) -> bool:
        """
        Send CSV report via email

        Args:
            to_email: Recipient email address
            csv_path: Path to CSV file
            start_date: Report start date
            end_date: Report end date

        Returns:
            True if successful
        """
        # Create message
        msg = MIMEMultipart()
        msg['From'] = self.from_email
        msg['To'] = to_email
        msg['Subject'] = f"Newsletter Performance Report: {start_date} to {end_date}"

        # Email body
        body = f"""
Hello,

Please find attached the newsletter performance report for {start_date} to {end_date}.

This report includes data from both TinyEmail and Beehiiv platforms, formatted for direct import into Google Sheets.

Best regards,
Newsletter Metrics System
        """
        msg.attach(MIMEText(body, 'plain'))

        # Attach CSV
        with open(csv_path, 'rb') as f:
            part = MIMEBase('application', 'octet-stream')
            part.set_payload(f.read())
            encoders.encode_base64(part)
            filename = os.path.basename(csv_path)
            part.add_header('Content-Disposition', f'attachment; filename= {filename}')
            msg.attach(part)

        # Send email
        try:
            server = smtplib.SMTP(self.smtp_server, self.smtp_port)
            server.starttls()
            server.login(self.smtp_username, self.smtp_password)
            server.sendmail(self.from_email, to_email, msg.as_string())
            server.quit()
            print(f"Email sent successfully to {to_email}")
            return True
        except Exception as e:
            print(f"Failed to send email: {e}")
            return False


def main():
    parser = argparse.ArgumentParser(
        description="Export newsletter metrics to CSV for Google Sheets"
    )
    parser.add_argument(
        '--date',
        type=str,
        help='Single date to export (YYYY-MM-DD)'
    )
    parser.add_argument(
        '--range',
        type=str,
        nargs=2,
        metavar=('START', 'END'),
        help='Date range to export (YYYY-MM-DD YYYY-MM-DD)'
    )
    parser.add_argument(
        '--output',
        type=str,
        help='Output file path (default: exports/newsletter_DATE.csv)'
    )
    parser.add_argument(
        '--platform',
        type=str,
        choices=['Beehiiv', 'TinyEmail', 'all'],
        default='all',
        help='Platform to export (default: all)'
    )
    parser.add_argument(
        '--email',
        type=str,
        help='Email address to send the report to'
    )

    args = parser.parse_args()

    # Determine date range
    if args.range:
        start_date, end_date = args.range
    elif args.date:
        start_date = end_date = args.date
    else:
        # Default to yesterday
        yesterday = datetime.now() - timedelta(days=1)
        start_date = end_date = yesterday.strftime("%Y-%m-%d")

    # Determine platform filter
    platform = None if args.platform == 'all' else args.platform

    # Export
    exporter = NewsletterExporter()
    output_path = exporter.export_to_file(start_date, end_date, args.output, platform)

    # Email if requested
    if args.email:
        try:
            sender = EmailSender()
            sender.send_report(args.email, output_path, start_date, end_date)
        except ValueError as e:
            print(f"Email not configured: {e}")
        except Exception as e:
            print(f"Failed to send email: {e}")

    return output_path


if __name__ == "__main__":
    main()
