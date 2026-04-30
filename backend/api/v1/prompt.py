"""
提示词 API 路由
提供获取提示词文件的接口
"""
from fastapi import APIRouter, HTTPException
from pathlib import Path

router = APIRouter()

# 提示词文件映射
PROMPT_FILES = {
    "step1_outline": "大纲.txt",
    "step2_timeline": "时间点.txt",
    "step3_scoring": "推荐理由.txt",
    "step4_title": "标题生成.txt"
}

@router.get("/{step_type}")
async def get_prompt(step_type: str):
    """获取指定步骤的提示词内容"""
    if step_type not in PROMPT_FILES:
        return {"prompt": None, "message": "该步骤没有提示词"}
    
    prompt_file = Path(__file__).parent.parent.parent / "prompt" / PROMPT_FILES[step_type]
    
    if not prompt_file.exists():
        return {"prompt": None, "message": "提示词文件不存在"}
    
    with open(prompt_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    return {"prompt": content}
