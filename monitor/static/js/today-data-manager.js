/**
 * 鸽切监控系统 - 今日数据管理模块
 * 负责今日数据页面相关功能
 */

(function() {
    'use strict';

    class TodayDataManager extends BaseDataManager {
        constructor() {
            super(); // 调用父类构造函数
            this.trendChart = null;
            this.countdownInterval = null;
            this.refreshInterval = null;
            this.nextUpdateTime = null;}

        /**
         * 初始化今日数据页面
         */
        init() {try {
                // 设置导航栏激活状态
                this.setNavActive();

                // 设置今天日期
                this.setTodayDate();

                // 强制初始化日期选择器
                this.setupHistoryDate();

                // 加载主播信息和数据
                this.loadRoomInfo();
                this.loadDateData();

                // 启动自动刷新
                this.startAutoRefresh();

                // 监听管理员权限状态变化
                this.setupAuthChangeListener();} catch (error) {
                console.error('加载房间信息失败:', error);
            }
        }

        /**
         * 设置导航栏激活状态
         */
        setNavActive() {
            const navLinks = document.querySelectorAll('.nav-link[data-page]');
            navLinks.forEach(l => l.classList.remove('active'));
            const todayLink = document.querySelector('.nav-link[data-page="today"]');
            if (todayLink) {
                todayLink.classList.add('active');
            }
        }

        /**
         * 设置今天日期
         */
        setTodayDate() {
            if (window.Core && window.Core.getTodayDateString) {
                const todayElement = document.getElementById('today-date');
                if (todayElement) {
                    todayElement.textContent = window.Core.getTodayDateString();
                }
            }
        }

        /**
         * 加载指定日期的数据
         */
        async loadDateData() {
            const container = document.getElementById('data-list');

            try {
                // 显示加载状态
                this.showLoading('data-list', '正在加载今日数据...');

                // 使用统一的API请求方法
                const data = await this.safeApiRequest('/api/today');

                if (data.success) {
                    this.updateDataList(data.data);
                    this.updateStats(data.data.length);
                } else {
                    throw new Error(data.error || '服务器返回错误');
                }

                // 加载统计数据
                await this.loadStats();
                
            } catch (error) {
                this.handleError(error, '加载今日数据', () => {
                    // 降级处理：显示错误状态并提供重试按钮
                    container.innerHTML = `
                        <tr>
                            <td colspan="2" class="text-center py-4 text-danger">
                                <i class="bi bi-exclamation-triangle text-3xl"></i>
                                <p class="mt-2 mb-0">加载失败，请重试</p>
                                <button class="btn btn-sm btn-outline-primary mt-2" onclick="window.TodayDataManager.loadDateData()">重试</button>
                            </td>
                        </tr>
                    `;
                });
            }
        }

        /**
         * 加载今日数据（包含主播信息）
         */
        async loadTodayData() {
            try {
                // 加载直播间信息
                await this.loadRoomInfo();
                
                // 加载今日数据
                this.loadDateData();
                
            } catch (error) {
                console.error('加载房间信息失败:', error);
            }
        }

        /**
         * 只加载今日数据，不更新趋势图表（用于10秒定时刷新）
         */
        async loadTodayDataWithoutStats() {
            try {
                const response = await fetch('/api/today');
                const data = await response.json();

                if (data.success) {
                    this.updateDataList(data.data);
                    this.updateStats(data.data.length);
                }
            } catch (error) {
                // 出错时不显示错误信息，保持原有数据
            }
        }

        /**
         * 加载直播间信息
         */
        async loadRoomInfo() {
            try {
                console.log('开始加载房间信息...');
                // 强制刷新参数，避免缓存问题
                const forceRefresh = new URLSearchParams(window.location.search).get('force_refresh') === 'true' || 
                                   localStorage.getItem('force_refresh_room_info') === 'true';
                
                const url = forceRefresh ? '/api/room_info?force_refresh=true' : '/api/room_info';
                console.log('使用URL:', url);
                const response = await fetch(url);
                console.log('API响应状态:', response.status);
                const data = await response.json();
                console.log('API响应数据:', data);

                if (data.success) {
                    console.log('房间信息获取成功:', data.room_info);
                    console.log('房间标题字段检查:', 'room_title' in data.room_info ? '存在' : '不存在');
                    console.log('room_title值:', data.room_info.room_title);
                    console.log('room_id值:', data.room_info.room_id);
                    // 更新房间信息显示
                    this.updateRoomInfo(data.room_info);
                } else {
                    console.error('API返回失败:', data.error);
                }
            } catch (error) {
                console.error('加载房间信息失败:', error);
                // 显示错误信息
                const roomTitleElement = document.getElementById('room-title');
                if (roomTitleElement) {
                    roomTitleElement.textContent = '加载失败';
                    roomTitleElement.style.color = 'red';
                }
            }
        }

        /**
         * 更新房间信息显示
         */
        updateRoomInfo(roomInfo) {
            console.log('updateRoomInfo被调用，参数:', roomInfo);
            console.log('room_title值:', roomInfo.room_title);
            
            const roomTitleElement = document.getElementById('room-title');
            const roomIdElement = document.getElementById('room-id');
            
            console.log('找到room-title元素:', roomTitleElement ? '是' : '否');
            console.log('找到room-id元素:', roomIdElement ? '是' : '否');
            
            if (roomTitleElement) {
                console.log('设置room-title文本:', roomInfo.room_title || '未知直播间');
                roomTitleElement.textContent = roomInfo.room_title || '未知直播间';
            } else {
                console.error('错误: 找不到#room-title元素！');
            }
            
            if (roomIdElement) {
                roomIdElement.textContent = roomInfo.room_id || '未知';
            }
        }

        /**
         * 更新数据列表
         */
        updateDataList(data) {
            // 保存当前数据，供编辑功能使用
            this.currentData = data;

            const container = document.getElementById('data-list');
            if (!container) {return;
            }

            if (data.length === 0) {
                container.innerHTML = `
                    <tr>
                        <td colspan="3" class="text-center py-4 empty-data-cell">
                            <div class="d-flex flex-column align-items-center justify-content-center">
                                <i class="bi bi-inbox text-3xl text-bilibili-light mb-2"></i>
                                <p class="mb-0 text-muted">今日暂无鸽切数据</p>
                            </div>
                        </td>
                    </tr>
                `;
                return;
            }

            // 确保数据按时间戳倒序排列（最新的在前）
            const sortedData = [...data].sort((a, b) => b.timestamp - a.timestamp);

            const isAdmin = window.Core ? window.Core.getGlobalState('isAdminLoggedIn') : false;

            container.innerHTML = sortedData.map(item => {
                const hasSlice = item.slice_url && item.slice_url.trim();
                const hasReason = item.skip_reason && item.skip_reason.trim();
                const emailStatus = item.email_status || 'none';

                // 根据邮件状态设置行样式
                let rowStyle = '';
                if (emailStatus === 'success') {
                    rowStyle = 'style="border-left: 4px solid #28a745; background-color: rgba(40, 167, 69, 0.05);"';
                } else if (emailStatus === 'failed') {
                    rowStyle = 'style="border-left: 4px solid #dc3545; background-color: rgba(220, 53, 69, 0.05);"';
                }

                let manageContent = '';

                if (hasSlice) {
                    manageContent = `
                        <div class="d-flex justify-content-center gap-2">
                            <a href="${window.Core.escapeHtml(item.slice_url)}" target="_blank" class="btn btn-sm btn-success btn-sm-compact">
                                <i class="bi bi-play-circle"></i> 已切片
                            </a>
                            <button class="btn btn-sm btn-outline-primary btn-sm-compact" onclick="TodayDataManager.openEditModal(${item.id})">
                                <i class="bi bi-pencil"></i> 修改
                            </button>
                            <button class="btn btn-sm btn-outline-danger btn-sm-compact" onclick="TodayDataManager.openDeleteModal(${item.id})">
                                <i class="bi bi-trash"></i> 删除
                            </button>
                        </div>
                    `;
                } else if (hasReason) {
                    manageContent = `
                        <div class="d-flex flex-column align-items-center gap-1">
                            <div class="d-flex justify-content-center gap-2">
                                <button class="btn btn-sm btn-sm-compact gradient-skip-reason">
                                    <i class="bi bi-x-circle"></i> 已处理
                                </button>
                                <button class="btn btn-sm btn-outline-primary btn-sm-compact" onclick="TodayDataManager.openEditModal(${item.id})">
                                    <i class="bi bi-pencil"></i> 修改
                                </button>
                                <button class="btn btn-sm btn-outline-danger btn-sm-compact" onclick="TodayDataManager.openDeleteModal(${item.id})">
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
                    if (isAdmin) {
                        manageContent = `
                            <div class="d-flex justify-content-center gap-2">
                                <button class="btn btn-sm btn-outline-primary btn-sm-compact" onclick="TodayDataManager.openSliceModal(${item.id})">
                                    <i class="bi bi-link-45deg"></i> 切片
                                </button>
                                <button class="btn btn-sm btn-outline-secondary btn-sm-compact" onclick="TodayDataManager.openSkipModal(${item.id})">
                                    <i class="bi bi-x-circle"></i> 不切
                                </button>
                                <button class="btn btn-sm btn-outline-danger btn-sm-compact" onclick="TodayDataManager.openDeleteModal(${item.id})">
                                    <i class="bi bi-trash"></i> 删除
                                </button>
                            </div>
                        `;
                    } else {
                        manageContent = `
                            <div class="d-flex justify-content-center gap-2">
                                <button class="btn btn-sm btn-outline-primary btn-sm-compact" onclick="TodayDataManager.checkAdminPermission(event)">
                                    <i class="bi bi-shield-lock"></i> 需要登录
                                </button>
                            </div>
                        `;
                    }
                }
                
                const currentRating = item.rating || 0;
                const isRated = currentRating > 0;
                
                let starsHtml = '';
                if (isRated) {
                    const filledStars = '★'.repeat(currentRating);
                    const emptyStars = '☆'.repeat(5 - currentRating);
                    starsHtml = `<span class="rated-stars" title="已评分: ${currentRating}星">${filledStars}${emptyStars}</span>`;
                } else {
                    starsHtml = `
                        <div class="rating-stars" data-record-id="${item.id}">
                            <span class="star" data-value="1">☆</span>
                            <span class="star" data-value="2">☆</span>
                            <span class="star" data-value="3">☆</span>
                            <span class="star" data-value="4">☆</span>
                            <span class="star" data-value="5">☆</span>
                        </div>
                    `;
                }
                
                return `
                    <tr class="data-row" ${rowStyle}>
                        <td class="table-cell-center rating-cell">
                            ${starsHtml}
                        </td>
                        <td class="table-cell-center">
                            <div class="d-flex flex-column align-items-center">
                                <span class="badge user-badge">${window.Core.escapeHtml(item.username)}</span>
                                <small class="time-badge mt-1">${item.time_display}</small>
                            </div>
                        </td>
                        <td class="table-cell-center">
                            ${manageContent}
                        </td>
                    </tr>
                `;
            }).join('');

            // 添加行悬停效果
            if (window.Core && window.Core.addRowHoverEffects) {
                window.Core.addRowHoverEffects(container);
            }
            
            // 初始化评分组件事件
            this.initRatingEvents();
        }

        /**
         * 初始化评分组件事件
         */
        initRatingEvents() {
            const ratingContainers = document.querySelectorAll('.rating-stars');
            ratingContainers.forEach(container => {
                const stars = container.querySelectorAll('.star');
                const recordId = container.dataset.recordId;
                
                stars.forEach((star, index) => {
                    // 悬停效果
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
                    
                    // 离开恢复
                    star.addEventListener('mouseleave', () => {
                        stars.forEach(s => {
                            s.textContent = '☆';
                            s.classList.remove('hovered');
                        });
                    });
                    
                    // 点击评分
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
                    // 替换为已评分显示
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
         * 更新统计信息
         */
        updateStats(count) {
            const el = document.getElementById('today-count');
            if (el) el.textContent = count;
        }

        /**
         * 加载统计数据
         */
        async loadStats() {try {
                const response = await fetch('/api/stats?days=7');
                const data = await response.json();if (data.success) {
                    const stats = data.total_stats;document.getElementById('total-count').textContent = stats.total_count.toLocaleString();
                    document.getElementById('week-count').textContent = stats.week_count.toLocaleString();

                    // 无论是否有数据，都调用 updateTopUsers 来更新显示状态
                    if (stats.top_users && stats.top_users.length > 0) {
                        const topUserCountElement = document.getElementById('top-user-count');
                        if (topUserCountElement) {
                            topUserCountElement.textContent = stats.top_users[0].count.toLocaleString();
                        }
                    }this.updateTopUsers(stats.top_users || []);

                    this.calculateRealTimeStats(data.recent_data);
                    this.updateTrendChart(data.daily_stats || []);
                } else {}
            } catch (error) {
                console.error('加载房间信息失败:', error);
            }
        }

        /**
         * 更新趋势图表
         */
        updateTrendChart(dailyStats) {
            const canvas = document.getElementById('trendChart');
            if (!canvas) {// 延迟 500ms 重试一次（可能是 DOM 还没加载完成）
                setTimeout(() => {
                    const retryCanvas = document.getElementById('trendChart');
                    if (retryCanvas) {this.updateTrendChart(dailyStats);
                    } else {}
                }, 500);
                return;
            }if (!dailyStats || dailyStats.length === 0) {// 销毁现有图表
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
            if (!canvas.isConnected) {container.innerHTML = '<canvas id="trendChart"></canvas>';
                const newCanvas = document.getElementById('trendChart');
                if (!newCanvas) {return;
                }
            }

            if (typeof Chart === 'undefined') {return;
            }

            // 销毁旧图表
            if (this.trendChart) {
                this.trendChart.destroy();
            }const actualCanvas = document.getElementById('trendChart');
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
            } catch (error) {
                console.error('加载房间信息失败:', error);
            }
        }

        /**
         * 计算实时统计
         */
        calculateRealTimeStats(recentData) {
            let allData = [];
            for (const date in recentData) {
                if (Array.isArray(recentData[date])) {
                    allData = allData.concat(recentData[date]);
                }
            }

            const todayData = allData.filter(item => {
                const itemDate = new Date(item.timestamp * 1000);
                const today = new Date();
                return itemDate.toDateString() === today.toDateString();
            });

            if (todayData.length > 0) {
                const now = new Date();
                const startOfDay = new Date(now.getFullYear(), now.getMonth(), now.getDate());
                const hoursPassed = (now - startOfDay) / (1000 * 60 * 60);
                const avgPerHour = todayData.length / Math.max(hoursPassed, 1);
                document.getElementById('today-avg').textContent = avgPerHour.toFixed(1) + '/小时';
            }
        }

        /**
         * 更新最活跃用户列表
         */
        updateTopUsers(users) {
            const container = document.getElementById('top-users');

            if (!container) {return;
            }if (!users || users.length === 0) {container.innerHTML = `
                    <div class="d-flex flex-column align-items-center justify-content-center py-4 text-muted">
                        <i class="bi bi-trophy" style="font-size: 2.5rem; opacity: 0.4;"></i>
                        <p class="mt-3 mb-0 text-center">暂无活跃用户数据</p>
                        <small class="mt-1 text-center">等待数据录入后显示排行榜</small>
                    </div>
                `;
                return;
            }const top5 = users.slice(0, 5);

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
         * 检查管理员权限
         */
        async checkAdminPermission(event, actionCallback = null) {if (!window.Core || !window.Core.getGlobalState('isAdminLoggedIn')) {// 阻止默认行为（如按钮点击）
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

                        // 刷新数据await this.loadTodayData();window.Core.showNotification('管理员权限已启用', 'success');
                        return true;
                    }
                } catch (error) {
                console.error('加载房间信息失败:', error);
            }
                return false;
            }
            return true;
        }

        /**
         * 打开切片地址弹窗
         */
        async openSliceModal(recordId, existingSliceUrl = '', event = null) {// 先保存 recordId，避免在登录流程中丢失
            this.currentEditId = recordId;

            // 检查管理员权限
            const hasPermission = await this.checkAdminPermission(event);
            if (!hasPermission) return;

            // 使用统一弹窗管理器打开弹窗
            // 注意：不再使用 Promise 回调，因为 handleSaveAction 已经处理了保存逻辑
            window.ModalManager.showTemplate('slice');

            // 延迟预填充数据，确保弹窗已加载
            setTimeout(() => {
                const sliceUrlInput = document.getElementById('sliceUrl');
                if (sliceUrlInput) {
                    if (existingSliceUrl && typeof existingSliceUrl === 'string') {
                        // 从完整URL中提取BV号
                        const bvMatch = existingSliceUrl.match(/(BV[a-zA-Z0-9]+)/);
                        sliceUrlInput.value = bvMatch ? bvMatch[1] : existingSliceUrl;
                    } else {
                        sliceUrlInput.value = '';
                    }
                } else {window.Core.showNotification('系统错误：切片弹窗未正确加载', 'error');
                }
            }, 200);
        }

        /**
         * 打开不切原因弹窗
         */
        async openSkipModal(recordId, existingReason = '', event = null) {// 先保存 recordId，避免在登录流程中丢失
            this.currentEditId = recordId;// 检查管理员权限
            const hasPermission = await this.checkAdminPermission(event);if (!hasPermission) return;// 使用统一弹窗管理器打开弹窗
            // 注意：不再使用 Promise 回调，因为 handleSaveAction 已经处理了保存逻辑
            window.ModalManager.showTemplate('skip');

            // 延迟预填充数据，确保弹窗已加载
            setTimeout(() => {
                const skipReasonInput = document.getElementById('skipReason');
                if (skipReasonInput) {
                    if (existingReason && typeof existingReason === 'string') {
                        skipReasonInput.value = existingReason;
                    } else {
                        skipReasonInput.value = '';
                    }
                } else {window.Core.showNotification('系统错误：不切弹窗未正确加载', 'error');
                }
            }, 200);
        }

        /**
         * 打开编辑弹窗
         */
        async openEditModal(recordId, event = null) {// 先保存 recordId，避免在登录流程中丢失
            this.currentEditId = recordId;

            // 检查管理员权限
            const hasPermission = await this.checkAdminPermission(event);
            if (!hasPermission) return;

            // 获取记录数据以预填充
            let existingSliceUrl = '';
            let existingSkipReason = '';
            let isSliceActive = true;  // 默认显示切片标签页

            // 从当前数据中查找记录
            const record = this.currentData?.find(r => r.id === recordId);
            if (record) {
                existingSliceUrl = record.slice_url || '';
                existingSkipReason = record.skip_reason || '';
                // 如果有切片地址，默认显示切片标签页，否则显示不切原因标签页
                isSliceActive = !!record.slice_url;
            }

            // 使用统一弹窗管理器打开弹窗
            // 注意：不再使用 Promise 回调，因为 handleSaveAction 已经处理了保存逻辑
            window.ModalManager.showTemplate('edit');

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
                        this.switchEditTab('slice');
                    } else {
                        this.switchEditTab('skip');
                    }
                }, 100);
            }, 200);
        }

        /**
         * 打开删除确认弹窗
         */
        async openDeleteModal(recordId, event = null) {
            // 先保存 recordId，避免在登录流程中丢失
            this.currentEditId = recordId;

            const hasPermission = await this.checkAdminPermission(event);
            if (!hasPermission) return;

            window.ModalManager.showTemplate('delete').then(async result => {
                if (result === 'confirm') {
                    const password = document.getElementById('deletePassword').value.trim();
                    
                    if (!password) {
                        window.Core.showNotification('请输入管理员密码', 'warning');
                        return;
                    }

                    try {
                        const response = await fetch('/api/record/delete', {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({ id: recordId, password })
                        });

                        const data = await response.json();

                        if (data.success) {
                            window.Core.showNotification('删除成功', 'success');
                            this.loadDateData();
                            const selectedDate = document.getElementById('history-date').value;
                            if (selectedDate) this.loadHistoryData();
                        } else {
                            window.Core.showNotification(data.error || '删除失败', 'error');
                        }
                    } catch (error) {
                        window.Core.showNotification('删除失败: ' + error.message, 'error');
                    }
                }
            });
        }

        /**
         * 保存切片地址
         */
        async saveSliceUrl() {const bvCode = document.getElementById('sliceUrl').value.trim();

            // 验证BV号格式
            const validation = window.Core.validateBVCode(bvCode);
            if (!validation.valid) {
                window.Core.showNotification(validation.message, 'error');
                return;
            }

            // 构建 B站视频链接
            const sliceUrl = bvCode ? `https://www.bilibili.com/video/${bvCode}` : '';try {
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

                const data = await response.json();if (data.success) {
                    // 关闭弹窗并传递 'save' 结果
                    window.ModalManager.close('sliceModal', 'save');

                    // 清空输入框
                    document.getElementById('sliceUrl').value = '';

                    // 刷新今日数据
                    this.loadDateData();

                    // 刷新历史数据表格（如果有显示）
                    this.refreshHistoryTable();

                    window.Core.showNotification('切片地址保存成功', 'success');
                } else {
                    window.Core.showNotification('保存失败: ' + data.error, 'error');
                }
            } catch (error) {
                window.Core.showNotification('操作失败: ' + error.message, 'error');
            }
        }

        /**
         * 保存不切原因
         */
        async saveSkipReason() {const skipReasonInput = document.getElementById('skipReason');
            if (!skipReasonInput) {window.Core.showNotification('系统错误：输入框未找到', 'error');
                return;
            }

            const skipReason = skipReasonInput.value.trim();if (!skipReason) {
                window.Core.showNotification('请输入不切原因', 'warning');
                return;
            }try {
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

                const data = await response.json();if (data.success) {
                    // 关闭弹窗并传递 'save' 结果
                    window.ModalManager.close('skipModal', 'save');

                    // 清空输入框
                    document.getElementById('skipReason').value = '';

                    // 刷新今日数据
                    this.loadDateData();

                    // 刷新历史数据表格（如果有显示）
                    this.refreshHistoryTable();

                    window.Core.showNotification('不切原因保存成功', 'success');
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

                    // 刷新今日数据
                    this.loadDateData();

                    // 刷新历史数据表格（如果有显示）
                    this.refreshHistoryTable();

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
            }if (tabType === 'slice') {
                sliceTab.classList.add('active', 'btn-primary');
                sliceTab.classList.remove('btn-outline-primary');
                skipTab.classList.remove('active', 'btn-secondary');
                skipTab.classList.add('btn-outline-secondary');
                slicePanel.style.display = 'block';
                skipPanel.style.display = 'none';} else {
                sliceTab.classList.remove('active', 'btn-primary');
                sliceTab.classList.add('btn-outline-primary');
                skipTab.classList.add('active', 'btn-secondary');
                skipTab.classList.remove('btn-outline-secondary');
                slicePanel.style.display = 'none';
                skipPanel.style.display = 'block';}
        }

    /**
     * 启动自动刷新
     */
    startAutoRefresh() {
        // 每10秒自动刷新今日鸽切记录数据
        const REFRESH_INTERVAL = 10000;

        // 清除旧的刷新定时器（如果存在）
        if (this.refreshInterval) {
            clearInterval(this.refreshInterval);
        }
        this.refreshInterval = setInterval(() => {
            this.loadTodayDataWithoutStats();
            // 更新下次更新时间
            this.nextUpdateTime = Date.now() + REFRESH_INTERVAL;
        }, REFRESH_INTERVAL);

        // 初始化下次更新时间为10秒
        this.nextUpdateTime = Date.now() + REFRESH_INTERVAL;

        // 每秒更新倒计时显示
        if (this.countdownInterval) {
            clearInterval(this.countdownInterval);
        }
        this.countdownInterval = setInterval(() => this.updateCountdown(), 1000);

        // 初始更新倒计时
        this.updateCountdown();
    }

        /**
         * 停止自动刷新
         */
        stopAutoRefresh() {
            if (this.refreshInterval) {
                clearInterval(this.refreshInterval);
                this.refreshInterval = null;
            }
            if (this.countdownInterval) {
                clearInterval(this.countdownInterval);
                this.countdownInterval = null;
            }
        }

        /**
         * 更新倒计时显示
         */
        updateCountdown() {
            const countdownElement = document.getElementById('countdown');

            if (this.nextUpdateTime) {
                const now = Date.now();
                const timeLeft = Math.max(0, this.nextUpdateTime - now);
                const secondsLeft = Math.ceil(timeLeft / 1000);

                if (countdownElement) {
                    countdownElement.textContent = secondsLeft;
                }
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
                dateInput.max = localDateString;// 自动加载今天的数据
                this.loadHistoryData();}, 500);
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
                // 直接调用日期数据API
                const response = await fetch(`/api/date/${selectedDate}`);
                const data = await response.json();
                
                if (data.success) {
                    this.updateHistoryTable(data.data, selectedDate);
                } else {
                    window.Core.showNotification('查询失败: ' + data.error, 'error');
                }
            } catch (error) {window.Core.showNotification('查询失败: ' + error.message, 'error');
            }
        }

        /**
         * 更新历史数据表格
         */
        updateHistoryTable(data, selectedDate) {
            const container = document.getElementById('history-data-container');
            const tbody = document.getElementById('history-data-body');
            const totalCount = document.getElementById('history-total-count');

            // 显示容器
            if (container) {
                container.style.display = 'block';
            }

            if (data.length === 0) {
                tbody.innerHTML = `
                    <tr>
                        <td colspan="2" class="text-center py-4 empty-data-cell">
                            <div class="d-flex flex-column align-items-center justify-content-center">
                                <i class="bi bi-inbox text-3xl text-bilibili-light mb-2"></i>
                                <p class="mb-0 text-muted">${window.Core.escapeHtml(selectedDate)} 暂无数据</p>
                            </div>
                        </td>
                    </tr>
                `;
                totalCount.textContent = '共0条记录';
            } else {
                tbody.innerHTML = data.map(item => {
                    const hasSlice = item.slice_url && item.slice_url.trim();
                    const hasReason = item.skip_reason && item.skip_reason.trim();
                    
                    let actionButtons = '';
                    
                    if (hasSlice) {
                        if (window.Core.getGlobalState('isAdminLoggedIn')) {
                            actionButtons = `
                                <div class="d-flex justify-content-center gap-2">
                                    <a href="${window.Core.escapeHtml(item.slice_url)}" target="_blank" class="btn btn-sm btn-success btn-sm-compact">
                                        <i class="bi bi-play-circle"></i> 已切片
                                    </a>
                                    <button class="btn btn-sm btn-outline-primary btn-sm-compact" onclick="TodayDataManager.openEditModal(${item.id})">
                                        <i class="bi bi-pencil"></i> 修改
                                    </button>
                                    <button class="btn btn-sm btn-outline-danger btn-sm-compact" onclick="TodayDataManager.openDeleteModal(${item.id})">
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
                                    <button class="btn btn-sm btn-outline-primary btn-sm-compact" onclick="TodayDataManager.checkAdminPermission(event)">
                                        <i class="bi bi-shield-lock"></i> 需要登录
                                    </button>
                                </div>
                            `;
                        }
                    } else if (hasReason) {
                        if (window.Core.getGlobalState('isAdminLoggedIn')) {
                            actionButtons = `
                                <div class="d-flex flex-column align-items-center gap-1">
                                    <div class="d-flex justify-content-center gap-2">
                                        <button class="btn btn-sm btn-sm-compact gradient-skip-reason">
                                            <i class="bi bi-x-circle"></i> 已处理
                                        </button>
                                        <button class="btn btn-sm btn-outline-primary btn-sm-compact" onclick="TodayDataManager.openEditModal(${item.id})">
                                            <i class="bi bi-pencil"></i> 修改
                                        </button>
                                        <button class="btn btn-sm btn-outline-danger btn-sm-compact" onclick="TodayDataManager.openDeleteModal(${item.id})">
                                            <i class="bi bi-trash"></i> 删除
                                        </button>
                                    </div>
                                    <div class="d-flex justify-content-center">
                                        <small class="text-muted text-2xs max-w-180 text-truncate-single" title="${window.Core.escapeHtml(item.skip_reason)}">
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
                                        <button class="btn btn-sm btn-outline-primary btn-sm-compact" onclick="TodayDataManager.checkAdminPermission(event)">
                                            <i class="bi bi-shield-lock"></i> 需要登录
                                        </button>
                                    </div>
                                    <div class="d-flex justify-content-center">
                                        <small class="text-muted text-2xs max-w-180 text-truncate-single" title="${window.Core.escapeHtml(item.skip_reason)}">
                                            <i class="bi bi-chat-quote me-1"></i>${window.Core.escapeHtml(item.skip_reason)}
                                        </small>
                                    </div>
                                </div>
                            `;
                        }
                    } else {
                        if (window.Core.getGlobalState('isAdminLoggedIn')) {
                            actionButtons = `
                                <div class="d-flex justify-content-center gap-2">
                                    <button class="btn btn-sm btn-outline-primary btn-sm-compact" onclick="TodayDataManager.openSliceModal(${item.id})">
                                        <i class="bi bi-link-45deg"></i> 切片
                                    </button>
                                    <button class="btn btn-sm btn-outline-secondary btn-sm-compact" onclick="TodayDataManager.openSkipModal(${item.id})">
                                        <i class="bi bi-x-circle"></i> 不切
                                    </button>
                                    <button class="btn btn-sm btn-outline-danger btn-sm-compact" onclick="TodayDataManager.openDeleteModal(${item.id})">
                                        <i class="bi bi-trash"></i> 删除
                                    </button>
                                </div>
                            `;
                        } else {
                            actionButtons = `
                                <div class="d-flex justify-content-center gap-2">
                                    <button class="btn btn-sm btn-outline-primary btn-sm-compact" onclick="TodayDataManager.checkAdminPermission(event)">
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
                    
                    return `
                        <tr class="data-row" ${rowStyle}>
                            <td class="table-cell-center">
                                <div class="d-flex flex-column align-items-center">
                                    <span class="badge user-badge">${window.Core.escapeHtml(item.username)}</span>
                                    <small class="time-badge mt-1">${item.time_display}</small>
                                </div>
                            </td>
                            <td class="table-cell-center">${actionButtons}</td>
                        </tr>
                    `;
                }).join('');
                
                totalCount.textContent = `共${data.length}条记录`;
            }
            
            // 显示表格容器
            container.style.display = 'block';
        }

        /**
         * 设置管理员权限状态变化监听器
         */
        setupAuthChangeListener() {
            // 监听管理员权限状态变化
            if (window.AuthManager && window.AuthManager.onAuthChange) {
                window.AuthManager.onAuthChange(() => {this.refreshTodayTable();
                });
            }
        }

        /**
         * 刷新今日数据表格（重新渲染权限相关按钮）
         */
        refreshTodayTable() {// 不检查页面类型，直接刷新（因为历史数据组件也在今日页面）this.loadTodayDataWithoutStats();

            // 同时刷新历史数据表格（如果有显示的话）
            this.refreshHistoryTable();
        }

        /**
         * 刷新历史数据表格
         */
        refreshHistoryTable() {
            const container = document.getElementById('history-data-container');
            const dateInput = document.getElementById('history-date');

            // 如果历史数据容器可见且有选中的日期，则刷新历史数据
            if (container && container.style.display !== 'none' && dateInput && dateInput.value) {this.loadHistoryData();
            }
        }

        /**
         * 销毁管理器
         */
        destroy() {
            if (this.trendChart) {
                this.trendChart.destroy();
            }
            
            if (this.countdownInterval) {
                clearInterval(this.countdownInterval);
            }}
    }

    // 创建全局实例
    window.TodayDataManager = new TodayDataManager();

    // 暴露全局保存函数供 ModalManager 调用
    window.saveSliceUrl = function() {
        return window.TodayDataManager.saveSliceUrl.call(window.TodayDataManager);
    };

    window.saveSkipReason = function() {try {
            return window.TodayDataManager.saveSkipReason.call(window.TodayDataManager);
        } catch (error) {window.Core?.showNotification('保存失败: ' + error.message, 'error');
        }
    };

    window.saveEdit = function() {
        return window.TodayDataManager.saveEdit.call(window.TodayDataManager);
    };

    // 暴露标签切换函数供编辑弹窗使用
    window.switchEditTab = function(tabType) {
        if (window.TodayDataManager) {
            return window.TodayDataManager.switchEditTab(tabType);
        } else if (window.HistoryDataManager) {
            return window.HistoryDataManager.switchEditTab(tabType);
        }
    };})();