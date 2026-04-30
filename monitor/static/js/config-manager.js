/**
 * 鸽切监控系统 - 配置管理器
 * 提供前端配置读取和缓存功能
 */

(function() {
    'use strict';

    class ConfigManager {
        constructor() {
            this.configCache = null;
            this.configLastFetch = 0;
            this.cacheDuration = 300000; // 5分钟缓存
            this.isInitialized = false;
        }

        /**
         * 初始化配置管理器
         */
        async init() {
            if (this.isInitialized) {
                return;
            }

            try {
                // 尝试从服务器获取配置
                await this.refreshConfig();
                this.isInitialized = true;
            } catch (error) {
                this.configCache = this.getDefaultConfig();
                this.isInitialized = true;
            }
        }

        /**
         * 获取默认配置（当无法从服务器获取时使用）
         */
        getDefaultConfig() {
            return {
                app: {
                    host: "0.0.0.0",
                    port: 5000,
                    debug: false,
                    timezone: "Asia/Shanghai"
                },
                bilibili: {
                    room_id: 22391541,
                    api_urls: [
                        "https://api.live.bilibili.com/room/v1/Room/get_info?id={room_id}",
                        "https://api.live.bilibili.com/room/v1/Room/room_init?id={room_id}"
                    ],
                    headers: {
                        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                        "Referer": "https://live.bilibili.com/{room_id}",
                        "Origin": "https://live.bilibili.com"
                    }
                },
                monitor: {
                    keyword: "鸽切",
                    email_cooldown: 1,
                    max_reconnect_attempts: 10,
                    reconnect_delay: 30,
                    heartbeat_timeout: 300
                }
            };
        }

        /**
         * 刷新配置（从服务器获取最新配置）
         */
        async refreshConfig() {
            try {
                const response = await fetch('/api/config');
                if (response.ok) {
                    const data = await response.json();
                    if (data.success) {
                        this.configCache = data.config || {};
                        this.configLastFetch = Date.now();
                        return true;
                    }
                }
                throw new Error('获取配置失败');
            } catch (error) {
                // 如果缓存为空，使用默认配置
                if (!this.configCache) {
                    this.configCache = this.getDefaultConfig();
                }
                return false;
            }
        }

        /**
         * 获取完整配置
         */
        async getConfig() {
            if (!this.isInitialized) {
                await this.init();
            }

            // 检查缓存是否过期
            if (this.configCache && Date.now() - this.configLastFetch > this.cacheDuration) {
                // 后台刷新配置，但不阻塞当前请求
                this.refreshConfig().catch(error => {
                    // 静默处理刷新失败
                });
            }

            return this.configCache || this.getDefaultConfig();
        }

        /**
         * 获取特定配置项
         * @param {string} section - 配置段
         * @param {string} key - 配置键
         * @param {any} defaultValue - 默认值
         */
        async get(section, key, defaultValue = null) {
            const config = await this.getConfig();
            
            if (!section) {
                return config;
            }
            
            if (!key) {
                return config[section] || {};
            }
            
            return config[section]?.[key] ?? defaultValue;
        }

        /**
         * 获取B站房间ID
         */
        async getRoomId() {
            return await this.get('bilibili', 'room_id', 22391541);
        }

        /**
         * 获取监控关键词
         */
        async getMonitorKeyword() {
            return await this.get('monitor', 'keyword', '鸽切');
        }

        /**
         * 获取应用时区
         */
        async getTimezone() {
            return await this.get('app', 'timezone', 'Asia/Shanghai');
        }

        /**
         * 获取应用端口
         */
        async getPort() {
            return await this.get('app', 'port', 5000);
        }

        /**
         * 检查是否启用调试模式
         */
        async isDebugEnabled() {
            return await this.get('app', 'debug', false);
        }

        /**
         * 获取B站API URL列表
         */
        async getBilibiliApiUrls(roomId = null) {
            const urls = await this.get('bilibili', 'api_urls', []);
            if (!roomId) {
                roomId = await this.getRoomId();
            }
            
            return urls.map(url => url.replace('{room_id}', roomId));
        }

        /**
         * 获取B站请求头
         */
        async getBilibiliHeaders(roomId = null) {
            const headers = await this.get('bilibili', 'headers', {});
            if (!roomId) {
                roomId = await this.getRoomId();
            }
            
            const formattedHeaders = {};
            for (const [key, value] of Object.entries(headers)) {
                formattedHeaders[key] = value.replace('{room_id}', roomId);
            }
            
            return formattedHeaders;
        }

        /**
         * 获取邮件配置
         */
        async getEmailConfig() {
            return await this.get('email');
        }

        /**
         * 获取登录凭证配置
         */
        async getCredentialConfig() {
            return await this.get('credential');
        }

        /**
         * 获取监控配置
         */
        async getMonitorConfig() {
            return await this.get('monitor');
        }

        /**
         * 强制刷新配置并返回
         */
        async refreshAndGet() {
            await this.refreshConfig();
            return await this.getConfig();
        }

        /**
         * 获取配置哈希（用于检测配置变化）
         */
        async getConfigHash() {
            const config = await this.getConfig();
            const configStr = JSON.stringify(config);
            
            // 简单的哈希函数
            let hash = 0;
            for (let i = 0; i < configStr.length; i++) {
                const char = configStr.charCodeAt(i);
                hash = ((hash << 5) - hash) + char;
                hash = hash & hash; // 转换为32位整数
            }
            
            return hash.toString(36);
        }
    }

    // 创建全局实例
    const configManager = new ConfigManager();

    // 暴露公共API
    window.ConfigManager = {
        getInstance: () => configManager,
        
        // 快捷方法
        get: async (section, key, defaultValue) => await configManager.get(section, key, defaultValue),
        getConfig: async () => await configManager.getConfig(),
        getRoomId: async () => await configManager.getRoomId(),
        getMonitorKeyword: async () => await configManager.getMonitorKeyword(),
        getTimezone: async () => await configManager.getTimezone(),
        getMonitorConfig: async () => await configManager.getMonitorConfig(),
        refreshConfig: async () => await configManager.refreshConfig(),
        
        // 初始化方法
        init: async () => await configManager.init()
    };

    // 自动初始化
    document.addEventListener('DOMContentLoaded', async () => {
        await configManager.init();
    });

})();