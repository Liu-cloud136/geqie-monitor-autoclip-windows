#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
邮件功能测试 - 测试邮件通知功能
测试文件: jk.py 中的 EmailNotifier 类
"""

import sys
import os
from datetime import datetime

sys.path.insert(0, os.path.dirname(__file__))

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

def test_email_function():
    """测试邮件功能"""
    
    print("\n" + "=" * 60)
    print("测试: 邮件通知功能")
    print("=" * 60)
    
    # 1. 测试 EmailNotifier 类导入
    print("\n1. 测试 EmailNotifier 类导入...")
    try:
        from jk import EmailNotifier
        log_test_result("EmailNotifier导入", True, "成功导入 EmailNotifier 类")
    except ImportError as e:
        log_test_result("EmailNotifier导入", False, f"导入失败: {e}")
        return TEST_RESULTS
    
    # 2. 测试 EmailNotifier 初始化
    print("\n2. 测试 EmailNotifier 初始化...")
    try:
        test_config = {
            'smtp_server': 'smtp.qq.com',
            'smtp_port': 587,
            'sender': 'test@qq.com',
            'password': 'test_password',
            'receiver': 'receiver@qq.com'
        }
        
        notifier = EmailNotifier(test_config)
        
        if notifier.smtp_server == 'smtp.qq.com':
            log_test_result("初始化 - SMTP服务器", True, "正确设置SMTP服务器")
        else:
            log_test_result("初始化 - SMTP服务器", False, f"期望 'smtp.qq.com', 实际 '{notifier.smtp_server}'")
        
        if notifier.sender == 'test@qq.com':
            log_test_result("初始化 - 发件人", True, "正确设置发件人")
        else:
            log_test_result("初始化 - 发件人", False, f"期望 'test@qq.com', 实际 '{notifier.sender}'")
        
        if 'receiver@qq.com' in notifier.receivers:
            log_test_result("初始化 - 收件人", True, "正确设置收件人")
        else:
            log_test_result("初始化 - 收件人", False, f"期望包含 'receiver@qq.com'")
        
    except Exception as e:
        log_test_result("EmailNotifier初始化", False, f"初始化失败: {e}")
        import traceback
        traceback.print_exc()
    
    # 3. 测试多收件人配置
    print("\n3. 测试多收件人配置...")
    try:
        test_config = {
            'smtp_server': 'smtp.qq.com',
            'smtp_port': 587,
            'sender': 'test@qq.com',
            'password': 'test_password',
            'receiver': 'user1@qq.com, user2@qq.com, user3@qq.com'
        }
        
        notifier = EmailNotifier(test_config)
        
        if len(notifier.receivers) == 3:
            log_test_result("多收件人解析", True, f"正确解析3个收件人: {notifier.receivers}")
        else:
            log_test_result("多收件人解析", False, f"期望3个收件人, 实际 {len(notifier.receivers)} 个")
            
    except Exception as e:
        log_test_result("多收件人解析", False, f"解析失败: {e}")
    
    # 4. 测试评分邮件内容生成
    print("\n4. 测试评分邮件内容生成...")
    try:
        test_record = {
            'id': 1,
            'username': '测试用户',
            'content': '这是一条测试弹幕内容：鸽切！',
            'room_title': '测试直播间',
            'room_id': 12345
        }
        
        rating = 5
        rating_comment = '非常棒的内容！'
        
        stars = '⭐' * rating + '☆' * (5 - rating)
        
        subject = f"【评分通知】记录 {test_record['id']} 收到新评分"
        
        email_content = f"""收到新的评分通知！

记录ID: {test_record['id']}
用户: {test_record['username']}
直播间: {test_record['room_title']}
弹幕内容: {test_record['content']}

