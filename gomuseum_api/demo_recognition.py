#!/usr/bin/env python3
"""
临时的演示识别API - 用于Step 2演示
"""
from fastapi import APIRouter, UploadFile, HTTPException, File
from pydantic import BaseModel
import base64
from typing import Optional
import json

router = APIRouter()

class DemoRecognitionRequest(BaseModel):
    image: str  # base64编码的图片
    format: Optional[str] = "base64"
    language: Optional[str] = "zh"

class ArtworkCandidate(BaseModel):
    artwork_id: str = "mona_lisa_001"  # 添加artwork_id
    name: str  # 重命名为name
    artist: str  # 重命名为artist
    confidence: float
    museum: str
    period: str  # 重命名为period
    image_url: str = None  # 添加image_url
    description: str = None  # 可选字段

class RecognitionData(BaseModel):
    candidates: list[ArtworkCandidate]
    processing_time: float
    cached: bool = False

class DemoRecognitionResponse(BaseModel):
    success: bool
    data: RecognitionData
    mock_response: bool = True

@router.post("/api/v1/recognition/demo", response_model=DemoRecognitionResponse)
async def demo_recognize(request: DemoRecognitionRequest):
    """演示识别API - 返回模拟的识别结果"""
    
    try:
        # 简单验证base64图片
        if request.format == "base64":
            try:
                # 处理data URI格式
                image_data = request.image
                if image_data.startswith("data:"):
                    # 提取Base64部分
                    image_data = image_data.split(",")[1]
                
                image_bytes = base64.b64decode(image_data)
                if len(image_bytes) < 10:  # 降低最小限制用于测试
                    raise ValueError("图片数据过小")
            except Exception as e:
                raise HTTPException(status_code=400, detail="无效的图片格式")
        
        # 创建候选作品
        candidate = ArtworkCandidate(
            artwork_id="mona_lisa_001",
            name="蒙娜丽莎",
            artist="莱奥纳多·达·芬奇",
            confidence=0.92,
            museum="卢浮宫博物馆",
            period="1503-1519",
            description="这是一幅世界闻名的肖像画作品，展现了文艺复兴时期的艺术特色。画中人物神秘的微笑和细腻的绘画技法令人印象深刻。"
        )
        
        # 创建识别数据
        data = RecognitionData(
            candidates=[candidate],
            processing_time=0.15,  # 模拟处理时间
            cached=False
        )
        
        # 返回模拟识别结果
        return DemoRecognitionResponse(
            success=True,
            data=data,
            mock_response=True
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"识别服务错误: {str(e)}")

# 为了兼容性，也提供文件上传版本
@router.post("/api/v1/recognition/demo-upload")
async def demo_recognize_upload(file: UploadFile = File(...)):
    """演示识别API - 文件上传版本"""
    
    try:
        # 读取文件内容
        image_bytes = await file.read()
        
        if len(image_bytes) < 100:
            raise HTTPException(status_code=400, detail="文件过小")
        
        # 创建候选作品
        candidate = ArtworkCandidate(
            artwork_id="starry_night_001",
            name="星夜",
            artist="文森特·梵高",
            confidence=0.88,
            museum="现代艺术博物馆",
            period="1889",
            description="这是梵高最著名的作品之一，以其独特的漩涡状笔触和鲜明的色彩而闻名。画作展现了夜空下的村庄景象。"
        )
        
        # 创建识别数据
        data = RecognitionData(
            candidates=[candidate],
            processing_time=0.22,
            cached=False
        )
        
        # 返回模拟识别结果
        return DemoRecognitionResponse(
            success=True,
            data=data,
            mock_response=True
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"识别服务错误: {str(e)}")

# 健康检查
@router.get("/api/v1/recognition/demo-health")
async def demo_health():
    """演示API健康检查"""
    return {"status": "healthy", "message": "Demo recognition service is running"}