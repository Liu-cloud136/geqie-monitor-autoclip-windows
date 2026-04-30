#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
为现有项目生成切片缩略图的脚本
"""

import sys
import io
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from utils.thumbnail_generator import ThumbnailGenerator
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def generate_clip_thumbnails_for_project(project_id: str):
    """为指定项目的所有切片生成缩略图"""
    from core.path_utils import get_project_output_directory
    
    # 获取项目的clips目录
    clips_dir = get_project_output_directory(project_id) / "clips"
    
    if not clips_dir.exists():
        print(f"❌ 切片目录不存在: {clips_dir}")
        return False
    
    # 获取所有mp4文件
    clip_files = list(clips_dir.glob("*.mp4"))
    
    if not clip_files:
        print(f"❌ 没有找到切片文件")
        return False
    
    print(f"📋 找到 {len(clip_files)} 个切片文件")
    
    # 创建缩略图生成器
    thumbnail_generator = ThumbnailGenerator()
    
    success_count = 0
    for clip_file in clip_files:
        try:
            # 生成缩略图路径
            thumbnail_path = clip_file.parent / f"{clip_file.stem}_thumbnail.jpg"
            
            # 检查缩略图是否已存在
            if thumbnail_path.exists():
                print(f"✅ 缩略图已存在，跳过: {thumbnail_path.name}")
                success_count += 1
                continue
            
            print(f"🎬 正在为切片生成缩略图: {clip_file.name}")
            
            # 生成缩略图
            generated_thumbnail = thumbnail_generator.generate_thumbnail(
                video_path=clip_file,
                width=320,
                height=180
            )
            
            if generated_thumbnail:
                print(f"✅ 缩略图生成成功: {generated_thumbnail.name}")
                success_count += 1
            else:
                print(f"❌ 缩略图生成失败: {clip_file.name}")
                
        except Exception as e:
            print(f"❌ 处理切片 {clip_file.name} 时发生错误: {e}")
            continue
    
    print(f"🎉 完成！成功生成 {success_count}/{len(clip_files)} 个缩略图")
    return success_count == len(clip_files)

def main():
    """主函数"""
    if len(sys.argv) > 1:
        # 为指定项目生成缩略图
        project_id = sys.argv[1]
        print(f"🚀 开始为项目 {project_id} 生成切片缩略图...")
        if generate_clip_thumbnails_for_project(project_id):
            print("🎉 所有切片缩略图生成完成！")
        else:
            print("⚠️ 部分切片缩略图生成失败")
            sys.exit(1)
    else:
        print("❌ 请提供项目ID")
        print("用法: python generate_clip_thumbnails.py <project_id>")
        sys.exit(1)

if __name__ == "__main__":
    main()