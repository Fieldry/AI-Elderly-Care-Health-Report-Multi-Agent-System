# 🎉 AI 养老健康系统 - 完整启动指南

## ✅ 系统状态

### 后端服务器
- ✅ **状态**: 运行中
- 📍 **地址**: http://localhost:8000
- 📚 **API 文档**: http://localhost:8000/docs

### 前端应用
- ⏳ **状态**: 启动中
- 📍 **地址**: http://localhost:5173
- 📂 **目录**: `/Users/zhangyuntao/Desktop/tiaozhanzhe/AI-Elderly-Care-Health-Report-Frontend`

### 数据库
- ✅ **状态**: 就绪
- 📍 **位置**: `/tmp/elderly-care-db/users.db`

---

## 🚀 启动步骤

### 步骤 1：后端服务器（已运行）

后端服务器已在运行，无需重新启动。

如果需要重新启动，运行：
```bash
cd /Users/zhangyuntao/Desktop/tiaozhanzhe/AI-Elderly-Care-Health-Report-Multi-Agent-System/api
python3 server.py
```

### 步骤 2：前端应用

打开**新的终端窗口**，运行：

```bash
cd /Users/zhangyuntao/Desktop/tiaozhanzhe/AI-Elderly-Care-Health-Report-Frontend
npm run dev
```

前端会在 `http://localhost:5173` 启动

### 步骤 3：访问应用

打开浏览器访问：
```
http://localhost:5173/login
```

---

## 🔑 登录凭证

### 家属账号（推荐）
- **手机**: 13800138001
- **密码**: 123456
- **名字**: 张小明

### 老年人账号
- **手机**: 13800138000
- **密码**: 123456
- **名字**: 张奶奶

### 第二个老年人账号
- **手机**: 13800138002
- **密码**: 123456
- **名字**: 李爷爷

---

## 🎯 功能演示

使用家属账号登录后，你可以：

### 1. 查看老年人列表
- 显示所有关联的老年人
- 显示每个老年人的信息完整度
- 显示关联时间

### 2. 编辑老年人信息
- 进入编辑页面
- 查看所有 62 个字段
- 按分组组织（基本信息、健康限制、基本生活等）
- 直接编辑和保存

### 3. 查看完整度
- 实时显示信息完整度进度条
- 显示缺失的字段列表
- 支持搜索字段

### 4. 生成报告
- 完成信息编辑后生成新报告
- 自动版本号递增（v1.0 → v2.0 → v3.0）
- 保留所有历史版本

### 5. 查看报告版本
- 显示所有报告版本
- 显示版本号、生成时间、完整度
- 支持查看、删除、对比版本

---

## 📊 系统架构

```
┌─────────────────────────────────────────────────────────┐
│                    前端 (Vue 3)                         │
│              http://localhost:5173                      │
│  ├─ 登录页面 (/login)                                   │
│  ├─ 家属端首页 (/family/hub)                            │
│  ├─ 编辑页面 (/family/edit/:elderly_id)                 │
│  └─ 报告版本 (/family/reports/:elderly_id)              │
└────────────────────┬────────────────────────────────────┘
                     │ HTTP/REST
┌────────────────────▼────────────────────────────────────┐
│                  后端 (FastAPI)                         │
│              http://localhost:8000                      │
│  ├─ 认证 API (/auth/*)                                  │
│  └─ 家属端 API (/family/*)                              │
└────────────────────┬────────────────────────────────────┘
                     │ SQLite
┌────────────────────▼────────────────────────────────────┐
│              数据库 (SQLite)                            │
│          /tmp/elderly-care-db/users.db                  │
│  ├─ users 表                                            │
│  ├─ elderly_family_relation 表                          │
│  ├─ user_profiles 表                                    │
│  ├─ profile_edit_log 表                                 │
│  └─ report_versions 表                                  │
└─────────────────────────────────────────────────────────┘
```

---

## 🔧 故障排除

### 问题 1：前端无法启动

**错误**: `npm: command not found`

**解决**: 安装 Node.js
```bash
brew install node
```

### 问题 2：前端无法连接后端

**错误**: 登录失败或 API 错误

**解决**: 
1. 确保后端服务器正在运行（http://localhost:8000）
2. 检查前端 `.env` 文件中的 API 地址：
   ```
   VITE_BACKEND_ORIGIN=http://localhost:8000
   ```

### 问题 3：登录失败

**错误**: 手机号或密码错误

**解决**: 使用正确的测试账号
- 手机: 13800138001
- 密码: 123456

### 问题 4：数据库错误

**错误**: `sqlite3.OperationalError`

**解决**: 数据库已自动创建在 `/tmp/elderly-care-db/users.db`

---

## 📚 API 文档

访问 http://localhost:8000/docs 查看完整的 Swagger API 文档

### 主要 API 端点

**认证 API**
- `POST /auth/register` - 用户注册
- `POST /auth/login` - 用户登录
- `GET /auth/me` - 获取当前用户

**家属端 API**
- `GET /family/elderly-list` - 获取老年人列表
- `GET /family/elderly/{id}/profile` - 获取档案
- `GET /family/elderly/{id}/completion-rate` - 获取完整度
- `PUT /family/elderly/{id}/profile` - 更新档案
- `GET /family/elderly/{id}/edit-log` - 获取修改日志
- `GET /family/elderly/{id}/reports` - 获取报告版本
- `POST /family/elderly/{id}/generate-report` - 生成新报告
- `GET /family/elderly/{id}/reports/{vid}` - 获取特定版本
- `DELETE /family/elderly/{id}/reports/{vid}` - 删除版本
- `GET /family/elderly/{id}/reports/{v1}/compare/{v2}` - 对比版本

---

## 💡 提示

1. **保持两个终端窗口打开**
   - 一个运行后端服务器
   - 一个运行前端开发服务器

2. **使用浏览器开发者工具**
   - 按 F12 打开开发者工具
   - 查看 Network 标签中的 API 请求
   - 查看 Console 标签中的错误信息

3. **检查终端输出**
   - 后端和前端的错误信息会在终端显示
   - 查看是否有 ERROR 或 WARNING 信息

4. **清除浏览器缓存**
   - 如果页面显示异常，尝试清除缓存
   - 或使用无痕模式打开浏览器

---

## 📖 文档

查看以下文档获取更多信息：

- `QUICK_START.md` - 快速启动指南
- `FAMILY_IMPLEMENTATION.md` - 详细实现文档
- `COMPLETION_SUMMARY.md` - 完成总结
- `CHECKLIST.md` - 完成清单
- `RUNNING.md` - 运行状态

---

## 🎉 开始使用

现在你可以：

1. ✅ 访问 http://localhost:5173/login
2. ✅ 使用家属账号登录
3. ✅ 查看和编辑老年人信息
4. ✅ 生成健康评估报告
5. ✅ 查看和对比报告版本

祝你使用愉快！🚀

---

**创建时间**: 2026-03-17  
**版本**: 1.0  
**状态**: ✅ 完全就绪
