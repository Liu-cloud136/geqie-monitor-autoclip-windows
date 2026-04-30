#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Test rating API"""

import requests
import json

base_url = "http://localhost:5000"

print("=" * 60)
print("Test Rating API")
print("=" * 60)

print("\n1. Test server connection...")
response = requests.get(base_url + "/health", timeout=5)
print("   Status code:", response.status_code)

print("\n2. Get a record for testing...")
response = requests.get(base_url + "/api/today", timeout=5)
print("   Status code:", response.status_code)
data = response.json()

if data.get('success') and data.get('data') and len(data['data']) > 0:
    test_record = data['data'][0]
    record_id = test_record['id']
    print("   Got record ID:", record_id)
    print("\n3. Test rating API (Record ID:", record_id, ")...")
    
    rating_data = {
        "id": record_id,
        "rating": 5
    }
    
    headers = {
        "Content-Type": "application/json"
    }
    
    response = requests.post(
        base_url + "/api/record/rate",
        json=rating_data,
        headers=headers,
        timeout=10
    )
    
    print("   Status code:", response.status_code)
    print("   Content-Type:", response.headers.get('Content-Type', 'unknown'))
    
    if response.status_code == 200:
        try:
            result = response.json()
            print("   Response:", json.dumps(result, ensure_ascii=False))
            if result.get('success'):
                print("\n" + "=" * 60)
                print("SUCCESS! Rating API works!")
                print("=" * 60)
            else:
                print("\nRating failed:", result.get('error', 'Unknown error'))
        except Exception as e:
            print("   JSON parse error:", e)
            print("   Raw response:", response.text[:500])
    elif response.status_code == 404:
        print("\n   404 Not Found - Route not found!")
        print("\n   This means:")
        print("   1. Server is running OLD code, OR")
        print("   2. Server was NOT restarted properly")
        print("\n   Please:")
        print("   - FULLY stop the old server process")
        print("   - Run again: python jk.py")
        print("   - Refresh browser (Ctrl+F5)")
    else:
        print("   Response:", response.text[:500])
else:
    print("   No records found. Please generate test data first.")
    print("\n   Run: python generate_test_data.py")
