import asyncio
import edge_tts
from fastapi import APIRouter, Request, Response, HTTPException
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/tts", tags=["tts"])

DEFAULT_VOICE = "zh-CN-XiaoxiaoNeural"

@router.post("/synthesize")
async def synthesize(request: Request):
    body = await request.body()
    # 从 SSML 中提取文本和语音名称（简单提取，也可完整解析 SSML）
    text = extract_text_from_ssml(body.decode("utf-8"))
    voice = extract_voice_from_ssml(body.decode("utf-8")) or DEFAULT_VOICE
    
    try:
        # 使用 edge-tts 生成音频
        communicate = edge_tts.Communicate(text, voice)
        audio_data = b""
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                audio_data += chunk["data"]
        
        return Response(content=audio_data, media_type="audio/mpeg")
    except Exception as e:
        logger.exception("Edge TTS 生成失败")
        raise HTTPException(status_code=502, detail=f"TTS 失败: {str(e)}")

def extract_text_from_ssml(ssml: str) -> str:
    # 简单提取：去掉标签，只保留内容（可根据需要完善）
    import re
    text = re.sub(r"<[^>]+>", "", ssml)
    return text.strip()

def extract_voice_from_ssml(ssml: str) -> str:
    import re
    match = re.search(r'voice name="([^"]+)"', ssml)
    return match.group(1) if match else None