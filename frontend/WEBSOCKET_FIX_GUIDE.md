# WebSocket进度更新修复指南

## 问题诊断

前端进度不实时更新的问题已通过以下方式修复：

### 1. 后端修复（已完成）
- ✅ 修复了`websocket_gateway_service.py`引用已删除模块的问题
- ✅ 验证了WebSocket服务正常启动
- ✅ 验证了Redis消息传递正常
- ✅ 验证了端到端进度消息传递成功

### 2. 前端增强（已完成）
- ✅ 添加了详细的调试日志
- ✅ 创建了WebSocket调试页面
- ✅ 添加了后端测试API端点

## 如何使用

### 方法1：使用调试页面（推荐）

1. **启动后端服务**
   ```bash
   cd d:/jz/autoclip-windows/backend
   python main.py
   ```

2. **启动前端**
   ```bash
   cd d:/jz/autoclip-windows/frontend
   npm run dev
   ```

3. **访问调试页面**
   打开浏览器访问：`http://localhost:5173/debug/websocket`

4. **检查连接状态**
   - 查看WebSocket连接状态（应为"已连接"）
   - 查看用户ID是否正确
   - 查看处理中的项目数量

5. **测试功能**
   - 点击"测试连接"按钮，检查WebSocket实例
   - 点击"测试订阅"按钮，订阅处理中的项目
   - 点击"触发后端进度"按钮，触发测试进度更新
   - 查看日志和进度数据是否更新

### 方法2：使用浏览器Console

1. 打开主页：`http://localhost:5173/`

2. 打开浏览器开发者工具（F12）

3. 在Console中运行：
   ```javascript
   // 检查WebSocket状态
   console.log('WebSocket实例:', window.__WEBSOCKET__)
   console.log('是否已连接:', window.__WS_CONNECTED__)
   console.log('用户ID:', window.__WS_USER_ID__)
   
   // 检查项目状态
   const projectStore = window.__PROJECT_STORE__?.getState()
   console.log('项目列表:', projectStore?.projects)
   
   // 检查进度数据
   const progressStore = window.__PROGRESS_STORE__?.getState()
   console.log('进度数据:', progressStore?.byId)
   
   // 手动触发进度更新
   const projectId = projectStore?.projects?.[0]?.id
   if (projectId) {
     window.__PROGRESS_STORE__?.getState().updateProgress(
       projectId,
       'TEST',
       50,
       '手动测试进度'
     )
     console.log('已触发手动进度更新')
   }
   ```

### 方法3：测试实际处理流程

1. **上传一个新视频**
   - 在主页上传一个视频文件
   - 等待项目创建

2. **观察进度更新**
   - 打开Console，查看日志
   - 应该看到：
     ```
     📋 处理中的项目ID: [项目ID]
     ✅ WebSocket连接成功
     开始订阅项目: [项目ID]
     收到进度更新: {项目ID, 阶段, 进度, 消息}
     ```

3. **验证UI更新**
   - 项目卡片应该显示实时进度
   - 进度条应该动态更新
   - 阶段标签应该变化

## 常见问题排查

### 问题1：WebSocket未连接
**症状**：调试页面显示"未连接"

**解决方案**：
1. 确认后端服务正在运行
2. 检查后端日志，确认WebSocket服务已启动
3. 刷新前端页面，重新建立连接
4. 检查浏览器Console是否有错误

### 问题2：没有处理中的项目
**症状**：`processingProjectIds` 为空

**解决方案**：
1. 上传一个新视频创建项目
2. 或将现有项目的状态改为 `processing`：
   ```sql
   UPDATE projects SET status = 'processing' WHERE id = '项目ID';
   ```

### 问题3：未收到进度消息
**症状**：WebSocket已连接，但未收到消息

**解决方案**：
1. 使用调试页面的"触发后端进度"按钮测试
2. 检查Redis连接状态
3. 查看后端日志，确认进度消息已发送

### 问题4：UI未更新
**症状**：收到消息，但UI未变化

**解决方案**：
1. 检查进度Store是否正确更新
2. 检查组件是否正确订阅Store
3. 查看Console日志中的进度更新记录

## 后端验证

### 测试WebSocket连接
```bash
cd d:/jz/autoclip-windows/backend
python -c "
import asyncio
import websockets
import json

async def test():
    ws = await websockets.connect('ws://localhost:8000/api/v1/ws/test-user')
    print('✅ 连接成功')
    
    # 订阅
    await ws.send(json.dumps({
        'type': 'sync_subscriptions',
        'channels': ['progress:project:test-id']
    }))
    
    # 接收消息
    msg = await asyncio.wait_for(ws.recv(), timeout=2.0)
    print('收到消息:', msg)
    
    await ws.close()

asyncio.run(test())
"
```

### 触发测试进度
```bash
curl -X POST http://localhost:8000/api/v1/projects/项目ID/trigger-progress \
  -H "Content-Type: application/json" \
  -d '{"stage": "TEST", "percent": 75, "message": "测试进度"}'
```

## 技术细节

### 进度更新流程
```
1. 后端调用 emit_progress()
   ↓
2. 发送到Redis频道 progress:project:{项目ID}
   ↓
3. WebSocket服务订阅该频道
   ↓
4. 收到消息后转发给前端WebSocket连接
   ↓
5. 前端调用 updateProgress() 更新Store
   ↓
6. UI组件自动重新渲染显示进度
```

### 关键文件
- **后端**:
  - `services/simple_progress.py` - 进度消息发送
  - `services/unified_websocket_service.py` - WebSocket服务
  - `api/v1/test_progress.py` - 测试API端点

- **前端**:
  - `hooks/useWebSocket.ts` - WebSocket连接管理
  - `stores/useSimpleProgressStore.ts` - 进度状态管理
  - `pages/WebSocketDebugPage.tsx` - 调试页面
  - `components/UnifiedStatusBar.tsx` - 进度显示组件

## 需要帮助？

如果以上步骤都无法解决问题，请提供：
1. 浏览器Console完整日志
2. Network面板截图
3. 后端日志最后100行
4. 调试页面的截图
