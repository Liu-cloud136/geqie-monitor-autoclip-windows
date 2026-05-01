#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import yaml

try:
    with open(r'd:\jz\5\monitor\config.yaml', 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)
    print("YAML 解析成功")
    print("auto_clip 配置:")
    print(config.get('auto_clip', {}))
except Exception as e:
    print(f"YAML 解析失败: {e}")
