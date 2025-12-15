"""
Beehiiv Newsletter Data Collector - FIXED VERSION
Fixes:
- Explicit max_pages = 50 (searches up to 5,000 posts)
- Better error handling and logging
- Proper tag filtering for brands with/without tags
"""

import requests
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional

class BeehiivCollector:
    """Wrapper around Beehiiv collection logic"""
    
    def __init__(self, config: Dict):
        """
        Initialize with config dict containing api_key and brands
        
        Args:
            config: Dict with structure:
                    {
                        'group1': {
                            'api_key': 'key_here',
                            'brands': ['Brand1', 'Brand2']
                        },
                        'group2': {...}
                    }
        """
        self.config = config
        self.base_url = "https://api.beehiiv.com/v2"
        self.session = requests.Session()
    
    def collect(self, target_date: Optional[datetime] = None) -> List[Dict]:
        """
        Main collection method
        
        Args:
            target_date: Optional date to collect (defaults to yesterday)
            
        Returns list of metrics dictionaries
        """
        if target_date is None:
            target_date = datetime.now() - timedelta(days=1)
            
        yesterday = target_date
        day_before_yesterday = target_date - timedelta(days=1)
        all_metrics = []
        
        print("\n" + "="*60)
        print(" BEEHIIV NEWSLETTER DATA COLLECTION")
        print("="*60)
        print(f"Target Date: {yesterday.strftime('%Y-%m-%d')}")
        print(f"List Growth Base: {day_before_yesterday.strftime('%Y-%m-%d')}")
        
        # Process each group (skip BRAND_NAMES key if present)
        for group_name, group_config in self.config.items():
            if group_name == 'BRAND_NAMES':
                continue
                
            print(f"\n{group_name}:")
            collector = BeehiivNewsletterCollector(group_config['api_key'])
            
            for brand_name in group_config['brands']:
                print(f"\n  {brand_name}:")
                
                # Get day before yesterday's recipient count
                day_before_data = collector.get_posts_for_date(
                    brand_name, day_before_yesterday, get_full_data=False
                )
                previous_recipients = day_before_data['recipients']
                
                # Get yesterday's full newsletter post data
                yesterday_data = collector.get_posts_for_date(
                    brand_name, yesterday, get_full_data=True
                )
                
                # Extract metrics for each post
                for post in yesterday_data['posts']:
                    metrics = collector.extract_metrics(
                        post, brand_name, 
                        previous_day_recipients=previous_recipients
                    )
                    
                    # Show list growth calculation
                    current_recipients = metrics['Brand List Size']
                    list_growth = metrics['List Growth']
                    
                    if previous_recipients > 0:
                        print(f"      List Growth: {current_recipients:,} - {previous_recipients:,} = {list_growth:+,}")
                    
                    all_metrics.append(metrics)
        
        return all_metrics


