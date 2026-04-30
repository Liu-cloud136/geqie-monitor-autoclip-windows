/**
 * 鸽切监控系统 - 数据表格模块
 * 负责数据表格的渲染、排序和交互
 * 使用IIFE封装，避免全局变量污染
 */

(function() {
    'use strict';

    // 私有变量
    const tableInstances = new Map();
    let sortOrder = {}; // 存储各列的排序状态

    /**
     * 渲染数据表格
     * @param {string} containerId - 容器元素ID
     * @param {Array} data - 数据数组
     * @param {Array} columns - 列配置
     * @param {Object} options - 选项配置
     */
    function renderTable(containerId, data, columns, options = {}) {
        const container = document.getElementById(containerId);
        if (!container) {return;
        }
        
        const {
            emptyMessage = '暂无数据',
            enableSort = true,
            rowHoverEffect = true,
            pagination = null
        } = options;
        
        // 保存表格配置
        tableInstances.set(containerId, {
            data: data,
            columns: columns,
            options: options
        });
        
        // 清空容器
        container.innerHTML = '';
        
        if (data.length === 0) {
            container.innerHTML = `
                <tr>
                    <td colspan="${columns.length}" class="text-center py-4">
                        <i class="bi bi-inbox" style="font-size: 2.5rem; color: var(--bilibili-text-light);"></i>
                        <p class="mt-2 text-muted">${emptyMessage}</p>
                    </td>
                </tr>
            `;
            return;
        }
        
        // 如果需要排序，先排序数据
        const sortedData = enableSort ? sortData(data, columns) : data;
        
        // 渲染表格行
        container.innerHTML = sortedData.map((item, index) => {
            return `
                <tr class="data-row" data-index="${index}">
                    ${columns.map(col => {
                        const value = col.render ? col.render(item, index) : escapeHtml(item[col.key]);
                        const classes = [];
                        if (col.class) classes.push(col.class);
                        if (col.align) classes.push(`text-${col.align}`);
                        
                        return `<td${classes.length ? ` class="${classes.join(' ')}"` : ''}>${value}</td>`;
                    }).join('')}
                </tr>
            `;
        }).join('');
        
        // 添加行悬停效果
        if (rowHoverEffect) {
            addRowHoverEffects(container);
        }
        
        // 添加行点击事件
        if (options.onRowClick) {
            addRowClickHandler(container, options.onRowClick);
        }

    }

    /**
     * 更新表格数据
     * @param {string} containerId - 容器ID
     * @param {Array} newData - 新数据
     */
    function updateTableData(containerId, newData) {
        const instance = tableInstances.get(containerId);
        if (instance) {
            instance.data = newData;
            renderTable(containerId, newData, instance.columns, instance.options);
        }
    }

    /**
     * 排序数据
     * @param {Array} data - 原始数据
     * @param {Array} columns - 列配置
     * @returns {Array} 排序后的数据
     */
    function sortData(data, columns) {
        // 检查是否有排序列
        const sortColumn = columns.find(col => col.sortable && sortOrder[col.key]);
        
        if (!sortColumn) return data;
        
        const order = sortOrder[sortColumn.key];
        const sortKey = sortColumn.key;
        
        return [...data].sort((a, b) => {
            let valueA = a[sortKey];
            let valueB = b[sortKey];
            
            // 特殊处理：时间列按照时间戳排序
            if (sortKey === 'time_display' && a.timestamp && b.timestamp) {
                valueA = a.timestamp;
                valueB = b.timestamp;
            }
            
            // 处理不同类型的排序
            if (typeof valueA === 'string') {
                valueA = valueA.toLowerCase();
                valueB = valueB.toLowerCase();
            }
            
            if (valueA < valueB) return order === 'asc' ? -1 : 1;
            if (valueA > valueB) return order === 'asc' ? 1 : -1;
            return 0;
        });
    }

    /**
     * 设置排序列
     * @param {string} columnKey - 列键名
     * @param {string} order - 排序方向 'asc' 或 'desc'
     */
    function setSortOrder(columnKey, order) {
        sortOrder = { [columnKey]: order };
        
        // 重新渲染所有表格
        tableInstances.forEach((instance, containerId) => {
            renderTable(containerId, instance.data, instance.columns, instance.options);
        });
    }

    /**
     * 添加行悬停效果（使用Core模块）
     * @param {HTMLElement} container - 表格容器
     */
    function addRowHoverEffects(container) {
        if (window.Core) {
            window.Core.addRowHoverEffects(container);
        }
    }

    /**
     * 添加行点击处理器
     * @param {HTMLElement} container - 表格容器
     * @param {Function} callback - 点击回调
     */
    function addRowClickHandler(container, callback) {
        const rows = container.querySelectorAll('.data-row');
        rows.forEach(row => {
            row.addEventListener('click', function() {
                const index = parseInt(this.getAttribute('data-index'));
                const instance = tableInstances.get(container.id);
                if (instance && instance.data[index]) {
                    callback(instance.data[index], index);
                }
            });
        });
    }

    /**
     * HTML转义（使用Core模块）
     * @param {string} text - 原始文本
     * @returns {string} 转义后的文本
     */
    function escapeHtml(text) {
        return window.Core ? window.Core.escapeHtml(text) : text;
    }

    /**
     * 创建表格列配置
     * @param {Object} config - 列配置
     * @returns {Object} 列对象
     */
    function createColumn(config) {
        return {
            key: config.key,
            title: config.title || config.key,
            class: config.class || '',
            align: config.align || 'left',
            sortable: config.sortable || false,
            render: config.render || null
        };
    }

    /**
     * 通用列定义
     */
    const columns = {
        user: createColumn({
            key: 'username',
            title: '用户',
            class: 'text-truncate',
            render: function(item) {
                return `<span class="badge user-badge">${escapeHtml(item.username)}</span>`;
            }
        }),
        
        content: createColumn({
            key: 'content',
            title: '内容',
            render: function(item) {
                return `
                    <div class="fw-medium">${escapeHtml(item.content)}</div>
                    <small class="text-muted">
                        <i class="bi bi-broadcast"></i> ${escapeHtml(item.room_title || '未知直播间')}
                    </small>
                `;
            }
        }),
        
        time: createColumn({
            key: 'time_display',
            title: '时间',
            align: 'center',
            sortable: true,
            render: function(item) {
                return `<small class="text-muted time-badge">${item.time_display}</small>`;
            }
        }),
        
        actions: createColumn({
            key: 'actions',
            title: '操作',
            align: 'center',
            render: function(item, index) {
                return `
                    <div class="btn-group btn-group-sm">
                        <button class="btn btn-outline-primary btn-sm" onclick="window.DataTableManager.handleEdit(${item.id || index})">
                            <i class="bi bi-pencil"></i>
                        </button>
                        <button class="btn btn-outline-danger btn-sm" onclick="window.DataTableManager.handleDelete(${item.id || index})">
                            <i class="bi bi-trash"></i>
                        </button>
                    </div>
                `;
            }
        })
    };

    /**
     * 处理编辑操作（需要管理员权限）
     * @param {number} recordId - 记录ID
     */
    function handleEdit(recordId) {
        if (window.AuthManager && window.AuthManager.checkAdminPermission()) {
            // 这里可以触发编辑模态框或进行其他操作
        } else {
            Utils.showAlert('需要管理员权限才能编辑记录', '权限不足');
        }
    }

    /**
     * 处理删除操作（需要管理员权限）
     * @param {number} recordId - 记录ID
     */
    async function handleDelete(recordId) {
        if (window.AuthManager && window.AuthManager.checkAdminPermission()) {
            const result = await Utils.showConfirm('确定要删除这条记录吗？', '确认删除');
            if (result) {
            // 这里可以调用删除API
            }
        } else {
            Utils.showAlert('需要管理员权限才能删除记录', '权限不足');
        }
    }

    /**
     * 过滤掉未来日期的数据（使用Core模块）
     * @param {Array} data - 原始数据
     * @returns {Array} 过滤后的数据
     */
    function filterFutureDates(data) {
        return window.Core ? window.Core.filterFutureDates(data) : data;
    }

    /**
     * 刷新数据表格
     * 重新获取数据并更新表格显示
     */
    function refresh() {// 从服务器获取最新数据并重新渲染所有表格实例
        tableInstances.forEach(async (instance, containerId) => {
            try {
                // 从服务器重新获取数据
                const response = await fetch('/api/today');
                if (!response.ok) {
                    throw new Error(`获取数据失败: ${response.status}`);
                }
                
                const result = await response.json();
                if (result.success) {
                    // 直接使用后端返回的数据，不再进行前端过滤
                    instance.data = result.data || [];
                    renderTable(containerId, instance.data, instance.columns, instance.options);} else {}
            } catch (error) {// 降级处理：重新渲染现有数据
                renderTable(containerId, instance.data, instance.columns, instance.options);
            }
        });}

    // 暴露公共API
    window.DataTableManager = {
        renderTable: renderTable,
        updateTableData: updateTableData,
        setSortOrder: setSortOrder,
        createColumn: createColumn,
        columns: columns,
        handleEdit: handleEdit,
        handleDelete: handleDelete,
        refresh: refresh
    };

})();