# 🚀 快速启动指南

## ✅ 已完成

数据库已成功初始化！创建了以下测试账号：

### 测试账号

**家属账号：**
- 手机: 13800138001
- 密码: 123456
- 名字: 张小明

**老年人账号 1：**
- 手机: 13800138000
- 密码: 123456
- 名字: 张奶奶

**老年人账号 2：**
- 手机: 13800138002
- 密码: 123456
- 名字: 李爷爷

---

## 🚀 启动步骤

### 1️⃣ 启动后端服务器

```bash
cd /Users/zhangyuntao/Desktop/tiaozhanzhe/AI-Elderly-Care-Health-Report-Multi-Agent-System/api
python3 server.py
```

后端会在 `http://localhost:8000` 启动

### 2️⃣ 启动前端开发服务器

打开新的终端窗口：

```bash
cd /Users/zhangyuntao/Desktop/tiaozhanzhe/AI-Elderly-Care-Health-Report-Multi-Agent-System/AI-Elderly-Care-Health-Report-Frontend
npm run dev
```

前端会在 `http://localhost:5173` 启动

### 3️⃣ 访问应用

打开浏览器访问：
```
http://localhost:5173/login
```

### 4️⃣ 使用家属账号登录

- 手机: 13800138001
- 密码: 123456

---

## 📍 数据库位置

数据库文件存储在：
```
/tmp/elderly-care-db/users.db
```

---

## 🎯 功能演示

### 家属端功能

1. **登录** → 输入手机号和密码
2. **查看老年人列表** → 显示所有关联的老年人
3. **编辑信息** → 补全老年人的健康信息
4. **查看完整度** → 实时显示信息完整度进度条
5. **保存修改** → 直接更新数据库
6. **生成报告** → 生成新的健康评估报告
7. **查看报告版本** → 查看所有报告版本
8. **对比版本** → 对比两个报告版本的差异

---

## 🔧 故障排除

### 问题 1：后端启动失败

**错误**: `ModuleNotFoundError: No module named 'fastapi'`

**解决**: 安装依赖
```bash
pip3 install fastapi uvicorn
```

### 问题 2：前端启动失败

**错误**: `npm: command not found`

**解决**: 安装 Node.js 和 npm
```bash
# 使用 Homebrew
brew install node
```

### 问题 3：数据库连接失败

**错误**: `sqlite3.OperationalError: attempt to write a readonly database`

**解决**: 数据库已自动使用 `/tmp/elderly-care-db/` 目录，应该没有权限问题

---

## 📊 系统架构

```
┌─────────────────────────────────────────────────────────┐
│                    前端 (Vue 3)                         │
│              http://localhost:5173                      │
└────────────────────┬────────────────────────────────────┘
                     │ HTTP/REST
┌────────────────────▼────────────────────────────────────┐
│                  后端 (FastAPI)                         │
│              http://localhost:8000                      │
└────────────────────┬────────────────────────────────────┘
                     │ SQLite
┌────────────────────▼────────────────────────────────────┐
│              数据库 (SQLite)                            │
│          /tmp/elderly-care-db/users.db                  │
└─────────────────────────────────────────────────────────┘
```

---

## 📝 API 端点

### 认证 API
- `POST /auth/register` - 用户注册
- `POST /auth/login` - 用户登录
- `GET /auth/me` - 获取当前用户

### 家属端 API
- `GET /family/elderly-list` - 获取老年人列表
- `GET /family/elderly/{id}/profile` - 获取档案
- `PUT /family/elderly/{id}/profile` - 更新档案
- `GET /family/elderly/{id}/reports` - 获取报告版本
- `POST /family/elderly/{id}/generate-report` - 生成新报告
- ...更多 API 见文档

---

## 💡 提示

1. **保持两个终端窗口打开**：一个运行后端，一个运行前端
2. **使用浏览器开发者工具**：F12 查看网络请求和控制台错误
3. **检查终端输出**：后端和前端的错误信息会在终端显示
4. **清除浏览器缓存**：如果页面显示异常，尝试清除缓存

---

## 🎉 开始使用

现在你可以：

1. ✅ 以家属身份登录
2. ✅ 查看关联的老年人
3. ✅ 编辑老年人的健康信息
4. ✅ 生成健康评估报告
5. ✅ 查看和对比报告版本

祝你使用愉快！🚀

---

**创建时间**: 2026-03-17  
**版本**: 1.0  
**状态**: ✅ 就绪
