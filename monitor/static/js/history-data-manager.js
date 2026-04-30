/**
 * 鸽切监控系统 - 历史数据管理模块
 * 负责历史数据查询相关功能
 */

(function() {
    'use strict';

    class HistoryDataManager extends BaseDataManager {
        constructor() {
            super(); // 调用父类构造函数
            this.currentHistoryData = [];
            this.modalCloseListener = null;
            this.authChangeListener = null;
            this.trendChart = null;}

        /**
         * 初始化历史数据页面
         */
        init() {// 设置导航栏激活状态
            this.setNavActive();

            // 初始化日期选择器
            this.setupHistoryDate();

            // 绑定事件监听器
            this.bindEventListeners();

            // 监听管理员权限状态变化
            this.setupAuthChangeListener();

            // 加载统计数据和趋势图表
            this.loadStats();}

        /**
         * 设置导航栏激活状态
         */
        setNavActive() {
            const navLinks = document.querySelectorAll('.nav-link[data-page]');
            navLinks.forEach(l => l.classList.remove('active'));
            const historyLink = document.querySelector('.nav-link[data-page="history"]');
            if (historyLink) {
                historyLink.classList.add('active');
            }
        }

        /**
         * 页面加载时设置默认日期
         */
        setupHistoryDate() {setTimeout(() => {
                const dateInput = document.getElementById('history-date');
                if (!dateInput) {return;
                }
                
                const today = new Date();
                const localDateString = today.toLocaleDateString('en-CA');// 设置默认日期为今天
                dateInput.value = localDateString;// 设置最大可选日期为今天
                dateInput.max = localDateString;// 触发change事件加载数据
                setTimeout(() => {dateInput.dispatchEvent(new Event('change'));
                }, 100);}, 500);
        }

        /**
         * 绑定事件监听器
         */
        bindEventListeners() {
            const dateInput = document.getElementById('history-date');
            if (dateInput) {
                dateInput.addEventListener('change', () => {
                    this.loadHistoryData();
                });
            }

            // 绑定日历图标点击事件
            const calendarButton = document.querySelector('.btn-outline-secondary');
            if (calendarButton) {
                calendarButton.addEventListener('click', () => {
                    const dateInput = document.getElementById('history-date');
                    if (dateInput) {
                        dateInput.showPicker();
                    }
                });
            }
        }

        /**
         * 加载历史数据
         */
        async loadHistoryData() {
            const dateInput = document.getElementById('history-date');
            let selectedDate = dateInput.value;
            
            if (!selectedDate) {
                window.Core.showNotification('请选择日期', 'warning');
                return;
            }
            
            // 验证日期不超过今天
            const today = new Date();
            const todayLocal = today.toLocaleDateString('en-CA');
            
            if (selectedDate > todayLocal) {
                window.Core.showNotification('不能选择未来日期，已自动调整为今天', 'warning');
                dateInput.value = todayLocal;
                selectedDate = todayLocal;
            }
            
            try {
                // 显示加载状态
                this.showLoading('history-data-body', '正在加载历史数据...');
                
                // 使用统一的API请求方法
                const data = await this.safeApiRequest(`/api/date/${selectedDate}`);
                
                if (data.success) {
                    this.currentHistoryData = data.data;
                    this.updateHistoryTable(data.data, selectedDate);
                } else {
                    throw new Error(data.error || '服务器返回错误');
                }
            } catch (error) {
                this.handleError(error, '加载历史数据', () => {
                    // 降级处理：显示错误状态
                    const container = document.getElementById('history-data-container');
                    const tbody = document.getElementById('history-data-body');
                    
                    if (container && tbody) {
                        tbody.innerHTML = `
                            <tr>
                                <td colspan="2" class="text-center py-4 text-danger">
                                    <i class="bi bi-exclamation-triangle text-3xl"></i>
                                    <p class="mt-2 mb-0">加载失败，请重试</p>
                                    <button class="btn btn-sm btn-outline-primary mt-2" onclick="window.HistoryDataManager.loadHistoryData()">重试</button>
                                </td>
                            </tr>
                        `;
                        container.style.display = 'block';
                    }
                });
            }
        }

        /**
         * 更新历史数据表格（优化版）
         */
        updateHistoryTable(data, selectedDate) {
            // 保存当前数据，供编辑功能使用
            this.currentHistoryData = data;

            const container = document.getElementById('history-data-container');
            const tbody = document.getElementById('history-data-body');
            const totalCount = document.getElementById('history-total-count');

            if (!container || !tbody || !totalCount) {return;
            }
            
            if (data.length === 0) {
                // 显示空数据状态
                tbody.innerHTML = `
                    <tr>
                        <td colspan="3" class="text-center py-4 empty-data-cell">
                            <div class="d-flex flex-column align-items-center justify-content-center">
                                <i class="bi bi-inbox text-3xl text-bilibili-light mb-2"></i>
                                <p class="mb-0 text-muted">${window.Core.escapeHtml(selectedDate)} 暂无数据</p>
                            </div>
                        </td>
                    </tr>
                `;
                totalCount.textContent = '共0条记录';
            } else {
                // 使用批量DOM更新优化性能
                this.batchUpdateDOM(tbody, (item) => {
                    const hasSlice = item.slice_url && item.slice_url.trim();
                    const hasReason = item.skip_reason && item.skip_reason.trim();
                    
                    let actionButtons = '';
                    
                    if (hasSlice) {
                        if (window.Core && window.Core.getGlobalState('isAdminLoggedIn')) {
                            actionButtons = `
                                <div class="d-flex justify-content-center gap-2">
                                    <a href="${window.Core.escapeHtml(item.slice_url)}" target="_blank" class="btn btn-sm btn-success btn-sm-compact">
                                        <i class="bi bi-play-circle"></i> 已切片
                                    </a>
                                    <button class="btn btn-sm btn-outline-primary btn-sm-compact" onclick="HistoryDataManager.openEditModal(${item.id})">
                                        <i class="bi bi-pencil"></i> 修改
                                    </button>
                                    <button class="btn btn-sm btn-outline-danger btn-sm-compact" onclick="HistoryDataManager.openDeleteModal(${item.id})">
                                        <i class="bi bi-trash"></i> 删除
                                    </button>
                                </div>
                            `;
                        } else {
                            actionButtons = `
                                <div class="d-flex justify-content-center gap-2">
                                    <a href="${window.Core.escapeHtml(item.slice_url)}" target="_blank" class="btn btn-sm btn-success btn-sm-compact">
                                        <i class="bi bi-play-circle"></i> 已切片
                                    </a>
                                    <button class="btn btn-sm btn-outline-primary btn-sm-compact" onclick="HistoryDataManager.handleLoginClick(event)">
                                        <i class="bi bi-shield-lock"></i> 需要登录
                                    </button>
                                </div>
                            `;
                        }
                    } else if (hasReason) {
                        if (window.Core && window.Core.getGlobalState('isAdminLoggedIn')) {
                            actionButtons = `
                                <div class="d-flex flex-column align-items-center gap-1">
                                    <div class="d-flex justify-content-center gap-2">
                                        <button class="btn btn-sm btn-sm-compact gradient-skip-reason">
                                            <i class="bi bi-x-circle"></i> 已处理
                                        </button>
                                        <button class="btn btn-sm btn-outline-primary btn-sm-compact" onclick="HistoryDataManager.openEditModal(${item.id})">
                                            <i class="bi bi-pencil"></i> 修改
                                        </button>
                                        <button class="btn btn-sm btn-outline-danger btn-sm-compact" onclick="HistoryDataManager.openDeleteModal(${item.id})">
                                            <i class="bi bi-trash"></i> 删除
                                        </button>
                                    </div>
                                    <div class="d-flex justify-content-center">
                                        <small class="text-muted text-2xs skip-reason-text" title="${window.Core.escapeHtml(item.skip_reason)}">
                                            <i class="bi bi-chat-quote me-1"></i>${window.Core.escapeHtml(item.skip_reason)}
                                        </small>
                                    </div>
                                </div>
                            `;
                        } else {
                            actionButtons = `
                                <div class="d-flex flex-column align-items-center gap-1">
                                    <div class="d-flex justify-content-center gap-2">
                                        <button class="btn btn-sm btn-sm-compact gradient-skip-reason">
                                            <i class="bi bi-x-circle"></i> 已处理
                                        </button>
                                    <button class="btn btn-sm btn-outline-primary btn-sm-compact" onclick="HistoryDataManager.handleLoginClick(event)">
                                        <i class="bi bi-shield-lock"></i> 需要登录
                                    </button>
                                    </div>
                                    <div class="d-flex justify-content-center">
                                        <small class="text-muted text-2xs skip-reason-text" title="${window.Core.escapeHtml(item.skip_reason)}">
                                            <i class="bi bi-chat-quote me-1"></i>${window.Core.escapeHtml(item.skip_reason)}
                                        </small>
                                    </div>
                                </div>
                            `;
                        }
                    } else {
                        if (window.Core && window.Core.getGlobalState('isAdminLoggedIn')) {
                            actionButtons = `
                                <div class="d-flex justify-content-center gap-2">
                                    <button class="btn btn-sm btn-outline-primary btn-sm-compact" onclick="HistoryDataManager.openSliceModal(${item.id})">
                                        <i class="bi bi-link-45deg"></i> 切片
                                    </button>
                                    <button class="btn btn-sm btn-outline-secondary btn-sm-compact" onclick="HistoryDataManager.openSkipModal(${item.id})">
                                        <i class="bi bi-x-circle"></i> 不切
                                    </button>
                                    <button class="btn btn-sm btn-outline-danger btn-sm-compact" onclick="HistoryDataManager.openDeleteModal(${item.id})">
                                        <i class="bi bi-trash"></i> 删除
                                    </button>
                                </div>
                            `;
                        } else {
                            actionButtons = `
                                <div class="d-flex justify-content-center gap-2">
                                    <button class="btn btn-sm btn-outline-primary btn-sm-compact" onclick="HistoryDataManager.handleLoginClick(event)">
                                        <i class="bi bi-shield-lock"></i> 需要登录
                                    </button>
                                </div>
                            `;
                        }
                    }
                    
                    // 检查邮件状态
                    const emailStatus = item.email_status || 'none';
                    
                    // 根据邮件状态设置行样式
                    let rowStyle = '';
                    if (emailStatus === 'success') {
                        rowStyle = 'style="border-left: 4px solid #28a745; background-color: rgba(40, 167, 69, 0.05);"';
                    } else if (emailStatus === 'failed') {
                        rowStyle = 'style="border-left: 4px solid #dc3545; background-color: rgba(220, 53, 69, 0.05);"';
                    }
                    
                    // 创建表格行元素
                    const row = document.createElement('tr');
                    row.className = 'data-row';
                    row.setAttribute('style', rowStyle.replace('style="', '').replace('"', ''));
                    
                    let ratingCell = '';
                    const itemRating = item.rating || 0;
                    
                    if (itemRating > 0) {
                        const filledStars = '★'.repeat(itemRating);
                        const emptyStars = '☆'.repeat(5 - itemRating);
                        ratingCell = `
                            <td class="table-cell-center rating-cell">
                                <span class="rated-stars" title="已评分: ${itemRating}星">${filledStars}${emptyStars}</span>
                            </td>
                        `;
                    } else {
                        ratingCell = `
                            <td class="table-cell-center rating-cell">
                                <div class="rating-stars" data-record-id="${item.id}">
                                    <span class="star" data-value="1">☆</span>
                                    <span class="star" data-value="2">☆</span>
                                    <span class="star" data-value="3">☆</span>
                                    <span class="star" data-value="4">☆</span>
                                    <span class="star" data-value="5">☆</span>
                                </div>
                            </td>
                        `;
                    }
                    
                    row.innerHTML = `
                        ${ratingCell}
                        <td class="table-cell-center">
                            <div class="d-flex flex-column align-items-center">
                                <span class="badge user-badge">${window.Core.escapeHtml(item.username)}</span>
                                <small class="time-badge mt-1">${item.time_display}</small>
                            </div>
                        </td>
                        <td class="table-cell-center">${actionButtons}</td>
                    `;
                    
                    return row;
                }, data);
                
                totalCount.textContent = `共${data.length}条记录`;
            }
            
            // 显示表格容器
            container.style.display = 'block';
            
            this.initRatingEvents();
        }

        /**
         * 初始化评分事件
         */
        initRatingEvents() {
            const ratingContainers = document.querySelectorAll('#history-data-body .rating-stars');
            
            ratingContainers.forEach(container => {
                const recordId = container.dataset.recordId;
                const stars = container.querySelectorAll('.star');
                
                stars.forEach((star, index) => {
                    star.addEventListener('mouseenter', () => {
                        for (let i = 0; i <= index; i++) {
                            stars[i].textContent = '★';
                            stars[i].classList.add('hovered');
                        }
                        for (let i = index + 1; i < 5; i++) {
                            stars[i].textContent = '☆';
                            stars[i].classList.remove('hovered');
                        }
                    });
                    
                    star.addEventListener('mouseleave', () => {
                        stars.forEach(s => {
                            s.textContent = '☆';
                            s.classList.remove('hovered');
                        });
                    });
                    
                    star.addEventListener('click', (e) => {
                        e.stopPropagation();
                        const rating = parseInt(star.dataset.value);
                        this.submitRating(recordId, rating, container);
                    });
                });
            });
        }

        /**
         * 提交评分
         */
        async submitRating(recordId, rating, container) {
            try {
                const response = await fetch('/api/record/rate', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({
                        id: parseInt(recordId),
                        rating: rating
                    })
                });
                
                const result = await response.json();
                
                if (result.success) {
                    const filledStars = '★'.repeat(rating);
                    const emptyStars = '☆'.repeat(5 - rating);
                    container.outerHTML = `<span class="rated-stars" title="已评分: ${rating}星">${filledStars}${emptyStars}</span>`;
                    
                    if (window.Core && window.Core.showNotification) {
                        window.Core.showNotification(`评分成功: ${rating} 星`, 'success');
                    }
                } else {
                    if (window.Core && window.Core.showNotification) {
                        window.Core.showNotification(result.error || '评分失败', 'error');
                    }
                }
            } catch (error) {
                console.error('提交评分失败:', error);
                if (window.Core && window.Core.showNotification) {
                    window.Core.showNotification('评分失败: ' + error.message, 'error');
                }
            }
        }

        /**
         * 检查管理员权限
         */
        async checkAdminPermission(event, actionCallback = null) {
            if (!window.Core || !window.Core.getGlobalState('isAdminLoggedIn')) {
                // 阻止默认行为（如按钮点击）
                if (event) {
                    event.preventDefault();
                    event.stopPropagation();
                }
                
                // 保存待执行的操作
                if (actionCallback) {
                    window.Core.setGlobalState('pendingAction', actionCallback);
                }
                
                // 使用统一弹窗管理器
                try {
                    const result = await window.ModalManager.showTemplate('adminLogin');
                    if (result === 'verify') {
                        // 授予管理员权限
                        window.Core.setGlobalState('isAdminLoggedIn', true);

                        // 同时更新 AuthManager 状态
                        if (window.AuthManager) {
                            window.AuthManager.setAdminLoggedIn(true);
                        }

                        // 显示管理员徽章
                        const adminBadge = document.getElementById('admin-badge');
                        if (adminBadge) adminBadge.classList.remove('d-none');

                        // 执行待处理的操作
                        const pending = window.Core.getGlobalState('pendingAction');
                        if (pending) {
                            pending();
                            window.Core.setGlobalState('pendingAction', null);
                        }

                        // 刷新表格以显示管理按钮
                        this.refreshHistoryTable();

                        window.Core.showNotification('管理员权限已启用', 'success');
                        return true;
                    }
                } catch (error) {}
                return false;
            }
            return true;
        }

        /**
         * 打开切片地址弹窗（使用统一弹窗管理器）
         */
        async openSliceModal(recordId, existingSliceUrl = '', event = null) {// 检查管理员权限
            const hasPermission = await this.checkAdminPermission(event);
            if (!hasPermission) return;

            this.currentEditId = recordId;

            // 使用 showTemplate 而不是 showSliceModal，以便正确处理回调
            // 注意：不再使用 Promise 回调，因为 handleSaveAction 已经处理了保存逻辑
            if (window.ModalManager) {
                window.ModalManager.showTemplate('slice');

                // 延迟预填充数据，确保弹窗已加载
                setTimeout(() => {
                    const sliceUrlInput = document.getElementById('sliceUrl');
                    if (sliceUrlInput) {
                        sliceUrlInput.value = existingSliceUrl;
                    }
                }, 100);
            } else {}
        }

        /**
         * 打开不切原因弹窗（使用统一弹窗管理器）
         */
        async openSkipModal(recordId, existingReason = '', event = null) {// 检查管理员权限
            const hasPermission = await this.checkAdminPermission(event);
            if (!hasPermission) return;

            this.currentEditId = recordId;

            // 使用 showTemplate 而不是 showSkipModal，以便正确处理回调
            // 注意：不再使用 Promise 回调，因为 handleSaveAction 已经处理了保存逻辑
            if (window.ModalManager) {
                window.ModalManager.showTemplate('skip');

                // 延迟预填充数据，确保弹窗已加载
                setTimeout(() => {
                    const skipReasonInput = document.getElementById('skipReason');
                    if (skipReasonInput) {
                        skipReasonInput.value = existingReason;
                    }
                }, 100);
            } else {}
        }

        /**
         * 打开编辑弹窗
         */
        async openEditModal(recordId, event = null) {// 检查管理员权限
            const hasPermission = await this.checkAdminPermission(event);
            if (!hasPermission) return;

            this.currentEditId = recordId;

            // 获取记录数据以预填充
            let existingSliceUrl = '';
            let existingSkipReason = '';
            let isSliceActive = true;  // 默认显示切片标签页

            // 从当前历史数据中查找记录
            const record = this.currentHistoryData?.find(r => r.id === recordId);
            if (record) {
                existingSliceUrl = record.slice_url || '';
                existingSkipReason = record.skip_reason || '';
                // 如果有切片地址，默认显示切片标签页，否则显示不切原因标签页
                isSliceActive = !!record.slice_url;
            }

            // 使用统一弹窗管理器打开弹窗
            window.ModalManager.showTemplate('edit').then(result => {
                if (result === 'save') {
                    // 保存编辑
                    window.historySaveEdit();
                }
            });

            // 延迟预填充数据，确保弹窗已加载
            setTimeout(() => {
                const editSliceUrlInput = document.getElementById('editSliceUrl');
                const editSkipReasonInput = document.getElementById('editSkipReason');

                if (editSliceUrlInput) {
                    // 从完整URL中提取BV号
                    if (existingSliceUrl && typeof existingSliceUrl === 'string') {
                        // 匹配BV号(通常以BV开头,后跟10个字符)
                        const bvMatch = existingSliceUrl.match(/BV[a-zA-Z0-9]{10}/);
                        editSliceUrlInput.value = bvMatch ? bvMatch[0] : '';
                    } else {
                        editSliceUrlInput.value = '';
                    }
                }
                if (editSkipReasonInput) editSkipReasonInput.value = existingSkipReason;

                // 根据数据默认显示对应的标签页
                setTimeout(() => {
                    if (isSliceActive) {
                        window.HistoryDataManager.switchEditTab('slice');
                    } else {
                        window.HistoryDataManager.switchEditTab('skip');
                    }
                }, 100);
            }, 200);
        }

        /**
         * 打开删除确认弹窗（使用统一弹窗管理器）
         */
        async openDeleteModal(recordId, event = null) {
            const hasPermission = await this.checkAdminPermission(event);
            if (!hasPermission) return;

            // 使用统一的弹窗管理器
            if (window.ModalManager) {
                // 先保存当前recordId到全局状态，供后续使用
                window.Core.setGlobalState('currentDeleteRecordId', recordId);
                
                // 使用showTemplate方法显示删除弹窗
                window.ModalManager.showTemplate('delete', {
                    dataCallback: 'handleDeleteModalCallback'
                }).then(result => {
                    if (result === 'confirm') {
                        this.handleDeleteConfirmation(recordId);
                    }
                });
            } else {}
        }

        /**
         * 确认删除记录
         */
        async handleDeleteConfirmation(recordId) {
            try {
                const response = await fetch('/api/record/delete', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        id: recordId,
                        password: window.AuthManager.getSessionPassword()
                    })
                });

                const data = await response.json();

                if (data.success) {
                    window.Core.showNotification('删除成功', 'success');
                    this.refreshHistoryData();
                } else {
                    window.Core.showNotification('删除失败: ' + (data.error || '未知错误'), 'error');
                }
            } catch (error) {window.Core.showNotification('删除失败: ' + error.message, 'error');
            }
        }

        /**
         * 设置弹窗关闭监听器
         */
        setupModalCloseListener(modalId) {
            // 先清除之前的监听器
            if (this.modalCloseListener) {
                clearInterval(this.modalCloseListener);
            }
            
            // 设置新的监听器
            this.modalCloseListener = setInterval(() => {
                const modal = document.getElementById(modalId);
                if (!modal || modal.style.display === 'none' || modal.classList.contains('d-none')) {
                    // 弹窗已关闭，刷新历史数据
                    clearInterval(this.modalCloseListener);
                    this.modalCloseListener = null;
                    
                    // 延迟刷新，确保操作已完成
                    setTimeout(() => {
                        this.refreshHistoryData();
                    }, 300);
                }
            }, 100);
        }

        /**
         * 刷新历史数据
         */
        refreshHistoryData() {
            // 检查当前页面是否是历史数据页面
            const currentPage = document.querySelector('.nav-link.active[data-page]');
            if (!currentPage || currentPage.getAttribute('data-page') !== 'history') {
                return;
            }

            // 检查是否有历史数据容器
            const container = document.getElementById('history-data-container');
            if (!container || container.style.display === 'none') {
                return;
            }

            // 检查是否有选中的日期
            const dateInput = document.getElementById('history-date');
            if (!dateInput || !dateInput.value) {
                return;
            }this.loadHistoryData();
        }

        /**
         * 加载统计数据
         */
        async loadStats() {
            try {
                const response = await fetch('/api/stats?days=7');
                const data = await response.json();

                if (data.success) {
                    const stats = data.total_stats;

                    document.getElementById('total-count').textContent = stats.total_count.toLocaleString();
                    document.getElementById('week-count').textContent = stats.week_count.toLocaleString();

                    // 无论是否有数据，都调用 updateTopUsers 来更新显示状态
                    if (stats.top_users && stats.top_users.length > 0) {
                        const topUserCountElement = document.getElementById('top-user-count');
                        if (topUserCountElement) {
                            topUserCountElement.textContent = stats.top_users[0].count.toLocaleString();
                        }
                    }
                    this.updateTopUsers(stats.top_users || []);

                    this.updateTrendChart(data.daily_stats || []);
                } else {}
            } catch (error) {}
        }

        /**
         * 更新趋势图表
         */
        updateTrendChart(dailyStats) {
            const canvas = document.getElementById('trendChart');
            if (!canvas) {return;
            }

            if (!dailyStats || dailyStats.length === 0) {
                // 销毁现有图表
                if (this.trendChart) {
                    this.trendChart.destroy();
                    this.trendChart = null;
                }

                // 显示友好的空数据提示
                const container = canvas.parentElement;
                container.innerHTML = `
                    <div class="d-flex flex-column align-items-center justify-content-center h-100 text-muted">
                        <i class="bi bi-graph-up-arrow" style="font-size: 3rem; opacity: 0.5;"></i>
                        <p class="mt-3 mb-0">暂无近7日鸽切趋势数据</p>
                        <small class="mt-1">等待数据录入后显示</small>
                    </div>
                `;
                return;
            }

            // 恢复canvas元素（如果之前被替换了）
            const container = canvas.parentElement;
            if (!canvas.isConnected) {
                container.innerHTML = '<canvas id="trendChart"></canvas>';
                const newCanvas = document.getElementById('trendChart');
                if (!newCanvas) {return;
                }
            }

            if (typeof Chart === 'undefined') {return;
            }

            // 销毁旧图表
            if (this.trendChart) {
                this.trendChart.destroy();
            }

            const actualCanvas = document.getElementById('trendChart');
            const ctx = actualCanvas.getContext('2d');
            const sortedStats = [...dailyStats].sort((a, b) => new Date(a.date) - new Date(b.date));

            try {
                this.trendChart = new Chart(ctx, {
                    type: 'line',
                    data: {
                        labels: sortedStats.map(s => s.date),
                        datasets: [{
                            label: '鸽切次数',
                            data: sortedStats.map(s => s.count),
                            borderColor: '#3b82f6',
                            backgroundColor: 'rgba(59, 130, 246, 0.1)',
                            borderWidth: 2,
                            fill: true,
                            tension: 0.3
                        }]
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        plugins: { legend: { display: false } },
                        scales: {
                            y: { beginAtZero: true, grid: { color: '#f3f4f6' }, ticks: { stepSize: 1 } },
                            x: { grid: { color: '#f3f4f6' } }
                        }
                    }
                });
            } catch (error) {}
        }

        /**
         * 更新最活跃用户列表
         */
        updateTopUsers(users) {
            const container = document.getElementById('top-users');

            // history.html 页面没有 top-users 元素，静默返回
            if (!container) {
                return;
            }

            if (!users || users.length === 0) {
                container.innerHTML = `
                    <div class="d-flex flex-column align-items-center justify-content-center py-4 text-muted">
                        <i class="bi bi-trophy" style="font-size: 2.5rem; opacity: 0.4;"></i>
                        <p class="mt-3 mb-0 text-center">暂无活跃用户数据</p>
                        <small class="mt-1 text-center">等待数据录入后显示排行榜</small>
                    </div>
                `;
                return;
            }

            const top5 = users.slice(0, 5);

            container.innerHTML = top5.map((user, index) => {
                let rankStyle = '';
                if (index === 0) rankStyle = 'background: linear-gradient(135deg, #ffd700 0%, #ffed4e 100%); color: #5a3e36;';
                else if (index === 1) rankStyle = 'background: linear-gradient(135deg, #c0c0c0 0%, #e8e8e8 100%); color: #5a3e36;';
                else if (index === 2) rankStyle = 'background: linear-gradient(135deg, #cd7f32 0%, #e8a87c 100%); color: #fff;';
                else rankStyle = 'background: linear-gradient(135deg, #ff9a9e 0%, #fecfef 100%); color: #fff;';

                return `
                    <div class="d-flex align-items-center p-3 mb-2 rounded hover-effect" style="background: rgba(255, 255, 255, 0.9); border: 1px solid rgba(255, 255, 255, 0.6);">
                        <span class="badge me-3 d-flex align-items-center justify-content-center" style="width: 32px; height: 32px; ${rankStyle} font-size: 1rem; border-radius: 50%;">${index + 1}</span>
                        <div class="flex-grow-1">
                            <div style="font-weight: 500; color: #5a3e36;" class="text-truncate" title="${window.Core.escapeHtml(user.username)}">
                                ${window.Core.escapeHtml(user.username)}
                            </div>
                        </div>
                        <div style="font-weight: 600; color: #ff6b6b; font-size: 1.1rem;">
                            ${user.count}
                        </div>
                    </div>
                `;
            }).join('');
        }

        /**
         * 保存切片地址
         */
        async saveSliceUrl() {
            const bvCode = document.getElementById('sliceUrl').value.trim();

            // 验证BV号格式
            const validation = window.Core.validateBVCode(bvCode);
            if (!validation.valid) {
                window.Core.showNotification(validation.message, 'error');
                return;
            }

            // 构建 B站视频链接
            const sliceUrl = `https://www.bilibili.com/video/${bvCode}`;

            try {
                const response = await fetch('/api/record/update', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({
                        id: this.currentEditId,
                        slice_url: sliceUrl,
                        password: window.AuthManager.getSessionPassword()
                    })
                });

                const data = await response.json();

                if (data.success) {
                    // 关闭弹窗并传递 'save' 结果
                    window.ModalManager.close('sliceModal', 'save');

                    // 清空输入框
                    document.getElementById('sliceUrl').value = '';

                    // 刷新历史数据
                    this.loadHistoryData();

                    window.Core.showNotification('切片地址保存成功', 'success');
                } else {
                    window.Core.showNotification('保存失败: ' + data.error, 'error');
                }
            } catch (error) {
                window.Core.showNotification('操作失败: ' + error.message, 'error');
            }
        }

        /**
         * 保存编辑
         */
        async saveEdit() {const bvCode = document.getElementById('editSliceUrl').value.trim();
            const skipReason = document.getElementById('editSkipReason').value.trim();

            // 确定当前激活的标签
            const editModal = document.getElementById('editModal');
            const sliceTab = editModal ? editModal.querySelector('button[data-tab="slice"]') : null;
            const isSliceActive = sliceTab ? sliceTab.classList.contains('active') : true;

            // 如果当前是切片标签且输入了BV号，需要验证格式
            if (isSliceActive && bvCode) {
                const validation = window.Core.validateBVCode(bvCode);
                if (!validation.valid) {
                    window.Core.showNotification(validation.message, 'error');
                    return;
                }
            }

            // 构建 B站视频链接
            const sliceUrl = isSliceActive && bvCode ? `https://www.bilibili.com/video/${bvCode}` : '';try {
                const response = await fetch('/api/record/update', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({
                        id: this.currentEditId,
                        slice_url: sliceUrl,
                        skip_reason: !isSliceActive ? skipReason : '',
                        password: window.AuthManager.getSessionPassword()
                    })
                });

                const data = await response.json();

                if (data.success) {
                    // 关闭弹窗并传递 'save' 结果
                    window.ModalManager.close('editModal', 'save');

                    // 清空输入框
                    document.getElementById('editSliceUrl').value = '';
                    document.getElementById('editSkipReason').value = '';

                    // 刷新历史数据
                    this.loadHistoryData();

                    window.Core.showNotification('编辑保存成功', 'success');
                } else {
                    window.Core.showNotification('保存失败: ' + data.error, 'error');
                }
            } catch (error) {
                window.Core.showNotification('操作失败: ' + error.message, 'error');
            }
        }

        /**
         * 编辑标签切换函数
         */
        switchEditTab(tabType) {const editModal = document.getElementById('editModal');
            if (!editModal) {setTimeout(() => this.switchEditTab(tabType), 100);
                return;
            }

            // 查找按钮
            const sliceTab = editModal.querySelector('button[data-tab="slice"]');
            const skipTab = editModal.querySelector('button[data-tab="skip"]');
            const slicePanel = editModal.querySelector('#slice-panel');
            const skipPanel = editModal.querySelector('#skip-panel');

            if (!sliceTab || !skipTab || !slicePanel || !skipPanel) {setTimeout(() => this.switchEditTab(tabType), 100);
                return;
            }

            if (tabType === 'slice') {
                // 切换到切片标签页
                sliceTab.classList.add('active');
                sliceTab.classList.remove('btn-outline-primary');
                sliceTab.classList.add('btn-outline-primary');
                sliceTab.classList.remove('btn-outline-secondary');
                slicePanel.style.display = 'block';
                skipPanel.style.display = 'none';
            } else {
                // 切换到不切原因标签页
                skipTab.classList.add('active');
                skipTab.classList.remove('btn-outline-secondary');
                skipTab.classList.add('btn-outline-secondary');
                skipTab.classList.remove('btn-outline-primary');
                slicePanel.style.display = 'none';
                skipPanel.style.display = 'block';
            }
        }

        /**
         * 保存不切原因
         */
        async saveSkipReason() {
            const skipReason = document.getElementById('skipReason').value.trim();

            if (!skipReason) {
                window.Core.showNotification('请输入不切原因', 'warning');
                return;
            }

            try {
                const response = await fetch('/api/record/update', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({
                        id: this.currentEditId,
                        skip_reason: skipReason,
                        password: window.AuthManager.getSessionPassword()
                    })
                });

                const data = await response.json();

                if (data.success) {
                    // 关闭弹窗并传递 'save' 结果
                    window.ModalManager.close('skipModal', 'save');

                    // 清空输入框
                    document.getElementById('skipReason').value = '';

                    // 刷新历史数据
                    this.loadHistoryData();

                    window.Core.showNotification('不切原因保存成功', 'success');
                } else {
                    window.Core.showNotification('保存失败: ' + data.error, 'error');
                }
            } catch (error) {
                window.Core.showNotification('操作失败: ' + error.message, 'error');
            }
        }

        /**
         * 处理登录按钮点击事件（用于onclick事件处理）
         */
        async handleLoginClick(event) {
            event.preventDefault();
            event.stopPropagation();
            
            // 直接显示登录弹窗
            try {
                const result = await window.ModalManager.showTemplate('adminLogin');
                if (result === 'verify') {
                    // 授予管理员权限
                    window.Core.setGlobalState('isAdminLoggedIn', true);
                    
                    // 显示管理员徽章
                    const adminBadge = document.getElementById('admin-badge');
                    if (adminBadge) adminBadge.classList.remove('d-none');
                    
                    window.Core.showNotification('管理员权限已启用', 'success');
                    
                    // 刷新表格以显示管理按钮
                    this.refreshHistoryTable();
                }
            } catch (error) {}
        }

        /**
         * 设置管理员权限状态变化监听器
         */
        setupAuthChangeListener() {
            // 清除之前的监听器
            if (this.authChangeListener) {
                this.authChangeListener();
                this.authChangeListener = null;
            }
            
            // 监听管理员权限状态变化
            if (window.AuthManager && window.AuthManager.onAuthChange) {
                this.authChangeListener = window.AuthManager.onAuthChange(() => {this.refreshHistoryTable();
                });
            }
        }

        /**
         * 刷新历史数据表格（重新渲染权限相关按钮）
         */
        refreshHistoryTable() {// 检查是否有历史数据容器
            const container = document.getElementById('history-data-container');
            if (!container) {return;
            }// 如果容器隐藏，但有当前数据，则重新加载以更新权限按钮
            if (container.style.display === 'none') {
                const dateInput = document.getElementById('history-date');if (dateInput && dateInput.value && this.currentHistoryData.length > 0) {this.updateHistoryTable(this.currentHistoryData, dateInput.value);
                } else {}
                return;
            }

            // 检查是否有当前历史数据
            if (this.currentHistoryData.length === 0) {return;
            }

            // 检查是否有选中的日期
            const dateInput = document.getElementById('history-date');
            if (!dateInput || !dateInput.value) {return;
            }this.updateHistoryTable(this.currentHistoryData, dateInput.value);
        }

        /**
         * 销毁管理器
         */
        destroy() {// 销毁图表
            if (this.trendChart) {
                this.trendChart.destroy();
                this.trendChart = null;
            }

            // 清除弹窗关闭监听器
            if (this.modalCloseListener) {
                clearInterval(this.modalCloseListener);
                this.modalCloseListener = null;
            }

            // 清除权限状态变化监听器
            if (this.authChangeListener) {
                this.authChangeListener();
                this.authChangeListener = null;
            }
        }
    }

    // 创建全局实例
    window.HistoryDataManager = new HistoryDataManager();

    // 暴露全局保存函数供 ModalManager 调用
    window.historySaveSkipReason = function() {
        return window.HistoryDataManager.saveSkipReason();
    };

    window.historySaveSliceUrl = function() {
        return window.HistoryDataManager.saveSliceUrl();
    };

    window.historySaveEdit = function() {
        return window.HistoryDataManager.saveEdit();
    };

    // 暴露标签切换函数
    window.switchEditTab = function(tabType) {
        return window.HistoryDataManager.switchEditTab(tabType);
    };})();