#!/usr/bin/env python3
"""
测试敏感词过滤功能
"""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from jk import filter_sensitive_words, FILTER_ENABLE, SENSITIVE_WORDS, FILTER_ACTION

print("=" * 60)
print("敏感词过滤测试")
print("=" * 60)
print(f"过滤启用: {FILTER_ENABLE}")
print(f"敏感词数量: {len(SENSITIVE_WORDS)}")
print(f"过滤动作: {FILTER_ACTION}")
print("=" * 60)

# 测试用例
test_cases = [
    ("你好，这是一个正常的消息", True),
    ("你这个傻逼", False),
    ("去死吧", False),
    ("垃圾人", False),
    ("快乐鸽子123", True),
    ("这是一个关于天安门的消息", False),
]

print("\n开始测试:")
print("-" * 60)

for message, expected_valid in test_cases:
    filtered, is_valid = filter_sensitive_words(message)
    status = "✓" if is_valid == expected_valid else "✗"
    print(f"{status} 原文: {message}")
    print(f"  过滤后: {filtered}")
    print(f"  有效: {is_valid} (期望: {expected_valid})")
    print("-" * 60)

print("\n测试完成！")
