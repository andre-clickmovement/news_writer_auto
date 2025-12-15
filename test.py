#!/usr/bin/env python3
"""
List actual Beehiiv publication names from API
Use this to find the exact names for your config
"""
import requests
from dotenv import load_dotenv
import os

load_dotenv()

def list_beehiiv_publications():
    """Show all publication names for each API key"""
    
    base_url = "https://api.beehiiv.com/v2"
    
    groups = {
        'group1': os.getenv('BEEHIIV_API_KEY_GROUP1'),
        'group2': os.getenv('BEEHIIV_API_KEY_GROUP2')
    }
    
    print("=" * 60)
    print(" BEEHIIV PUBLICATION NAMES")
    print("=" * 60)
    
    for group_name, api_key in groups.items():
        if not api_key:
            print(f"\n❌ {group_name}: No API key found")
            continue
        
        print(f"\n📧 {group_name}:")
        print(f"   API Key: {api_key[:10]}...{api_key[-10:]}")
        
        try:
            response = requests.get(
                f"{base_url}/publications",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json"
                },
                timeout=30
            )
            
            if response.status_code != 200:
                print(f"   ❌ HTTP {response.status_code}: {response.text[:200]}")
                continue
            
            data = response.json()
            publications = data.get("data", [])
            
            if not publications:
                print(f"   ⚠️  No publications found")
                continue
            
            print(f"   ✅ Found {len(publications)} publication(s):\n")
            
            for pub in publications:
                name = pub.get("name", "Unnamed")
                pub_id = pub.get("id", "No ID")
                print(f"      • \"{name}\"")
                print(f"        ID: {pub_id}\n")
            
        except Exception as e:
            print(f"   ❌ Error: {e}")
    
    print("\n" + "=" * 60)
    print(" UPDATE YOUR CONFIG WITH EXACT NAMES ABOVE")
    print("=" * 60)
    print("\nIn collector_main.py, update BEEHIIV_CONFIG:")
    print("\nBEEHIIV_CONFIG = {")
    print("    'group1': {")
    print("        'api_key': os.getenv('BEEHIIV_API_KEY_GROUP1'),")
    print("        'brands': [")
    print("            'EXACT NAME FROM ABOVE',  # Copy/paste exact name")
    print("            'EXACT NAME FROM ABOVE',")
    print("        ]")
    print("    },")
    print("    ...")
    print("}")

if __name__ == '__main__':
    list_beehiiv_publications()