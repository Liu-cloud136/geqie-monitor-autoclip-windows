#!/usr/bin/env python3
"""验证 NLP 库安装是否成功"""

print("=" * 50)
print("验证 NLP 库安装")
print("=" * 50)

# 1. 验证 Flask
try:
    import flask
    print(f"[OK] Flask: {flask.__version__}")
except ImportError as e:
    print(f"[FAIL] Flask: {e}")

# 2. 验证 SnowNLP (情感分析)
try:
    from snownlp import SnowNLP
    s = SnowNLP('这个产品真的很好用')
    print(f"[OK] SnowNLP: 情感分数 = {s.sentiments:.2f}")
except ImportError as e:
    print(f"[FAIL] SnowNLP: {e}")

# 3. 验证 jieba (分词)
try:
    import jieba
    words = list(jieba.cut('我喜欢使用Python编程'))
    print(f"[OK] jieba: 分词结果 = {' '.join(words)}")
except ImportError as e:
    print(f"[FAIL] jieba: {e}")

# 4. 验证 wordcloud
try:
    import wordcloud
    print(f"[OK] wordcloud: {wordcloud.__version__}")
except ImportError as e:
    print(f"[FAIL] wordcloud: {e}")

# 5. 验证 bilibili-api-python
try:
    import bilibili_api
    print(f"[OK] bilibili-api-python: 已安装")
except ImportError as e:
    print(f"[FAIL] bilibili-api-python: {e}")

# 6. 验证 danmaku_analyzer 模块
try:
    from danmaku_analyzer import get_danmaku_analyzer, DanmakuAnalyzer, SentimentType
    print(f"[OK] danmaku_analyzer 模块: 已加载")
    
    # 测试分析器
    analyzer = get_danmaku_analyzer()
    print(f"[OK] DanmakuAnalyzer 实例: 创建成功")
    
    # 测试情感分析
    test_text = '今天天气真好，心情愉快！'
    score, sentiment = analyzer.analyze_sentiment(test_text)
    print(f"[OK] 情感分析测试: \"{test_text}\"")
    print(f"     - 情感分数: {score:.2f}")
    print(f"     - 情感类型: {sentiment.value}")
    
    # 测试关键词提取
    keywords = analyzer.extract_keywords(test_text, topK=3)
    print(f"[OK] 关键词提取: {keywords}")
    
except ImportError as e:
    print(f"[FAIL] danmaku_analyzer 模块: {e}")
except Exception as e:
    print(f"[WARN] danmaku_analyzer 测试: {e}")

print("")
print("=" * 50)
print("验证完成！")
print("=" * 50)
