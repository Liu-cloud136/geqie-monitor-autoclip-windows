#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
API层测试 - 测试评分API接口
测试文件: jk.py 中的 /api/record/rate 接口
"""

import sys
import os
import json
from datetime import datetime

sys.path.insert(0, os.path.dirname(__file__))

try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False
    print("警告: requests 库未安装，无法进行API测试")
    print("请运行: pip install requests")

TEST_RESULTS = []

def log_test_result(test_name, passed, message=""):
    """记录测试结果"""
    result = {
        "name": test_name,
        "passed": passed,
        "message": message,
        "timestamp": datetime.now().isoformat()
    }
    TEST_RESULTS.append(result)
    status = "PASS" if passed else "FAIL"
    print(f"  [{status}] {test_name}")
    if message:
        print(f"       {message}")

def test_rating_api():
    """测试评分API"""
    
    print("\n" + "=" * 60)
    print("测试: 评分API接口 (/api/record/rate)")
    print("=" * 60)
    
    if not HAS_REQUESTS:
        log_test_result("requests库检查", False, "requests库未安装，跳过API测试")
        return TEST_RESULTS
    
    base_url = "http://localhost:5000"
    
    # 1. 测试服务器连接
    print("\n1. 测试服务器连接...")
    try:
        response = requests.get(f"{base_url}/health", timeout=5)
        if response.status_code == 200:
            log_test_result("服务器连接", True, "服务器运行正常")
        else:
            log_test_result("服务器连接", False, f"状态码: {response.status_code}")
    except requests.exceptions.ConnectionError:
        log_test_result("服务器连接", False, "无法连接到服务器，请确保服务器已启动")
        print("\n提示: 请先运行 'python jk.py' 启动服务器")
        return TEST_RESULTS
    except Exception as e:
        log_test_result("服务器连接", False, f"连接错误: {e}")
        return TEST_RESULTS
    
    # 2. 测试获取测试数据
    print("\n2. 获取测试数据...")
    test_record = None
    try:
        response = requests.get(f"{base_url}/api/today", timeout=5)
        if response.status_code == 200:
            data = response.json()
            if data.get('success') and data.get('data') and len(data['data']) > 0:
                test_record = data['data'][0]
                log_test_result("获取测试数据", True, f"获取到记录 ID={test_record['id']}")
            else:
                log_test_result("获取测试数据", False, "没有测试数据，请先生成测试数据")
                print("\n提示: 请运行 'python generate_test_data.py' 生成测试数据")
        else:
            log_test_result("获取测试数据", False, f"API返回状态码: {response.status_code}")
    except Exception as e:
        log_test_result("获取测试数据", False, f"请求错误: {e}")
    
    if test_record is None:
        return TEST_RESULTS
    
    # 3. 测试评分API - 正常情况
    print("\n3. 测试评分API - 正常情况...")
    try:
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
        
        if response.status_code == 200:
            try:
                result = response.json()
                if result.get('success'):
                    log_test_result("正常评分", True, f"成功提交5星评分: {result.get('message')}")
                else:
                    log_test_result("正常评分", False, f"API返回错误: {result.get('error')}")
            except json.JSONDecodeError:
                log_test_result("正常评分", False, "返回内容不是有效的JSON")
                print(f"       原始响应: {response.text[:200]}")
        elif response.status_code == 404:
            log_test_result("正常评分", False, "路由未找到 (404)")
            print("       提示: 服务器可能运行旧代码，请重启服务器")
        else:
            log_test_result("正常评分", False, f"状态码: {response.status_code}")
            print(f"       响应: {response.text[:200]}")
            
    except Exception as e:
        log_test_result("正常评分", False, f"请求错误: {e}")
        import traceback
        traceback.print_exc()
    
    # 4. 测试评分API - 边界值
    print("\n4. 测试评分API - 边界值验证...")
    
    # 测试 0 星
    try:
        rating_data = {
            "id": test_record['id'],
            "rating": 0
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
        
        if response.status_code == 400:
            log_test_result("边界值 - 0星", True, "正确拒绝0星评分 (状态码400)")
        elif response.status_code == 200:
            result = response.json()
            if not result.get('success'):
                log_test_result("边界值 - 0星", True, "正确拒绝0星评分 (返回错误)")
            else:
                log_test_result("边界值 - 0星", False, "应该拒绝但接受了0星评分")
        else:
            log_test_result("边界值 - 0星", False, f"状态码: {response.status_code}")
    except Exception as e:
        log_test_result("边界值 - 0星", False, f"请求错误: {e}")
    
    # 测试 6 星
    try:
        rating_data = {
            "id": test_record['id'],
            "rating": 6
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
        
        if response.status_code == 400:
            log_test_result("边界值 - 6星", True, "正确拒绝6星评分 (状态码400)")
        elif response.status_code == 200:
            result = response.json()
            if not result.get('success'):
                log_test_result("边界值 - 6星", True, "正确拒绝6星评分 (返回错误)")
            else:
                log_test_result("边界值 - 6星", False, "应该拒绝但接受了6星评分")
        else:
            log_test_result("边界值 - 6星", False, f"状态码: {response.status_code}")
    except Exception as e:
        log_test_result("边界值 - 6星", False, f"请求错误: {e}")
    
    # 5. 测试评分API - 缺失参数
    print("\n5. 测试评分API - 缺失参数...")
    
    # 测试缺失 id
    try:
        rating_data = {
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
        
        if response.status_code == 400:
            log_test_result("缺失参数 - id", True, "正确拒绝缺失id的请求 (状态码400)")
        elif response.status_code == 200:
            result = response.json()
            if not result.get('success'):
                log_test_result("缺失参数 - id", True, "正确拒绝缺失id的请求 (返回错误)")
            else:
                log_test_result("缺失参数 - id", False, "应该拒绝但接受了缺失id的请求")
        else:
            log_test_result("缺失参数 - id", False, f"状态码: {response.status_code}")
    except Exception as e:
        log_test_result("缺失参数 - id", False, f"请求错误: {e}")
    
    # 测试缺失 rating
    try:
        rating_data = {
            "id": test_record['id']
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
        
        if response.status_code == 400:
            log_test_result("缺失参数 - rating", True, "正确拒绝缺失rating的请求 (状态码400)")
        elif response.status_code == 200:
            result = response.json()
            if not result.get('success'):
                log_test_result("缺失参数 - rating", True, "正确拒绝缺失rating的请求 (返回错误)")
            else:
                log_test_result("缺失参数 - rating", False, "应该拒绝但接受了缺失rating的请求")
        else:
            log_test_result("缺失参数 - rating", False, f"状态码: {response.status_code}")
    except Exception as e:
        log_test_result("缺失参数 - rating", False, f"请求错误: {e}")
    
    # 6. 测试评分API - 无效的记录ID
    print("\n6. 测试评分API - 无效的记录ID...")
    try:
        rating_data = {
            "id": 999999999,
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
        
        if response.status_code == 404:
            log_test_result("无效记录ID", True, "正确返回404表示记录不存在")
        elif response.status_code == 200:
            result = response.json()
            if not result.get('success'):
                log_test_result("无效记录ID", True, "正确拒绝无效记录ID的请求")
            else:
                log_test_result("无效记录ID", False, "应该拒绝但接受了无效记录ID的请求")
        else:
            log_test_result("无效记录ID", False, f"状态码: {response.status_code}")
    except Exception as e:
        log_test_result("无效记录ID", False, f"请求错误: {e}")
    
    # 输出测试汇总
    print("\n" + "=" * 60)
    print("评分API测试汇总")
    print("=" * 60)
    
    passed = sum(1 for r in TEST_RESULTS if r['passed'])
    failed = sum(1 for r in TEST_RESULTS if not r['passed'])
    
    print(f"\n通过: {passed}, 失败: {failed}")
    
    if failed > 0:
        print("\n失败的测试:")
        for r in TEST_RESULTS:
            if not r['passed']:
                print(f"  - {r['name']}: {r['message']}")
    
    return TEST_RESULTS

if __name__ == "__main__":
    test_rating_api()
