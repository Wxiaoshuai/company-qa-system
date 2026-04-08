# 阿里云 ECS 部署指南

本文档适用于将当前 `company-qa-system` 项目部署到阿里云 ECS 服务器，并通过 Nginx 对外提供 Web/H5 问答页面访问。

推荐部署架构：

- `Nginx`：对外监听 `80/443`
- `Uvicorn`：运行 FastAPI 应用
- `systemd`：托管服务，支持开机自启和异常重启

## 1. 部署前准备

### 1.1 服务器建议

- 云服务器：阿里云 ECS
- 系统建议：Ubuntu 22.04 LTS
- CPU/内存：最低 `1核2G` 可用于测试，正式使用建议 `2核4G` 起

### 1.2 安全组放行

在阿里云控制台为 ECS 安全组放行：

- `22`：SSH 登录
- `80`：HTTP
- `443`：HTTPS

如果只是临时测试，也可以额外放行：

- `8000`：直接访问 Uvicorn

### 1.3 域名准备

如果你要正式对外提供访问，建议提前准备域名，并将域名解析到 ECS 公网 IP。

## 2. 登录服务器并安装基础环境

通过 SSH 登录服务器：

```bash
ssh root@你的服务器公网IP
```

更新系统并安装基础依赖：

```bash
apt update
apt install -y git python3 python3-venv python3-pip nginx
```

检查版本：

```bash
python3 --version
nginx -v
git --version
```

## 3. 拉取项目代码

建议将项目放到 `/opt` 目录：

```bash
cd /opt
git clone https://github.com/Wxiaoshuai/company-qa-system.git
cd company-qa-system
```

如果你不是使用 `root` 用户运行，可以调整目录权限：

```bash
chown -R $USER:$USER /opt/company-qa-system
```

## 4. 创建虚拟环境并安装依赖

```bash
cd /opt/company-qa-system
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

## 5. 配置环境变量

复制环境变量模板：

```bash
cp .env.example .env
```

编辑 `.env`：

```bash
vim .env
```

至少配置以下内容：

```env
APP_NAME=Company QA System
APP_ENV=prod
APP_HOST=127.0.0.1
APP_PORT=8000

OPENAI_API_KEY=你的OpenAI密钥
OPENAI_BASE_URL=

EMBEDDING_MODEL=text-embedding-3-small
CHAT_MODEL=gpt-4o-mini

RAG_CHUNK_SIZE=800
RAG_CHUNK_OVERLAP=120
RAG_TOP_K=4
RAG_VECTOR_INDEX_PATH=data/vector_store/index.json
```

说明：

- `OPENAI_API_KEY` 必填
- `OPENAI_BASE_URL` 只有在你使用中转网关时才需要填写
- `APP_HOST` 建议保持 `127.0.0.1`，由 Nginx 转发即可

## 6. 准备知识库文档

将你的知识库文档放到：

```text
data/docs/
```

支持文件格式：

- `.txt`
- `.md`
- `.markdown`

例如：

```bash
ls data/docs
```

## 7. 构建向量索引

首次部署或知识库更新后，都需要重新构建索引：

```bash
cd /opt/company-qa-system
source .venv/bin/activate
python scripts/ingest.py
```

执行完成后会生成：

```text
data/vector_store/index.json
```

如果这里失败，优先检查：

- `.env` 是否已正确配置
- `OPENAI_API_KEY` 是否有效
- `data/docs/` 是否存在有效文档

## 8. 手动启动验证

先手动启动一次，确认服务正常：

```bash
cd /opt/company-qa-system
source .venv/bin/activate
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

在另一个终端测试：

```bash
curl http://127.0.0.1:8000/health
```

预期返回：

```json
{"status":"ok","env":"prod"}
```

你也可以测试页面入口：

```bash
curl http://127.0.0.1:8000/
```

如果返回 HTML 内容，说明页面入口正常。

停止当前手动运行：

```bash
Ctrl+C
```