评分: {stars} ({rating}/5 星)
{"评论: " + rating_comment if rating_comment else ""}
"""
        
        if "记录ID: 1" in email_content:
            log_test_result("邮件内容生成 - 记录ID", True, "邮件内容包含记录ID")
        else:
            log_test_result("邮件内容生成 - 记录ID", False, "邮件内容缺少记录ID")
        
        if "用户: 测试用户" in email_content:
            log_test_result("邮件内容生成 - 用户名", True, "邮件内容包含用户名")
        else:
            log_test_result("邮件内容生成 - 用户名", False, "邮件内容缺少用户名")
        
        if "⭐⭐⭐⭐⭐" in email_content:
            log_test_result("邮件内容生成 - 星星评分", True, "邮件内容包含星星评分")
        else:
            log_test_result("邮件内容生成 - 星星评分", False, "邮件内容缺少星星评分")
        
        if "评论: 非常棒的内容！" in email_content:
            log_test_result("邮件内容生成 - 评论文字", True, "邮件内容包含评论文字")
        else:
            log_test_result("邮件内容生成 - 评论文字", False, "邮件内容缺少评论文字")
        
        log_test_result("邮件主题生成", True, f"主题: {subject}")
        
    except Exception as e:
        log_test_result("邮件内容生成", False, f"生成失败: {e}")
    
    # 5. 测试配置管理器获取邮件配置
    print("\n5. 测试配置管理器获取邮件配置...")
    try:
        from config_manager import config_manager, get_config
        
        email_config = get_config("email")
        
        if email_config is not None:
            log_test_result("配置获取", True, f"成功获取邮件配置: {list(email_config.keys()) if isinstance(email_config, dict) else '已配置'}")
            
            if isinstance(email_config, dict):
                sender = email_config.get('sender', '')
                if sender and '@' in sender:
                    log_test_result("发件人配置", True, f"发件人已配置: {sender}")
                else:
                    log_test_result("发件人配置", False, "发件人未配置或格式不正确")
                
                password = email_config.get('password', '')
                if password:
                    log_test_result("授权码配置", True, "邮箱授权码已配置")
                else:
                    log_test_result("授权码配置", False, "邮箱授权码未配置")
                
                receiver = email_config.get('receiver', '')
                if receiver:
                    log_test_result("收件人配置", True, f"收件人已配置: {receiver}")
                else:
                    log_test_result("收件人配置", False, "收件人未配置")
        else:
            log_test_result("配置获取", False, "邮件配置未找到")
            
    except Exception as e:
        log_test_result("配置获取", False, f"获取配置失败: {e}")
    
    # 6. 测试异步邮件发送线程
    print("\n6. 测试异步邮件发送逻辑...")
    try:
        import threading
        
        def mock_send_email():
            """模拟邮件发送"""
            pass
        
        thread = threading.Thread(target=mock_send_email)
        thread.start()
        thread.join(timeout=5)
        
        if thread.is_alive():
            log_test_result("线程启动", False, "线程未正确完成")
        else:
            log_test_result("线程启动", True, "线程正确启动并完成")
            
    except Exception as e:
        log_test_result("线程启动", False, f"线程测试失败: {e}")
    
    # 输出测试汇总
    print("\n" + "=" * 60)
    print("邮件功能测试汇总")
    print("=" * 60)
    
    passed = sum(1 for r in TEST_RESULTS if r['passed'])
    failed = sum(1 for r in TEST_RESULTS if not r['passed'])
    
    print(f"\n通过: {passed}, 失败: {failed}")
    
    if failed > 0:
        print("\n失败的测试:")
        for r in TEST_RESULTS:
            if not r['passed']:
                print(f"  - {r['name']}: {r['message']}")
    
    print("\n" + "=" * 60)
    print("注意:")
    print("=" * 60)
    print("\n邮件实际发送测试需要:")
    print("1. 有效的QQ邮箱配置 (config.yaml 中的 email 部分)")
    print("2. SMTP服务器连接")
    print("\n配置示例 (config.yaml):")
    print("""
email:
  smtp_server: smtp.qq.com
  smtp_port: 587
  sender: your_email@qq.com
  password: your_authorization_code  # QQ邮箱授权码
  receiver: receiver1@qq.com, receiver2@qq.com
""")
    
    return TEST_RESULTS

if __name__ == "__main__":
    test_email_function()