class BeehiivNewsletterCollector:
    """Beehiiv collector - FIXED with explicit max_pages"""
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://api.beehiiv.com/v2"
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        })
        self.publications = {}
        self._load_publications()
    
    def _load_publications(self):
        """Load all publications for this API key"""
        try:
            response = self.session.get(f"{self.base_url}/publications")
            if response.status_code == 200:
                data = response.json()
                for pub in data.get("data", []):
                    self.publications[pub["name"]] = {
                        'id': pub["id"],
                        'name': pub["name"]
                    }
                print(f"  Loaded {len(self.publications)} publications")
        except Exception as e:
            print(f"  Error loading publications: {e}")
    
    def is_newsletter_post(self, content_tags: List) -> bool:
        """Check if post has newsletter tag"""
        if not content_tags:
            return False
        
        tags_lower = [str(tag).lower() for tag in content_tags]
        newsletter_variations = [
            'newsletter', 'news-letter', 'news_letter',
            'daily newsletter', 'daily-newsletter', 'daily_newsletter'
        ]
        
        for tag in tags_lower:
            for variation in newsletter_variations:
                if variation in tag:
                    return True
        return False
    
    def get_posts_for_date(self, brand_name: str, target_date: datetime, 
                          get_full_data: bool = True) -> Dict:
        """
        Get newsletter posts for a specific date
        FIXED: Explicit max_pages = 50 (searches up to 5,000 posts)
        """
        if brand_name not in self.publications:
            print(f"    ⚠️ Brand '{brand_name}' not found")
            return {'posts': [], 'recipients': 0}
        
        pub_id = self.publications[brand_name]['id']
        newsletter_posts = []
        total_recipients = 0
        page = 1
        max_pages = 50  # ✅ EXPLICIT: Search up to 50 pages (5,000 posts)
        
        date_str = target_date.strftime('%Y-%m-%d')
        if get_full_data:
            print(f"    Fetching full data for {date_str}...")
        else:
            print(f"    Fetching recipient count for {date_str}...")
        
        # Brands that don't use newsletter tags
        no_tag_brands = ['News Flash', 'News Stand']
        use_tag_filter = brand_name not in no_tag_brands
        
        # NOTE: Beehiiv API does NOT return posts in date order - they're in creation order
        # Dec 2025 posts may be on page 15+ for older publications
        # We must search ALL pages to find the target date

        while page <= max_pages:
            try:
                response = self.session.get(
                    f"{self.base_url}/publications/{pub_id}/posts",
                    params={
                        "status": "confirmed",
                        "limit": 100,
                        "page": page,
                        "expand": "stats"
                    }
                )

                if response.status_code != 200:
                    if response.status_code == 404 or response.status_code == 400:
                        break
                    print(f"      ⚠️ HTTP {response.status_code} on page {page}")
                    break

                data = response.json()
                posts = data.get("data", [])

                if not posts:
                    break

                for post in posts:
                    if not post.get("publish_date"):
                        continue

                    post_date = datetime.fromtimestamp(post["publish_date"])

                    if post_date.date() == target_date.date():
                        # Skip Dedicated CPM posts
                        if "Dedicated CPM" in post.get("title", ""):
                            if get_full_data:
                                print(f"      ✗ Skipping CPM: {post.get('title', 'Untitled')[:50]}")
                            continue

                        if use_tag_filter:
                            content_tags = post.get("content_tags", [])
                            if self.is_newsletter_post(content_tags):
                                email_stats = post.get("stats", {}).get("email", {})
                                recipients = email_stats.get("recipients", 0)
                                total_recipients += recipients

                                if get_full_data:
                                    newsletter_posts.append(post)
                                    print(f"      ✓ Newsletter: {post.get('title', 'Untitled')[:50]} ({recipients:,} recipients)")
                            else:
                                if get_full_data:
                                    print(f"      ✗ No newsletter tag: {post.get('title', 'Untitled')[:50]}")
                        else:
                            # No tag filter - collect all non-CPM posts
                            email_stats = post.get("stats", {}).get("email", {})
                            recipients = email_stats.get("recipients", 0)
                            total_recipients += recipients

                            if get_full_data:
                                newsletter_posts.append(post)
                                print(f"      ✓ Post: {post.get('title', 'Untitled')[:50]} ({recipients:,} recipients)")

                # Check if we've reached the last page
                total_pages = data.get("total_pages", 1)
                if page >= total_pages:
                    if get_full_data:
                        print(f"      ✓ Searched all {total_pages} pages")
                    break

                page += 1

            except Exception as e:
                print(f"      Error on page {page}: {e}")
                break
        
        if get_full_data:
            if newsletter_posts:
                print(f"      Found {len(newsletter_posts)} post(s)")
            else:
                print(f"      ⚠️ No posts found for {date_str} (searched {page} pages)")
        
        return {'posts': newsletter_posts, 'recipients': total_recipients}
    
    def extract_metrics(self, post: Dict, brand_name: str, 
                       previous_day_recipients: int = 0) -> Dict:
        """Extract metrics from a post - Uses Sends as base for all calculations"""
        post_date = datetime.fromtimestamp(post["publish_date"]) if post.get("publish_date") else datetime.now()
        email_stats = post.get("stats", {}).get("email", {})
        
        # Use recipients as Sends (the base for ALL calculations)
        sends = email_stats.get("recipients", 0)
        delivered = email_stats.get("delivered", 0)
        opens = email_stats.get("opens", 0)
        unique_opens = email_stats.get("unique_opens", 0)
        clicks = email_stats.get("clicks", 0)
        unique_clicks = email_stats.get("unique_clicks", 0)
        unsubscribes = email_stats.get("unsubscribes", 0)
        spam = email_stats.get("spam_reports", 0)
        
        # Calculate ALL rates based on SENDS, not delivered
        if sends > 0:
            delivery_rate = (delivered / sends) * 100
            open_rate = (opens / sends) * 100
            unique_open_rate = (unique_opens / sends) * 100
            ctr = (clicks / sends) * 100
            uctr = (unique_clicks / sends) * 100
            unsubscribe_rate = (unsubscribes / sends)
        else:
            delivery_rate = open_rate = unique_open_rate = ctr = uctr = unsubscribe_rate = 0
        
        # List growth = current sends - previous day's sends
        list_growth = sends - previous_day_recipients
        
        return {
            "Date": post_date.strftime("%Y-%m-%d"),
            "Brand": brand_name,
            "Platform": "Beehiiv",  # ← Added
            "Campaign_Type": "Newsletter",  # ← Added (Beehiiv only has one type)
            "Sends": sends,
            "Delivered": round(delivery_rate, 2),
            "Opens": opens,
            "Open Rate": round(open_rate, 2),
            "Unique Opens": unique_opens,
            "Unique Open Rate": round(unique_open_rate, 2),
            "Clicks": clicks,
            "CTR": round(ctr, 2),
            "Unique Clicks": unique_clicks,
            "UCTR": round(uctr, 2),
            "Brand List Size": sends,
            "List Growth": list_growth,
            "% Unsubscribe": round(unsubscribe_rate, 4),
            "Unsubscribes": unsubscribes,
            "Spam": spam
        }