# GoMuseum 项目前置和初始化实操手册（详细版）

## 🎯 手册目标
- 标准化环境搭建流程（避免因版本/缺依赖反复踩坑）  
- 一次性建立目录结构、配置文件、GitHub 仓库、CI/CD 流程  
- 保证通过环境验证脚本和初始化验收脚本  
- 形成可复用模板，后续任何新项目直接套用  

---

## 1️⃣ 开发环境准备

### 1.1 必备软件安装（Mac mini / Linux）
```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

brew install nvm pyenv git redis postgresql@16
brew install --cask docker

# Node.js
mkdir ~/.nvm
echo 'export NVM_DIR="$HOME/.nvm"' >> ~/.zshrc
echo '[ -s "/opt/homebrew/opt/nvm/nvm.sh" ] && \. "/opt/homebrew/opt/nvm/nvm.sh"' >> ~/.zshrc
source ~/.zshrc
nvm install 20.11.0
nvm alias default 20.11.0

# Python
echo 'eval "$(pyenv init --path)"' >> ~/.zprofile
source ~/.zprofile
pyenv install 3.11.7
pyenv global 3.11.7
```

### 1.2 版本验证
```bash
node -v              # v20.11.x
npm -v               # 10.x
python3 --version    # 3.11.x
docker --version     # 25.x
docker compose version
psql --version       # PostgreSQL 16.x
redis-server --version # Redis 7.2.x
git --version        # 2.43.x
```

### 1.3 Git 配置
```bash
git config --global user.name "你的名字"
git config --global user.email "你的邮箱"
ssh-keygen -t ed25519 -C "你的邮箱"
cat ~/.ssh/id_ed25519.pub
```
👉 添加到 GitHub → Settings → SSH and GPG Keys。

### 1.4 Python 虚拟环境
```bash
cd gomuseum
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
```

---

## 2️⃣ GitHub 仓库准备

### 2.1 创建仓库
- GitHub → New repository → 名称：`GoMuseum`  
- 初始化选项：`.gitignore` → Python + Node，License → MIT，README.md  

### 2.2 本地初始化并推送
```bash
git init
git add .
git commit -m "chore: initial commit"
git branch -M main
git remote add origin git@github.com:<your-username>/GoMuseum.git
git push -u origin main
```

### 2.3 创建分支
```bash
git checkout -b staging
git push origin staging

git checkout -b feature/init/basic-structure
git push -u origin feature/init/basic-structure
```

### 2.4 分支保护规则
- main: 禁止直接 push，必须 PR + CI  
- staging: 允许 push，但要求基础 CI  

---

## 3️⃣ 项目目录结构

在 gomuseum/ 下创建：

```bash
gomuseum/
├── README.md
├── docker-compose.yml
├── docker-compose.staging.yml
├── docker-compose.production.yml
├── .env.example
├── .gitignore
├── Makefile
├── backend/{app,tests,alembic,scripts,requirements}
├── frontend/gomuseum_app/{lib,test,integration_test,assets,android,ios,web}
├── deployment/{nginx,docker,terraform,kubernetes,ansible}
├── monitoring/{logs,metrics,alerts}
├── scripts/
├── tools/
├── .github/workflows/
└── docs/{requirements,api,architecture,deployment,development,user}
```

---

## 4️⃣ 核心配置文件

### 根目录
- docker-compose.yml / .staging.yml / .production.yml  
- .env.example  
- Makefile  
- .gitignore  

### Backend
- Dockerfile / Dockerfile.prod  
- pyproject.toml  
- .flake8 / .coveragerc  

### Frontend
- pubspec.yaml / analysis_options.yaml  
- Dockerfile  

---

## 5️⃣ CI/CD 配置

📄 `.github/workflows/ci.yml`
```yaml
name: CI
on:
  push:
    branches: [main, staging, 'feature/**']
  pull_request:
    branches: [main, staging]

jobs:
  backend:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: 3.11
      - run: pip install -r backend/requirements/dev.txt
      - run: black --check backend && flake8 backend
      - run: pytest --cov=backend

  frontend:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: subosito/flutter-action@v2
        with:
          flutter-version: '3.22.2'
      - run: flutter pub get
      - run: flutter analyze
      - run: flutter test
```

📄 `.github/workflows/deploy.yml`
```yaml
name: Deploy
on:
  workflow_run:
    workflows: ["CI"]
    types:
      - completed
    branches: [main, staging]

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - run: echo "🚀 部署任务执行（Staging/Production 按分支区分）"
```

---

## 6️⃣ 脚本

📄 `scripts/verify-environment.sh`
```bash
#!/bin/bash
echo "🔍 GoMuseum 环境验证开始..."
REPORT_FILE="environment-report.txt"
echo "GoMuseum 环境验证报告 - $(date)" > $REPORT_FILE

verify_version() {
    local cmd=$1
    local expected=$2
    local actual=$($cmd 2>/dev/null || echo "未安装")
    if [[ $actual == *"$expected"* ]]; then
        echo "✅ $cmd: $actual" | tee -a $REPORT_FILE
    else
        echo "❌ $cmd: 期望 $expected, 实际 $actual" | tee -a $REPORT_FILE
        return 1
    fi
}
verify_version "node --version" "v20.11"
verify_version "python3 --version" "Python 3.11"
verify_version "docker --version" "Docker version 25"
verify_version "psql --version" "psql (PostgreSQL) 16"
verify_version "redis-server --version" "v=7.2"
verify_version "git --version" "2.43"

echo "📋 验证报告已生成: $REPORT_FILE"
```

📄 `scripts/acceptance-test.sh`
```bash
#!/bin/bash
echo "🧪 项目初始化验收测试开始..."

for dir in frontend backend scripts .github; do
    if [ -d "$dir" ]; then
        echo "✅ 必需目录 $dir 存在"
    else
        echo "❌ 缺少目录 $dir"
        exit 1
    fi
done

for file in docker-compose.yml .env.example .gitignore; do
    if [ -f "$file" ]; then
        echo "✅ $file 存在"
    else
        echo "❌ 缺少 $file"
        exit 1
    fi
done

cd frontend && flutter pub get && cd ..
cd backend && pip install -r requirements/dev.txt && cd ..

docker-compose up -d
sleep 10
curl -f http://localhost:3000 || echo "⚠️ 前端未启动"
curl -f http://localhost:8000/api/health || echo "⚠️ 后端未启动"
docker-compose down

echo "🎉 项目初始化验收测试完成！"
```

---

## 7️⃣ 验收流程
```bash
./scripts/verify-environment.sh
./scripts/acceptance-test.sh
```
检查：
- `flutter analyze && flutter test`  
- `pytest --cov`  
- `docker-compose up` 成功启动服务  
- GitHub Actions CI 变绿  

---

## 8️⃣ 下一步
- 进入 MVP 核心功能开发  
- 功能开发分支 → staging → main  
- CI/CD 自动部署  
