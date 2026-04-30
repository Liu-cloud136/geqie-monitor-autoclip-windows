/**
 * 鸽切监控系统 - 应用控制器
 * 协调各个模块，实现开播状态检测的前端集成
 */

(function() {
    'use strict';

    class AppController {
        constructor() {
            // 模块状态
            this.modules = {
                liveMonitor: null,
                dataTable: null,
                chartManager: null,
                authManager: null,
                configManager: null
            };
            
            // 应用状态
            this.appState = {
                isInitialized: false,
                isLive: false,
                roomInfo: null,
                lastUpdate: null
            };
            
            // 配置（将从配置管理器动态加载）
            this.config = {
                autoRefreshInterval: 10000, // 默认10秒自动刷新数据
                statusUpdateInterval: 30000, // 默认30秒更新状态
                pollingInterval: 30000       // 默认30秒轮询房间信息
            };
            
            // 配置加载状态
            this.configLoaded = false;}

        /**
         * 初始化应用（优化加载顺序）
         */
        async init() {
            try {// 0. 先加载配置
                await this.initConfigManager();
                
                // 1. 初始化基础UI（不依赖模块）
                this.updateBasicUI();
                
                // 2. 异步并行加载核心模块
                await Promise.allSettled([
                    this.initUtils(),
                    this.initAuthManager(),
                    this.initDataTable()
                ]);
                
                // 3. 初始化非关键模块（可延迟加载）
                this.initNonCriticalModules();
                
                // 4. 启动自动刷新
                this.startAutoRefresh();
                
                this.appState.isInitialized = true;} catch (error) {this.showError('应用初始化失败: ' + error.message);
            }
        }

    /**
     * 初始化配置管理器
     */
        async initConfigManager() {
            try {
                if (typeof ConfigManager !== 'undefined') {
                    this.modules.configManager = ConfigManager;
                    
                    // 初始化配置管理器
                    await ConfigManager.init();
                    
                    // 加载应用配置
                    await this.loadAppConfig();return true;
                } else {return false;
                }
            } catch (error) {return false;
            }
        }

        /**
         * 加载应用配置
         */
        async loadAppConfig() {
            if (!this.modules.configManager) return;

            try {
                // 获取监控配置
                if (typeof this.modules.configManager.getMonitorConfig === 'function') {
                    const monitorConfig = await this.modules.configManager.getMonitorConfig();

                    // 根据监控配置调整应用配置
                    if (monitorConfig.email_cooldown) {
                        // 根据邮件冷却时间调整自动刷新频率
                        this.config.autoRefreshInterval = Math.max(5000, monitorConfig.email_cooldown * 2000);
                    }
                    if (monitorConfig.heartbeat_timeout) {
                        // 根据心跳超时调整状态更新频率
                        this.config.statusUpdateInterval = Math.max(15000, monitorConfig.heartbeat_timeout * 1000 / 2);
                    }
                    if (monitorConfig.reconnect_delay) {
                        // 根据重连延迟调整轮询频率
                        this.config.pollingInterval = Math.max(10000, monitorConfig.reconnect_delay * 2000);
                    }

                    this.configLoaded = true;}

            } catch (error) {}
    }

    /**
     * 初始化工具模块
     */
    initUtils() {
        // 优先检查核心模块
        if (typeof Core !== 'undefined') {return true;
        } else if (typeof Utils !== 'undefined') {return true;
        } else {// 延迟检查，避免阻塞初始化
            setTimeout(() => {
                if (typeof Core !== 'undefined' || typeof Utils !== 'undefined') {} else {}
            }, 500);
            return false;
        }
    }

        /**
         * 初始化认证模块
         */
        async initAuthManager() {
            if (typeof AuthManager !== 'undefined') {
                this.modules.authManager = AuthManager;
                
                // 初始化认证
                await AuthManager.initAuth({ persistSession: true });
                
                // 监听认证状态变化
                AuthManager.onAuthChange((isLoggedIn) => {
                    this.onAuthChange(isLoggedIn);
                });return true;
            } else {return false;
            }
        }

        /**
         * 初始化直播监控模块
         */
        async initLiveMonitor() {
            if (typeof LiveMonitor !== 'undefined') {
                this.modules.liveMonitor = LiveMonitor;
                
                // 注册事件监听器
                LiveMonitor.on('live_start', (data) => {
                    this.onLiveStart(data);
                });
                
                LiveMonitor.on('live_end', (data) => {
                    this.onLiveEnd(data);
                });
                
                LiveMonitor.on('room_info_update', (data) => {
                    this.onRoomInfoUpdate(data);
                });
                
                LiveMonitor.on('keyword_match', (data) => {
                    this.onKeywordMatch(data);
                });
                
                LiveMonitor.on('error', (error) => {
                    this.onMonitorError(error);
                });
                
                // 启动监控
                LiveMonitor.start();return true;
            } else {return false;
            }
        }

        /**
         * 初始化数据表格
         */
        initDataTable() {
            if (typeof DataTableManager !== 'undefined') {
                this.modules.dataTable = DataTableManager;
                
                // 数据表格模块不需要显式初始化return true;
            } else {return false;
            }
        }

        /**
         * 初始化图表管理器
         */
        async initChartManager() {
            try {
                // 优先使用简化的图表管理器
                if (typeof SimpleChartManager !== 'undefined') {
                    this.modules.chartManager = SimpleChartManager;return true;
                } else if (typeof ChartManager !== 'undefined') {
                    this.modules.chartManager = ChartManager;
                    
                    // 初始化图表
                    await ChartManager.init();return true;
                } else {return false;
                }
            } catch (error) {return false;
            }
        }

        /**
         * 直播开始事件处理
         */
        onLiveStart(data) {this.appState.isLive = true;
            this.appState.lastUpdate = new Date();
            
            // 更新UI状态
            this.updateStreamStatus('live');
            
            // 刷新数据
            this.refreshData();}

        /**
         * 直播结束事件处理
         */
        onLiveEnd(data) {this.appState.isLive = false;
            this.appState.lastUpdate = new Date();
            
            // 更新UI状态
            this.updateStreamStatus('offline');}

        /**
         * 房间信息更新事件处理
         */
        onRoomInfoUpdate(data) {this.appState.roomInfo = data;
            this.appState.lastUpdate = new Date();
            
            // 立即更新UI状态，不等待其他处理
            this.updateStreamStatus(data.live_status === 1 ? 'live' : 'offline');
            
            // 更新房间信息
            this.updateRoomInfo(data);
            
            // 立即更新应用状态
            this.appState.isLive = data.live_status === 1;
        }

        /**
         * 关键词匹配事件处理
         */
        onKeywordMatch(data) {// 刷新数据表格
            if (this.modules.dataTable) {
                this.modules.dataTable.refresh();
            }}

        /**
         * 监控错误事件处理
         */
        onMonitorError(error) {}

        /**
         * 认证状态变化处理
         */
        onAuthChange(user) {// 更新UI以反映认证状态
            this.updateAuthUI(user);
        }

        /**
         * 更新直播间状态显示
         */
        updateStreamStatus(status) {
            const statusElement = document.getElementById('stream-status');
            const statusText = document.getElementById('status-text');
            
            if (!statusElement || !statusText) return;
            
            // 移除所有状态类
            statusElement.className = statusElement.className
                .replace(/status-(live|offline|loading)/g, '')
                .trim();
            
            // 添加新状态类
            statusElement.classList.add(`status-${status}`);
            
            // 更新状态文本
            const statusMap = {
                'live': '🟢 直播中',
                'offline': '🔴 未开播',
                'loading': '⏳ 加载中...'
            };
            
            statusText.textContent = statusMap[status] || statusMap['loading'];
        }

        /**
         * 更新房间信息显示
         */
        updateRoomInfo(roomInfo) {
            const roomTitleElement = document.getElementById('room-title');
            const roomIdElement = document.getElementById('room-id');
            
            if (roomTitleElement) {
                roomTitleElement.textContent = roomInfo.room_title || '未知直播间';
            }
            
            if (roomIdElement) {
                roomIdElement.textContent = roomInfo.room_id || '未知';
            }
        }

        /**
         * 更新认证UI
         */
        updateAuthUI(user) {
            const adminBadge = document.getElementById('admin-badge');
            
            if (adminBadge) {
                if (user) {
                    adminBadge.classList.remove('d-none');
                } else {
                    adminBadge.classList.add('d-none');
                }
            }
        }

        /**
         * 过滤掉未来日期的数据
         * @param {Array} data - 原始数据
         * @returns {Array} 过滤后的数据
         */
        filterFutureDates(data) {
            if (!data || !Array.isArray(data)) return [];
            
            // 使用服务器时间而不是浏览器本地时间
            // 获取当前UTC时间戳（秒），然后加上8小时转换为中国时间
            const nowUTC = Math.floor(Date.now() / 1000); // 当前UTC时间戳（秒）
            const nowChina = nowUTC + (8 * 3600); // 转换为中国时间戳（UTC+8）
            
            return data.filter(item => {
                // 检查时间戳是否在当前时间或之前（使用中国时间）
                if (item.timestamp) {
                    if (item.timestamp > nowChina) {
                        const itemDate = new Date(item.timestamp * 1000);return false;
                    }
                }
                
                // 检查日期字段是否在今天或之前（使用中国时间）
                const todayChina = new Date(nowChina * 1000);
                const todayStr = todayChina.toISOString().split('T')[0]; // YYYY-MM-DD格式
                if (item.date && item.date > todayStr) {return false;
                }
                
                return true;
            });
        }

        /**
         * 刷新数据
         */
        async refreshData() {
            try {// 刷新数据表格
                if (this.modules.dataTable) {
                    await this.modules.dataTable.refresh();
                }
                
                // 刷新图表
                if (this.modules.chartManager) {
                    await this.modules.chartManager.refresh();
                }
                
                // 更新最后更新时间
                if (window.Utils && typeof window.Utils.updateLastUpdate === 'function') {
                    window.Utils.updateLastUpdate();
                }} catch (error) {}
        }

        /**
         * 启动自动刷新
         */
        startAutoRefresh() {
            // 直播中时更频繁地刷新
            setInterval(() => {
                if (this.appState.isLive) {
                    this.refreshData();
                }
            }, this.config.autoRefreshInterval);}

        /**
         * 更新基础UI（不依赖任何模块）
         */
        updateBasicUI() {
            // 初始化状态显示
            this.updateStreamStatus('loading');
            
            // 设置今天日期（使用原生JavaScript）
            const todayElement = document.getElementById('today-date');
            if (todayElement) {
                const today = new Date();
                todayElement.textContent = today.toLocaleDateString('zh-CN', {
                    year: 'numeric',
                    month: 'long',
                    day: 'numeric',
                    weekday: 'long'
                });
            }}

        /**
         * 初始化非关键模块（可延迟加载）
         */
        initNonCriticalModules() {
            // 延迟初始化直播监控（需要网络连接）
            setTimeout(() => {
                this.initLiveMonitor().catch(error => {});
            }, 1000);
            
            // 延迟初始化图表管理器（需要DOM加载完成）
            setTimeout(() => {
                this.initChartManager().catch(error => {});
            }, 500);
        }

        /**
         * 更新UI（依赖模块加载完成）
         */
        updateUI() {
            // 设置今天日期（使用工具模块）
            if (Utils && typeof Utils.getTodayDateString === 'function') {
                const todayElement = document.getElementById('today-date');
                if (todayElement) {
                    todayElement.textContent = Utils.getTodayDateString();
                }
            }
            
            // 更新最后更新时间
            if (window.Utils && typeof window.Utils.updateLastUpdate === 'function') {
                window.Utils.updateLastUpdate();
            }}

        /**
         * 显示错误
         */
        showError(message) {}

        /**
         * 获取应用状态
         */
        getStatus() {
            return {
                ...this.appState,
                modules: Object.keys(this.modules).reduce((acc, key) => {
                    acc[key] = this.modules[key] !== null;
                    return acc;
                }, {})
            };
        }

        /**
         * 销毁应用
         */
        destroy() {
            // 停止监控
            if (this.modules.liveMonitor) {
                this.modules.liveMonitor.stop();
            }
            
            // 清除定时器等资源
            this.appState.isInitialized = false;}
    }

    // 创建全局实例
    window.AppController = new AppController();
    
    // 页面加载完成后初始化应用
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', function() {
            setTimeout(() => {
                window.AppController.init();
            }, 100);
        });
    } else {
        setTimeout(() => {
            window.AppController.init();
        }, 100);
    }})();