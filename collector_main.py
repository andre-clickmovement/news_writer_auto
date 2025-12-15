"""
Newsletter Data Collector - Main Script
Collects data from TinyEmail and Beehiiv APIs and stores in Supabase
"""
import os
import sys
from datetime import datetime, timedelta
from typing import List, Dict, Any
import argparse
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Configuration
SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_KEY = os.getenv('SUPABASE_KEY')

# TinyEmail Config - Format: {API_KEYS: {internal_name: key}, BRAND_NAMES: {internal_name: display_name}}
TINYEMAIL_CONFIG = {
    'API_KEYS': {
        'AC': os.getenv('TINYEMAIL_API_KEY_AC'),
        'CD': os.getenv('TINYEMAIL_API_KEY_CD'),
        'WR': os.getenv('TINYEMAIL_API_KEY_WR'),
        'PW': os.getenv('TINYEMAIL_API_KEY_PW')
    },
    'BRAND_NAMES': {
        'AC': 'American Conservative',
        'CD': 'Conservatives Daily',
        'WR': 'Worldly Reports',
        'PW': 'Patriots Wire'
    }
}

# Beehiiv Config - Format: {group_name: {api_key: key, brands: [list]}}
BEEHIIV_CONFIG = {
    'group1': {
        'api_key': os.getenv('BEEHIIV_API_KEY_GROUP1'),
        'brands': [
            'Americans Daily Digest',
            'Republicans Report'
            # Note: Group 1 also has: Real Estate Revival, Your Devotional, Personal Security News
            # Add them to the list above if you want to track them
        ]
    },
    'group2': {
        'api_key': os.getenv('BEEHIIV_API_KEY_GROUP2'),
        'brands': [
            'Keeping Up With America',  # ← FIXED: Moved from group1 to group2
            'News Stand',
            'News Flash'
            # Note: Group 2 also has: Uncommon Advice, Healthy Habits, Newsletter Bytes,
            # Learn.RealEstate, Operator's Edge, Charlotte Dirt, Kingdom Capital Strategies
            # Add them to the list above if you want to track them
        ]
    }
}

def validate_config():
    """Validate all required configuration"""
    missing = []
    
    if not SUPABASE_URL:
        missing.append('SUPABASE_URL')
    if not SUPABASE_KEY:
        missing.append('SUPABASE_KEY')
    
    # Check TinyEmail keys
    tiny_mapping = {
        'AC': 'TINYEMAIL_API_KEY_AC',
        'CD': 'TINYEMAIL_API_KEY_CD',
        'WR': 'TINYEMAIL_API_KEY_WR',
        'PW': 'TINYEMAIL_API_KEY_PW'
    }
    for brand_code, api_key in TINYEMAIL_CONFIG['API_KEYS'].items():
        if not api_key:
            missing.append(tiny_mapping[brand_code])
    
    # Check Beehiiv keys
    for group in ['group1', 'group2']:
        if not BEEHIIV_CONFIG[group]['api_key']:
            missing.append(f'BEEHIIV_API_KEY_{group.upper()}')
    
    if missing:
        print(f"❌ Missing configuration: {', '.join(missing)}")
        print("\nSet these environment variables in .env file")
        sys.exit(1)
    
    print("✅ Configuration validated")

def collect_tinyemail_data(date_str: str) -> List[Dict[str, Any]]:
    from collectors.tinyemail import TinyEmailCollector
    
    # Convert to datetime
    target_date = datetime.strptime(date_str, '%Y-%m-%d')
    
    print(f"\n📧 Collecting TinyEmail campaigns for {date_str}")
    
    try:
        collector = TinyEmailCollector(TINYEMAIL_CONFIG)
        data = collector.collect(target_date=target_date)  # ← ADD THIS
        print(f"✅ TinyEmail: Collected {len(data)} campaign(s)")
        return data
    except Exception as e:
        print(f"❌ TinyEmail Error: {e}")
        import traceback
        traceback.print_exc()
        return []

