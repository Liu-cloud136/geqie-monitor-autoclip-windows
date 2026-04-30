/**
 * 鸽切监控系统 - 数据管理器基类
 * 提供TodayDataManager和HistoryDataManager的公共功能
 */

(function() {
    'use strict';

    class BaseDataManager {
        constructor() {
            this.currentEditId = null;
            this.currentDeleteId = null;
            this.pendingAction = null;
        }

        /**
         * 安全的API请求（带重试机制）
         * @param {string} url - 请求URL
         * @param {Object} options - 请求选项
         * @param {number} maxRetries - 最大重试次数
         * @returns {Promise<any>}
         */
        async safeApiRequest(url, options = {}, maxRetries = 3) {
            for (let attempt = 1; attempt <= maxRetries; attempt++) {
                try {
                    return await window.Core.safeApiRequest(url, options);
                } catch (error) {
                    // 静默处理API请求失败
                    
                    if (attempt === maxRetries) {
                        throw error;
                    }
                    
                    // 指数退避策略
                    await new Promise(resolve => setTimeout(resolve, Math.pow(2, attempt) * 1000));
                }
            }
        }

        /**
         * 统一的错误处理
         * @param {Error} error - 错误对象
         * @param {string} context - 错误上下文
         * @param {Function} fallback - 降级处理函数
         */
        handleError(error, context = '操作失败', fallback = null) {
            // 使用统一的错误通知
            const errorMessage = error.message || '系统错误，请稍后重试';
            window.Core.showNotification(`${context}: ${errorMessage}`, 'error');
            
            // 执行降级处理
            if (fallback && typeof fallback === 'function') {
                try {
                    fallback();
                } catch (fallbackError) {
                    // 降级处理失败
                }
            }
        }

        /**
         * 检查管理员权限
         * @param {Event} event - 事件对象
         * @returns {Promise<boolean>}
         */
        async checkAdminPermission(event) {
            if (!window.Core.getGlobalState('isAdminLoggedIn')) {
                try {
                    const result = await window.ModalManager.showTemplate('adminLogin');
                    if (!result) {
                        event && event.preventDefault();
                        return false;
                    }
                } catch (error) {
                    this.handleError(error, '权限验证失败');
                    event && event.preventDefault();
                    return false;
                }
            }
            return true;
        }

        /**
         * 显示加载状态
         * @param {string} containerId - 容器ID
         * @param {string} message - 加载消息
         */
        showLoading(containerId, message = '加载中...') {
            const container = document.getElementById(containerId);
            if (container) {
                container.innerHTML = `
                    <div class="text-center py-4">
                        <div class="spinner-border text-primary" role="status">
                            <span class="visually-hidden">${message}</span>
                        </div>
                        <p class="mt-2 text-muted">${message}</p>
                    </div>
                `;
            }
        }

        /**
         * 显示空数据状态
         * @param {string} containerId - 容器ID
         * @param {string} message - 空数据消息
         */
        showEmptyState(containerId, message = '暂无数据') {
            const container = document.getElementById(containerId);
            if (container) {
                container.innerHTML = `
                    <div class="text-center py-4">
                        <i class="bi bi-inbox" style="font-size: 3rem; color: #6c757d;"></i>
                        <p class="mt-2 text-muted">${message}</p>
                    </div>
                `;
            }
        }

        /**
         * 批量更新DOM（减少重绘）
         * @param {HTMLElement} container - 容器元素
         * @param {Function} createElement - 创建元素的函数
         * @param {Array} data - 数据数组
         */
        batchUpdateDOM(container, createElement, data) {
            const fragment = document.createDocumentFragment();
            
            data.forEach((item, index) => {
                const element = createElement(item, index);
                if (element) {
                    fragment.appendChild(element);
                }
            });
            
            container.innerHTML = '';
            container.appendChild(fragment);
        }

        /**
         * 防抖函数
         * @param {Function} func - 要防抖的函数
         * @param {number} delay - 延迟时间
         * @returns {Function}
         */
        debounce(func, delay = 300) {
            return window.Core.debounce(func, delay);
        }

        /**
         * 节流函数
         * @param {Function} func - 要节流的函数
         * @param {number} delay - 延迟时间
         * @returns {Function}
         */
        throttle(func, delay = 300) {
            return window.Core.throttle(func, delay);
        }

        /**
         * 验证BV号
         * @param {string} bvCode - BV号
         * @returns {Object}
         */
        validateBVCode(bvCode) {
            return window.Core.validateBVCode(bvCode);
        }

        /**
         * HTML转义
         * @param {string} text - 原始文本
         * @returns {string}
         */
        escapeHtml(text) {
            return window.Core.escapeHtml(text);
        }
    }

    // 暴露基类
    window.BaseDataManager = BaseDataManager;

})();