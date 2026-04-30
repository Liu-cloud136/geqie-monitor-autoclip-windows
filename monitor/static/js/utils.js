/**
 * 鸽切监控系统 - 工具函数模块（精简版）
 * 提供通用工具函数，避免重复功能
 * 核心函数已移至 core.js，此文件仅保留特定工具
 */

(function() {
    'use strict';

    // 检查是否已加载 core.js，如果未加载则提供基础功能
    const hasCore = typeof window.Core !== 'undefined';
    
    /**
     * 处理错误显示
     * @param {Error} error - 错误对象
     * @param {string} containerId - 容器ID
     */
    function handleError(error, containerId) {
        const container = document.getElementById(containerId);
        if (container) {
            container.innerHTML = `
                <div class="text-center py-3">
                    <i class="bi bi-exclamation-triangle" style="font-size: 2rem; color: #ef4444;"></i>
                    <p class="mt-2 text-muted">加载失败: ${hasCore ? window.Core.escapeHtml(error.message) : error.message}</p>
                </div>
            `;
        }
    }

    /**
     * 验证邮箱格式
     * @param {string} email - 邮箱地址
     * @returns {boolean} 是否有效
     */
    function isValidEmail(email) {
        const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
        return emailRegex.test(email);
    }

    /**
     * 验证手机号格式
     * @param {string} phone - 手机号
     * @returns {boolean} 是否有效
     */
    function isValidPhone(phone) {
        const phoneRegex = /^1[3-9]\d{9}$/;
        return phoneRegex.test(phone);
    }

    /**
     * 加载CSS文件
     * @param {string} href - CSS文件路径
     * @param {string} id - 样式表ID（可选）
     */
    function loadCSS(href, id = '') {
        return new Promise((resolve, reject) => {
            const link = document.createElement('link');
            link.rel = 'stylesheet';
            link.href = href;
            if (id) link.id = id;
            
            link.onload = resolve;
            link.onerror = reject;
            
            document.head.appendChild(link);
        });
    }

    /**
     * 加载JavaScript文件
     * @param {string} src - JS文件路径
     * @param {string} id - 脚本ID（可选）
     */
    function loadJS(src, id = '') {
        return new Promise((resolve, reject) => {
            const script = document.createElement('script');
            script.src = src;
            if (id) script.id = id;
            
            script.onload = resolve;
            script.onerror = reject;
            
            document.head.appendChild(script);
        });
    }

    // 弹窗管理功能已移至 modal-manager.js，此处不再重复实现

    // 通知和验证功能已移至 core.js 和 modal-manager.js，此处不再重复实现

    // 暴露精简后的API
    window.Utils = {
        handleError: handleError,
        isValidEmail: isValidEmail,
        isValidPhone: isValidPhone,
        loadCSS: loadCSS,
        loadJS: loadJS
    };

})();