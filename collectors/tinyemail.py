"""
TinyEmail collector - FIXED VERSION
Collects Daily Digest AM/PM and Dedicated CPM campaigns correctly
"""

import requests
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional

class TinyEmailCollector:
    """Fixed TinyEmail collection logic - handles all AM/PM patterns"""
    
    def __init__(self, config):
        """Initialize with config dict containing API_KEYS and BRAND_NAMES"""
        if isinstance(config, dict) and 'API_KEYS' in config and 'BRAND_NAMES' in config:
            self.api_keys = config['API_KEYS']
            self.brand_names = config['BRAND_NAMES']
        else:
            raise ValueError("TinyEmailCollector requires a config dict with API_KEYS and BRAND_NAMES")
        
        self.base_url = "https://api.tinyemail.com/v1"
    
    def collect(self, target_date: Optional[datetime] = None) -> List[Dict]:
        """
        Main collection method - FIXED to handle all campaign patterns
        
        Args:
            target_date: Optional date to collect (defaults to yesterday)
            
        Returns list of metrics dictionaries
        """
        if target_date is None:
            target_date = datetime.now() - timedelta(days=1)
        
        yesterday = target_date
        day_before = target_date - timedelta(days=1)    
        print("\n" + "="*60)
        print(" TINYEMAIL DATA COLLECTION (FIXED)")
        print("="*60)
        print(f"Target Date: {yesterday.strftime('%Y-%m-%d')}")
        print(f"List Growth Base: {day_before.strftime('%Y-%m-%d')}")
        print(f"Collecting: Daily Digest AM + Daily Digest PM + Dedicated CPM")
        
        all_metrics = []
        
        for api_brand, api_key in self.api_keys.items():
            print(f"\n{api_brand}:")
            
            # Get yesterday's campaigns
            yesterday_campaigns = self.get_campaigns_for_date(api_key, api_brand, yesterday)
            print(f"  Found {len(yesterday_campaigns)} campaigns for yesterday")
            
            # Get day before yesterday's campaigns for list growth
            previous_campaigns = self.get_campaigns_for_date(api_key, api_brand, day_before)
            print(f"  Found {len(previous_campaigns)} campaigns for day before")
            
            # Build map of previous day sends
            previous_sends = self.get_previous_sends(previous_campaigns)
            
            # Separate ALL campaigns by type (AM/PM) - FIXED LOGIC
            am_campaigns, pm_campaigns = self.separate_all_campaigns(yesterday_campaigns)
            
            # Process AM campaigns
            if am_campaigns:
                for campaign in am_campaigns:
                    metric = self.process_campaign(
                        campaign, api_brand, "AM", 
                        yesterday, previous_sends.get("AM", 0)
                    )
                    if metric:
                        all_metrics.append(metric)
            else:
                print(f"    ℹ️  No AM campaigns found")
            
            # Process PM campaigns
            if pm_campaigns:
                for campaign in pm_campaigns:
                    metric = self.process_campaign(
                        campaign, api_brand, "PM", 
                        yesterday, previous_sends.get("PM", 0)
                    )
                    if metric:
                        all_metrics.append(metric)
            else:
                print(f"    ℹ️  No PM campaigns found")
        
        return all_metrics
    
    def get_campaigns_for_date(self, api_key: str, brand_name: str, 
                               target_date: datetime) -> List[Dict]:
        """Get all campaigns for a specific date - INCREASED page limit"""
        headers = {
            "X-API-Key": api_key,
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        
        # Format date strings to look for
        date_formats = [
            target_date.strftime("%m.%d.%y"),    # 10.15.25
            target_date.strftime("%m.%d.%Y"),    # 10.15.2025
            target_date.strftime("%-m.%-d.%y"),  # 10.15.25 (no leading zeros)
            target_date.strftime("%Y-%m-%d"),    # 2025-10-15
        ]
        
        found_campaigns = []
        page = 0
        
        # FIXED: Increased from 5 to 20 pages (1000 campaigns)
        while page < 20:
            try:
                response = requests.get(
                    f"{self.base_url}/campaign?page={page}&size=50", 
                    headers=headers,
                    timeout=30
                )
                
                if response.status_code == 200:
                    data = response.json()
                    campaigns_data = data.get("campaigns", {})
                    content = campaigns_data.get("content", [])
                    
                    for campaign in content:
                        campaign_obj = campaign.get("campaign", {})
                        name = campaign_obj.get("name", "")
                        
                        # Check if any date format matches
                        matches_date = any(date_fmt in name for date_fmt in date_formats)
                        
                        if matches_date:
                            found_campaigns.append(campaign)
                    
                    # Check if last page
                    if campaigns_data.get('last', True):
                        break
                    else:
                        page += 1
                else:
                    break
                    
            except Exception as e:
                break
        
        return found_campaigns
    
    def get_previous_sends(self, campaigns: List[Dict]) -> Dict[str, int]:
        """Get previous day sends by AM/PM segment"""
        previous_sends = {}
        
        for campaign in campaigns:
            name = campaign.get("campaign", {}).get("name", "")
            status = campaign.get("status", "")
            sends = campaign.get("sent", 0)
            
            # Only count completed campaigns with volume
            if status == "COMPLETED" and sends > 100:
                # FIXED: Check PM patterns FIRST before Daily Digest
                is_pm = (
                    "Daily Digest PM" in name or
                    "Dedicated CPM" in name or
                    (" PM " in name and "Daily Digest" in name and "CPM" not in name) or
                    (" PM-" in name) or
                    ("_PM" in name)
                )
                
                segment = "PM" if is_pm else "AM"
                
                # Sum all campaigns of this type (in case multiple)
                if segment not in previous_sends:
                    previous_sends[segment] = 0
                previous_sends[segment] += sends
        
        return previous_sends
    
    def separate_all_campaigns(self, campaigns: List[Dict]) -> tuple:
        """
        Separate campaigns into AM and PM - FIXED to collect ALL campaigns
        Returns: (list of AM campaigns, list of PM campaigns)
        """
        am_campaigns = []
        pm_campaigns = []
        
        for campaign in campaigns:
            campaign_info = campaign.get("campaign", {})
            name = campaign_info.get("name", "")
            status = campaign.get("status", "")
            sends = campaign.get("sent", 0)
            
            # Only process completed campaigns with volume
            if status != "COMPLETED" or sends <= 100:
                continue
            
            # FIXED: Check PM patterns FIRST (before checking Daily Digest)
            is_daily_digest_pm = (
                "Daily Digest PM" in name or
                (" PM " in name and "Daily Digest" in name and "CPM" not in name)
            )
            
            is_dedicated_cpm = (
                "Dedicated CPM" in name or 
                ("CPM" in name and "Daily Digest" not in name)
            )
            
            # PM campaigns: Daily Digest PM OR Dedicated CPM
            if is_daily_digest_pm or is_dedicated_cpm:
                pm_campaigns.append(campaign)
            # AM campaigns: Daily Digest (without PM marker)
            elif "Daily Digest" in name:
                am_campaigns.append(campaign)
        
        return am_campaigns, pm_campaigns
    
    def process_campaign(self, campaign: Dict, api_brand: str, segment: str,
                        target_date: datetime, prev_sends: int) -> Optional[Dict]:
        """Process a campaign and create metric"""
        campaign_info = campaign.get("campaign", {})
        name = campaign_info.get("name", "")
        sends = campaign.get("sent", 0)
        
        # Get the display brand name
        display_brand = self.brand_names.get(api_brand, api_brand)
        brand_with_segment = f"{display_brand} {segment}"
        
        # Calculate list growth
        list_growth = sends - prev_sends
        
        # Create metric - pass segment parameter
        metric = self.create_metric(campaign, brand_with_segment, target_date, segment, list_growth)
        
        # Determine campaign type for display
        campaign_type = "Daily Digest PM" if "Daily Digest PM" in name else \
                       "Dedicated CPM" if "Dedicated CPM" in name or "CPM" in name else \
                       "Daily Digest"
        
        print(f"    ✓ {campaign_type} {segment}: {name[:50]}")
        print(f"      Sends: {sends:,}, Opens: {metric['Opens']:,}, Clicks: {metric['Clicks']:,}")
        
        return metric
    
    def create_metric(self, campaign: Dict, brand_name: str, 
                     target_date: datetime, segment: str, list_growth: int = 0) -> Dict:
        """Create a metric row matching format exactly"""
        # Extract base metrics
        sends = campaign.get("sent", 0)
        delivered = campaign.get("delivered", 0)
        total_opens = campaign.get("totalOpen", 0)
        unique_opens = campaign.get("open", 0)
        total_clicks = campaign.get("totalClicked", 0)
        unique_clicks = campaign.get("clicked", 0)
        unsubscribes = campaign.get("unsubscribed", 0)
        spam = campaign.get("spam", 0)
        
        # Calculate rates based on sends
        if sends > 0:
            delivery_rate = (delivered / sends) * 100
            open_rate = (total_opens / sends) * 100
            unique_open_rate = (unique_opens / sends) * 100
            ctr = (total_clicks / sends) * 100
            uctr = (unique_clicks / sends) * 100
            unsubscribe_rate = (unsubscribes / sends) * 100
        else:
            delivery_rate = open_rate = unique_open_rate = ctr = uctr = unsubscribe_rate = 0
        
        return {
            "Date": target_date.strftime("%Y-%m-%d"),
            "Brand": brand_name,
            "Platform": "TinyEmail",
            "Campaign_Type": segment if segment in ["AM", "PM"] else "Newsletter",
            "Sends": sends,
            "Delivered": round(delivery_rate, 2),
            "Opens": total_opens,
            "Open Rate": round(open_rate, 2),
            "Unique Opens": unique_opens,
            "Unique Open Rate": round(unique_open_rate, 2),
            "Clicks": total_clicks,
            "CTR": round(ctr, 2),
            "Unique Clicks": unique_clicks,
            "UCTR": round(uctr, 2),
            "Brand List Size": sends,
            "List Growth": list_growth,
            "% Unsubscribe": round(unsubscribe_rate, 4),
            "Unsubscribes": unsubscribes,
            "Spam": spam
        }