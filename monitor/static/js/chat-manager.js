/**
 * 鸽切监控系统 - 留言板管理模块
 * 处理异步留言功能
 */

(function() {
    'use strict';

    const ChatManager = {
        isOpen: false,
        username: '',
        messageHistory: [],
        isInitialized: false,
        isAdmin: false,
        adminPassword: '',
        pollInterval: null,
        lastTimestamp: 0,
        config: {
            enable: true,
            max_messages: 100,
            max_message_length: 500,
            max_title_length: 50,
            max_username_length: 20,
            username: {
                adjectives: ['快乐', '开心', '可爱'],
                nouns: ['鸽子', '小鸟', '猫咪']
            },
            filter: {
                enable: true,
                sensitive_words: [],
                filter_action: 'replace'
            },
            mute: {
                enable: true,
                mute_duration: 3600
            }
        },

        /**
         * 初始化留言板管理器
         */
        init: async function() {
            if (this.isInitialized) {
                console.log('ChatManager already initialized');
                return;
            }

            // 加载配置
            await this.loadConfig();

            // 检查是否启用留言功能
            if (!this.config.enable) {
                this.disableChatBox();
                return;
            }

            // 生成随机用户名
            this.username = this.generateUsername();

            // 初始化 DOM 元素
            this.initDOM();

            // 绑定事件
            this.bindEvents();

            // 加载留言历史
            await this.loadMessages();

            // 开始轮询
            this.startPolling();

            this.isInitialized = true;
        },

        /**
         * 加载配置
         */
        async loadConfig() {
            try {
                const response = await fetch('/api/guestbook/config');
                const data = await response.json();

                if (data.success) {
                    this.config = data.config;
                }
            } catch (error) {
                console.error('加载留言板配置失败:', error);
            }
        },

        /**
         * 禁用留言板
         */
        disableChatBox: function() {
            const chatBox = document.getElementById('chat-box');
            if (chatBox) {
                chatBox.style.display = 'none';
            }
        },

        /**
         * 生成随机用户名
         */
        generateUsername: function() {
            const adjectives = this.config.username.adjectives;
            const nouns = this.config.username.nouns;

            const adj = adjectives[Math.floor(Math.random() * adjectives.length)];
            const noun = nouns[Math.floor(Math.random() * nouns.length)];
            const randomNum = Math.floor(Math.random() * 1000);

            return `${adj}${noun}${randomNum}`;
        },

        /**
         * 初始化 DOM 元素
         */
        initDOM: function() {
            this.toggleBtn = document.getElementById('chat-toggle');
            this.mainBox = document.getElementById('chat-main');
            this.closeBtn = document.getElementById('chat-close');
            this.messagesContainer = document.getElementById('chat-messages');
            this.titleField = document.getElementById('chat-title');
            this.inputField = document.getElementById('chat-input');
            this.sendBtn = document.getElementById('chat-send');
            this.adminLoginBtn = document.getElementById('chat-admin-login');
        },

        /**
         * 绑定事件
         */
        bindEvents: function() {
            // 切换留言板
            if (this.toggleBtn) {
                this.toggleBtn.addEventListener('click', () => this.toggle());
            }

            // 关闭留言板
            if (this.closeBtn) {
                this.closeBtn.addEventListener('click', () => this.close());
            }

            // 发送留言
            if (this.sendBtn) {
                this.sendBtn.addEventListener('click', () => this.sendMessage());
            }

            // 管理员登录按钮
            if (this.adminLoginBtn && this.config.mute.enable) {
                this.adminLoginBtn.style.display = 'block';
                this.adminLoginBtn.addEventListener('click', () => this.adminLogin());
            }

            // 回车发送
            if (this.inputField) {
                this.inputField.addEventListener('keypress', (e) => {
                    if (e.key === 'Enter' && !e.shiftKey) {
                        e.preventDefault();
                        this.sendMessage();
                    }
                });

                // 输入长度限制提示
                this.inputField.setAttribute('maxlength', this.config.max_message_length);
            }

            if (this.titleField) {
                this.titleField.setAttribute('maxlength', this.config.max_title_length);
            }
        },

        /**
         * 开始轮询新留言
         */
        startPolling: function() {
            // 每 5 秒轮询一次
            this.pollInterval = setInterval(() => {
                this.pollNewMessages();
            }, 5000);
        },

        /**
         * 停止轮询
         */
        stopPolling: function() {
            if (this.pollInterval) {
                clearInterval(this.pollInterval);
                this.pollInterval = null;
            }
        },

        /**
         * 轮询新留言
         */
        async pollNewMessages() {
            try {
                const response = await fetch(`/api/guestbook/messages?since=${this.lastTimestamp}`);
                const data = await response.json();

                if (data.success && data.messages) {
                    data.messages.forEach(msg => {
                        // 检查是否已存在
                        if (!this.messageHistory.find(m => m.id === msg.id)) {
                            this.messageHistory.push(msg);
                            this.displayMessage(msg, true);
                        }
                    });

                    if (data.messages.length > 0) {
                        this.lastTimestamp = Math.max(...data.messages.map(m => m.timestamp));
                    }
                }
            } catch (error) {
                console.error('轮询留言失败:', error);
            }
        },

        /**
         * 加载留言历史
         */
        async loadMessages() {
            try {
                const response = await fetch('/api/guestbook/messages');
                const data = await response.json();

                if (data.success && data.messages) {
                    this.messageHistory = data.messages || [];

                    // 清空欢迎消息并显示历史
                    if (this.messageHistory.length > 0) {
                        this.messagesContainer.innerHTML = '';
                        this.messageHistory.forEach(msg => this.displayMessage(msg, false));
                        this.lastTimestamp = Math.max(...this.messageHistory.map(m => m.timestamp));
                    }
                }
            } catch (error) {
                console.error('加载留言历史失败:', error);
            }
        },

        /**
         * 切换留言板显示状态
         */
        toggle: function() {
            if (this.isOpen) {
                this.close();
            } else {
                this.open();
            }
        },

        /**
         * 打开留言板
         */
        open: function() {
            this.isOpen = true;
            this.mainBox.classList.add('show');

            // 聚焦输入框
            setTimeout(() => {
                this.inputField.focus();
            }, 300);

            // 滚动到底部
            this.scrollToBottom();
        },

        /**
         * 关闭留言板
         */
        close: function() {
            this.isOpen = false;
            this.mainBox.classList.remove('show');
        },

        /**
         * 发送留言
         */
        sendMessage: async function() {
            const title = this.titleField.value.trim();
            const message = this.inputField.value.trim();

            if (!message) {
                return;
            }

            try {
                const response = await fetch('/api/guestbook/message', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({
                        username: this.username,
                        title: title,
                        message: message
                    })
                });

                const data = await response.json();

                if (data.success) {
                    // 清空输入框
                    this.titleField.value = '';
                    this.inputField.value = '';

                    // 添加到本地
                    if (data.message) {
                        this.messageHistory.push(data.message);
                        this.displayMessage(data.message, true);
                    }
                } else {
                    this.showSystemMessage(data.message || '发送失败');
                }
            } catch (error) {
                console.error('发送留言失败:', error);
                this.showSystemMessage('发送失败，请稍后重试');
            }
        },

        /**
         * 显示留言
         */
        displayMessage: function(message, animate = false) {
            const ip = message.ip || '';
            const title = message.title || '';
            const timestamp = message.timestamp || 0;

            const messageElement = document.createElement('div');
            messageElement.className = `chat-message ${message.type === 'system' ? 'system' : ''}`;
            messageElement.dataset.id = message.id;

            messageElement.innerHTML = `
                <div class="chat-message-info">
                    <span class="chat-message-username">${this.escapeHtml(message.username)}</span>
                    ${ip ? `<span class="chat-message-ip" data-ip="${this.escapeHtml(ip)}">${this.escapeHtml(ip)}</span>` : ''}
                    ${timestamp ? `<span class="chat-message-time">${this.formatTime(timestamp)}</span>` : ''}
                </div>
                ${title ? `<div class="chat-message-title">${this.escapeHtml(title)}</div>` : ''}
                <div class="chat-message-bubble">${this.escapeHtml(message.message)}</div>
            `;

            if (animate) {
                messageElement.style.animation = 'messageFadeIn 0.2s ease-out';
            }

            this.messagesContainer.appendChild(messageElement);

            // 如果是管理员，添加点击事件
            this.bindIpClickEvent(messageElement, ip);

            // 滚动到底部
            this.scrollToBottom();
        },

        /**
         * 为 IP 元素绑定点击事件
         */
        bindIpClickEvent: function(messageElement, ip) {
            if (!this.isAdmin || !ip) {
                return;
            }

            const ipElement = messageElement.querySelector('.chat-message-ip');
            if (!ipElement) {
                return;
            }

            // 移除旧的事件监听器（防止重复绑定）
            const newIpElement = ipElement.cloneNode(true);
            ipElement.parentNode.replaceChild(newIpElement, ipElement);

            newIpElement.style.cursor = 'pointer';
            newIpElement.title = '点击禁言/解禁此用户';
            newIpElement.addEventListener('click', () => {
                this.showMuteDialog(ip);
            });
        },

        /**
         * 重新绑定所有 IP 点击事件（管理员登录后调用）
         */
        rebindAllIpClickEvents: function() {
            const ipElements = this.messagesContainer.querySelectorAll('.chat-message-ip');
            ipElements.forEach(ipElement => {
                const ip = ipElement.getAttribute('data-ip');
                if (ip) {
                    // 找到父元素
                    const messageElement = ipElement.closest('.chat-message');
                    if (messageElement) {
                        this.bindIpClickEvent(messageElement, ip);
                    }
                }
            });
        },

        /**
         * 显示系统消息
         */
        showSystemMessage: function(text) {
            const messageElement = document.createElement('div');
            messageElement.className = 'chat-message system';
            messageElement.innerHTML = `
                <div class="chat-message-bubble">${this.escapeHtml(text)}</div>
            `;

            this.messagesContainer.appendChild(messageElement);
            this.scrollToBottom();
        },

        /**
         * 滚动到底部
         */
        scrollToBottom: function() {
            setTimeout(() => {
                this.messagesContainer.scrollTop = this.messagesContainer.scrollHeight;
            }, 50);
        },

        /**
         * 格式化时间（中国时区）
         * 将 timestamp 转换为中国时区（东八区）的时间字符串
         */
        formatTime: function(timestamp) {
            const date = new Date(timestamp * 1000);
            
            try {
                const chinaDateStr = date.toLocaleString('zh-CN', {
                    timeZone: 'Asia/Shanghai',
                    year: 'numeric',
                    month: '2-digit',
                    day: '2-digit',
                    hour: '2-digit',
                    minute: '2-digit',
                    hour12: false
                });
                
                const match = chinaDateStr.match(/(\d{4})\/(\d{2})\/(\d{2}),?\s*(\d{2}):(\d{2})/);
                if (match) {
                    return `${match[2]}-${match[3]} ${match[4]}:${match[5]}`;
                }
            } catch (e) {
                console.warn('toLocaleString with timeZone failed, using fallback:', e);
            }
            
            const chinaOffset = 8 * 60;
            const localOffset = date.getTimezoneOffset();
            const totalOffset = localOffset + chinaOffset;
            
            const chinaDate = new Date(date.getTime() + totalOffset * 60 * 1000);
            
            const month = (chinaDate.getUTCMonth() + 1).toString().padStart(2, '0');
            const day = chinaDate.getUTCDate().toString().padStart(2, '0');
            const hours = chinaDate.getUTCHours().toString().padStart(2, '0');
            const minutes = chinaDate.getUTCMinutes().toString().padStart(2, '0');
            
            return `${month}-${day} ${hours}:${minutes}`;
        },

        /**
         * HTML 转义
         */
        escapeHtml: function(text) {
            const div = document.createElement('div');
            div.textContent = text;
            return div.innerHTML;
        },

        /**
         * 管理员登录
         */
        adminLogin: async function() {
            const password = prompt('请输入管理员密码:');
            if (!password) {
                return;
            }

            try {
                const response = await fetch('/api/guestbook/admin/login', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({ password })
                });

                const data = await response.json();

                if (data.success) {
                    this.isAdmin = true;
                    this.adminPassword = password;
                    this.showSystemMessage('✅ 管理员登录成功，点击用户IP可禁言/解禁');
                    document.body.classList.add('admin-mode');

                    // 重新绑定所有 IP 点击事件
                    setTimeout(() => {
                        this.rebindAllIpClickEvents();
                    }, 100);
                } else {
                    this.showSystemMessage('❌ ' + (data.message || '管理员密码错误'));
                }
            } catch (error) {
                console.error('管理员登录失败:', error);
                this.showSystemMessage('❌ 登录失败');
            }
        },

        /**
         * 显示禁言对话框
         */
        showMuteDialog: async function(ip) {
            const action = confirm(`用户 ${ip}\n\n点击"确定"禁言，点击"取消"解禁\n\n禁言默认时长: ${this.config.mute.mute_duration}秒 (${Math.floor(this.config.mute.mute_duration / 60)}分钟)`);
            if (action === null) {
                return; // 用户点击了取消
            }

            try {
                let url, body;

                if (action) {
                    // 禁言
                    const reason = prompt('禁言原因（可选）:', '违规行为') || '违规行为';
                    const duration = parseInt(prompt(`禁言时长（秒）:`, this.config.mute.mute_duration)) || this.config.mute.mute_duration;

                    url = '/api/guestbook/admin/mute';
                    body = {
                        password: this.adminPassword,
                        ip: ip,
                        reason: reason,
                        duration: duration
                    };
                } else {
                    // 解禁
                    url = '/api/guestbook/admin/unmute';
                    body = {
                        password: this.adminPassword,
                        ip: ip
                    };
                }

                const response = await fetch(url, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify(body)
                });

                const data = await response.json();

                if (data.success) {
                    this.showSystemMessage(`✅ ${data.message}`);
                } else {
                    this.showSystemMessage(`❌ ${data.message}`);
                }
            } catch (error) {
                console.error('管理员操作失败:', error);
                this.showSystemMessage('❌ 操作失败');
            }
        },

        /**
         * 显示禁言用户列表
         */
        showMutedList: async function() {
            try {
                const response = await fetch('/api/guestbook/admin/muted-list');
                const data = await response.json();

                if (data.success && data.list) {
                    if (data.list.length === 0) {
                        this.showSystemMessage('当前没有禁言用户');
                    } else {
                        this.showSystemMessage('🔒 禁言用户列表:');
                        data.list.forEach(user => {
                            const remaining = Math.floor(user.remaining / 60);
                            this.showSystemMessage(`  ${user.ip} - 剩余${remaining}分钟 (${user.reason})`);
                        });
                    }
                }
            } catch (error) {
                console.error('获取禁言列表失败:', error);
            }
        }
    };

    // 暴露到全局
    window.ChatManager = ChatManager;

})();
