#!/usr/bin/env python3
"""
GoMuseum 项目验证脚本
验证项目结构和配置文件是否正确
"""

import os
import json
from pathlib import Path

def check_file(file_path, description):
    """检查文件是否存在"""
    if os.path.exists(file_path):
        print(f"✅ {description}: {file_path}")
        return True
    else:
        print(f"❌ {description}: {file_path} (缺失)")
        return False

def check_directory(dir_path, description):
    """检查目录是否存在"""
    if os.path.isdir(dir_path):
        print(f"✅ {description}: {dir_path}")
        return True
    else:
        print(f"❌ {description}: {dir_path} (缺失)")
        return False

def main():
    print("🔍 GoMuseum 项目结构验证")
    print("=" * 40)
    
    base_dir = Path(__file__).parent.parent
    print(f"📁 项目根目录: {base_dir}")
    print()
    
    # 检查项目结构
    print("📋 检查项目结构:")
    structure_checks = [
        # Flutter App
        (f"{base_dir}/gomuseum_app", "Flutter应用目录"),
        (f"{base_dir}/gomuseum_app/pubspec.yaml", "Flutter配置文件"),
        (f"{base_dir}/gomuseum_app/lib/main.dart", "Flutter主文件"),
        
        # FastAPI Backend  
        (f"{base_dir}/gomuseum_api", "API后端目录"),
        (f"{base_dir}/gomuseum_api/requirements.txt", "Python依赖文件"),
        (f"{base_dir}/gomuseum_api/app/main.py", "FastAPI主文件"),
        (f"{base_dir}/gomuseum_api/app/core/config.py", "配置文件"),
        
        # Docker配置
        (f"{base_dir}/docker-compose.yml", "Docker Compose配置"),
        (f"{base_dir}/docker/Dockerfile.api", "API Dockerfile"),
        
        # 配置文件
        (f"{base_dir}/.env.example", "环境变量模板"),
        (f"{base_dir}/.gitignore", "Git忽略文件"),
        (f"{base_dir}/README.md", "项目说明"),
    ]
    
    passed = 0
    total = len(structure_checks)
    
    for file_path, description in structure_checks:
        if os.path.isdir(file_path):
            if check_directory(file_path, description):
                passed += 1
        else:
            if check_file(file_path, description):
                passed += 1
    
    print()
    print("📊 API端点检查:")
    api_files = [
        (f"{base_dir}/gomuseum_api/app/api/v1/health.py", "健康检查端点"),
        (f"{base_dir}/gomuseum_api/app/api/v1/recognition.py", "识别端点"),
        (f"{base_dir}/gomuseum_api/app/api/v1/explanation.py", "讲解端点"),
        (f"{base_dir}/gomuseum_api/app/api/v1/user.py", "用户端点"),
    ]
    
    for file_path, description in api_files:
        if check_file(file_path, description):
            passed += 1
        total += 1
    
    print()
    print("🗄️ 数据模型检查:")
    model_files = [
        (f"{base_dir}/gomuseum_api/app/models/user.py", "用户模型"),
        (f"{base_dir}/gomuseum_api/app/models/artwork.py", "艺术品模型"),
        (f"{base_dir}/gomuseum_api/app/models/museum.py", "博物馆模型"),
        (f"{base_dir}/gomuseum_api/app/models/recognition_cache.py", "缓存模型"),
    ]
    
    for file_path, description in model_files:
        if check_file(file_path, description):
            passed += 1
        total += 1
    
    print()
    print("🔧 服务层检查:")
    service_files = [
        (f"{base_dir}/gomuseum_api/app/services/recognition_service.py", "识别服务"),
        (f"{base_dir}/gomuseum_api/app/services/explanation_service.py", "讲解服务"),
    ]
    
    for file_path, description in service_files:
        if check_file(file_path, description):
            passed += 1
        total += 1
    
    print()
    print("=" * 40)
    print(f"📈 验证结果: {passed}/{total} ({passed/total*100:.1f}%)")
    
    if passed == total:
        print("🎉 所有检查通过！项目结构完整")
        print("\n📋 下一步:")
        print("1. 运行 './scripts/start.sh' 启动开发环境")
        print("2. 访问 http://localhost:8000/docs 查看API文档")
        print("3. 开始实施 Step 2 - AI识别功能")
    else:
        print("⚠️  部分文件缺失，请检查项目结构")
        
    print()
    print("🛠 开发命令:")
    print("- 启动环境: ./scripts/start.sh")
    print("- Docker状态: docker-compose ps")
    print("- 查看日志: docker-compose logs api")
    print("- 停止服务: docker-compose down")

if __name__ == "__main__":
    main()