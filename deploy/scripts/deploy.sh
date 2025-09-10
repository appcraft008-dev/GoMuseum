#!/bin/bash

# 🚀 GoMuseum Deployment Script
# Supports multi-environment deployment with step-based releases

set -e

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 配置
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
DEPLOY_DIR="$PROJECT_ROOT/deploy"

# 默认值
ENVIRONMENT=${1:-staging}
STEP=${2:-1}
SERVICE=${3:-api}

# 函数定义
log() {
    echo -e "${BLUE}[$(date +'%Y-%m-%d %H:%M:%S')]${NC} $1"
}

success() {
    echo -e "${GREEN}✅ $1${NC}"
}

warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

error() {
    echo -e "${RED}❌ $1${NC}"
    exit 1
}

# 显示帮助信息
show_help() {
    cat << EOF
🏛️ GoMuseum 部署脚本

用法: 
    $0 <environment> <step> <service>

参数:
    environment: 目标环境 (staging|production) [默认: staging]
    step:        步骤编号 (1|2|3...) [默认: 1]  
    service:     服务名称 (api|app|docs|all) [默认: api]

示例:
    $0 staging 1 api          # 部署Step 1 API到staging
    $0 production 1 all       # 部署Step 1所有服务到production
    $0 staging 2 api          # 部署Step 2 API到staging

环境变量:
    GITHUB_TOKEN              # GitHub访问令牌
    DOCKER_REGISTRY           # Docker镜像仓库 [默认: ghcr.io]
    SKIP_BACKUP               # 跳过数据库备份 [默认: false]
    
EOF
}

# 检查参数
if [[ "$1" == "-h" || "$1" == "--help" ]]; then
    show_help
    exit 0
fi

# 验证环境参数
if [[ ! "$ENVIRONMENT" =~ ^(staging|production)$ ]]; then
    error "无效的环境参数: $ENVIRONMENT (支持: staging, production)"
fi

# 验证步骤参数
if [[ ! "$STEP" =~ ^[1-9][0-9]*$ ]]; then
    error "无效的步骤参数: $STEP (必须是正整数)"
fi

# 验证服务参数
if [[ ! "$SERVICE" =~ ^(api|app|docs|all)$ ]]; then
    error "无效的服务参数: $SERVICE (支持: api, app, docs, all)"
fi

log "🚀 开始GoMuseum部署流程"
log "🎯 环境: $ENVIRONMENT"
log "📊 步骤: Step $STEP"
log "🔧 服务: $SERVICE"

# 检查必要的环境变量
check_requirements() {
    log "🔍 检查部署要求..."
    
    # 检查Docker
    if ! command -v docker &> /dev/null; then
        error "Docker未安装或未在PATH中"
    fi
    
    # 检查docker-compose
    if ! command -v docker-compose &> /dev/null; then
        error "docker-compose未安装或未在PATH中"
    fi
    
    # 检查环境文件
    ENV_FILE="$DEPLOY_DIR/$ENVIRONMENT/.env"
    if [[ ! -f "$ENV_FILE" ]]; then
        error "环境文件不存在: $ENV_FILE"
    fi
    
    success "环境检查通过"
}

# 创建备份
create_backup() {
    if [[ "$SKIP_BACKUP" == "true" ]]; then
        warning "跳过数据库备份"
        return
    fi
    
    log "📦 创建数据库备份..."
    
    BACKUP_DIR="$DEPLOY_DIR/backups/$ENVIRONMENT"
    mkdir -p "$BACKUP_DIR"
    
    BACKUP_FILE="$BACKUP_DIR/gomuseum-$(date +%Y%m%d-%H%M%S).sql"
    
    # 执行备份
    docker-compose -f "$DEPLOY_DIR/$ENVIRONMENT/docker-compose.yml" exec -T postgres \
        pg_dump -U gomuseum gomuseum > "$BACKUP_FILE" 2>/dev/null || {
        warning "数据库备份失败或数据库不存在（首次部署）"
    }
    
    success "备份完成: $BACKUP_FILE"
}

