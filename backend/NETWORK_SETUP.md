# 网络连接配置指南

## 问题分析

从错误日志可以看到：
- 小程序成功选择了图片
- 但上传时出现 `net::ERR_CONNECTION_REFUSED`
- 这是因为小程序无法连接到后端服务器

## 原因

小程序运行在手机/模拟器上，无法直接访问开发机器的 `127.0.0.1` 或 `localhost`。

## 解决方案

### 方案1：修改服务器地址为电脑IP（推荐）

#### 1. 查看电脑IP地址
```bash
# Windows
ipconfig

# macOS/Linux
ifconfig 或 ip addr
```

查找类似 `192.168.1.xxx` 或 `10.0.0.xxx` 的IP地址。

#### 2. 修改小程序配置
在 `utils/config.js` 中修改：
```javascript
BASE_URL: 'http://你的电脑IP:8000',  // 例如：http://192.168.1.100:8000
```

#### 3. 启动后端服务器
```bash
cd backend
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

#### 4. 确保防火墙允许连接
- Windows：允许Python通过防火墙
- macOS：检查防火墙设置

### 方案2：使用内网穿透工具

如果方案1不可行，可以使用内网穿透工具：

#### ngrok（推荐）
```bash
# 下载并安装 ngrok
# https://ngrok.com/

# 启动内网穿透
ngrok http 8000

# 会得到类似 https://abc123.ngrok.io 的地址
```

然后修改 `utils/config.js`：
```javascript
BASE_URL: 'https://你的ngrok地址',
```

#### LocalTunnel
```bash
npm install -g localtunnel
lt --port 8000
```

### 方案3：部署到云服务器

将后端部署到云服务器，然后修改BASE_URL为服务器地址。

## 测试连接

### 1. 启动后端
```bash
cd backend
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 2. 测试API访问
在浏览器中访问：
```
http://你的IP:8000/health
http://你的IP:8000/docs
```

### 3. 测试小程序
重新编译小程序，测试图片上传功能。

## 常见问题

### Q: 还是连接不上？
A: 检查：
- IP地址是否正确
- 端口8000是否被占用
- 防火墙设置
- 电脑和手机是否在同一网络

### Q: 如何在真机上测试？
A: 确保手机和电脑在同一WiFi网络下，使用电脑的内网IP地址。

### Q: 开发 vs 生产环境？
A: 生产环境建议使用域名，并配置HTTPS。

## 快速测试命令

```bash
# 1. 查看IP
ipconfig  # Windows
ifconfig  # macOS/Linux

# 2. 启动服务器
cd backend && uvicorn app.main:app --host 0.0.0.0 --port 8000

# 3. 测试连接
curl http://你的IP:8000/health
```