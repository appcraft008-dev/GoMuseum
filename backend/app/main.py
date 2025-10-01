# backend/app/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(
    title="GoMuseum API",
    description="Backend API service for GoMuseum project",
    version="0.1.0"
)

# 允许跨域（前端访问）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 可以改成前端的实际域名
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def root():
    return {"message": "Welcome to GoMuseum API"}

@app.get("/api/health/")
def health_check():
    """健康检查端点，用于docker-compose验收脚本"""
    return {"status": "ok"}

@app.get("/api/info/")
def project_info():
    return {
        "project": "GoMuseum",
        "version": "0.1.0",
        "description": "An AI-powered museum guide platform."
    }

