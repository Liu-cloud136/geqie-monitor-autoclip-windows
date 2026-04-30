/**
 * 鸽切监控系统 - 统一弹窗管理模块
 * 替代原有的三套弹窗系统（simple-modals、utils.showModal、内联弹窗）
 * 提供一致的弹窗API
 */

(function() {
    'use strict';

    // 当前显示的弹窗栈
    const modalStack = [];
    
    // 遮罩层
    let overlay = null;

    /**
     * 创建遮罩层
     */
    function createOverlay() {
        if (overlay) return overlay;
        
        overlay = document.createElement('div');
        overlay.className = 'modal-overlay';
        overlay.style.cssText = `
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: rgba(0, 0, 0, 0.5);
            z-index: 9999;
            display: none;
        `;
        
        document.body.appendChild(overlay);
        return overlay;
    }

    /**
     * 显示遮罩层
     */
    function showOverlay() {
        const ov = createOverlay();
        ov.style.display = 'block';
    }

    /**
     * 隐藏遮罩层
     */
    function hideOverlay() {
        if (overlay && modalStack.length === 0) {
            overlay.style.display = 'none';
        }
    }

    /**
     * 检测是否为移动设备
     */
    function isMobile() {
        return window.innerWidth <= 768;
    }

    /**
     * 创建弹窗HTML
     * @param {Object} options - 弹窗配置
     * @returns {HTMLElement} 弹窗元素
     */
    function createModal(options) {
        const {
            id,
            title = '',
            content = '',
            size = 'medium', // small, medium, large
            showClose = true,
            closeOnOverlay = true,
            buttons = []
        } = options;

        const modal = document.createElement('div');
        modal.id = id;
        modal.className = 'modal-container';
        modal.setAttribute('role', 'dialog');
        modal.setAttribute('aria-modal', 'true');

        // 移动端使用更小的尺寸
        const mobile = isMobile();
        const sizeStyles = {
            small: mobile ? 'max-width: 320px; min-width: 280px;' : 'max-width: 420px; min-width: 360px;',
            medium: mobile ? 'max-width: 90%; min-width: 320px;' : 'max-width: 540px; min-width: 400px;',
            large: mobile ? 'max-width: 90%; min-width: 320px;' : 'max-width: 720px; min-width: 500px;'
        };

        modal.style.cssText = `
            display: none;
            position: fixed;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
            z-index: 10000;
            background: white;
            border-radius: ${mobile ? '8px' : '12px'};
            box-shadow: 0 10px 40px rgba(0,0,0,0.2);
            ${sizeStyles[size] || sizeStyles.medium};
            width: auto;
            max-height: ${mobile ? '85vh' : '80vh'};
            overflow: hidden;
        `;

        // 构建按钮HTML
        const buttonsHtml = buttons.map(btn => `
            <button type="button" 
                    class="btn ${btn.class || 'btn-secondary'}" 
                    data-result="${btn.result || ''}"
                    ${btn.primary ? 'data-primary="true"' : ''}>
                ${btn.icon ? `<i class="bi ${btn.icon}"></i> ` : ''}${btn.text}
            </button>
        `).join('');

        modal.innerHTML = `
            <div class="modal-header" style="
                background: linear-gradient(135deg, #ffe4e1 0%, #ffc0cb 100%);
                padding: ${mobile ? '0.875rem 1rem' : '1rem 1.25rem'};
                border-bottom: 1px solid rgba(255, 255, 255, 0.3);
                display: flex;
                align-items: center;
                justify-content: space-between;
                flex-shrink: 0;
            ">
                <h5 class="modal-title mb-0" style="color: #5a3e36; font-weight: 600; font-size: ${mobile ? '1rem' : '1.125rem'};">
                    ${title}
                </h5>
                ${showClose ? `
                    <button type="button" class="btn-close-modal" onclick="window.ModalManager.close('${id}')"
                            style="background: none; border: none; font-size: ${mobile ? '1.25em' : '1.5em'}; color: #5a3e36; cursor: pointer;">
                        ×
                    </button>
                ` : ''}
            </div>
            <div class="modal-body" style="padding: ${mobile ? '1rem' : '1.25rem'}; max-height: ${mobile ? '50vh' : '55vh'}; overflow-y: auto; font-size: ${mobile ? '0.875rem' : '0.95rem'};">
                ${content}
            </div>
            ${buttons.length > 0 ? `
                <div class="modal-footer" style="
                    padding: ${mobile ? '0.875rem 1rem' : '1rem 1.25rem'};
                    border-top: 1px solid #e5e7eb;
                    display: flex;
                    gap: ${mobile ? '0.5rem' : '0.625rem'};
                    justify-content: flex-end;
                    flex-shrink: 0;
                ">
                    ${buttonsHtml}
                </div>
            ` : ''}
        `;

    // 绑定按钮事件
    const buttonElements = modal.querySelectorAll('[data-result]');
    buttonElements.forEach(btn => {
        const result = btn.getAttribute('data-result');
        const clickHandler = () => {
            const primary = btn.hasAttribute('data-primary');

            // 对于特殊按钮需要特殊处理
            if (result === 'save') {handleSaveAction(id, modal);
            } else if (result === 'verify' && id === 'adminLoginModal') {// 管理员登录验证按钮特殊处理（异步）
                handleAdminLogin(id, modal).then((success) => {// 只有验证成功后才触发回调并关闭弹窗
                    if (success) {
                        const callback = modal.getAttribute('data-callback');
                        if (callback && window[callback]) {
                            window[callback](result, primary);
                        }
                        // 关闭弹窗
                        close(id);
                    }
                    // 验证失败时不关闭弹窗，让用户重新输入
                }).catch((error) => {});
                return; // 提前返回，不执行后续逻辑
            } else if (result === 'confirm' && id === 'deleteModal') {// 删除确认按钮特殊处理（异步）
                handleDeleteConfirm(id, modal).then((success) => {// 只有验证成功后才关闭弹窗
                    if (success) {
                        close(id);
                    }
                }).catch((error) => {});
                return; // 提前返回，不执行后续逻辑
            } else {
                // 触发回调 - 这是主要的处理方式
                const callback = modal.getAttribute('data-callback');
                if (callback && window[callback]) {
                    window[callback](result, primary);
                }
                // 关闭弹窗
                close(id);
            }
        };
        btn.addEventListener('click', clickHandler);
    });

        // 点击遮罩关闭
        if (closeOnOverlay) {
            modal.addEventListener('click', (e) => {
                if (e.target === modal) {
                    close(id);
                }
            });
        }

        document.body.appendChild(modal);
        return modal;
    }

    /**
     * 处理管理员登录验证
     * @param {string} id - 弹窗ID
     * @param {HTMLElement} modal - 弹窗元素
     * @returns {Promise<void>}
     */
    async function handleAdminLogin(id, modal) {
        const passwordInput = modal.querySelector('#adminLoginPassword');
        const errorContainer = modal.querySelector('#loginError');

        if (!passwordInput) {
            window.Core.showNotification('密码输入框未找到', 'error');
            return false;
        }

        const password = passwordInput.value.trim();
        if (!password) {
            if (errorContainer) {
                errorContainer.textContent = '请输入管理密码';
                errorContainer.classList.remove('d-none');
            }
            return false;
        }

        // 使用 AuthManager 验证密码
        if (window.AuthManager) {
            const result = await window.AuthManager.verifyAdminPassword(password);

            if (result.success) {
                // 验证成功，隐藏错误信息
                if (errorContainer) {
                    errorContainer.classList.add('d-none');
                }

                // 注意：不在这里关闭弹窗，让回调处理

                return true;
            } else {
                // 验证失败，显示错误信息
                if (errorContainer) {
                    errorContainer.textContent = result.error || '密码错误，请重试';
                    errorContainer.classList.remove('d-none');
                    setTimeout(() => {
                        errorContainer.classList.add('d-none');
                    }, 3000);
                }
                return false;
            }
        } else {
            window.Core.showNotification('认证模块未加载', 'error');
            return false;
        }
    }

    /**
     * 处理删除确认操作
     * @param {string} id - 弹窗ID
     * @param {HTMLElement} modal - 弹窗元素
     * @returns {Promise<boolean>}
     */
    async function handleDeleteConfirm(id, modal) {
        const passwordInput = modal.querySelector('#deletePassword');
        const errorContainer = modal.querySelector('#deleteError');

        if (!passwordInput) {
            window.Core.showNotification('密码输入框未找到', 'error');
            return false;
        }

        const password = passwordInput.value.trim();
        if (!password) {
            if (errorContainer) {
                errorContainer.textContent = '请输入管理密码';
                errorContainer.classList.remove('d-none');
            }
            return false;
        }

        // 使用 AuthManager 验证密码
        if (window.AuthManager) {
            const result = await window.AuthManager.verifyAdminPassword(password);

            if (result.success) {
                // 验证成功，隐藏错误信息
                if (errorContainer) {
                    errorContainer.classList.add('d-none');
                }

                // 触发实际的删除操作
                const callback = modal.getAttribute('data-callback');
                if (callback && window[callback]) {
                    window[callback]('confirm', true);
                }

                return true;
            } else {
                // 验证失败，显示错误信息
                if (errorContainer) {
                    errorContainer.textContent = result.error || '密码错误，删除失败';
                    errorContainer.classList.remove('d-none');
                    setTimeout(() => {
                        errorContainer.classList.add('d-none');
                    }, 3000);
                }
                return false;
            }
        } else {
            window.Core.showNotification('认证模块未加载', 'error');
            return false;
        }
    }

    /**
     * 处理保存操作
     * @param {string} id - 弹窗ID
     * @param {HTMLElement} modal - 弹窗元素
     */
    function handleSaveAction(id, modal) {
        // 检查是否正在处理中
        const isProcessing = modal.getAttribute('data-processing');
        if (isProcessing === 'true') {
            return;
        }

        // 标记为正在处理中
        modal.setAttribute('data-processing', 'true');

        // 判断当前页面类型 - 仅使用 URL 路径判断，因为两个页面都有 history-date 元素
        const isHistoryPage = window.location.pathname.includes('/history');

        // 根据弹窗类型调用相应的保存函数
        switch (id) {
            case 'skipModal':
                // 根据当前页面调用对应的保存函数
                const saveSkipReasonFunc = isHistoryPage ? (window.historySaveSkipReason || window.saveSkipReason) : window.saveSkipReason;
                if (saveSkipReasonFunc) {
                    // 将弹窗的输入框传递给保存函数
                    const skipReasonInput = modal.querySelector('#skipReason');
                    if (skipReasonInput) {
                        // 直接调用保存函数，让保存函数处理验证
                        try {
                            const result = saveSkipReasonFunc();
                            // 检查是否返回 Promise
                            if (result && typeof result.then === 'function') {
                                result
                                    .then(() => {
                                        modal.setAttribute('data-processing', 'false');
                                    })
                                    .catch((error) => {
                                        modal.setAttribute('data-processing', 'false');
                                    });
                            } else {
                                // 同步函数，直接清理
                                modal.setAttribute('data-processing', 'false');
                            }
                        } catch (error) {
                            modal.setAttribute('data-processing', 'false');
                        }
                    } else {
                        window.Core?.showNotification('输入框未找到', 'error');
                        modal.setAttribute('data-processing', 'false');
                    }
                } else {
                    modal.setAttribute('data-processing', 'false');
                }
                break;
            case 'sliceModal':
                // 根据当前页面调用对应的保存函数
                const saveSliceUrlFunc = isHistoryPage ? (window.historySaveSliceUrl || window.saveSliceUrl) : window.saveSliceUrl;
                if (saveSliceUrlFunc) {
                    try {
                        const result = saveSliceUrlFunc();
                        // 检查是否返回 Promise
                        if (result && typeof result.then === 'function') {
                            result
                                .then(() => {
                                    modal.setAttribute('data-processing', 'false');
                                })
                                .catch((error) => {
                                    modal.setAttribute('data-processing', 'false');
                                });
                        } else {
                            // 同步函数，直接清理
                            modal.setAttribute('data-processing', 'false');
                        }
                    } catch (error) {
                        modal.setAttribute('data-processing', 'false');
                    }
                } else {
                    modal.setAttribute('data-processing', 'false');
                }
                break;
            case 'editModal':
                // 根据当前页面调用对应的保存函数
                const saveEditFunc = isHistoryPage ? window.historySaveEdit : window.saveEdit;
                if (saveEditFunc) {
                    saveEditFunc().then(() => {}).catch((error) => {}).finally(() => {
                        modal.setAttribute('data-processing', 'false');
                    });
                } else {
                    modal.setAttribute('data-processing', 'false');
                }
                break;
            default:
                // 其他弹窗直接关闭
                modal.setAttribute('data-processing', 'false');
                close(id);
                break;
        }
    }

    /**
     * 显示弹窗
     * @param {string} id - 弹窗ID
     * @param {Object} options - 配置选项
     * @returns {Promise<any>} 弹窗操作结果
     */
    function show(id, options = {}) {
        return new Promise((resolve) => {
            let modal = document.getElementById(id);
            // 如果已存在，先删除旧弹窗，确保按钮事件正确绑定
            if (modal) {
                modal.remove();
            }

            // 创建新弹窗
            modal = createModal({ id, ...options });

            // 设置回调函数名
            const callbackName = `modal_callback_${id}_${Date.now()}`;
            window[callbackName] = (result) => {
                delete window[callbackName];
                resolve(result);
            };
            
            modal.setAttribute('data-callback', callbackName);
            modal.setAttribute('data-resolve', 'true');

            // 添加到栈
            modalStack.push(id);
            
            // 显示
            showOverlay();
            modal.style.display = 'block';
            
            // 聚焦第一个输入框
            setTimeout(() => {
                const firstInput = modal.querySelector('input, textarea');
                if (firstInput) firstInput.focus();
            }, 100);
        });
    }

    /**
     * 关闭弹窗
     * @param {string} id - 弹窗ID
     */
    function close(id, result = null) {
        const modal = document.getElementById(id);
        if (!modal) return;

        modal.style.display = 'none';

        // 从栈中移除
        const index = modalStack.indexOf(id);
        if (index > -1) {
            modalStack.splice(index, 1);
        }

        // 隐藏遮罩
        hideOverlay();

        // 触发回调（在删除之前）
        const callback = modal.getAttribute('data-callback');
        if (callback && window[callback]) {
            // 如果提供了 result，使用 result；否则使用 'cancel' 作为默认值
            window[callback](result || 'cancel');
            delete window[callback];
        }

        // 清空输入框
        const inputs = modal.querySelectorAll('input, textarea');
        inputs.forEach(input => {
            if (input.type !== 'password') {
                input.value = '';
            }
        });

        // 注意：不需要清理事件监听器
        // 因为每次 showTemplate 都会重新创建 modal DOM，不存在监听器累积问题
    }

    /**
     * 关闭所有弹窗
     */
    function closeAll() {
        [...modalStack].forEach(id => close(id));
    }

    /**
     * 预定义弹窗模板
     */
    const templates = {
        /**
         * 管理员登录弹窗
         */
        adminLogin: {
            id: 'adminLoginModal',
            title: '<i class="bi bi-shield-lock me-2"></i> 管理员验证',
            content: `
                <div class="text-center mb-3">
                    <p class="text-muted" style="font-size: 0.875rem;">请输入管理密码以解锁管理功能</p>
                </div>
                <div class="mb-3">
                    <div class="input-group input-group-lg">
                        <span class="input-group-text bg-light">
                            <i class="bi bi-key"></i>
                        </span>
                        <input type="password" class="form-control" id="adminLoginPassword" 
                               placeholder="输入管理密码" autocomplete="off">
                    </div>
                </div>
                <div id="loginError" class="alert alert-danger d-none py-2" role="alert">
                    <i class="bi bi-exclamation-circle me-2"></i> 密码错误，请重试
                </div>
            `,
            buttons: [
                { text: '取消', result: 'cancel', class: 'btn-outline-secondary' },
                { text: '验证', result: 'verify', class: 'btn-primary', primary: true, icon: 'bi-unlock' }
            ]
        },

        /**
         * 切片地址弹窗
         */
        slice: {
            id: 'sliceModal',
            title: '<i class="bi bi-play-circle text-primary me-2"></i> 添加切片地址',
            content: `
                <div class="mb-3">
                    <label for="sliceUrl" class="form-label fw-bold">BV 号</label>
                    <input type="text" class="form-control form-control-sm" id="sliceUrl" placeholder="例如：BV1xx411c7mD" 
                           oninput="window.Core.validateBVInput(this)">
                    <small class="text-muted" style="font-size: 0.75rem;">系统将自动生成B站视频链接</small>
                    <div id="sliceUrlError" class="invalid-feedback" style="display: none;"></div>
                    <div id="sliceUrlHelp" class="form-text" style="display: block; font-size: 0.75rem;">
                        输入正确的BV号，如 BV1xx411c7mD
                    </div>
                </div>
            `,
            buttons: [
                { text: '取消', result: 'cancel', class: 'btn-secondary' },
                { text: '保存', result: 'save', class: 'btn-primary', primary: true }
            ]
        },

        /**
         * 不切原因弹窗
         */
        skip: {
            id: 'skipModal',
            title: '<i class="bi bi-x-circle text-warning me-2"></i> 添加不切原因',
            content: `
                <div class="mb-3">
                    <label for="skipReason" class="form-label fw-bold">不切原因</label>
                    <textarea class="form-control" id="skipReason" rows="2" 
                              placeholder="请输入不切原因..." style="font-size: 0.875rem;"></textarea>
                </div>
            `,
            buttons: [
                { text: '取消', result: 'cancel', class: 'btn-secondary' },
                { text: '保存', result: 'save', class: 'btn-primary', primary: true }
            ]
        },

        /**
         * 删除确认弹窗
         */
        delete: {
            id: 'deleteModal',
            title: '<i class="bi bi-exclamation-triangle me-2"></i> 确认删除',
            content: `
                <p class="text-muted mb-3" style="font-size: 0.875rem;">删除后该记录将被永久移除，无法恢复。</p>
                <div class="mb-3">
                    <label for="deletePassword" class="form-label fw-bold">管理员密码</label>
                    <input type="password" class="form-control form-control-sm" id="deletePassword" placeholder="输入管理员密码">
                </div>
                <div id="deleteError" class="alert alert-danger d-none py-2" style="font-size: 0.875rem;">密码错误，删除失败</div>
            `,
            buttons: [
                { text: '取消', result: 'cancel', class: 'btn-outline-secondary' },
                { text: '确认删除', result: 'confirm', class: 'btn-danger', primary: true }
            ]
        },

        /**
         * 编辑记录弹窗
         */
        edit: {
            id: 'editModal',
            title: '<i class="bi bi-pencil-square me-2"></i> 编辑记录',
            content: `
                <div class="d-flex gap-2 mb-3">
                    <button class="btn btn-outline-primary flex-fill active" data-tab="slice" onclick="window.TodayDataManager ? TodayDataManager.switchEditTab('slice') : HistoryDataManager.switchEditTab('slice')" style="text-decoration: none; border: 1px solid #0d6efd; font-size: 0.875rem;">
                        <i class="bi bi-link-45deg me-1"></i>切片地址
                    </button>
                    <button class="btn btn-outline-secondary flex-fill" data-tab="skip" onclick="window.TodayDataManager ? TodayDataManager.switchEditTab('skip') : HistoryDataManager.switchEditTab('skip')" style="text-decoration: none; border: 1px solid #6c757d; font-size: 0.875rem;">
                        <i class="bi bi-x-circle me-1"></i>不切原因
                    </button>
                </div>

                <div id="slice-panel" class="tab-panel">
                    <div class="mb-3">
                        <label for="editSliceUrl" class="form-label fw-bold">BV 号</label>
                        <input type="text" class="form-control form-control-sm" id="editSliceUrl"
                               placeholder="例如：BV1xx411c7mD" oninput="window.Core.validateBVInput(this)">
                    </div>
                </div>

                <div id="skip-panel" class="tab-panel" style="display: none;">
                    <div class="mb-3">
                        <label for="editSkipReason" class="form-label fw-bold">不切原因</label>
                        <textarea class="form-control" id="editSkipReason" rows="2"
                                  placeholder="请输入不切原因..." style="font-size: 0.875rem;"></textarea>
                    </div>
                </div>
            `,
            buttons: [
                { text: '取消', result: 'cancel', class: 'btn-secondary' },
                { text: '保存', result: 'save', class: 'btn-primary', primary: true }
            ]
        },

    /**
     * 公告弹窗
     */
        announcement: {
            id: 'announcementModal',
            title: '<i class="bi bi-megaphone text-primary me-2"></i> 系统公告',
            size: 'medium',
            content: `
                <div id="announcementContent" style="padding: 15px 15px 0 15px; background: #f8f9fa; border-radius: 8px; line-height: 1.8; color: #333;">
                    <!-- 公告内容将动态加载 -->
                </div>
            `,
            buttons: [
                { text: '我知道了', result: 'close', class: 'btn-primary', primary: true }
            ],
            closeOnOverlay: false  // 不允许点击遮罩关闭
        }
    };

    /**
     * 显示模板弹窗
     * @param {string} templateName - 模板名称
     * @param {Object} options - 额外配置
     * @returns {Promise<any>}
     */
    function showTemplate(templateName, options = {}) {
        const template = templates[templateName];
        if (!template) {
            return Promise.resolve(null);
        }
        // 合并配置
        const mergedOptions = { ...template, ...options };

        return show(template.id, mergedOptions);
    }

    /**
     * ==================== 初始化 ====================
     */

    // 监听ESC键关闭弹窗
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape' && modalStack.length > 0) {
            close(modalStack[modalStack.length - 1]);
        }
    });

    /**
     * 显示切片地址弹窗（便捷方法）
     * @param {string} existingSliceUrl - 现有的切片地址（可选）
     * @returns {Promise<any>}
     */
    function showSliceModal(existingSliceUrl = '') {
        return showTemplate('slice');
    }

    /**
     * 显示删除确认弹窗（便捷方法）
     * @returns {Promise<any>}
     */
    function showDeleteModal() {
        return showTemplate('delete');
    }

    /**
     * 显示不切原因弹窗（便捷方法）
     * @returns {Promise<any>}
     */
    function showSkipModal() {
        return showTemplate('skip');
    }

    // 暴露API
    window.ModalManager = {
        show,
        close,
        closeAll,
        showTemplate,
        showSliceModal,
        showDeleteModal,
        showSkipModal,
        templates
    };})();
