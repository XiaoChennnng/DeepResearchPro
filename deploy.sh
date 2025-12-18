#!/bin/sh

# DeepResearch Pro 自动化部署脚本
# 作者：小陈
# 功能：从远端拉取代码并自动完成配置

set -e  # 遇到错误立即退出

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 日志函数
log_info() {
    printf "\033[0;34m[INFO]\033[0m %s\n" "$1"
}

log_success() {
    printf "\033[0;32m[SUCCESS]\033[0m %s\n" "$1"
}

log_warning() {
    printf "\033[1;33m[WARNING]\033[0m %s\n" "$1"
}

log_error() {
    printf "\033[0;31m[ERROR]\033[0m %s\n" "$1"
}


# 默认配置
DEFAULT_INSTALL_DIR="$HOME/DeepResearchPro"
DEFAULT_BACKEND_PORT=8000
DEFAULT_FRONTEND_PORT=3000

# 用户可配置的变量
INSTALL_DIR="${INSTALL_DIR:-$DEFAULT_INSTALL_DIR}"
BACKEND_PORT="${BACKEND_PORT:-$DEFAULT_BACKEND_PORT}"
FRONTEND_PORT="${FRONTEND_PORT:-$DEFAULT_FRONTEND_PORT}"
REPO_URL="${REPO_URL:-"https://github.com/XiaoChennnng/DeepResearchPro.git"}"
BRANCH="${BRANCH:-"main"}"

# 显示欢迎信息
printf "\033[0;34m"
printf "==================================================\n"
printf "     DeepResearch Pro 自动化部署脚本\n"
printf "                 小陈出品\n"
printf "==================================================\n"
printf "\033[0m\n"

# 调试输出：检查基本命令是否可用
printf "\033[0;34m[DEBUG]\033[0m 检查uname命令...\n"
uname -s 2>/dev/null || echo "\033[0;31m[ERROR]\033[0m uname命令不可用"
printf "\033[0;34m[DEBUG]\033[0m 检查id命令...\n"
id -u 2>/dev/null || echo "\033[0;31m[ERROR]\033[0m id命令不可用"
printf "\033[0;34m[DEBUG]\033[0m 检查shell类型...\n"
echo "$0" 2>/dev/null || echo "\033[0;31m[ERROR]\033[0m 无法获取shell类型"
printf "\033[0;34m[DEBUG]\033[0m 调试信息结束\n\n"

# 检查命令是否存在
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# 安装系统依赖
install_system_deps() {
    log_info "安装系统依赖..."
    
    # 检测操作系统
    OS_TYPE=$(uname -s 2>/dev/null || echo "Unknown")
    log_info "检测到操作系统类型: $OS_TYPE"
    
    # 使用case语句替代if-elif-else，更健壮
    case "$OS_TYPE" in
        Linux)
            # Linux
            if command_exists apt-get; then
                sudo apt-get update
                sudo apt-get install -y python3 python3-pip python3-venv git curl nginx
                
                # 安装Node.js v20（使用NodeSource）
                log_info "安装Node.js v20..."
                
                # 移除旧的Node.js相关包，避免冲突
                log_info "移除旧的Node.js相关包..."
                sudo apt-get purge -y nodejs libnode-dev libnode72 2>/dev/null || true
                sudo apt-get autoremove -y
                
                # 安装Node.js v20
                curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
                sudo apt-get install -y nodejs
            elif command_exists yum; then
                sudo yum update -y
                sudo yum install -y python3 python3-pip nodejs npm git curl nginx
            elif command_exists dnf; then
                sudo dnf update -y
                sudo dnf install -y python3 python3-pip nodejs npm git curl nginx
            else
                log_error "不支持的操作系统包管理器"
                exit 1
            fi
            ;;
        Darwin)
            # macOS
            if ! command_exists brew; then
                log_error "请先安装Homebrew: https://brew.sh"
                exit 1
            fi
            brew install python node@20 git nginx
            brew link --overwrite node@20
            ;;
        *)
            log_error "不支持的操作系统类型: $OS_TYPE"
            exit 1
            ;;
    esac
    
    log_success "系统依赖安装完成"
    
    # 验证Node.js版本
    log_info "验证Node.js和npm版本..."
    node --version
    npm --version
    
    log_success "Node.js和npm版本验证完成"
}

# 克隆或更新代码
clone_or_update_repo() {
    log_info "处理代码仓库..."
    
    if [ -d "$INSTALL_DIR/.git" ]; then
        log_info "检测到现有仓库，正在更新..."
        cd "$INSTALL_DIR"
        git fetch origin
        git checkout "$BRANCH"
        git pull origin "$BRANCH"
    else
        log_info "正在克隆仓库..."
        git clone -b "$BRANCH" "$REPO_URL" "$INSTALL_DIR"
        cd "$INSTALL_DIR"
    fi
    
    log_success "代码仓库处理完成"
}

