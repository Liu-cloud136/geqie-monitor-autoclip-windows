"""
AI 流式调用 API 路由
借鉴 author 项目设计，支持 SSE 流式响应
"""
from typing import Optional, AsyncGenerator
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
import json
import logging

from core.llm_manager import get_llm_manager, ProviderType, APIFormat

logger = logging.getLogger(__name__)

router = APIRouter()

class AIRequest(BaseModel):
    """AI 请求模型"""
    prompt: str
    input_data: Optional[dict] = None
    temperature: Optional[float] = None
    top_p: Optional[float] = None
    max_tokens: Optional[int] = None

@router.post("/")
async def ai_stream(request: AIRequest):
    """流式 AI 调用（SSE）"""
    from fastapi.responses import StreamingResponse
    
    try:
        llm_manager = get_llm_manager()
        
        # 生成流式响应
        async def generate() -> AsyncGenerator[str, None]:
            try:
                async for chunk in llm_manager.stream_call(
                    prompt=request.prompt,
                    input_data=request.input_data,
                    temperature=request.temperature,
                    top_p=request.top_p,
                    max_tokens=request.max_tokens
                ):
                    # 转换为 SSE 格式
                    if "text" in chunk:
                        yield f"data: {json.dumps({'text': chunk['text']}, ensure_ascii=False)}\n\n"
                    if "thinking" in chunk:
                        yield f"data: {json.dumps({'thinking': chunk['thinking']}, ensure_ascii=False)}\n\n"
                    if "usage" in chunk:
                        yield f"data: {json.dumps({'usage': chunk['usage']}, ensure_ascii=False)}\n\n"
                    if chunk.get("done"):
                        yield "data: [DONE]\n\n"
            except Exception as e:
                logger.error(f"流式生成错误: {e}")
                yield f"data: {json.dumps({'error': str(e)}, ensure_ascii=False)}\n\n"
        
        return StreamingResponse(
            generate(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
            }
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI 调用失败: {e}")

@router.post("/chat")
async def ai_chat_stream(request: AIRequest):
    """聊天模式的流式 AI 调用"""
    from fastapi.responses import StreamingResponse
    
    try:
        llm_manager = get_llm_manager()
        
        async def generate() -> AsyncGenerator[str, None]:
            try:
                async for chunk in llm_manager.stream_call(
                    prompt=request.prompt,
                    input_data=request.input_data,
                    temperature=request.temperature,
                    top_p=request.top_p,
                    max_tokens=request.max_tokens
                ):
                    if "text" in chunk:
                        yield f"data: {json.dumps({'content': chunk['text']}, ensure_ascii=False)}\n\n"
                    if "thinking" in chunk:
                        yield f"data: {json.dumps({'reasoning': chunk['thinking']}, ensure_ascii=False)}\n\n"
                    if "usage" in chunk:
                        yield f"data: {json.dumps({'usage': chunk['usage']}, ensure_ascii=False)}\n\n"
                    if chunk.get("done"):
                        yield "data: [DONE]\n\n"
            except Exception as e:
                logger.error(f"聊天流式生成错误: {e}")
                yield f"data: {json.dumps({'error': str(e)}, ensure_ascii=False)}\n\n"
        
        return StreamingResponse(
            generate(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
            }
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"聊天 AI 调用失败: {e}")
