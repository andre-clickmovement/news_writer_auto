"""
Supabase Writer - Writes newsletter metrics to Supabase
"""
from supabase import create_client, Client
from typing import Dict, Any
from datetime import datetime

class SupabaseWriter:
    def __init__(self, url: str, key: str):
        self.client: Client = create_client(url, key)
    
    def write_metrics(self, record: Dict[str, Any]) -> bool:
        """
        Write a single metrics record to Supabase
        
        Args:
            record: Dictionary with keys matching CSV format:
                Date, Brand, Platform, Campaign_Type, Sends, Delivered, Opens, etc.
        
        Returns:
            True if successful, False otherwise
        """
        try:
            # Transform record to match database schema
            data = {
                'date': record['Date'],
                'brand': record['Brand'],
                'platform': record['Platform'],
                'campaign_type': record.get('Campaign_Type'),
                'sends': int(record['Sends']),
                'delivered': int(float(record['Delivered'])),  # Convert percentage to integer (90.64 -> 90)
                'opens': int(record['Opens']),
                'open_rate': float(record['Open Rate']),
                'unique_opens': int(record['Unique Opens']),
                'unique_open_rate': float(record['Unique Open Rate']),
                'clicks': int(record['Clicks']),
                'ctr': float(record['CTR']),
                'unique_clicks': int(record['Unique Clicks']),
                'uctr': float(record['UCTR']),
                'brand_list_size': int(record['Brand List Size']),
                'list_growth': int(record['List Growth']),
                'unsubscribes': int(record['Unsubscribes']),
                'unsubscribe_rate': float(record['% Unsubscribe']),
                'spam_reports': int(record['Spam']),
                'created_at': datetime.now().isoformat(),
                'updated_at': datetime.now().isoformat()
            }
            
            # Insert or update (upsert)
            result = self.client.table('newsletter_metrics').upsert(
                data,
                on_conflict='date,brand,campaign_type'
            ).execute()
            
            return True
            
        except Exception as e:
            raise Exception(f"Failed to write to Supabase: {str(e)}")
    
    def write_batch(self, records: list[Dict[str, Any]]) -> tuple[int, int]:
        """
        Write multiple records to Supabase
        
        Returns:
            Tuple of (success_count, failure_count)
        """
        success = 0
        failed = 0
        
        for record in records:
            try:
                self.write_metrics(record)
                success += 1
            except Exception as e:
                print(f"Failed to write record: {e}")
                failed += 1
        
        return success, failed
    
    def get_recent_metrics(self, days: int = 7) -> list[Dict[str, Any]]:
        """Get recent metrics for verification"""
        try:
            result = self.client.table('newsletter_metrics')\
                .select('*')\
                .order('date', desc=True)\
                .limit(days * 10)\
                .execute()
            
            return result.data
        except Exception as e:
            print(f"Error fetching recent metrics: {e}")
            return []