/**
 * 鸽切监控系统 - 核心工具模块
 * 提供全局通用的工具函数，消除重复代码
 * 所有模块共享此核心库
 */

(function() {
    'use strict';

    /**
     * ==================== 基础工具函数 ====================
     */

    /**
     * HTML转义（全局统一实现）
     * @param {string} text - 原始文本
     * @returns {string} 转义后的文本
     */
    function escapeHtml(text) {
        if (!text) return '';
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    /**
     * 防抖函数
     * @param {Function} func - 要防抖的函数
     * @param {number} delay - 延迟时间（毫秒）
     * @returns {Function} 防抖后的函数
     */
    function debounce(func, delay) {
        let timeoutId;
        return function(...args) {
            clearTimeout(timeoutId);
            timeoutId = setTimeout(() => func.apply(this, args), delay);
        };
    }

    /**
     * 节流函数
     * @param {Function} func - 要节流的函数
     * @param {number} delay - 延迟时间（毫秒）
     * @returns {Function} 节流后的函数
     */
    function throttle(func, delay) {
        let lastCall = 0;
        return function(...args) {
            const now = Date.now();
            if (now - lastCall >= delay) {
                lastCall = now;
                func.apply(this, args);
            }
        };
    }

    /**
     * 深拷贝对象
     * @param {any} obj - 要拷贝的对象
     * @returns {any} 深拷贝后的对象
     */
    function deepClone(obj) {
        if (obj === null || typeof obj !== 'object') return obj;
        if (obj instanceof Date) return new Date(obj);
        if (obj instanceof Array) return obj.map(item => deepClone(item));
        
        const cloned = {};
        for (let key in obj) {
            if (obj.hasOwnProperty(key)) {
                cloned[key] = deepClone(obj[key]);
            }
        }
        return cloned;
    }

    /**
     * 检查对象是否为空
     * @param {any} obj - 要检查的对象
     * @returns {boolean} 是否为空
     */
    function isEmpty(obj) {
        if (obj == null) return true;
        if (Array.isArray(obj)) return obj.length === 0;
        if (typeof obj === 'object') return Object.keys(obj).length === 0;
        return false;
    }

    /**
     * ==================== 日期时间函数 ====================
     */

    /**
     * 格式化日期（中国时区）
     * @param {Date|string} date - 日期对象或字符串
     * @param {Object} options - 格式化选项
     * @returns {string} 格式化后的日期
     */
    function formatDate(date, options = {}) {
        const defaultOptions = {
            year: 'numeric',
            month: 'long',
            day: 'numeric',
            weekday: 'long'
        };
        return new Date(date).toLocaleDateString('zh-CN', { ...defaultOptions, ...options });
    }

    /**
     * 格式化时间
     * @param {Date|string} date - 日期对象或字符串
     * @returns {string} 格式化后的时间
     */
    function formatTime(date) {
        return new Date(date).toLocaleTimeString('zh-CN');
    }

    /**
     * 获取今天的日期字符串
     * @returns {string} 今天日期的字符串表示
     */
    function getTodayDateString() {
        const today = new Date();
        return formatDate(today);
    }

    /**
     * 获取日期范围
     * @param {number} days - 天数
     * @returns {Object} 开始和结束日期
     */
    function getDateRange(days) {
        const end = new Date();
        const start = new Date();
        start.setDate(start.getDate() - days);
        
        return {
            start: start.toISOString().split('T')[0],
            end: end.toISOString().split('T')[0]
        };
    }

    /**
     * 过滤掉未来日期的数据
     * @param {Array} data - 原始数据
     * @returns {Array} 过滤后的数据
     */
    function filterFutureDates(data) {
        if (!data || !Array.isArray(data)) return [];
        
        const nowUTC = Math.floor(Date.now() / 1000);
        const nowChina = nowUTC + (8 * 3600); // UTC+8
        
        return data.filter(item => {
            if (item.timestamp && item.timestamp > nowChina) {return false;
            }
            
            const todayChina = new Date(nowChina * 1000);
            const todayStr = todayChina.toISOString().split('T')[0];
            if (item.date && item.date > todayStr) {return false;
            }
            
            return true;
        });
    }

    /**
     * ==================== 验证函数 ====================
     */

    /**
     * 验证BV号格式（全局统一）
     * @param {string} bvCode - BV号
     * @returns {Object} 验证结果 {valid: boolean, message: string}
     */
    function validateBVCode(bvCode) {
        if (!bvCode) {
            return { valid: false, message: '请输入BV号' };
        }
        
        const cleanCode = bvCode.trim();
        const bvPattern = /^BV[a-zA-Z0-9]{9,11}$/;
        
        if (!bvPattern.test(cleanCode)) {
            return { 
                valid: false, 
                message: 'BV号格式不正确，应为类似 BV1xx411c7mD 的格式' 
            };
        }
        
        return { valid: true, message: '' };
    }

    /**
     * 实时验证BV号输入
     * @param {HTMLInputElement} inputElement - 输入框元素
     */
    function validateBVInput(inputElement) {
        const bvCode = inputElement.value.trim();
        const helpElement = document.getElementById(inputElement.id + 'Help');
        const errorElement = document.getElementById(inputElement.id + 'Error');

        // 清空状态和重置样式
        inputElement.classList.remove('is-invalid', 'is-valid');
        // 移除可能的内联样式（如果有）
        inputElement.style.borderColor = '';
        inputElement.style.boxShadow = '';

        if (errorElement) errorElement.style.display = 'none';
        if (helpElement) {
            helpElement.style.display = 'block';
            helpElement.style.color = '#6c757d';  // 重置为灰色
            // 重置 help 文本内容
            helpElement.textContent = '输入正确的BV号，如 BV1xx411c7mD';
        }

        if (!bvCode) {
            // 输入为空时，不再设置任何状态
            return;
        }

        const validation = validateBVCode(bvCode);

        if (validation.valid) {
            inputElement.classList.add('is-valid');
            if (helpElement) {
                helpElement.textContent = '格式正确，系统将自动生成B站视频链接';
                helpElement.style.color = '#198754';  // 绿色
            }
        } else {
            inputElement.classList.add('is-invalid');
            if (errorElement) {
                errorElement.textContent = validation.message;
                errorElement.style.display = 'block';
            }
            if (helpElement) helpElement.style.display = 'none';
        }
    }

    /**
     * ==================== 通知和提示 ====================
     */

    /**
     * 统一的API错误处理
     * @param {Error|Response} error - 错误对象或响应对象
     * @param {string} context - 错误上下文描述
     * @param {boolean} showUser - 是否向用户显示错误
     */
    function handleApiError(error, context = 'API请求', showUser = true) {
        let errorMessage = '未知错误';
        let errorDetails = '';
        
        if (error instanceof Error) {
            errorMessage = error.message;
            errorDetails = error.stack || '';
        } else if (error && error.status) {
            // 响应错误
            switch (error.status) {
                case 400:
                    errorMessage = '请求参数错误';
                    break;
                case 401:
                    errorMessage = '未授权访问';
                    break;
                case 403:
                    errorMessage = '权限不足';
                    break;
                case 404:
                    errorMessage = '请求的资源不存在';
                    break;
                case 500:
                    errorMessage = '服务器内部错误';
                    break;
                case 502:
                    errorMessage = '网关错误';
                    break;
                case 503:
                    errorMessage = '服务不可用';
                    break;
                default:
                    errorMessage = `HTTP ${error.status} 错误`;
            }
            errorDetails = `URL: ${error.url || '未知'}`;
        }
        
        // 控制台日志// 向用户显示错误（如果需要）
        if (showUser) {
            showNotification(`${context}失败: ${errorMessage}`, 'error');
        }
        
        return errorMessage;
    }

    /**
     * 安全的API请求封装
     * @param {string} url - 请求URL
     * @param {Object} options - 请求选项
     * @returns {Promise<any>} 响应数据
     */
    async function safeApiRequest(url, options = {}) {
        const defaultOptions = {
            method: 'GET',
            headers: {
                'Content-Type': 'application/json',
            },
            timeout: 10000, // 10秒超时
            ...options
        };
        
        try {
            // 设置超时
            const controller = new AbortController();
            const timeoutId = setTimeout(() => controller.abort(), defaultOptions.timeout);
            
            const response = await fetch(url, {
                ...defaultOptions,
                signal: controller.signal
            });
            
            clearTimeout(timeoutId);
            
            // 检查HTTP状态码
            if (!response.ok) {
                throw { status: response.status, url, statusText: response.statusText };
            }
            
            const data = await response.json();
            
            // 检查API返回的成功状态
            if (data && data.success === false) {
                throw new Error(data.error || 'API返回错误');
            }
            
            return data;
            
        } catch (error) {
            if (error.name === 'AbortError') {
                handleApiError(new Error('请求超时'), `请求 ${url}`, true);
            } else {
                handleApiError(error, `请求 ${url}`, true);
            }
            throw error;
        }
    }

    /**
     * 显示通知消息（替代alert）
     * @param {string} message - 消息内容
     * @param {string} type - 消息类型：success, error, warning, info
     * @param {number} duration - 显示时长（毫秒）
     */
    function showNotification(message, type = 'info', duration = 3000) {
        const colors = {
            success: '#10b981',
            error: '#ef4444',
            warning: '#f59e0b',
            info: '#3b82f6'
        };
        
        const icons = {
            success: 'bi-check-circle',
            error: 'bi-exclamation-circle',
            warning: 'bi-exclamation-triangle',
            info: 'bi-info-circle'
        };
        
        const notification = document.createElement('div');
        notification.style.cssText = `
            position: fixed;
            top: 20px;
            right: 20px;
            background: ${colors[type] || colors.info};
            color: white;
            padding: 12px 16px;
            border-radius: 6px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.15);
            z-index: 10000;
            max-width: 300px;
            font-size: 14px;
            transition: all 0.3s ease;
            transform: translateX(100%);
            opacity: 0;
        `;
        
        notification.innerHTML = `
            <div style="display: flex; align-items: center; gap: 8px;">
                <i class="bi ${icons[type] || icons.info}"></i>
                <span>${escapeHtml(message)}</span>
            </div>
        `;
        
        document.body.appendChild(notification);
        
        setTimeout(() => {
            notification.style.transform = 'translateX(0)';
            notification.style.opacity = '1';
        }, 10);
        
        setTimeout(() => {
            notification.style.transform = 'translateX(100%)';
            notification.style.opacity = '0';
            setTimeout(() => notification.remove(), 300);
        }, duration);
    }

    /**
     * 显示确认对话框（替代confirm）
     * @param {string} message - 消息内容
     * @param {string} title - 对话框标题
     * @returns {Promise<boolean>} 用户选择结果
     */
    function showConfirm(message, title = '请确认') {
        return new Promise((resolve) => {
            // 创建确认对话框
            const modalId = 'confirm-modal-' + Date.now();
            const modal = document.createElement('div');
            modal.id = modalId;
            modal.className = 'simple-modal';
            modal.style.cssText = `
                display: block;
                position: fixed;
                top: 50%;
                left: 50%;
                transform: translate(-50%, -50%);
                z-index: 10000;
                background: white;
                border-radius: 8px;
                box-shadow: 0 4px 20px rgba(0,0,0,0.3);
                max-width: 400px;
                width: 90%;
            `;
            
            modal.innerHTML = `
                <div class="modal-header bg-primary text-white p-3" style="border-radius: 8px 8px 0 0;">
                    <h5 class="modal-title mb-0">
                        <i class="bi bi-question-circle me-2"></i> ${escapeHtml(title)}
                    </h5>
                    <button type="button" class="btn-close btn-close-white" onclick="this.closest('.simple-modal').remove()" style="background: none; border: none; font-size: 1.2em; color: white;">×</button>
                </div>
                <div class="modal-body p-4">
                    <p class="text-muted">${escapeHtml(message)}</p>
                </div>
                <div class="modal-footer p-3">
                    <button type="button" class="btn btn-outline-secondary" data-result="false">取消</button>
                    <button type="button" class="btn btn-primary" data-result="true">确定</button>
                </div>
            `;
            
            document.body.appendChild(modal);
            
            // 绑定按钮事件
            modal.querySelectorAll('[data-result]').forEach(btn => {
                btn.addEventListener('click', (e) => {
                    const result = e.target.getAttribute('data-result') === 'true';
                    modal.remove();
                    resolve(result);
                });
            });
        });
    }

    /**
     * 显示加载指示器
     * @param {string} message - 加载消息
     */
    function showLoading(message = '加载中...') {
        const loadingEl = document.createElement('div');
        loadingEl.id = 'global-loading';
        loadingEl.innerHTML = `
            <div style="position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.5); z-index: 99999; display: flex; align-items: center; justify-content: center;">
                <div style="background: white; padding: 2rem; border-radius: 8px; text-align: center;">
                    <div class="loading"></div>
                    <p class="mt-2">${escapeHtml(message)}</p>
                </div>
            </div>
        `;
        document.body.appendChild(loadingEl);
    }

    /**
     * 隐藏加载指示器
     */
    function hideLoading() {
        const loadingEl = document.getElementById('global-loading');
        if (loadingEl) loadingEl.remove();
    }

    /**
     * 更新最后更新时间显示
     */
    function updateLastUpdate() {
        const element = document.getElementById('last-update');
        if (element) {
            element.textContent = `最后更新: ${formatTime(new Date())}`;
        }
    }

    /**
     * 生成随机ID
     * @param {number} length - ID长度
     * @returns {string} 随机ID
     */
    function generateId(length = 8) {
        const chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789';
        let result = '';
        for (let i = 0; i < length; i++) {
            result += chars.charAt(Math.floor(Math.random() * chars.length));
        }
        return result;
    }

    /**
     * 添加行悬停效果（表格用）
     * @param {HTMLElement} container - 表格容器
     */
    function addRowHoverEffects(container) {
        const rows = container.querySelectorAll('.data-row');
        rows.forEach(row => {
            row.addEventListener('mouseenter', function() {
                this.style.backgroundColor = 'rgba(255, 236, 210, 0.3)';
            });
            row.addEventListener('mouseleave', function() {
                this.style.backgroundColor = '';
            });
        });
    }

    /**
     * ==================== 全局状态管理 ====================
     */

    // 全局应用状态（私有状态，通过API访问）
    const globalState = new Map();

    // 初始化默认状态
    globalState.set('currentEditId', null);
    globalState.set('currentDeleteId', null);
    globalState.set('pendingAction', null);
    globalState.set('isAdminLoggedIn', false);
    globalState.set('userSession', null);

    /**
     * 获取全局状态
     * @param {string} key - 状态键
     * @returns {any} 状态值
     */
    function getGlobalState(key) {
        return globalState.get(key);
    }

    /**
     * 设置全局状态
     * @param {string} key - 状态键
     * @param {any} value - 状态值
     */
    function setGlobalState(key, value) {
        globalState.set(key, value);
    }

    /**
     * 重置状态到默认值
     */
    function resetGlobalState() {
        globalState.clear();
        globalState.set('currentEditId', null);
        globalState.set('currentDeleteId', null);
        globalState.set('pendingAction', null);
        globalState.set('isAdminLoggedIn', false);
        globalState.set('userSession', null);
    }

    /**
     * 获取所有状态（调试用）
     * @returns {Object} 状态快照
     */
    function getGlobalStateSnapshot() {
        const snapshot = {};
        for (let [key, value] of globalState) {
            snapshot[key] = value;
        }
        return snapshot;
    }

    /**
     * ==================== 模块初始化 ====================
     */

    // 核心模块加载完成标志// 暴露全局API
    window.Core = {
        // 基础工具
        escapeHtml,
        debounce,
        throttle,
        deepClone,
        isEmpty,
        generateId,
        
        // 日期时间
        formatDate,
        formatTime,
        getTodayDateString,
        getDateRange,
        filterFutureDates,
        updateLastUpdate,
        
        // 验证
        validateBVCode,
        validateBVInput,
        
        // 通知
        showNotification,
        showConfirm,
        showLoading,
        hideLoading,
        
        // UI效果
        addRowHoverEffects,
        
        // 状态管理
        getGlobalState,
        setGlobalState,
        resetGlobalState,
        getGlobalStateSnapshot,
        
        // 错误处理
        handleApiError,
        safeApiRequest,
        
        // 常量
        VERSION: '2.0'
    };

})();
