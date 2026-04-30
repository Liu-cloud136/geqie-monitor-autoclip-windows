/**
 * 弹幕分析页面JavaScript
 * 处理情感分析、词云展示、热门话题、用户分析等
 */

const DanmakuAnalysis = {
    timeWindow: 300,
    autoRefresh: true,
    refreshInterval: null,
    analyzedCount: 0,
    maxRealtimeItems: 50,

    init: function() {
        console.log('🎯 弹幕分析模块初始化');
        
        this.bindEvents();
        this.startAutoRefresh();
        this.connectWebSocket();
        this.loadAllData();
    },

    bindEvents: function() {
        const self = this;
        
        document.querySelectorAll('.time-window-btn').forEach(btn => {
            btn.addEventListener('click', function() {
                const window = parseInt(this.dataset.window);
                self.setTimeWindow(window);
                
                document.querySelectorAll('.time-window-btn').forEach(b => {
                    b.classList.remove('btn-primary');
                    b.classList.add('btn-outline-secondary');
                });
                this.classList.remove('btn-outline-secondary');
                this.classList.add('btn-primary');
            });
        });
    },

    setTimeWindow: function(window) {
        this.timeWindow = window;
        this.loadAllData();
    },

    startAutoRefresh: function() {
        const self = this;
        this.refreshInterval = setInterval(function() {
            if (self.autoRefresh) {
                self.loadAllData();
            }
        }, 10000);
    },

    stopAutoRefresh: function() {
        if (this.refreshInterval) {
            clearInterval(this.refreshInterval);
            this.refreshInterval = null;
        }
    },

    connectWebSocket: function() {
        const self = this;
        
        if (typeof ConcurrencyManager !== 'undefined' && ConcurrencyManager.socket) {
            const socket = ConcurrencyManager.socket;
            
            socket.on('danmaku_analysis', function(data) {
                self.handleDanmakuAnalysis(data);
            });
            
            socket.on('suspicious_behavior', function(data) {
                self.handleSuspiciousBehavior(data);
            });
        }
    },

    handleDanmakuAnalysis: function(data) {
        this.analyzedCount++;
        this.updateAnalyzedCount();
        this.addRealtimeDanmaku(data);
    },

    handleSuspiciousBehavior: function(data) {
        console.warn('⚠️ 检测到可疑行为:', data);
        this.showSuspiciousAlert(data);
        this.loadSuspiciousUsers();
    },

    showSuspiciousAlert: function(data) {
        const badge = document.getElementById('suspicious-badge');
        if (badge) {
            const current = parseInt(badge.textContent) || 0;
            badge.textContent = current + 1;
        }
    },

    updateAnalyzedCount: function() {
        const elem = document.getElementById('analyzed-count');
        if (elem) {
            elem.textContent = this.analyzedCount;
        }
    },

    loadAllData: function() {
        this.loadRealtimeStats();
        this.loadSentimentStats();
        this.loadWordcloud();
        this.loadHotTopics();
        this.loadActiveUsers();
        this.loadSuspiciousUsers();
        this.loadDuplicateStats();
    },

    loadRealtimeStats: function() {
        fetch('/api/danmaku/analysis/realtime')
            .then(response => response.json())
            .then(data => {
                if (data.success && data.data) {
                    this.analyzedCount = data.data.total_danmaku_analyzed || 0;
                    this.updateAnalyzedCount();
                    
                    if (data.data.sentiment && data.data.sentiment.last_hour) {
                        this.updateSentimentCards(data.data.sentiment.last_hour);
                    }
                }
            })
            .catch(error => console.error('加载实时统计失败:', error));
    },

    loadSentimentStats: function() {
        fetch(`/api/danmaku/analysis/sentiment?time_window=${this.timeWindow}`)
            .then(response => response.json())
            .then(data => {
                if (data.success && data.data) {
                    this.updateSentimentCards(data.data);
                }
            })
            .catch(error => console.error('加载情感统计失败:', error));
    },

    updateSentimentCards: function(stats) {
        const total = stats.total || 1;
        
        const positiveCount = document.getElementById('positive-count');
        const neutralCount = document.getElementById('neutral-count');
        const negativeCount = document.getElementById('negative-count');
        const avgSentiment = document.getElementById('avg-sentiment');
        
        if (positiveCount) positiveCount.textContent = stats.positive || 0;
        if (neutralCount) neutralCount.textContent = stats.neutral || 0;
        if (negativeCount) negativeCount.textContent = stats.negative || 0;
        if (avgSentiment) avgSentiment.textContent = (stats.avg_sentiment || 0.5).toFixed(2);
        
        const positiveBar = document.getElementById('positive-bar');
        const neutralBar = document.getElementById('neutral-bar');
        const negativeBar = document.getElementById('negative-bar');
        const sentimentBar = document.getElementById('sentiment-bar');
        
        if (positiveBar) positiveBar.style.width = `${(stats.positive_ratio || 0) * 100}%`;
        if (neutralBar) neutralBar.style.width = `${(stats.neutral_ratio || 0) * 100}%`;
        if (negativeBar) negativeBar.style.width = `${(stats.negative_ratio || 0) * 100}%`;
        if (sentimentBar) sentimentBar.style.width = `${(stats.avg_sentiment || 0.5) * 100}%`;
    },

    loadWordcloud: function() {
        fetch(`/api/danmaku/analysis/wordcloud?time_window=${this.timeWindow}&max_words=100`)
            .then(response => response.json())
            .then(data => {
                if (data.success && data.data) {
                    this.renderWordcloud(data.data);
                }
            })
            .catch(error => console.error('加载词云失败:', error));
    },

    renderWordcloud: function(wordcloudData) {
        const container = document.getElementById('wordcloud-container');
        if (!container) return;
        
        if (!wordcloudData.words || wordcloudData.words.length === 0) {
            container.innerHTML = `
                <div class="text-center py-5 text-muted">
                    <i class="bi bi-cloud" style="font-size: 3rem;"></i>
                    <p class="mt-2 mb-0">暂无弹幕数据</p>
                </div>
            `;
            return;
        }
        
        const words = wordcloudData.words;
        const maxCount = Math.max(...words.map(w => w.value));
        const minCount = Math.min(...words.map(w => w.value));
        
        const colors = [
            '#0d6efd', '#6610f2', '#6f42c1', '#d63384', '#dc3545',
            '#fd7e14', '#ffc107', '#198754', '#20c997', '#0dcaf0'
        ];
        
        let html = '<div class="wordcloud-inner" style="padding: 20px; min-height: 300px;">';
        
        words.slice(0, 50).forEach((word, index) => {
            const normalized = (word.value - minCount) / (maxCount - minCount + 1);
            const fontSize = 14 + normalized * 30;
            const color = colors[index % colors.length];
            const rotation = (Math.random() - 0.5) * 20;
            const opacity = 0.6 + normalized * 0.4;
            
            html += `
                <span class="wordcloud-word" 
                      style="font-size: ${fontSize}px; color: ${color}; 
                             transform: rotate(${rotation}deg); opacity: ${opacity};
                             display: inline-block; margin: 5px 8px; cursor: pointer;"
                      title="${word.text}: ${word.value}次">
                    ${word.text}
                </span>
            `;
        });
        
        html += '</div>';
        container.innerHTML = html;
    },

    loadHotTopics: function() {
        fetch(`/api/danmaku/analysis/hot_topics?time_window=${this.timeWindow}&top_n=10`)
            .then(response => response.json())
            .then(data => {
                if (data.success && data.data) {
                    this.renderHotTopics(data.data);
                }
            })
            .catch(error => console.error('加载热门话题失败:', error));
    },

    renderHotTopics: function(topics) {
        const container = document.getElementById('hot-topics');
        if (!container) return;
        
        if (!topics || topics.length === 0) {
            container.innerHTML = `
                <div class="text-center py-3 text-muted">
                    <p class="mb-0">暂无热门话题</p>
                </div>
            `;
            return;
        }
        
        let html = '';
        topics.slice(0, 10).forEach((topic, index) => {
            const trendClass = topic.trend_score > 0.5 ? 'text-danger' : 'text-muted';
            const trendIcon = topic.trend_score > 0.5 ? 'bi-fire' : 'bi-arrow-right';
            
            html += `
                <div class="hot-topic-item mb-2 p-2 bg-light rounded">
                    <div class="d-flex justify-content-between align-items-center">
                        <div class="d-flex align-items-center gap-2">
                            <span class="badge bg-secondary">#${index + 1}</span>
                            <span class="fw-bold text-primary">${topic.keyword}</span>
                        </div>
                        <div class="d-flex align-items-center gap-2">
                            <small class="text-muted">${topic.count}次</small>
                            <small class="${trendClass}">
                                <i class="bi ${trendIcon}"></i>
                            </small>
                        </div>
                    </div>
                    <div class="progress mt-1" style="height: 3px;">
                        <div class="progress-bar bg-primary" style="width: ${Math.min(topic.trend_score * 100, 100)}%;"></div>
                    </div>
                </div>
            `;
        });
        
        container.innerHTML = html;
    },

    loadActiveUsers: function() {
        fetch(`/api/danmaku/analysis/active_users?time_window=${this.timeWindow}&top_n=20`)
            .then(response => response.json())
            .then(data => {
                if (data.success && data.data) {
                    this.renderActiveUsers(data.data);
                }
            })
            .catch(error => console.error('加载活跃用户失败:', error));
    },

    renderActiveUsers: function(users) {
        const tbody = document.getElementById('active-users-table');
        if (!tbody) return;
        
        if (!users || users.length === 0) {
            tbody.innerHTML = `
                <tr>
                    <td colspan="5" class="text-center py-4 text-muted">
                        <p class="mb-0">暂无活跃用户数据</p>
                    </td>
                </tr>
            `;
            return;
        }
        
        let html = '';
        users.slice(0, 15).forEach(user => {
            const sentimentClass = user.avg_sentiment > 0.6 ? 'text-success' : 
                                  user.avg_sentiment < 0.4 ? 'text-warning' : 'text-muted';
            const duplicateClass = user.duplicate_ratio > 0.5 ? 'text-danger' : 'text-muted';
            
            html += `
                <tr>
                    <td>
                        <div class="d-flex align-items-center gap-2">
                            <i class="bi bi-person-circle text-secondary"></i>
                            <span class="fw-medium">${this.escapeHtml(user.username)}</span>
                        </div>
                    </td>
                    <td class="text-center">
                        <span class="badge bg-primary">${user.total_danmaku}</span>
                    </td>
                    <td class="text-center">
                        <span class="badge bg-success">${user.positive}</span>
                    </td>
                    <td class="text-center">
                        <span class="badge bg-warning">${user.negative}</span>
                    </td>
                    <td class="text-center ${duplicateClass}">
                        ${(user.duplicate_ratio * 100).toFixed(1)}%
                    </td>
                </tr>
            `;
        });
        
        tbody.innerHTML = html;
    },

    loadSuspiciousUsers: function() {
        fetch(`/api/danmaku/analysis/suspicious_users?time_window=${this.timeWindow}`)
            .then(response => response.json())
            .then(data => {
                if (data.success && data.data) {
                    this.renderSuspiciousUsers(data.data);
                }
            })
            .catch(error => console.error('加载可疑用户失败:', error));
    },

    renderSuspiciousUsers: function(users) {
        const container = document.getElementById('suspicious-users');
        const badge = document.getElementById('suspicious-badge');
        
        if (badge) {
            badge.textContent = users ? users.length : 0;
        }
        
        if (!container) return;
        
        if (!users || users.length === 0) {
            container.innerHTML = `
                <div class="text-center py-4 text-muted">
                    <i class="bi bi-check-circle text-success" style="font-size: 2rem;"></i>
                    <p class="mt-2 mb-0">暂无可疑行为</p>
                </div>
            `;
            return;
        }
        
        let html = '<div class="list-group list-group-flush">';
        
        users.forEach(user => {
            const riskLevel = user.risk_score >= 0.8 ? 'danger' : 
                             user.risk_score >= 0.6 ? 'warning' : 'info';
            
            html += `
                <div class="list-group-item list-group-item-${riskLevel}">
                    <div class="d-flex justify-content-between align-items-center">
                        <div>
                            <div class="fw-bold">
                                <i class="bi bi-person-x me-1"></i>
                                ${this.escapeHtml(user.username)}
                            </div>
                            <small class="text-muted">
                                弹幕数: ${user.total_danmaku} | 
                                负面率: ${(user.negative_ratio * 100).toFixed(1)}% | 
                                重复率: ${(user.duplicate_ratio * 100).toFixed(1)}%
                            </small>
                        </div>
                        <span class="badge bg-${riskLevel} rounded-pill">
                            风险: ${(user.risk_score * 100).toFixed(0)}%
                        </span>
                    </div>
                </div>
            `;
        });
        
        html += '</div>';
        container.innerHTML = html;
    },

    loadDuplicateStats: function() {
        fetch(`/api/danmaku/analysis/duplicates?top_n=20`)
            .then(response => response.json())
            .then(data => {
                if (data.success && data.data) {
                    this.renderDuplicateStats(data.data);
                }
            })
            .catch(error => console.error('加载重复弹幕统计失败:', error));
    },

    renderDuplicateStats: function(duplicates) {
        const tbody = document.getElementById('duplicate-table');
        if (!tbody) return;
        
        if (!duplicates || duplicates.length === 0) {
            tbody.innerHTML = `
                <tr>
                    <td colspan="6" class="text-center py-4 text-muted">
                        <p class="mb-0">暂无重复弹幕数据</p>
                    </td>
                </tr>
            `;
            return;
        }
        
        let html = '';
        duplicates.slice(0, 20).forEach((item, index) => {
            const sentimentClass = item.avg_sentiment > 0.6 ? 'bg-success' : 
                                   item.avg_sentiment < 0.4 ? 'bg-warning' : 'bg-secondary';
            const sentimentText = item.avg_sentiment > 0.6 ? '正面' : 
                                   item.avg_sentiment < 0.4 ? '负面' : '中性';
            
            const topUsers = item.top_users || [];
            const userList = topUsers.slice(0, 3).map(u => 
                `${this.escapeHtml(u.username)}(${u.count})`
            ).join(', ');
            
            const timeSpan = item.time_span ? 
                `${Math.round(item.time_span / 60)}分钟` : '-';
            
            html += `
                <tr>
                    <td class="text-center fw-bold">#${index + 1}</td>
                    <td>
                        <div class="text-truncate" style="max-width: 300px;" 
                             title="${this.escapeHtml(item.content_sample)}">
                            ${this.escapeHtml(item.content_sample)}
                        </div>
                    </td>
                    <td class="text-center">
                        <span class="badge bg-info">${item.count}</span>
                    </td>
                    <td class="text-center">
                        <span class="badge ${sentimentClass}">${sentimentText}</span>
                    </td>
                    <td class="text-center">
                        <small class="text-muted">${userList || '-'}</small>
                    </td>
                    <td class="text-center">
                        <small class="text-muted">${timeSpan}</small>
                    </td>
                </tr>
            `;
        });
        
        tbody.innerHTML = html;
    },

    addRealtimeDanmaku: function(data) {
        const container = document.getElementById('realtime-danmaku');
        if (!container) return;
        
        const sentimentColor = data.sentiment_type === 'positive' ? 'border-start-success' :
                               data.sentiment_type === 'negative' ? 'border-start-warning' :
                               'border-start-secondary';
        
        const sentimentIcon = data.sentiment_type === 'positive' ? 'bi-emoji-smile text-success' :
                             data.sentiment_type === 'negative' ? 'bi-emoji-frown text-warning' :
                             'bi-emoji-neutral text-secondary';
        
        const html = `
            <div class="realtime-danmaku-item border-start ${sentimentColor} p-2 mb-1 bg-light rounded">
                <div class="d-flex justify-content-between align-items-start">
                    <div class="d-flex align-items-center gap-2">
                        <i class="bi ${sentimentIcon}"></i>
                        <span class="fw-medium text-primary">${this.escapeHtml(data.username)}</span>
                        <small class="text-muted">${this.formatTime(data.timestamp)}</small>
                    </div>
                    <div class="d-flex gap-1">
                        ${data.is_duplicate ? 
                            `<span class="badge bg-info">重复x${data.duplicate_count}</span>` : ''}
                        ${data.is_suspicious ? 
                            '<span class="badge bg-danger">可疑</span>' : ''}
                    </div>
                </div>
                <div class="mt-1">
                    <span class="text-dark">${this.escapeHtml(data.content)}</span>
                    ${data.keywords && data.keywords.length > 0 ? 
                        `<div class="mt-1">
                            <small class="text-muted">关键词: </small>
                            ${data.keywords.slice(0, 3).map(k => 
                                `<span class="badge bg-light text-secondary me-1">${this.escapeHtml(k)}</span>`
                            ).join('')}
                        </div>` : ''}
                </div>
            </div>
        `;
        
        const existingItems = container.querySelectorAll('.realtime-danmaku-item');
        if (existingItems.length >= this.maxRealtimeItems) {
            container.removeChild(existingItems[existingItems.length - 1]);
        }
        
        const tempDiv = document.createElement('div');
        tempDiv.innerHTML = html;
        const newItem = tempDiv.firstElementChild;
        
        container.insertBefore(newItem, container.firstChild);
    },

    formatTime: function(timestamp) {
        const date = new Date(timestamp * 1000);
        return date.toLocaleTimeString('zh-CN', { 
            hour: '2-digit', 
            minute: '2-digit', 
            second: '2-digit' 
        });
    },

    escapeHtml: function(text) {
        if (!text) return '';
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
};

function refreshAnalysis() {
    DanmakuAnalysis.loadAllData();
}

function clearAnalysisData() {
    if (!confirm('确定要清空所有弹幕分析数据吗？此操作不可恢复。')) {
        return;
    }
    
    const password = prompt('请输入管理员密码:');
    if (!password) return;
    
    fetch('/api/danmaku/analysis/clear', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({ password: password })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            alert('数据已清空');
            DanmakuAnalysis.analyzedCount = 0;
            DanmakuAnalysis.loadAllData();
        } else {
            alert('操作失败: ' + (data.error || '未知错误'));
        }
    })
    .catch(error => {
        console.error('清空数据失败:', error);
        alert('操作失败');
    });
}

document.addEventListener('DOMContentLoaded', function() {
    DanmakuAnalysis.init();
});
