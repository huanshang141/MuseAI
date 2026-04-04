# 博物馆展品问答助手前端设计

**Date:** 2026-04-05  
**Status:** Approved

---

## Overview

将现有的 API 测试页面重构为博物馆展品问答助手应用，提供真实的业务场景体验。用户可以上传展品文档，基于文档内容进行智能问答，在真实使用中验证后端 API 功能。

---

## Goals

1. 提供完整的博物馆展品问答体验
2. 支持文档上传和管理（知识库构建）
3. 展示 RAG 检索来源和引用片段
4. 使用 Element Plus 构建专业 UI
5. 覆盖所有后端 API 接口测试

---

## Tech Stack

- **框架**: Vue 3 (Composition API)
- **构建工具**: Vite
- **UI 组件库**: Element Plus
- **样式**: Element Plus 主题 + 自定义样式
- **HTTP 客户端**: fetch API
- **状态管理**: Vue 3 reactive/ref

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         MuseAI Frontend                          │
├────────────┬────────────────────────────────────────────────────┤
│            │                                                    │
│  Sidebar   │                  Main Content                      │
│            │                                                    │
│  ┌──────┐  │  ┌──────────────────────────────────────────────┐  │
│  │知识库 │  │  │                                              │  │
│  │管理   │  │  │              Chat Panel                      │  │
│  └──────┘  │  │                                              │  │
│            │  │   - Session List (Tabs)                       │  │
│  - 文档列表 │  │   - Message History                           │  │
│  - 上传    │  │   - Streaming Response                        │  │
│  - 状态    │  │   - Source Citations                          │  │
│  - 删除    │  │   - Input Box                                 │  │
│            │  │                                              │  │
│            │  └──────────────────────────────────────────────┘  │
│            │                                                    │
└────────────┴────────────────────────────────────────────────────┘
```

---

## Component Structure

```
frontend/
├── index.html
├── package.json              # 添加 element-plus 依赖
├── vite.config.js
└── src/
    ├── App.vue               # 主布局（侧边栏 + 内容区）
    ├── main.js               # Element Plus 注册
    ├── api/
    │   └── index.js          # API 封装（保持现有）
    ├── composables/
    │   ├── useDocuments.js   # 文档管理逻辑
    │   └── useChat.js        # 聊天逻辑
    ├── components/
    │   ├── layout/
    │   │   ├── AppHeader.vue     # 顶部导航
    │   │   └── AppSidebar.vue    # 左侧知识库面板
    │   ├── knowledge/
    │   │   ├── DocumentList.vue  # 文档列表
    │   │   ├── DocumentUpload.vue # 上传组件
    │   │   └── DocumentStatus.vue # 状态查看对话框
    │   └── chat/
    │       ├── ChatPanel.vue     # 聊天主面板
    │       ├── SessionTabs.vue   # 会话标签页
    │       ├── MessageList.vue   # 消息列表
    │       ├── MessageItem.vue   # 单条消息
    │       ├── SourceCard.vue    # 检索来源卡片
    │       └── ChatInput.vue     # 输入框
    └── styles/
        └── custom.css        # 自定义样式
```

---

## Feature Design

### 1. 知识库管理（左侧边栏）

**DocumentUpload.vue**
- 拖拽上传区域（el-upload）
- 支持 .txt, .md, .pdf 文件
- 上传进度显示
- 调用 `POST /api/v1/documents/upload`

**DocumentList.vue**
- 文档列表（el-table）
- 列：文件名、状态、创建时间、操作
- 状态徽章：处理中/已完成/失败
- 操作按钮：查看状态、删除
- 自动轮询处理中的文档状态

**DocumentStatus.vue**
- el-dialog 显示文档处理详情
- chunk 数量、处理时间、错误信息
- 调用 `GET /api/v1/documents/{id}/status`

### 2. 智能问答（右侧主区域）

**SessionTabs.vue**
- el-tabs 管理多会话
- 新建会话按钮
- 会话标题可编辑
- 删除会话（el-popconfirm 确认）
- 调用 `POST/GET/DELETE /api/v1/chat/sessions`

**MessageList.vue**
- 消息气泡布局
- 用户消息：右对齐，蓝色背景
- 助手消息：左对齐，灰色背景
- 流式显示动画（打字机效果）

**MessageItem.vue**
- 角色图标
- 消息内容（支持 Markdown 渲染）
- 创建时间
- Trace ID（可折叠显示）

**SourceCard.vue**
- 来源文档名称
- 相似度分数
- 引用片段（高亮关键词）
- 可展开查看完整内容

**ChatInput.vue**
- el-input + el-button
- Enter 发送，Shift+Enter 换行
- 发送中禁用输入
- 流式调用 `POST /api/v1/chat/ask/stream`

### 3. 顶部导航（AppHeader.vue）

- 应用 Logo 和标题
- 历史会话菜单（el-dropdown）
- 设置按钮（预留）

---

## Data Flow

### 文档上传流程

```
用户拖拽文件
    ↓