# 配置Python环境
setup_python_env() {
    log_info "配置Python环境..."
    
    cd "$INSTALL_DIR/backend"
    
    # 创建虚拟环境
    if [ ! -d "venv" ]; then
        python3 -m venv venv
    fi
    
    # 激活虚拟环境（在sh中使用.代替source）
    . venv/bin/activate
    
    # 升级pip
    pip install --upgrade pip
    
    # 安装依赖
    pip install -r requirements.txt
    
    log_success "Python环境配置完成"
}

# 配置Node.js环境
setup_node_env() {
    log_info "配置Node.js环境..."
    
    cd "$INSTALL_DIR"
    
    # 安装依赖
    npm install
    
    # 构建前端
    npm run build
    
    log_success "Node.js环境配置完成"
}

# 创建环境配置文件
create_env_file() {
    log_info "创建环境配置文件..."
    
    cd "$INSTALL_DIR/backend"
    
    if [ ! -f ".env" ]; then
        cat > .env << EOF
# DeepResearch Pro 后端配置
APP_NAME="DeepResearch Pro"
APP_VERSION="1.0.0"
DEBUG=false
HOST="0.0.0.0"
PORT=$BACKEND_PORT

# 数据库配置
DATABASE_URL="sqlite+aiosqlite:///./deepresearch.db"

# CORS配置
CORS_ORIGINS=["http://localhost:$FRONTEND_PORT", "http://127.0.0.1:$FRONTEND_PORT"]

# LLM配置（支持国内外大模型）
LLM_PROVIDER="openai"
LLM_API_KEY="your-openai-api-key-here"
LLM_MODEL="gpt-4o-mini"
LLM_BASE_URL="https://api.openai.com/v1"

# 兼容旧配置
OPENAI_API_KEY="your-openai-api-key-here"
OPENAI_BASE_URL="https://api.openai.com/v1"
OPENAI_MODEL="gpt-4o-mini"

# 搜索配置
MAX_SEARCH_RESULTS=10
SEARCH_TIMEOUT=30
EOF
        log_warning "已创建.env文件，请编辑backend/.env文件配置你的API密钥"
    else
        log_warning ".env文件已存在，跳过创建"
    fi
}

# 创建systemd服务
create_systemd_service() {
    log_info "创建systemd服务..."
    
    sudo tee /etc/systemd/system/deepresearch-backend.service > /dev/null << EOF
[Unit]
Description=DeepResearch Pro Backend
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$INSTALL_DIR/backend
Environment="PATH=$INSTALL_DIR/backend/venv/bin"
ExecStart=$INSTALL_DIR/backend/venv/bin/python run.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

    sudo systemctl daemon-reload
    log_success "systemd服务创建完成"
}

# 配置Nginx
configure_nginx() {
    log_info "配置Nginx..."
    
    # 检查配置文件是否存在
    if [ -f "/etc/nginx/sites-available/deepresearch" ]; then
        log_warning "Nginx配置文件已存在，备份原文件..."
        sudo cp /etc/nginx/sites-available/deepresearch "/etc/nginx/sites-available/deepresearch.backup.$(date +%Y%m%d_%H%M%S)"
    fi
    
    sudo tee /etc/nginx/sites-available/deepresearch > /dev/null << EOF
server {
    listen 80;
    server_name _;
    
    # 禁用默认的server_tokens
    server_tokens off;

    # 前端静态文件
    location / {
        root $INSTALL_DIR/dist;
        try_files \$uri \$uri/ /index.html;
        index index.html;
    }

    # 后端API代理
    location /api {
        proxy_pass http://localhost:$BACKEND_PORT;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }

    # WebSocket支持
    location /ws {
        proxy_pass http://localhost:$BACKEND_PORT;
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }
}
EOF

    # 启用站点并禁用默认站点
    sudo ln -sf /etc/nginx/sites-available/deepresearch /etc/nginx/sites-enabled/
    
    # 禁用默认的Nginx站点
    if [ -f "/etc/nginx/sites-enabled/default" ]; then
        sudo rm -f /etc/nginx/sites-enabled/default
        log_info "已禁用Nginx默认站点"
    fi
    
    # 测试配置
    sudo nginx -t
    
    # 重启Nginx服务
    sudo systemctl restart nginx
    log_success "Nginx配置完成"
}

# 创建启动脚本
create_start_script() {
    log_info "创建启动脚本..."
    
    cat > "$INSTALL_DIR/start.sh" << 'EOF'
#!/bin/sh

# DeepResearch Pro 启动脚本

# 启动模式：dev（开发模式）或 prod（生产模式）
MODE="prod"

# 解析命令行参数
for arg in "$@";
do
    case $arg in
        -d|--dev)
        MODE="dev"
        shift
        ;;
        *)
        # 忽略其他参数
        shift
        ;;
    esac
done

echo "启动 DeepResearch Pro..."
echo "启动模式: $MODE"
echo "项目路径: $(pwd)"

# 记录原始目录
ORIGINAL_DIR=$(pwd)

# 启动后端服务
echo "启动后端服务..."
cd "$ORIGINAL_DIR/backend"
if [ ! -d "venv" ]; then
    echo "错误：虚拟环境不存在，请先运行部署脚本"
    exit 1
fi
. venv/bin/activate
python run.py &
BACKEND_PID=$!

# 等待后端启动
sleep 5

