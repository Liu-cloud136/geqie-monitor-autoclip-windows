/**
 * 鸽切监控系统 - 直播状态监控模块
 * 实时监控B站直播状态，支持SSE实时事件推送
 * 使用SSE + 轮询双重机制确保实时性和可靠性
 */

(function() {
    'use strict';

    class LiveMonitor {
        constructor() {
            // 直播状态相关属性
            this.isLive = false;              // 是否正在直播
            this.isMonitoring = false;        // 是否正在监控
            this.liveStartTime = null;        // 开播时间戳
            this.lastHeartbeatTime = Date.now(); // 最后心跳时间
            
            // WebSocket相关属性
            this.wsConnection = null;         // WebSocket连接对象
            this.wsReconnectAttempts = 0;     // WebSocket重连次数
            this.maxWsReconnectAttempts = 10; // 最大WebSocket重连次数
            
            // SSE相关属性
            this.sseConnection = null;        // SSE连接对象
            this.sseReconnectAttempts = 0;    // SSE重连次数
            this.maxSseReconnectAttempts = 5; // 最大SSE重连次数
            
            // 配置参数（将从配置管理器动态加载）
            this.pollingInterval = 15000;      // 默认轮询间隔：15秒
            this.heartbeatTimeout = 120000;   // 默认心跳超时：2分钟
            this.reconnectDelay = 5000;       // 默认重连延迟：5秒
            this.wsHeartbeatInterval = 30000; // 默认WebSocket心跳间隔：30秒
            
            // 配置管理器实例
            this.configManager = null;
            this.configLoaded = false;
            
            // 统计信息
            this.keywordCount = 0;
            this.totalDanmaku = 0;
            
            // 定时器
            this.pollingTimer = null;
            this.heartbeatTimer = null;
            this.wsHeartbeatTimer = null;
            
            // 事件监听器
            this.eventListeners = {
                'live_start': [],
                'live_end': [],
                'room_info_update': [],
                'keyword_match': [],
                'ws_connected': [],
                'ws_disconnected': [],
                'sse_connected': [],
                'sse_disconnected': [],
                'error': []
            };
            
            // 缓存信息
            this.roomInfo = null;
            this.lastUpdateTime = 0;
            this.connectionType = 'none';     // 当前连接类型：ws, sse, polling

            // 初始化配置管理器
            this.initConfigManager();
        }

        /**
         * 初始化配置管理器
         */
        async initConfigManager() {
            try {
                if (window.ConfigManager) {
                    this.configManager = window.ConfigManager;
                    // 等待 ConfigManager 完全初始化
                    await this.configManager.init();
                    await this.loadConfig();
                } else {
                }
            } catch (error) {}
        }

        /**
         * 加载配置参数
         */
        async loadConfig() {
            if (!this.configManager) return;

            try {
                // 获取监控配置
                if (typeof this.configManager.getMonitorConfig === 'function') {
                    const monitorConfig = await this.configManager.getMonitorConfig();

                    // 更新配置参数
                    if (monitorConfig.reconnect_delay) {
                        this.reconnectDelay = monitorConfig.reconnect_delay * 1000; // 转换为毫秒
                    }
                    if (monitorConfig.max_reconnect_attempts) {
                        this.maxWsReconnectAttempts = monitorConfig.max_reconnect_attempts;
                        this.maxSseReconnectAttempts = Math.min(5, monitorConfig.max_reconnect_attempts); // SSE重连次数限制
                    }
                    if (monitorConfig.heartbeat_timeout) {
                        this.heartbeatTimeout = monitorConfig.heartbeat_timeout * 1000; // 转换为毫秒
                    }
                    if (monitorConfig.email_cooldown) {
                        // 邮件冷却时间，用于其他频率控制
                        this.pollingInterval = Math.max(10000, monitorConfig.email_cooldown * 500); // 根据邮件冷却时间调整轮询频率
                    }

                    this.configLoaded = true;
                }

            } catch (error) {
            }
        }

        /**
         * 添加事件监听器
         */
        on(event, callback) {
            if (!this.eventListeners[event]) {
                this.eventListeners[event] = [];
            }
            this.eventListeners[event].push(callback);
            return this;
        }

        /**
         * 触发事件
         */
        emit(event, data) {
            const listeners = this.eventListeners[event] || [];
            listeners.forEach(callback => {
                try {
                    callback(data);
                } catch (error) {}
            });
        }

        /**
         * 获取直播间信息
         */
        async getRoomInfo() {
            try {
                const response = await fetch('/api/room_info/refresh');
                if (!response.ok) {
                    throw new Error(`HTTP ${response.status}: ${response.statusText}`);
                }
                
                const result = await response.json();
                if (result.success) {
                    this.roomInfo = result.room_info;
                    this.lastUpdateTime = Date.now();
                    
                    // 触发房间信息更新事件
                    this.emit('room_info_update', this.roomInfo);
                    
                    // 检查直播状态变化
                    this.checkLiveStatusChange(result.room_info.live_status);
                    
                    return result.room_info;
                } else {
                    throw new Error(result.error || '获取房间信息失败');
                }
            } catch (error) {
                this.emit('error', error);
                return null;
            }
        }

        /**
         * 检查直播状态变化
         */
        checkLiveStatusChange(newStatus) {
            const wasLive = this.isLive;
            const isNowLive = newStatus === 1;
            
            // 立即更新内部状态
            this.isLive = isNowLive;
            
            if (!wasLive && isNowLive) {
                // 直播开始
                this.onLiveStart();
            } else if (wasLive && !isNowLive) {
                // 直播结束
                this.onLiveEnd();
            }
        }

        /**
         * 处理房间信息更新
         */
        onRoomInfoUpdate(data) {
            // 更新房间信息
            this.roomInfo = data;
            this.lastUpdateTime = Date.now();
            
            // 触发房间信息更新事件
            this.emit('room_info_update', data);
            
            // 检查直播状态变化
            this.checkLiveStatusChange(data.live_status);
        }

        /**
         * 处理直播开始（带参数版本，用于SSE事件）
         */
        onLiveStart(data) {
            this.isLive = true;
            this.isMonitoring = true;
            this.liveStartTime = Date.now();
            
            // 更新房间信息
            if (data.roomInfo) {
                this.roomInfo = data.roomInfo;
            }
            
            // 重置统计
            this.keywordCount = 0;
            this.totalDanmaku = 0;
            
            // 触发事件
            this.emit('live_start', {
                roomInfo: this.roomInfo,
                startTime: this.liveStartTime
            });
        }

        /**
         * 处理直播开始
         */
        onLiveStart() {
            this.isLive = true;
            this.isMonitoring = true;
            this.liveStartTime = Date.now();
            
            // 重置统计
            this.keywordCount = 0;
            this.totalDanmaku = 0;
            
            // 触发事件
            this.emit('live_start', {
                roomInfo: this.roomInfo,
                startTime: this.liveStartTime
            });}

        /**
         * 处理直播结束
         */
        onLiveEnd() {
            this.isLive = false;
            this.isMonitoring = false;
            
            // 计算直播时长
            let duration = '未知';
            if (this.liveStartTime) {
                const seconds = Math.floor((Date.now() - this.liveStartTime) / 1000);
                duration = this.formatDuration(seconds);
            }
            
            // 触发事件
            this.emit('live_end', {
                roomInfo: this.roomInfo,
                duration: duration,
                keywordCount: this.keywordCount,
                totalDanmaku: this.totalDanmaku
            });
            // 重置开始时间
            this.liveStartTime = null;
        }

        /**
         * 格式化时间间隔
         */
        formatDuration(seconds) {
            if (!seconds) return "0秒";
            
            const hours = Math.floor(seconds / 3600);
            const minutes = Math.floor((seconds % 3600) / 60);
            const secs = seconds % 60;
            
            if (hours > 0) {
                return `${hours}小时${minutes}分钟${secs}秒`;
            } else if (minutes > 0) {
                return `${minutes}分钟${secs}秒`;
            } else {
                return `${secs}秒`;
            }
        }

        /**
         * 开始监控
         */
        async start() {
            if (this.isMonitoring) {
                return;
            }
            // 确保配置已加载
            if (!this.configLoaded) {
                await this.loadConfig();
            }
            
            // 立即获取一次房间信息（快速初始化）
            this.getRoomInfo().then(() => {});
            
            // 智能连接策略
            this.connectWithPriority();
            
            // 启动轮询（作为兜底方案）
            this.startPolling();
            
            // 启动心跳检测
            this.startHeartbeatCheck();
            
            this.isMonitoring = true;
        }

        /**
         * 智能连接策略：优先WebSocket，其次SSE
         */
        connectWithPriority() {
            // 优先尝试WebSocket（延迟加载，避免阻塞）
            if (typeof WebSocket !== 'undefined') {
                setTimeout(() => this.connectWebSocket(), 100);
            } else {
                this.connectSSE();
            }
        }

        /**
         * 连接WebSocket服务器
         */
        connectWebSocket() {
            if (this.wsConnection) {
                this.disconnectWebSocket();
            }

            try {
                // 创建Socket.IO连接，添加详细配置
                this.wsConnection = io({
                    transports: ['websocket', 'polling'],
                    reconnection: true,
                    reconnectionAttempts: 5,
                    reconnectionDelay: 1000,
                    reconnectionDelayMax: 5000,
                    timeout: 20000,
                    forceNew: false,
                    multiplex: true
                });

                // 连接成功
                this.wsConnection.on('connect', () => {
                    this.wsReconnectAttempts = 0;
                    this.connectionType = 'ws';
                    this.emit('ws_connected');

                    // 启动WebSocket心跳机制
                    this.startWebSocketHeartbeat();
                });

                // 接收消息
                this.wsConnection.on('room_info_update', (data) => {
                    this.handleWebSocketMessage({type: 'room_info_update', data: data});
                });

                this.wsConnection.on('live_start', (data) => {
                    this.handleWebSocketMessage({type: 'live_start', data: data});
                });

                this.wsConnection.on('live_end', (data) => {
                    this.handleWebSocketMessage({type: 'live_end', data: data});
                });
                
                this.wsConnection.on('keyword_match', (data) => {
                    this.handleWebSocketMessage({type: 'keyword_match', data: data});
                });

                // 连接错误
                this.wsConnection.on('error', (error) => {
                    this.emit('error', error);
                });

                // 连接关闭
                this.wsConnection.on('disconnect', (reason) => {
                    this.connectionType = 'none';
                    this.emit('ws_disconnected', {reason: reason});

                    // 自动重连
                    if (this.isMonitoring) {
                        this.handleWebSocketReconnect();
                    }
                });

            } catch (error) {
                this.emit('error', error);
            }
        }

        /**
         * 处理WebSocket消息
         */
        handleWebSocketMessage(data) {
            this.lastHeartbeatTime = Date.now();
            
            switch (data.type) {
                case 'room_info_update':
                    this.onRoomInfoUpdate(data.data);
                    break;

                case 'live_start':
                    this.onLiveStart(data.data);
                    break;

                case 'live_end':
                    this.onLiveEnd();
                    break;

                case 'keyword_match':
                    this.emit('keyword_match', data.data);
                    break;

                case 'heartbeat':
                    // 心跳响应，更新最后心跳时间
                    this.lastHeartbeatTime = Date.now();
                    break;

                default:
            }
        }

        /**
         * 启动WebSocket心跳
         */
        startWebSocketHeartbeat() {
            if (this.wsHeartbeatTimer) {
                clearInterval(this.wsHeartbeatTimer);
            }
            
            this.wsHeartbeatTimer = setInterval(() => {
                if (this.wsConnection && this.wsConnection.connected) {
                    try {
                        this.wsConnection.send(JSON.stringify({
                            type: 'heartbeat',
                            timestamp: Date.now()
                        }));
                    } catch (error) {}
                }
            }, this.wsHeartbeatInterval);
        }

        /**
         * 断开WebSocket连接
         */
        disconnectWebSocket() {
            if (this.wsConnection) {
                this.wsConnection.close(1000, '正常关闭');
                this.wsConnection = null;
                this.connectionType = 'none';
                this.emit('ws_disconnected');

                if (this.wsHeartbeatTimer) {
                    clearInterval(this.wsHeartbeatTimer);
                    this.wsHeartbeatTimer = null;
                }
            }
        }

        /**
         * 处理WebSocket重连
         */
        handleWebSocketReconnect() {
            if (this.wsReconnectAttempts >= this.maxWsReconnectAttempts) {
                this.connectSSE();
                return;
            }

            this.wsReconnectAttempts++;
            const delay = this.reconnectDelay * this.wsReconnectAttempts;
            setTimeout(() => {
                if (this.isMonitoring) {
                    this.connectWebSocket();
                }
            }, delay);
        }

        /**
         * 连接SSE服务器
         */
        connectSSE() {
            if (this.sseConnection) {
                this.disconnectSSE();
            }

            try {
                // 创建SSE连接
                this.sseConnection = new EventSource('/api/events');

                // 监听房间信息更新事件
                this.sseConnection.addEventListener('room_info_update', (event) => {
                    try {
                        const data = JSON.parse(event.data);
                        // 更新房间信息
                        this.roomInfo = data;
                        this.lastUpdateTime = Date.now();
                        
                        // 触发房间信息更新事件
                        this.emit('room_info_update', data);
                        
                        // 检查直播状态变化
                        this.checkLiveStatusChange(data.live_status);
                    } catch (error) {}
                });
                
                // 监听直播开始事件
                this.sseConnection.addEventListener('live_start', (event) => {
                    try {
                        const data = JSON.parse(event.data);
                        // 立即更新状态，不等待其他处理
                        this.isLive = true;
                        this.isMonitoring = true;
                        this.liveStartTime = Date.now();
                        this.roomInfo = data;
                        
                        // 立即触发事件，无需等待
                        this.emit('live_start', {
                            roomInfo: this.roomInfo,
                            startTime: this.liveStartTime
                        });
                        
                        // 异步重置统计
                        setTimeout(() => {
                            this.keywordCount = 0;
                            this.totalDanmaku = 0;
                        }, 0);
                        
                    } catch (error) {}
                });
                
                // 监听直播结束事件
                this.sseConnection.addEventListener('live_end', (event) => {
                    try {
                        const data = JSON.parse(event.data);
                        // 更新房间信息
                        this.roomInfo = data;
                        
                        // 调用直播结束处理
                        this.onLiveEnd();
                    } catch (error) {}
                });
                
                // 监听状态事件（心跳）
                this.sseConnection.addEventListener('status', (event) => {
                    try {
                        const data = JSON.parse(event.data);
                        if (data.message === 'heartbeat') {
                            this.lastHeartbeatTime = Date.now();
                        }
                    } catch (error) {}
                });

                // 连接成功
                this.sseConnection.addEventListener('open', () => {
                    this.sseReconnectAttempts = 0; // 重置重连计数器
                    this.emit('sse_connected');
                });

                // 连接错误
                this.sseConnection.addEventListener('error', (error) => {
                    // 触发断开连接事件
                    this.emit('sse_disconnected', error);

                    // 尝试重连
                    this.handleSSEReconnect();
                });

            } catch (error) {
                this.emit('error', error);

                // 尝试重连
                this.handleSSEReconnect();
            }
        }

        /**
         * 断开SSE连接
         */
        disconnectSSE() {
            if (this.sseConnection) {
                this.sseConnection.close();
                this.sseConnection = null;
                this.emit('sse_disconnected');
            }
        }

        /**
         * 处理SSE重连
         */
        handleSSEReconnect() {
            if (this.sseReconnectAttempts >= this.maxSseReconnectAttempts) {
                return;
            }

            this.sseReconnectAttempts++;
            const delay = this.reconnectDelay * this.sseReconnectAttempts; // 指数退避
            setTimeout(() => {
                if (this.isMonitoring) {
                    this.connectSSE();
                }
            }, delay);
        }

        /**
         * 停止监控
         */
        stop() {
            this.isMonitoring = false;

            // 断开WebSocket连接
            this.disconnectWebSocket();

            // 断开SSE连接
            this.disconnectSSE();

            // 清除定时器
            if (this.pollingTimer) {
                clearTimeout(this.pollingTimer);
                this.pollingTimer = null;
            }

            if (this.heartbeatTimer) {
                clearInterval(this.heartbeatTimer);
                this.heartbeatTimer = null;
            }

            if (this.wsHeartbeatTimer) {
                clearInterval(this.wsHeartbeatTimer);
                this.wsHeartbeatTimer = null;
            }
        }

        /**
         * 启动轮询（作为兜底方案）
         */
        startPolling() {
            const poll = async () => {
                if (!this.isMonitoring) return;
                
                // 智能频率控制：根据连接类型调整轮询频率
                let pollInterval = 60000; // 默认1分钟
                
                if (this.connectionType === 'ws') {
                    // WebSocket连接正常时，15分钟一次健康检查
                    pollInterval = 900000;
                } else if (this.connectionType === 'sse') {
                    // SSE连接正常时，10分钟一次健康检查
                    pollInterval = 600000;
                } else {
                    // 无实时连接时，15秒一次快速轮询
                    pollInterval = 15000;
                }
                
                try {
                    await this.getRoomInfo();
                    this.lastHeartbeatTime = Date.now();
                } catch (error) {}
                
                // 设置下一次轮询
                if (this.isMonitoring) {
                    this.pollingTimer = setTimeout(poll, pollInterval);
                }
            };
            
            // 延迟启动轮询，让实时连接先建立
            setTimeout(poll, 5000);
        }

        /**
         * 启动心跳检测
         */
        startHeartbeatCheck() {
            this.heartbeatTimer = setInterval(() => {
                if (!this.isMonitoring) return;

                const timeSinceLastHeartbeat = Date.now() - this.lastHeartbeatTime;
                if (timeSinceLastHeartbeat > this.heartbeatTimeout) {
                    this.handleReconnect();
                }
            }, 30000); // 每30秒检查一次
        }

        /**
         * 处理重连
         */
        async handleReconnect() {
            // 停止当前监控
            this.stop();
            
            // 延迟后重新开始
            setTimeout(() => {
                if (this.isMonitoring) {
                    this.start();
                }
            }, this.reconnectDelay);
        }

        /**
         * 获取当前状态信息
         */
        getStatus() {
            return {
                isLive: this.isLive,
                isMonitoring: this.isMonitoring,
                liveStartTime: this.liveStartTime,
                roomInfo: this.roomInfo,
                keywordCount: this.keywordCount,
                totalDanmaku: this.totalDanmaku
            };
        }

        /**
         * 模拟弹幕事件（用于测试）
         */
        simulateDanmaku(username, content) {
            if (!this.isLive || !this.isMonitoring) return;
            
            this.totalDanmaku++;
            
            // 检查是否包含关键词
            if (content.includes('鸽切')) {
                this.keywordCount++;
                
                // 触发关键词事件
                this.emit('keyword_match', {
                    username: username,
                    content: content,
                    matchedKeyword: '鸽切',
                    timestamp: Date.now()
                });
            }
        }
    }

    // 创建全局实例
    window.LiveMonitor = new LiveMonitor();
})();