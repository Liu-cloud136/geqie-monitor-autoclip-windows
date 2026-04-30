#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试运行器 - 运行所有功能测试并生成结果文档
"""

import sys
import os
import time
from datetime import datetime
from io import StringIO

sys.path.insert(0, os.path.dirname(__file__))

ALL_TEST_RESULTS = {}

def capture_output(func):
    """捕获函数的输出"""
    old_stdout = sys.stdout
    sys.stdout = StringIO()
    
    try:
        result = func()
        output = sys.stdout.getvalue()
        return result, output
    finally:
        sys.stdout = old_stdout

def run_test_data_manager():
    """运行数据管理器测试"""
    print("\n" + "=" * 60)
    print("运行测试: test_data_manager.py")
    print("=" * 60)
    
    from test_data_manager import test_data_manager, TEST_RESULTS
    TEST_RESULTS.clear()
    
    results = test_data_manager()
    
    return {
        "name": "数据管理器测试",
        "file": "test_data_manager.py",
        "results": results,
        "passed": sum(1 for r in results if r['passed']),
        "failed": sum(1 for r in results if not r['passed'])
    }

def run_test_filter():
    """运行敏感词过滤测试"""
    print("\n" + "=" * 60)
    print("运行测试: test_filter.py")
    print("=" * 60)
    
    try:
        from test_filter import filter_sensitive_words, FILTER_ENABLE, SENSITIVE_WORDS, FILTER_ACTION
        
        test_cases = [
            ("你好，这是一个正常的消息", True),
            ("你这个傻逼", False),
            ("去死吧", False),
            ("垃圾人", False),
            ("快乐鸽子123", True),
            ("这是一个关于天安门的消息", False),
        ]
        
        results = []
        passed = 0
        failed = 0
        
        for message, expected_valid in test_cases:
            filtered, is_valid = filter_sensitive_words(message)
            status = is_valid == expected_valid
            results.append({
                "name": f"敏感词测试: {message[:20]}",
                "passed": status,
                "message": f"过滤后: {filtered}, 有效: {is_valid}, 期望: {expected_valid}",
                "timestamp": datetime.now().isoformat()
            })
            if status:
                passed += 1
            else:
                failed += 1
        
        for r in results:
            status = "PASS" if r['passed'] else "FAIL"
            print(f"  [{status}] {r['name']}")
        
        print(f"\n通过: {passed}, 失败: {failed}")
        
        return {
            "name": "敏感词过滤测试",
            "file": "test_filter.py",
            "results": results,
            "passed": passed,
            "failed": failed
        }
        
    except Exception as e:
        print(f"  测试失败: {e}")
        return {
            "name": "敏感词过滤测试",
            "file": "test_filter.py",
            "results": [{
                "name": "测试执行",
                "passed": False,
                "message": str(e),
                "timestamp": datetime.now().isoformat()
            }],
            "passed": 0,
            "failed": 1
        }

def run_test_api_rating():
    """运行评分API测试"""
    print("\n" + "=" * 60)
    print("运行测试: test_api_rating.py")
    print("=" * 60)
    
    try:
        from test_api_rating import test_rating_api, TEST_RESULTS, HAS_REQUESTS
        TEST_RESULTS.clear()
        
        if not HAS_REQUESTS:
            print("  警告: requests库未安装，跳过API测试")
            return {
                "name": "评分API测试",
                "file": "test_api_rating.py",
                "results": [{
                    "name": "环境检查",
                    "passed": False,
                    "message": "requests库未安装，无法进行API测试",
                    "timestamp": datetime.now().isoformat()
                }],
                "passed": 0,
                "failed": 1,
                "note": "请安装 requests: pip install requests"
            }
        
        results = test_rating_api()
        
        return {
            "name": "评分API测试",
            "file": "test_api_rating.py",
            "results": results,
            "passed": sum(1 for r in results if r['passed']),
            "failed": sum(1 for r in results if not r['passed'])
        }
        
    except Exception as e:
        print(f"  测试失败: {e}")
        import traceback
        traceback.print_exc()
        return {
            "name": "评分API测试",
            "file": "test_api_rating.py",
            "results": [{
                "name": "测试执行",
                "passed": False,
                "message": str(e),
                "timestamp": datetime.now().isoformat()
            }],
            "passed": 0,
            "failed": 1
        }

def run_test_email():
    """运行邮件功能测试"""
    print("\n" + "=" * 60)
    print("运行测试: test_email.py")
    print("=" * 60)
    
    try:
        from test_email import test_email_function, TEST_RESULTS
        TEST_RESULTS.clear()
        
        results = test_email_function()
        
        return {
            "name": "邮件功能测试",
            "file": "test_email.py",
            "results": results,
            "passed": sum(1 for r in results if r['passed']),
            "failed": sum(1 for r in results if not r['passed'])
        }
        
    except Exception as e:
        print(f"  测试失败: {e}")
        import traceback
        traceback.print_exc()
        return {
            "name": "邮件功能测试",
            "file": "test_email.py",
            "results": [{
                "name": "测试执行",
                "passed": False,
                "message": str(e),
                "timestamp": datetime.now().isoformat()
            }],
            "passed": 0,
            "failed": 1
        }

def generate_report(test_suites):
    """生成测试报告"""
    total_passed = sum(ts['passed'] for ts in test_suites)
    total_failed = sum(ts['failed'] for ts in test_suites)
    total_tests = total_passed + total_failed
    
    report_lines = []
    report_lines.append("=" * 70)
    report_lines.append("                    功能测试报告")
    report_lines.append("=" * 70)
    report_lines.append(f"\n生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    report_lines.append(f"测试总计: {total_tests} 项")
    report_lines.append(f"通过: {total_passed} 项 ({total_passed/total_tests*100:.1f}%)")
    report_lines.append(f"失败: {total_failed} 项 ({total_failed/total_tests*100:.1f}%)")
    
    report_lines.append("\n" + "=" * 70)
    report_lines.append("各测试套件结果")
    report_lines.append("=" * 70)
    
    for ts in test_suites:
        report_lines.append(f"\n【{ts['name']}】")
        report_lines.append(f"  文件: {ts['file']}")
        report_lines.append(f"  通过: {ts['passed']}, 失败: {ts['failed']}")
        
        if ts['results']:
            report_lines.append("  详细结果:")
            for r in ts['results']:
                status = "✓ PASS" if r['passed'] else "✗ FAIL"
                report_lines.append(f"    [{status}] {r['name']}")
                if r['message']:
                    report_lines.append(f"       {r['message']}")
    
    if total_failed > 0:
        report_lines.append("\n" + "=" * 70)
        report_lines.append("失败项汇总")
        report_lines.append("=" * 70)
        
        for ts in test_suites:
            failed_tests = [r for r in ts['results'] if not r['passed']]
            if failed_tests:
                report_lines.append(f"\n【{ts['name']}】")
                for r in failed_tests:
                    report_lines.append(f"  ✗ {r['name']}")
                    report_lines.append(f"    {r['message']}")
    
    report_lines.append("\n" + "=" * 70)
    report_lines.append("测试说明")
    report_lines.append("=" * 70)
    report_lines.append("""
