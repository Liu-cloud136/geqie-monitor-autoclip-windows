#!/usr/bin/env python3
"""测试评分API"""

import requests
import json
import sys

# 设置输出编码
sys.stdout.reconfigure(encoding='utf-8')

base_url = "http://localhost:5000"

print("=" * 60)
print("Test Rating API")
print("=" * 60)

try:
    print("\n1. Test server connection...")
    response = requests.get(f"{base_url}/health", timeout=5)
    print(f"   Status code: {response.status_code}")
except Exception as e:
    print(f"   Connection failed: {e}")
    print("\nPlease start the server first: python jk.py")
    exit(1)

print("\n2. Get a record for testing...")
try:
    response = requests.get(f"{base_url}/api/today", timeout=5)
    print(f"   Status code: {response.status_code}")
    if response.status_code == 200:
        data = response.json()
        if data.get('success') and data.get('data') and len(data['data']) > 0:
            test_record = data['data'][0]
            print(f"   Got record: ID={test_record['id']}, User={test_record['username']}")
            print(f"\n3. Test rating API (Record ID: {test_record['id']})...")
            
            rating_data = {
                "id": test_record['id'],
                "rating": 5
            }
            
            headers = {
                "Content-Type": "application/json"
            }
            
            response = requests.post(
                f"{base_url}/api/record/rate",
                json=rating_data,
                headers=headers,
                timeout=10
            )
            
            print(f"   Status code: {response.status_code}")
            print(f"   Content-Type: {response.headers.get('Content-Type', 'unknown')}")
            
            if response.status_code == 200:
                try:
                    result = response.json()
                    print(f"   Response JSON: {json.dumps(result, ensure_ascii=False, indent=2)}")
                    if result.get('success'):
                        print("\n" + "=" * 60)
                        print("SUCCESS! Rating API works!")
                        print("=" * 60)
                    else:
                        print(f"\nRating failed: {result.get('error', 'Unknown error')}")
                except Exception as e:
                    print(f"   Cannot parse JSON: {e}")
                    print(f"   Raw response: {response.text[:500]}")
            elif response.status_code == 404:
                print(f"   404 Not Found - Route not found")
                print(f"\n   This means:")
                print(f"   1. Server is running old code, OR")
                print(f"   2. Server was not restarted properly")
                print(f"\n   Please:")
                print(f"   - Fully stop the old server process")
                print(f"   - Run again: python jk.py")
                print(f"   - Refresh browser (Ctrl+F5)")
            else:
                print(f"   Response: {response.text[:500]}")
        else:
            print(f"   No records found. Please generate test data first.")
            print(f"\n   Run: python generate_test_data.py")
    else:
        print(f"   API error: {response.text}")
except Exception as e:
    print(f"   Request failed: {e}")
    import traceback
    traceback.print_exc()