def collect_beehiiv_data(date_str: str) -> List[Dict[str, Any]]:
    from collectors.beehiiv import BeehiivCollector
    
    # Convert to datetime
    target_date = datetime.strptime(date_str, '%Y-%m-%d')
    
    print(f"\n🐝 Collecting Beehiiv posts for {date_str}")
    
    try:
        collector = BeehiivCollector(BEEHIIV_CONFIG)
        data = collector.collect(target_date=target_date)  # ← ADD THIS
        print(f"✅ Beehiiv: Collected {len(data)} post(s)")
        return data
    except Exception as e:
        print(f"❌ Beehiiv Error: {e}")
        import traceback
        traceback.print_exc()
        return []
    

def write_to_supabase(data: List[Dict[str, Any]]) -> tuple[int, int]:
    """Write collected data to Supabase"""
    from utils.supabase_writer import SupabaseWriter
    
    writer = SupabaseWriter(SUPABASE_URL, SUPABASE_KEY)
    
    success_count = 0
    fail_count = 0
    
    for record in data:
        try:
            writer.write_metrics(record)
            brand = record.get('Brand', 'Unknown')
            date = record.get('Date', 'Unknown')
            sends = record.get('Sends', 0)
            print(f"✅ Wrote: {date} | {brand} | {sends:,} sends")
            success_count += 1
        except Exception as e:
            print(f"❌ Failed: {e}")
            fail_count += 1
    
    return success_count, fail_count

def main():
    parser = argparse.ArgumentParser(description='Collect newsletter data')
    parser.add_argument('--date', type=str, help='Date to collect (YYYY-MM-DD). Default: yesterday')
    parser.add_argument('--start-date', type=str, help='Start date for range collection (YYYY-MM-DD)')
    parser.add_argument('--end-date', type=str, help='End date for range collection (YYYY-MM-DD)')
    parser.add_argument('--validate-only', action='store_true', help='Only validate configuration')
    
    args = parser.parse_args()
    
    print("=" * 60)
    print(" NEWSLETTER DATA COLLECTOR")
    print("=" * 60)
    
    # Validate configuration
    validate_config()
    
    if args.validate_only:
        print("\n✅ Configuration is valid!")
        return
    
    # Determine dates to collect
    dates_to_collect = []
    
    if args.start_date and args.end_date:
        # Date range
        start = datetime.strptime(args.start_date, '%Y-%m-%d')
        end = datetime.strptime(args.end_date, '%Y-%m-%d')
        current = start
        while current <= end:
            dates_to_collect.append(current.strftime('%Y-%m-%d'))
            current += timedelta(days=1)
        print(f"\n📅 Collecting date range: {args.start_date} to {args.end_date}")
    elif args.date:
        # Single date
        dates_to_collect = [args.date]
        print(f"\n📅 Collecting date: {args.date}")
    else:
        # Default: yesterday
        yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
        dates_to_collect = [yesterday]
        print(f"\n📅 Collecting date: {yesterday} (yesterday)")
    
    # Collect data for each date
    total_success = 0
    total_failed = 0
    
    for date_str in dates_to_collect:
        print(f"\n{'='*60}")
        print(f"Collecting data for: {date_str}")
        print(f"{'='*60}")
        
        # Collect from both sources
        tinyemail_data = collect_tinyemail_data(date_str)
        beehiiv_data = collect_beehiiv_data(date_str)
        
        # Combine all data
        all_data = tinyemail_data + beehiiv_data
        
        print(f"\n📊 Collected {len(all_data)} total records for {date_str}")
        print(f"   TinyEmail: {len(tinyemail_data)} campaigns")
        print(f"   Beehiiv: {len(beehiiv_data)} posts")
        
        if all_data:
            # Write to Supabase
            print(f"\n💾 Writing to Supabase...")
            success, failed = write_to_supabase(all_data)
            total_success += success
            total_failed += failed
    
    # Summary
    print("\n" + "="*60)
    print(" COLLECTION SUMMARY")
    print("="*60)
    print(f"✅ Successfully stored: {total_success}")
    print(f"❌ Failed: {total_failed}")
    print(f"📊 Total processed: {total_success + total_failed}")
    print("="*60)
    
    if total_failed == 0:
        print("\n✅ Collection complete!")
    else:
        print(f"\n⚠️  Collection complete with {total_failed} errors")

if __name__ == '__main__':
    main()