el-upload 组件
    ↓
POST /api/v1/documents/upload
    ↓
返回 DocumentResponse
    ↓
添加到文档列表（status: "processing"）
    ↓
轮询 GET /api/v1/documents/{id}/status
    ↓
状态更新为 "completed" 或 "failed"
```

### 问答流程

```
用户输入问题
    ↓
POST /api/v1/chat/sessions (如果无会话)
    ↓
SSE 连接 POST /api/v1/chat/ask/stream
    ↓
接收事件流:
  - thinking: 显示思考状态
  - chunk: 累加显示内容
  - done: 显示完整回答 + 来源
    ↓
保存消息到会话历史
```

---

## UI/UX Details

### 颜色主题

```css
--primary-color: #409EFF      /* Element Plus 默认蓝 */
--success-color: #67C23A      /* 成功/已完成 */
--warning-color: #E6A23C      /* 处理中 */
--danger-color: #F56C6C       /* 失败/删除 */
--text-primary: #303133       /* 主文本 */
--text-secondary: #909399     /* 次要文本 */
--bg-color: #F5F7FA           /* 背景色 */
```

### 响应式布局

- 侧边栏：固定宽度 280px，可折叠
- 主内容区：自适应宽度
- 最小支持 1024px 屏幕宽度

### 交互细节

- 文档上传成功：el-message 提示
- 删除确认：el-popconfirm
- 流式回答：打字机动画 + 光标闪烁
- 来源卡片：悬停高亮
- 错误处理：el-notification 显示错误详情

---

## API Coverage

| API 端点 | 功能 | 组件 |
|---------|------|------|
| GET /health | 健康检查 | AppHeader（状态指示器） |
| GET /ready | 就绪检查 | AppHeader（状态指示器） |
| POST /documents/upload | 上传文档 | DocumentUpload |
| GET /documents | 文档列表 | DocumentList |
| GET /documents/{id} | 文档详情 | DocumentStatus |
| GET /documents/{id}/status | 处理状态 | DocumentStatus |
| DELETE /documents/{id} | 删除文档 | DocumentList |
| POST /chat/sessions | 创建会话 | SessionTabs |
| GET /chat/sessions | 会话列表 | SessionTabs |
| GET /chat/sessions/{id} | 会话详情 | ChatPanel |
| DELETE /chat/sessions/{id} | 删除会话 | SessionTabs |
| GET /chat/sessions/{id}/messages | 消息历史 | MessageList |
| POST /ask | 非流式问答 | （备选，未使用） |
| POST /ask/stream | 流式问答 | ChatInput |

**覆盖率: 14/14 (100%)**

---

## Migration Plan

| 步骤 | 内容 | 工作量 |
|-----|------|-------|
| 1 | 安装 Element Plus，更新 main.js | 0.5h |
| 2 | 重构 App.vue 主布局 | 1h |
| 3 | 实现 AppSidebar + 文档管理组件 | 2h |
| 4 | 实现聊天相关组件 | 3h |
| 5 | 实现顶部导航 | 0.5h |
| 6 | 样式调优和交互完善 | 1h |
| 7 | 测试所有 API 调用 | 1h |

**总计: ~9h**

---

## Success Criteria

- [ ] 所有 14 个 API 端点可正常调用
- [ ] 文档上传后能看到处理状态变化
- [ ] 问答能正常流式返回并显示来源
- [ ] 会话管理功能完整（创建/切换/删除）
- [ ] UI 美观专业，符合 Element Plus 设计规范
- [ ] 响应式布局正常工作
- [ ] 错误提示清晰友好
