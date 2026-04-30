/**
 * 鸽切监控系统 - 认证管理模块
 * 提供管理员登录验证和权限检查功能
 * 使用IIFE封装，避免全局变量污染
 */

(function() {
    'use strict';

    // 私有变量
    let isAdminLoggedIn = false;
    let adminSessionPassword = '';
    let authCallbacks = [];

    /**
     * 管理员登录验证
     * @param {string} password - 管理员密码
     * @returns {Promise<Object>} 验证结果
     */
    async function verifyAdminPassword(password) {
        if (!password) {
            return {
                success: false,
                error: '请输入管理密码'
            };
        }

        try {
            // 从后端验证密码
            const response = await fetch('/api/verify_password', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    password: password
                })
            });

            const result = await response.json();

            if (result.success) {
                isAdminLoggedIn = true;
                adminSessionPassword = password;

                // 同时更新 Core 全局状态
                if (window.Core) {
                    window.Core.setGlobalState('isAdminLoggedIn', true);
                }

                notifyAuthChange();

                return {
                    success: true,
                    message: '管理员权限已启用'
                };
            } else {
                return {
                    success: false,
                    error: result.error || '密码错误，请重试'
                };
            }
        } catch (error) {
            return {
                success: false,
                error: '系统配置错误：' + error.message
            };
        }
    }

    /**
     * 检查管理员权限
     * @returns {boolean} 是否有管理员权限
     */
    function checkAdminPermission() {
        return isAdminLoggedIn;
    }

    /**
     * 获取当前会话密码（用于API调用）
     * @returns {string} 会话密码
     */
    function getSessionPassword() {
        return adminSessionPassword;
    }

    /**
     * 登出管理员
     */
    function logoutAdmin() {
        isAdminLoggedIn = false;
        adminSessionPassword = '';

        // 同时清除 Core 全局状态
        if (window.Core) {
            window.Core.setGlobalState('isAdminLoggedIn', false);
        }

        notifyAuthChange();
    }

    /**
     * 设置管理员登录状态（用于从外部更新状态）
     * @param {boolean} loggedIn - 是否已登录
     */
    function setAdminLoggedIn(loggedIn) {
        isAdminLoggedIn = loggedIn;
        if (!loggedIn) {
            adminSessionPassword = '';
        }

        // 同时更新 Core 全局状态
        if (window.Core) {
            window.Core.setGlobalState('isAdminLoggedIn', loggedIn);
        }

        notifyAuthChange();
    }

    /**
     * 获取登录状态
     * @returns {boolean} 是否已登录
     */
    function getLoginStatus() {
        return isAdminLoggedIn;
    }

    /**
     * 添加认证状态变化监听器
     * @param {Function} callback - 状态变化时的回调函数
     */
    function onAuthChange(callback) {
        if (typeof callback === 'function') {
            authCallbacks.push(callback);
        }
    }

    /**
     * 移除认证状态变化监听器
     * @param {Function} callback - 要移除的回调函数
     */
    function offAuthChange(callback) {
        const index = authCallbacks.indexOf(callback);
        if (index > -1) {
            authCallbacks.splice(index, 1);
        }
    }

    /**
     * 通知所有监听器认证状态已变化
     */
    function notifyAuthChange() {
        authCallbacks.forEach(callback => {
            try {
                callback(isAdminLoggedIn);
            } catch (error) {
                // 认证状态变化回调执行失败
            }
        });
    }

    /**
     * 更新记录（通用方法，需要管理员权限）
     * @param {number} recordId - 记录ID
     * @param {string} sliceUrl - 切片地址（可选）
     * @param {string} skipReason - 跳过原因（可选）
     * @returns {Promise<Object>} 操作结果
     */
    async function updateRecord(recordId, sliceUrl, skipReason) {
        if (!isAdminLoggedIn) {
            return {
                success: false,
                error: '需要管理员权限'
            };
        }

        // 检查会话密码是否为空（会话过期或刷新页面后）
        if (!adminSessionPassword) {
            return {
                success: false,
                error: '会话已过期，请重新输入管理密码',
                needReauth: true
            };
        }

        try {
            const response = await fetch('/api/record/update', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    id: recordId,
                    slice_url: sliceUrl || '',
                    skip_reason: skipReason || '',
                    password: adminSessionPassword
                })
            });

            return await response.json();
        } catch (error) {
            return {
                success: false,
                error: '操作失败: ' + error.message
            };
        }
    }

    /**
     * 删除记录（需要管理员权限）
     * @param {number} recordId - 记录ID
     * @returns {Promise<Object>} 操作结果
     */
    async function deleteRecord(recordId) {
        if (!isAdminLoggedIn) {
            return {
                success: false,
                error: '需要管理员权限'
            };
        }

        // 检查会话密码是否为空（会话过期或刷新页面后）
        if (!adminSessionPassword) {
            return {
                success: false,
                error: '会话已过期，请重新输入管理密码',
                needReauth: true
            };
        }

        try {
            const response = await fetch('/api/record/delete', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    id: recordId,
                    password: adminSessionPassword
                })
            });

            return await response.json();
        } catch (error) {
            return {
                success: false,
                error: '操作失败: ' + error.message
            };
        }
    }

    /**
     * 从表单获取密码并验证
     * 此函数用于直接从页面表单元素获取密码
     * @param {string} passwordInputId - 密码输入框ID
     * @param {string} errorContainerId - 错误信息容器ID
     * @returns {Promise<boolean>} 验证是否成功
     */
    async function verifyFromForm(passwordInputId = 'adminLoginPassword', errorContainerId = 'loginError') {
        const passwordInput = document.getElementById(passwordInputId);
        const errorContainer = document.getElementById(errorContainerId);
        
        if (!passwordInput) {
            Utils.showAlert('密码输入框不存在', '系统错误');
            return false;
        }

        const password = passwordInput.value;
        
        if (!password) {
            Utils.showAlert('请输入管理密码', '输入错误');
            return false;
        }

        const result = await verifyAdminPassword(password);
        
        if (result.success) {
            // 隐藏错误信息
            if (errorContainer) {
                errorContainer.classList.add('d-none');
            }
            return true;
        } else {
            // 显示错误信息
            if (errorContainer) {
                errorContainer.textContent = result.error || '密码错误';
                errorContainer.classList.remove('d-none');
                setTimeout(() => {
                    errorContainer.classList.add('d-none');
                }, 3000);
            }
            return false;
        }
    }

    /**
     * 初始化认证模块
     * 此函数应在页面加载完成后调用
     * @param {Object} options - 配置选项
     */
    function initAuth(options = {}) {
        // 从会话存储恢复登录状态（可选）
        if (options.persistSession) {
            try {
                const savedAuth = sessionStorage.getItem('geqie_admin_auth');
                if (savedAuth) {
                    const authData = JSON.parse(savedAuth);
                    // 只恢复登录状态，不恢复密码
                    isAdminLoggedIn = authData.isAdminLoggedIn || false;
                    adminSessionPassword = '';  // 密码需要重新输入

                    // 同时恢复 Core 全局状态
                    if (window.Core) {
                        window.Core.setGlobalState('isAdminLoggedIn', isAdminLoggedIn);
                    }

                    if (isAdminLoggedIn) {
                        // 登录状态已恢复，但密码需要重新输入
                        // 可以在这里提示用户重新输入密码以进行管理操作
                    }
                }
            } catch (error) {
                // 恢复登录状态失败
            }
        }
    }

    // 保存登录状态到会话存储（不保存密码，只保存登录状态）
    function saveAuthToStorage() {
        const authData = {
            isAdminLoggedIn: isAdminLoggedIn
            // 不再保存 adminSessionPassword 到存储
        };
        sessionStorage.setItem('geqie_admin_auth', JSON.stringify(authData));
    }

    // 暴露公共API
    window.AuthManager = {
        verifyAdminPassword: verifyAdminPassword,
        verifyFromForm: verifyFromForm,
        checkAdminPermission: checkAdminPermission,
        getSessionPassword: getSessionPassword,
        logoutAdmin: logoutAdmin,
        setAdminLoggedIn: setAdminLoggedIn,
        getLoginStatus: getLoginStatus,
        onAuthChange: onAuthChange,
        offAuthChange: offAuthChange,
        updateRecord: updateRecord,
        deleteRecord: deleteRecord,
        initAuth: initAuth
    };

    // 自动保存登录状态（每次状态变化时）
    onAuthChange(function() {
        saveAuthToStorage();
    });

})();