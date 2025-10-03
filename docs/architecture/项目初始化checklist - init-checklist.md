# GoMuseum 项目前置和初始化 Checklist ✅

## 环境准备
- [ ] Node.js v20.11 已安装（nvm）  
- [ ] Python 3.11 已安装（pyenv/venv）  
- [ ] Docker 25.x 已安装  
- [ ] PostgreSQL 16.x 已安装并启动  
- [ ] Redis 7.2.x 已安装并启动  
- [ ] Git 2.43 已安装，配置了用户名、邮箱、SSH key  

## GitHub 仓库
- [ ] 创建仓库 GoMuseum  
- [ ] 初始化 push 到 main  
- [ ] 创建 staging 分支  
- [ ] 创建 feature/init/basic-structure 分支  
- [ ] 设置分支保护规则（main → 严格，staging → 基础检查）  

## 项目结构
- [ ] backend/ FastAPI 框架目录已生成  
- [ ] frontend/gomuseum_app/ Flutter 框架目录已生成  
- [ ] deployment/、monitoring/、docs/ 等目录已生成  
- [ ] .github/workflows 已生成  

## 配置文件
- [ ] docker-compose.yml、staging、production 文件存在  
- [ ] backend 配置文件（Dockerfile、pyproject.toml、.flake8）存在  
- [ ] frontend 配置文件（pubspec.yaml、analysis_options.yaml）存在  
- [ ] .env.example 已创建  

## CI/CD
- [ ] .github/workflows/ci.yml 存在并配置  
- [ ] .github/workflows/deploy.yml 存在并配置  
- [ ] GitHub Secrets 设置（SONAR_TOKEN、CODECOV_TOKEN）  

## 脚本
- [ ] verify-environment.sh 已创建并通过  
- [ ] acceptance-test.sh 已创建并通过  

## 验收
- [ ] flutter analyze && flutter test ✅  
- [ ] pytest --cov ✅  
- [ ] docker-compose up 启动成功 ✅  
- [ ] GitHub Actions CI 工作流变绿 ✅  

## 下一步
- [ ] 初始化完成，进入 MVP 核心功能开发阶段  
