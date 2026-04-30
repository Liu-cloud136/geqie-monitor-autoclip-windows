(function() {
    'use strict';

    const LiveChatroomManager = {
        isOpen: false,
        isInitialized: false,
        isConnected: false,
        isAdmin: false,
        adminPassword: '',
        
        socket: null,
        username: '',
        onlineCount: 0,
        config: {
            max_message_length: 500,
            username: {
                adjectives: ['快乐', '开心', '可爱', '聪明', '勇敢', '温柔', '活泼', '机智', '帅气', '美丽'],
                nouns: ['鸽子', '小鸟', '猫咪', '狗狗', '兔子', '熊猫', '老虎', '海豚', '企鹅']
            }
        },

        elements: {
            toggleBtn: null,
            mainBox: null,
            closeBtn: null,
            messagesContainer: null,
            inputField: null,
            sendBtn: null,
            adminLoginBtn: null,
            onlineCountDisplay: null
        },

        init: async function() {
            if (this.isInitialized) {
                console.log('LiveChatroomManager already initialized');
                return;
            }

            console.log('🚀 LiveChatroomManager 开始初始化...');

            try {
                await this.loadConfig();
                console.log('✅ 配置加载完成:', this.config);

                this.username = this.generateUsername();
                console.log('✅ 用户名生成:', this.username);

                this.initDOM();
                console.log('✅ DOM元素初始化完成');

                this.bindEvents();
                console.log('✅ 事件绑定完成');

                this.connectWebSocket();
                console.log('✅ WebSocket连接已启动');

                this.isInitialized = true;
                console.log('✅ LiveChatroomManager 初始化完成!');

            } catch (error) {
                console.error('❌ LiveChatroomManager 初始化失败:', error);
            }
        },

        loadConfig: async function() {
            try {
                const response = await fetch('/api/live-chat/config');
                const data = await response.json();

                if (data.success && data.config) {
                    this.config = { ...this.config, ...data.config };
                }
            } catch (error) {
                console.error('加载聊天室配置失败:', error);
            }
        },

        generateUsername: function() {
            const adjectives = this.config.username.adjectives;
            const nouns = this.config.username.nouns;

            const adj = adjectives[Math.floor(Math.random() * adjectives.length)];
            const noun = nouns[Math.floor(Math.random() * nouns.length)];
            const randomNum = Math.floor(Math.random() * 900) + 100;

            return `${adj}${noun}${randomNum}`;
        },

        initDOM: function() {
            this.elements.toggleBtn = document.getElementById('live-chat-toggle');
            this.elements.mainBox = document.getElementById('live-chat-main');
            this.elements.closeBtn = document.getElementById('live-chat-close');
            this.elements.messagesContainer = document.getElementById('live-chat-messages');
            this.elements.inputField = document.getElementById('live-chat-input');
            this.elements.sendBtn = document.getElementById('live-chat-send');
            this.elements.adminLoginBtn = document.getElementById('live-chat-admin-login');
            this.elements.onlineCountDisplay = document.getElementById('live-chat-online-count');
        },

        bindEvents: function() {
            if (this.elements.toggleBtn) {
                this.elements.toggleBtn.addEventListener('click', () => this.toggle());
            }

            if (this.elements.closeBtn) {
                this.elements.closeBtn.addEventListener('click', () => this.close());
            }

            if (this.elements.sendBtn) {
                this.elements.sendBtn.addEventListener('click', () => this.sendMessage());
            }

            if (this.elements.inputField) {
                this.elements.inputField.addEventListener('keypress', (e) => {
                    if (e.key === 'Enter' && !e.shiftKey) {
                        e.preventDefault();
                        this.sendMessage();
                    }
                });

                this.elements.inputField.setAttribute('maxlength', this.config.max_message_length);
            }

            if (this.elements.adminLoginBtn) {
                this.elements.adminLoginBtn.style.display = 'block';
                this.elements.adminLoginBtn.addEventListener('click', () => this.adminLogin());
            }
        },

        connectWebSocket: function() {
            console.log('🔌 开始连接WebSocket...');

            try {
                this.socket = io({
                    transports: ['websocket', 'polling'],
                    reconnection: true,
                    reconnectionAttempts: 10,
                    reconnectionDelay: 1000,
                    reconnectionDelayMax: 5000,
                    timeout: 20000
                });

                console.log('✅ Socket.IO实例创建成功');

                this.socket.on('connect', () => {
                    console.log('✅ WebSocket 连接成功! SID:', this.socket.id);
                    this.isConnected = true;
                    this.joinRoom();
                });

                this.socket.on('connect_error', (error) => {
                    console.error('❌ WebSocket 连接错误:', error);
                    this.showSystemMessage('连接服务器失败，请刷新页面重试');
                });

                this.socket.on('disconnect', () => {
                    console.log('⚠️ WebSocket 连接断开');
                    this.isConnected = false;
                    this.showSystemMessage('与服务器断开连接');
                });

                this.socket.on('reconnect', (attemptNumber) => {
                    console.log('🔄 WebSocket 重连成功，尝试次数:', attemptNumber);
                    this.isConnected = true;
                    this.joinRoom();
                });

                this.socket.on('live_chat_joined', (data) => {
                    console.log('🎉 加入聊天室成功:', data);
                    this.username = data.username;
                    this.onlineCount = data.online_count;
                    this.updateOnlineCount();
                    this.showSystemMessage(`欢迎！您的昵称是: ${this.username}`);
                });

                this.socket.on('live_chat_history', (data) => {
                    console.log('📜 收到历史消息，数量:', data.messages ? data.messages.length : 0);
                    if (data.messages && data.messages.length > 0) {
                        data.messages.forEach(msg => this.displayMessage(msg, false));
                    }
                });

                this.socket.on('live_chat_message', (message) => {
                    console.log('💬 收到新消息:', message);
                    this.displayMessage(message, true);
                });

                this.socket.on('live_chat_user_online', (data) => {
                    console.log('👤 用户上线:', data);
                    this.onlineCount = data.online_count;
                    this.updateOnlineCount();
                    this.showSystemMessage(`${data.username} 进入聊天室`);
                });

                this.socket.on('live_chat_user_offline', (data) => {
                    console.log('👋 用户离线:', data);
                    this.onlineCount = data.online_count;
                    this.updateOnlineCount();
                    this.showSystemMessage(`${data.username} 离开聊天室`);
                });

                this.socket.on('live_chat_user_muted', (data) => {
                    console.log('🔇 用户被禁言:', data);
                    this.showSystemMessage(`用户 ${data.ip} 已被禁言`);
                });

                this.socket.on('live_chat_user_unmuted', (data) => {
                    console.log('🔊 用户被解禁:', data);
                    this.showSystemMessage(`用户 ${data.ip} 已被解禁`);
                });

                this.socket.on('live_chat_error', (data) => {
                    console.error('❌ 聊天室错误:', data);
                    this.showSystemMessage(data.message || '发生错误');
                });

                this.socket.on('live_chat_admin_login_success', (data) => {
                    console.log('🔑 管理员登录成功');
                    this.isAdmin = true;
                    this.showSystemMessage('✅ 管理员登录成功，点击用户IP可禁言');
                    document.body.classList.add('live-chat-admin-mode');
                    this.rebindAllIpClickEvents();
                });

                this.socket.on('live_chat_admin_login_failed', (data) => {
                    console.error('❌ 管理员登录失败:', data);
                    this.showSystemMessage('❌ 密码错误');
                });

                this.socket.on('live_chat_admin_operation_success', (data) => {
                    console.log('✅ 管理员操作成功:', data);
                    this.showSystemMessage('✅ ' + data.message);
                });

                this.socket.on('live_chat_admin_operation_failed', (data) => {
                    console.error('❌ 管理员操作失败:', data);
                    this.showSystemMessage('❌ ' + data.message);
                });

                this.socket.on('live_chat_muted_list', (data) => {
                    console.log('🔒 禁言列表:', data);
                });

            } catch (error) {
                console.error('❌ WebSocket初始化异常:', error);
            }
        },

        joinRoom: function() {
            if (this.socket && this.socket.connected) {
                console.log('🚪 发送加入聊天室请求，用户名:', this.username);
                this.socket.emit('live_chat_join', {
                    username: this.username
                });
            } else {
                console.warn('⚠️ 无法加入聊天室: socket未连接');
            }
        },

        updateOnlineCount: function() {
            if (this.elements.onlineCountDisplay) {
                this.elements.onlineCountDisplay.textContent = this.onlineCount;
            }
        },

        toggle: function() {
            if (this.isOpen) {
                this.close();
            } else {
                this.open();
            }
        },

        open: function() {
            this.isOpen = true;
            if (this.elements.mainBox) {
                this.elements.mainBox.classList.add('show');
            }

            setTimeout(() => {
                if (this.elements.inputField) {
                    this.elements.inputField.focus();
                }
            }, 300);

            this.scrollToBottom();
        },

        close: function() {
            this.isOpen = false;
            if (this.elements.mainBox) {
                this.elements.mainBox.classList.remove('show');
            }
        },

        sendMessage: function() {
            if (!this.elements.inputField) return;

            const message = this.elements.inputField.value.trim();

            if (!message) {
                return;
            }

            if (!this.isConnected || !this.socket) {
                this.showSystemMessage('未连接到服务器，请刷新页面重试');
                return;
            }

            console.log('📤 发送消息:', message.substring(0, 50));
            this.socket.emit('live_chat_message', {
                content: message
            });

            this.elements.inputField.value = '';
        },

        displayMessage: function(message, animate = false) {
            if (!this.elements.messagesContainer) return;

            const ip = message.ip || '';
            const username = message.username || '匿名用户';
            const content = message.content || '';
            const timestamp = message.timestamp || 0;

            const messageElement = document.createElement('div');
            messageElement.className = `live-chat-message ${message.type === 'system' ? 'system' : ''}`;
            messageElement.dataset.id = message.id || '';

            const timeStr = timestamp ? this.formatTime(timestamp) : '';

            messageElement.innerHTML = `
                <div class="live-chat-message-info">
                    <span class="live-chat-message-username">${this.escapeHtml(username)}</span>
                    ${ip ? `<span class="live-chat-message-ip" data-ip="${this.escapeHtml(ip)}">${this.escapeHtml(ip)}</span>` : ''}
                    ${timeStr ? `<span class="live-chat-message-time">${timeStr}</span>` : ''}
                </div>
                <div class="live-chat-message-bubble">${this.escapeHtml(content)}</div>
            `;

            if (animate) {
                messageElement.style.animation = 'liveChatMessageFadeIn 0.3s ease-out';
            }

            this.elements.messagesContainer.appendChild(messageElement);

            if (ip) {
                this.bindIpClickEvent(messageElement, ip);
            }

            this.scrollToBottom();
        },

        bindIpClickEvent: function(messageElement, ip) {
            if (!this.isAdmin || !ip) {
                return;
            }

            const ipElement = messageElement.querySelector('.live-chat-message-ip');
            if (!ipElement) {
                return;
            }

            const newIpElement = ipElement.cloneNode(true);
            ipElement.parentNode.replaceChild(newIpElement, ipElement);

            newIpElement.style.cursor = 'pointer';
            newIpElement.title = '点击禁言/解禁此用户';
            newIpElement.addEventListener('click', () => {
                this.showMuteDialog(ip);
            });
        },

        rebindAllIpClickEvents: function() {
            if (!this.elements.messagesContainer) return;

            const ipElements = this.elements.messagesContainer.querySelectorAll('.live-chat-message-ip');
            ipElements.forEach(ipElement => {
                const ip = ipElement.getAttribute('data-ip');
                if (ip) {
                    const messageElement = ipElement.closest('.live-chat-message');
                    if (messageElement) {
                        this.bindIpClickEvent(messageElement, ip);
                    }
                }
            });
        },

        showMuteDialog: function(ip) {
            const action = confirm(`用户 ${ip}\n\n点击"确定"禁言，点击"取消"解禁\n\n默认禁言时长: ${this.config.mute?.mute_duration || 3600}秒 (${Math.floor((this.config.mute?.mute_duration || 3600) / 60)}分钟)`);
            
            if (action === null) {
                return;
            }

            try {
                if (action) {
                    const reason = prompt('禁言原因（可选）:', '违规行为') || '违规行为';
                    const duration = parseInt(prompt('禁言时长（秒）:', this.config.mute?.mute_duration || 3600)) || 3600;

                    this.socket.emit('live_chat_admin_mute', {
                        password: this.adminPassword,
                        ip: ip,
                        reason: reason,
                        duration: duration
                    });
                } else {
                    this.socket.emit('live_chat_admin_unmute', {
                        password: this.adminPassword,
                        ip: ip
                    });
                }
            } catch (error) {
                console.error('管理员操作失败:', error);
                this.showSystemMessage('操作失败');
            }
        },

        showSystemMessage: function(text) {
            if (!this.elements.messagesContainer) return;

            const messageElement = document.createElement('div');
            messageElement.className = 'live-chat-message system';
            messageElement.innerHTML = `
                <div class="live-chat-message-bubble">${this.escapeHtml(text)}</div>
            `;

            this.elements.messagesContainer.appendChild(messageElement);
            this.scrollToBottom();
        },

        scrollToBottom: function() {
            if (!this.elements.messagesContainer) return;

            setTimeout(() => {
                this.elements.messagesContainer.scrollTop = this.elements.messagesContainer.scrollHeight;
            }, 50);
        },

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

        escapeHtml: function(text) {
            if (!text) return '';
            const div = document.createElement('div');
            div.textContent = text;
            return div.innerHTML;
        },

        adminLogin: function() {
            const password = prompt('请输入管理员密码:');
            if (!password) {
                return;
            }

            this.adminPassword = password;
            this.socket.emit('live_chat_admin_login', {
                password: password
            });
        }
    };

    window.LiveChatroomManager = LiveChatroomManager;

})();