# 检查后端是否启动成功
if ! ps -p $BACKEND_PID > /dev/null; then
    echo "错误：后端服务启动失败"
    exit 1
fi

# 根据模式启动前端服务
if [ "$MODE" = "dev" ]; then
    # 开发模式：启动前端开发服务器
    echo "启动前端开发服务器..."
    cd "$ORIGINAL_DIR"
    
    # 检查package.json是否存在
    if [ ! -f "package.json" ]; then
        echo "错误：package.json不存在，前端无法启动"
    else
        # 启动前端开发服务器，不使用&，直接在前台运行，这样可以看到前端输出
        echo "前端开发服务器启动命令：npm run dev"
        echo "====================================="
        npm run dev
    fi
else
    # 生产模式：前端使用Nginx服务，不需要单独启动
    echo "生产模式：前端使用Nginx服务，不需要单独启动"
    
    echo "服务启动完成!"
    echo "后端API: http://localhost:8000"
    echo "前端页面: http://localhost"
    echo "健康检查: http://localhost:8000/health"
    echo "API文档: http://localhost:8000/docs"
    echo ""
    echo "按 Ctrl+C 停止服务"
    
    # 等待用户中断
    trap "kill $BACKEND_PID 2>/dev/null; exit" INT
    wait $BACKEND_PID
fi
EOF

    chmod +x "$INSTALL_DIR/start.sh"
    log_success "启动脚本创建完成"
}

# 创建停止脚本
create_stop_script() {
    log_info "创建停止脚本..."
    
    cat > "$INSTALL_DIR/stop.sh" << 'EOF'
#!/bin/bash

# DeepResearch Pro 停止脚本

echo "停止 DeepResearch Pro..."

# 停止后端服务
if pgrep -f "python.*run.py" > /dev/null; then
    pkill -f "python.*run.py"
    echo "后端服务已停止"
else
    echo "后端服务未运行"
fi

# 停止前端服务（如果在运行）
if pgrep -f "npm.*dev" > /dev/null; then
    pkill -f "npm.*dev"
    echo "前端服务已停止"
else
    echo "前端服务未运行"
fi

echo "服务已停止"
EOF

    chmod +x "$INSTALL_DIR/stop.sh"
    log_success "停止脚本创建完成"
}

# 显示使用说明
show_usage() {
    log_success "部署完成！"
    echo ""
    echo "=================================================="
    echo "使用说明："
    echo ""
    echo "1. 配置API密钥："
    echo "   编辑文件: $INSTALL_DIR/backend/.env"
    echo "   设置 LLM_API_KEY 和你的其他配置"
    echo ""
    echo "2. 手动启动："
    echo "   cd $INSTALL_DIR"
    echo "   ./start.sh              # 生产模式（默认）"
    echo "   ./start.sh -d           # 开发模式，启动前端开发服务器"
    echo "   ./start.sh --dev        # 开发模式，启动前端开发服务器"
    echo ""
    echo "3. 使用systemd启动（推荐，仅生产模式）："
    echo "   sudo systemctl start deepresearch-backend"
    echo "   sudo systemctl enable deepresearch-backend  # 开机自启"
    echo ""
    echo "4. 查看状态："
    echo "   sudo systemctl status deepresearch-backend"
    echo ""
    echo "5. 停止服务："
    echo "   ./stop.sh"
    echo "   sudo systemctl stop deepresearch-backend"
    echo ""
    echo "6. 查看日志："
    echo "   sudo journalctl -u deepresearch-backend -f"
    echo ""
    echo "7. 访问应用："
    echo "   开发模式："
    echo "   - 后端API: http://localhost:$BACKEND_PORT"
    echo "   - 前端页面: http://localhost:5173"
    echo "   - API文档: http://localhost:$BACKEND_PORT/docs"
    echo "   生产模式："
    echo "   - 后端API: http://localhost:$BACKEND_PORT"
    echo "   - 前端页面: http://localhost"
    echo "   - API文档: http://localhost:$BACKEND_PORT/docs"
    echo ""
    echo "=================================================="
}

# 主函数
main() {
    # 安装系统依赖
    printf "是否安装系统依赖？(y/n): "
    read install_deps
    if [ "$install_deps" = "y" ] || [ "$install_deps" = "Y" ]; then
        install_system_deps
    fi
    
    # 克隆/更新代码
    clone_or_update_repo
    
    # 配置Python环境
    setup_python_env
    
    # 配置Node.js环境
    setup_node_env
    
    # 创建环境配置文件
    create_env_file
    
    # 创建systemd服务
    printf "是否创建systemd服务？(y/n): "
    read create_service
    if [ "$create_service" = "y" ] || [ "$create_service" = "Y" ]; then
        create_systemd_service
    fi
    
    # 配置Nginx
    printf "是否配置Nginx？(y/n): "
    read config_nginx
    if [ "$config_nginx" = "y" ] || [ "$config_nginx" = "Y" ]; then
        configure_nginx
        sudo systemctl restart nginx
    fi
    
    # 创建启动/停止脚本
    create_start_script
    create_stop_script
    
    # 显示使用说明
    show_usage
}

# 运行主函数
main "$@"