1. 数据管理器测试 (test_data_manager.py)
   - 测试数据库迁移功能
   - 测试评分更新功能
   - 测试评分边界值验证
   - 测试评分邮件状态更新

2. 敏感词过滤测试 (test_filter.py)
   - 测试敏感词过滤功能
   - 测试正常消息放行

3. 评分API测试 (test_api_rating.py)
   - 需要服务器运行 (python jk.py)
   - 需要测试数据 (python generate_test_data.py)
   - 需要 requests 库 (pip install requests)

4. 邮件功能测试 (test_email.py)
   - 测试 EmailNotifier 类
   - 测试邮件内容生成
   - 测试配置获取

运行单个测试:
  python test_data_manager.py
  python test_filter.py
  python test_api_rating.py  (需要服务器运行)
  python test_email.py
""")
    
    report_text = "\n".join(report_lines)
    return report_text

def save_report(report_text, filename="test_report.txt"):
    """保存测试报告"""
    report_path = os.path.join(os.path.dirname(__file__), filename)
    
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write(report_text)
    
    print(f"\n报告已保存: {report_path}")
    return report_path

def main():
    """主函数"""
    print("\n" + "#" * 70)
    print("#                    功能测试运行器")
    print("#" * 70)
    print(f"\n开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    test_suites = []
    
    print("\n" + "#" * 70)
    print("# 第一阶段: 单元测试 (无需服务器)")
    print("#" * 70)
    
    test_suites.append(run_test_data_manager())
    test_suites.append(run_test_filter())
    test_suites.append(run_test_email())
    
    print("\n" + "#" * 70)
    print("# 第二阶段: API测试 (需要服务器运行)")
    print("#" * 70)
    
    test_suites.append(run_test_api_rating())
    
    print("\n" + "#" * 70)
    print("# 生成测试报告")
    print("#" * 70)
    
    report_text = generate_report(test_suites)
    print(report_text)
    
    save_report(report_text)
    
    total_passed = sum(ts['passed'] for ts in test_suites)
    total_failed = sum(ts['failed'] for ts in test_suites)
    
    print("\n" + "#" * 70)
    if total_failed == 0:
        print("#                    所有测试通过!")
    else:
        print(f"#                    测试完成，有 {total_failed} 项失败")
    print("#" * 70)
    
    return 0 if total_failed == 0 else 1

if __name__ == "__main__":
    sys.exit(main())
