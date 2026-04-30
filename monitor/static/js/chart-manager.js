/**
 * 鸽切监控系统 - 图表管理模块
 * 负责图表组件的创建、更新和销毁
 * 使用IIFE封装，避免全局变量污染
 */

(function() {
    'use strict';

    // 私有变量 - 存储图表实例
    const chartInstances = new Map();

    /**
     * 创建趋势图
     * @param {string} canvasId - 画布元素ID
     * @param {Array} dailyStats - 每日统计数据
     * @returns {Object|null} Chart.js实例
     */
    function createTrendChart(canvasId, dailyStats) {// 检查Chart.js库是否已加载
        if (typeof Chart === 'undefined') {return null;
        }
        
        const canvas = document.getElementById(canvasId);
        if (!canvas) {return null;
        }
        
        const ctx = canvas.getContext('2d');
        
        // 按日期从小到大排序
        const sortedStats = [...dailyStats].sort((a, b) => {
            return new Date(a.date) - new Date(b.date);
        });
        
        const dates = sortedStats.map(stat => stat.date);
        const counts = sortedStats.map(stat => stat.count);try {
            const chart = new Chart(ctx, {
                type: 'line',
                data: {
                    labels: dates,
                    datasets: [{
                        label: '鸽切次数',
                        data: counts,
                        borderColor: '#3b82f6',
                        backgroundColor: 'rgba(59, 130, 246, 0.1)',
                        borderWidth: 2,
                        fill: true,
                        tension: 0.3,
                        pointBackgroundColor: '#3b82f6',
                        pointBorderColor: '#fff',
                        pointBorderWidth: 2,
                        pointRadius: 4,
                        pointHoverRadius: 6
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: { display: false },
                        tooltip: {
                            backgroundColor: 'rgba(0, 0, 0, 0.8)',
                            titleColor: 'white',
                            bodyColor: 'white',
                            borderColor: '#e5e7eb',
                            borderWidth: 1
                        }
                    },
                    scales: {
                        y: {
                            beginAtZero: true,
                            grid: { color: '#f3f4f6' },
                            ticks: { stepSize: 1, color: '#9ca3af' }
                        },
                        x: {
                            grid: { color: '#f3f4f6' },
                            ticks: { color: '#9ca3af' }
                        }
                    }
                }
            });
            
            // 保存图表实例
            chartInstances.set(canvasId, chart);return chart;
        } catch (error) {return null;
        }
    }

    /**
     * 创建用户分布图
     * @param {string} canvasId - 画布元素ID
     * @param {Array} topUsers - 用户数据
     * @returns {Object|null} Chart.js实例
     */
    function createUserChart(canvasId, topUsers) {
        const canvas = document.getElementById(canvasId);
        if (!canvas) {return null;
        }
        
        const ctx = canvas.getContext('2d');
        
        const userNames = topUsers.slice(0, 5).map(user => user.username);
        const userCounts = topUsers.slice(0, 5).map(user => user.count);
        
        const chart = new Chart(ctx, {
            type: 'doughnut',
            data: {
                labels: userNames,
                datasets: [{
                    data: userCounts,
                    backgroundColor: [
                        '#3b82f6',
                        '#10b981',
                        '#f59e0b',
                        '#ef4444',
                        '#8b5cf6'
                    ],
                    borderWidth: 2,
                    borderColor: '#fff'
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                cutout: '60%',
                plugins: {
                    legend: {
                        position: 'bottom',
                        labels: {
                            usePointStyle: true,
                            padding: 15,
                            font: { size: 11 }
                        }
                    },
                    tooltip: {
                        backgroundColor: 'rgba(0, 0, 0, 0.8)',
                        titleColor: 'white',
                        bodyColor: 'white',
                        borderColor: '#e5e7eb',
                        borderWidth: 1
                    }
                }
            }
        });
        
        chartInstances.set(canvasId, chart);
        return chart;
    }

    /**
     * 更新图表数据
     * @param {string} canvasId - 图表ID
     * @param {Array} newData - 新数据
     * @param {string} datasetIndex - 数据集索引（默认0）
     */
    function updateChartData(canvasId, newData, datasetIndex = 0) {
        const chart = chartInstances.get(canvasId);
        if (chart) {
            chart.data.datasets[datasetIndex].data = newData;
            chart.update();
        }
    }

    /**
     * 更新图表标签
     * @param {string} canvasId - 图表ID
     * @param {Array} newLabels - 新标签
     */
    function updateChartLabels(canvasId, newLabels) {
        const chart = chartInstances.get(canvasId);
        if (chart) {
            chart.data.labels = newLabels;
            chart.update();
        }
    }

    /**
     * 销毁图表
     * @param {string} canvasId - 图表ID
     */
    function destroyChart(canvasId) {
        const chart = chartInstances.get(canvasId);
        if (chart) {
            chart.destroy();
            chartInstances.delete(canvasId);
        }
    }

    /**
     * 销毁所有图表
     */
    function destroyAllCharts() {
        chartInstances.forEach((chart, canvasId) => {
            chart.destroy();
        });
        chartInstances.clear();
    }

    /**
     * 获取图表实例
     * @param {string} canvasId - 图表ID
     * @returns {Object|null} 图表实例
     */
    function getChart(canvasId) {
        return chartInstances.get(canvasId) || null;
    }

    /**
     * 检查图表是否存在
     * @param {string} canvasId - 图表ID
     * @returns {boolean} 是否存在
     */
    function hasChart(canvasId) {
        return chartInstances.has(canvasId);
    }

    /**
     * 初始化图表管理器
     */
    function init() {return true;
    }

    /**
     * 刷新图表数据
     * 重新获取数据并更新所有图表
     */
    async function refresh() {// 这里可以添加从服务器重新获取图表数据的逻辑
        // 目前只是重新渲染现有图表
        chartInstances.forEach((chart, canvasId) => {
            chart.update();
        });}

    // 暴露公共API
    window.ChartManager = {
        init: init,
        createTrendChart: createTrendChart,
        createUserChart: createUserChart,
        updateChartData: updateChartData,
        updateChartLabels: updateChartLabels,
        destroyChart: destroyChart,
        destroyAllCharts: destroyAllCharts,
        getChart: getChart,
        hasChart: hasChart,
        refresh: refresh
    };

})();