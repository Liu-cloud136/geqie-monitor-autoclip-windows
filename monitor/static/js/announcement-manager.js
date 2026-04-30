/**
 * 鸽切监控系统 - 公告管理模块
 * 负责加载和显示系统公告
 */

(function() {
    'use strict';

    class AnnouncementManager {
        constructor() {
            this.storageKey = 'geqie_announcement_shown';
            this.currentAnnouncement = null;
        }

        /**
         * 初始化公告管理器
         */
        async init() {
            try {
                // 加载公告配置
                await this.loadAnnouncement();

                // 检查是否需要显示公告
                if (this.shouldShowAnnouncement()) {
                    await this.showAnnouncement();
                }
            } catch (error) {
                console.error('公告管理器初始化失败:', error);
            }
        }

        /**
         * 加载公告配置
         */
        async loadAnnouncement() {
            try {
                const response = await fetch('/api/announcement');
                const data = await response.json();

                if (data.success && data.announcement) {
                    this.currentAnnouncement = data.announcement;
                }
            } catch (error) {
                console.error('加载公告配置失败:', error);
            }
        }

        /**
         * 检查是否应该显示公告
         */
        shouldShowAnnouncement() {
            if (!this.currentAnnouncement) {
                return false;
            }

            // 检查是否启用
            if (!this.currentAnnouncement.enable) {
                return false;
            }

            // 检查是否需要显示
            const showOnce = this.currentAnnouncement.show_once;

            if (showOnce) {
                // 只显示一次：检查本地存储
                const lastShown = localStorage.getItem(this.storageKey);
                if (lastShown) {
                    return false;
                }
            }

            return true;
        }

        /**
         * 显示公告弹窗
         */
        async showAnnouncement() {
            if (!this.currentAnnouncement) {
                return;
            }

            const { title, content } = this.currentAnnouncement;

            // 显示公告弹窗
            if (window.ModalManager && window.ModalManager.showTemplate) {
                try {
                    // 立即显示弹窗并填充内容（不等待用户点击）
                    window.ModalManager.showTemplate('announcement', {
                        title: `<i class="bi bi-megaphone text-primary me-2"></i> ${title}`
                    }).then((result) => {
                        // 如果配置了只显示一次，关闭后记录
                        if (result === 'close' && this.currentAnnouncement.show_once) {
                            this.markAsShown();
                        }
                    });

                    // 立即填充内容（不等待 Promise 返回）
                    setTimeout(() => {
                        const contentEl = document.getElementById('announcementContent');
                        if (contentEl) {
                            const formattedContent = this.formatContent(content);
                            contentEl.innerHTML = formattedContent;
                        }
                    }, 100);

                } catch (error) {
                    console.error('显示公告弹窗时出错:', error);
                }
            }
        }

        /**
         * 格式化公告内容
         */
        formatContent(content) {
            // 按行分割内容，并过滤空行
            const lines = content.split('\n').filter(line => line.trim() !== '');

            // 处理每一行
            const formattedLines = lines.map((line, index) => {
                // 检查是否是最后一行（日期）
                const isLastLine = index === lines.length - 1;

                if (isLastLine) {
                    // 最后一行（日期）右对齐
                    return `<div class="announcement-line announcement-date">${line}</div>`;
                } else {
                    // 其他行居中显示
                    return `<div class="announcement-line">${line}</div>`;
                }
            });

            return formattedLines.join('');
        }

        /**
         * 标记公告已显示
         */
        markAsShown() {
            const timestamp = Date.now();
            localStorage.setItem(this.storageKey, timestamp.toString());
        }

        /**
         * 清除已显示标记（用于测试）
         */
        clearShownMark() {
            localStorage.removeItem(this.storageKey);
        }
    }

    // 暴露类到全局作用域
    window.AnnouncementManager = AnnouncementManager;

})();
