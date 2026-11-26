# Demo Repo

一个用于 RepoReady 检测器回归测试的示例项目。它故意包含若干硬编码路径、Windows 专用脚本和**假**密钥，
请勿用于生产。

## 安装 / Quick Start

```bash
npm install
```

Python 依赖：

```bash
pip install -r requirements.txt
```

## 使用 / Usage

启动开发服务器：

```bash
npm run dev
```

也可以直接运行后端：

```bash
python server.py
```

## 配置 / Environment

复制 `.env.example` 为 `.env`，配置以下环境变量：

- `PORT`：服务端口，默认 5000
- `API_KEY`：演示用的外部服务 Key

## API / Architecture

- `src/config.js`：前端配置
- `server.py`：Flask 示例服务
- `scripts/`：Windows 启动与部署脚本

## License

MIT