## 9. 配置 systemd 服务

创建服务文件：

```bash
vim /etc/systemd/system/company-qa.service
```

写入以下内容：

```ini
[Unit]
Description=Company QA System
After=network.target

[Service]
User=root
WorkingDirectory=/opt/company-qa-system
ExecStart=/opt/company-qa-system/.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
```

加载并启动服务：

```bash
systemctl daemon-reload
systemctl enable company-qa
systemctl start company-qa
systemctl status company-qa
```

查看日志：

```bash
journalctl -u company-qa -f
```

常用命令：

```bash
systemctl restart company-qa
systemctl stop company-qa
systemctl status company-qa
```

## 10. 配置 Nginx 反向代理

新建 Nginx 配置文件：

```bash
vim /etc/nginx/conf.d/company-qa.conf
```

写入以下内容：

```nginx
server {
    listen 80;
    server_name 你的域名或服务器公网IP;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_buffering off;
    }
}
```

说明：

- `proxy_buffering off;` 很重要，它能减少对流式回答的缓冲影响
- 当前前端使用流式输出，Nginx 不建议开启代理缓冲

检查配置并重启：

```bash
nginx -t
systemctl restart nginx
```

访问：

```text
http://你的域名/
```

或者：

```text
http://你的公网IP/
```

## 11. 配置 HTTPS

如果域名已解析，建议使用 Let’s Encrypt 申请免费证书。

安装 Certbot：

```bash
apt install -y certbot python3-certbot-nginx
```

申请证书：

```bash
certbot --nginx -d 你的域名
```

成功后可直接通过 HTTPS 访问：

```text
https://你的域名/
```

## 12. 更新发布流程

以后项目更新时，建议按这个流程发布：

```bash
cd /opt/company-qa-system
git pull origin main
source .venv/bin/activate
pip install -r requirements.txt
python scripts/ingest.py
systemctl restart company-qa
```

如果只是前端页面或 Python 代码变化，但知识库文档没有变化，可以不重新执行 `ingest.py`。

如果 `data/docs/` 内容有更新，则必须重新执行：

```bash
python scripts/ingest.py
```

## 13. 常见问题排查

### 13.1 页面打不开

检查：

- 阿里云安全组是否已开放 `80/443`
- `nginx` 是否已启动
- `company-qa` 服务是否正常运行

命令：

```bash
systemctl status nginx
systemctl status company-qa
```

### 13.2 API 报错 `OPENAI_API_KEY is not set`

说明 `.env` 没配置好，或服务没有加载到正确目录下的 `.env`。

检查：

```bash
cat /opt/company-qa-system/.env
```

### 13.3 问答接口提示索引不存在

说明没有执行索引构建，或者索引路径不对。

重新执行：

```bash
cd /opt/company-qa-system
source .venv/bin/activate
python scripts/ingest.py
```

### 13.4 页面能打开，但回答一直失败

重点检查：

- OpenAI 网络是否可用
- `OPENAI_BASE_URL` 是否需要配置
- 服务器是否能访问模型接口

可以先通过服务日志定位：

```bash
journalctl -u company-qa -f
```

### 13.5 流式输出不顺畅

检查：

- Nginx 配置里是否保留了 `proxy_buffering off;`
- 是否有 CDN 或额外网关在前面做响应缓冲

## 14. 生产建议

当前项目可以部署上线，但如果是正式长期运行，建议后续补充：

- 访问鉴权
- 请求日志和审计日志
- 限流和防刷
- 错误告警
- 文档更新后的自动重建索引
- 更规范的进程用户，而不是长期使用 `root`

## 15. 最小可用部署命令

如果你只是想最快跑起来，可以按下面顺序执行：

```bash
cd /opt
git clone https://github.com/Wxiaoshuai/company-qa-system.git
cd company-qa-system
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python scripts/ingest.py
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

然后在阿里云安全组开放 `8000`，直接通过：

```text
http://你的公网IP:8000/
```

进行首次验证。