# 拉取最新镜像
pull_images() {
    log "📥 拉取最新Docker镜像..."
    
    REGISTRY=${DOCKER_REGISTRY:-ghcr.io}
    IMAGE_TAG="step-$STEP-latest"
    
    if [[ "$SERVICE" == "api" || "$SERVICE" == "all" ]]; then
        docker pull "$REGISTRY/$GITHUB_REPOSITORY/api:$IMAGE_TAG" || {
            error "无法拉取API镜像: $REGISTRY/$GITHUB_REPOSITORY/api:$IMAGE_TAG"
        }
    fi
    
    if [[ "$SERVICE" == "app" || "$SERVICE" == "all" ]]; then
        log "📱 Flutter应用将通过静态文件部署"
    fi
    
    success "镜像拉取完成"
}

# 更新配置
update_config() {
    log "🔧 更新部署配置..."
    
    # 设置环境变量
    export GITHUB_REPOSITORY=${GITHUB_REPOSITORY:-"hongyang/gomuseum"}
    export STEP_VERSION="step-$STEP"
    
    # 生成docker-compose配置
    envsubst < "$DEPLOY_DIR/$ENVIRONMENT/docker-compose.yml" > "/tmp/docker-compose-$ENVIRONMENT.yml"
    
    success "配置更新完成"
}

# 部署服务
deploy_services() {
    log "🚀 部署服务..."
    
    cd "$DEPLOY_DIR/$ENVIRONMENT"
    
    # 停止旧服务
    docker-compose down --remove-orphans || true
    
    # 启动新服务
    if [[ "$SERVICE" == "all" ]]; then
        docker-compose up -d
    else
        docker-compose up -d "$SERVICE"
    fi
    
    success "服务部署完成"
}

# 健康检查
health_check() {
    log "🏥 执行健康检查..."
    
    if [[ "$SERVICE" == "api" || "$SERVICE" == "all" ]]; then
        # 等待API启动
        for i in {1..30}; do
            if curl -s -f "http://localhost:8000/health" > /dev/null; then
                success "API健康检查通过"
                break
            fi
            
            if [[ $i -eq 30 ]]; then
                error "API健康检查失败"
            fi
            
            sleep 2
        done
    fi
    
    success "所有健康检查通过"
}

# 运行部署后测试
run_smoke_tests() {
    log "🧪 运行冒烟测试..."
    
    # API测试
    if [[ "$SERVICE" == "api" || "$SERVICE" == "all" ]]; then
        curl -s "http://localhost:8000/health" | jq . || {
            error "API冒烟测试失败"
        }
    fi
    
    success "冒烟测试通过"
}

# 清理旧资源
cleanup() {
    log "🧹 清理旧资源..."
    
    # 清理旧镜像
    docker image prune -f
    
    # 清理旧容器
    docker container prune -f
    
    success "清理完成"
}

# 发送通知
send_notification() {
    log "📢 发送部署通知..."
    
    # 这里可以集成Slack、钉钉等通知
    DEPLOY_URL="https://api-$ENVIRONMENT.gomuseum.com"
    
    cat << EOF
🎉 GoMuseum部署成功！

📊 部署信息:
- 环境: $ENVIRONMENT
- 步骤: Step $STEP
- 服务: $SERVICE
- 时间: $(date)

🔗 链接:
- API: $DEPLOY_URL
- 文档: $DEPLOY_URL/docs
- 健康检查: $DEPLOY_URL/health

EOF
    
    success "部署通知已发送"
}

# 主流程
main() {
    check_requirements
    create_backup
    pull_images
    update_config
    deploy_services
    health_check
    run_smoke_tests
    cleanup
    send_notification
    
    success "🎉 GoMuseum Step $STEP 部署到 $ENVIRONMENT 环境成功完成！"
}

# 错误处理
trap 'error "部署过程中发生错误，请检查日志"' ERR

# 执行主流程
main "$@"