/**
 * 鸽切监控系统 - 音乐播放器模块
 * 负责音乐播放、播放列表管理和音频控制
 * 使用IIFE封装，避免全局变量污染
 */

(function() {
    'use strict';

    // 私有变量
    let musicFiles = [];
    let currentTrack = 0;
    let isPlaying = false;
    let audioElement = null;          // 主播放器元素
    let preloadPool = [];              // 预加载音频池（支持多首曲目预加载）
    let isDragging = false;
    let dragOffsetX = 0;
    let dragOffsetY = 0;
    let preloadTrackIndices = {};      // 记录预加载的曲目索引 {audioIndex: trackIndex}
    let domCache = {};                // DOM 元素缓存
    let isInit = false;               // 是否已初始化
    let PRELOAD_COUNT = 3;            // 预加载曲目数量（下一曲、下下曲、下下下曲），可通过配置文件修改
    let waitingHandler = null;        // waiting事件处理器引用
    let playingHandler = null;        // playing事件处理器引用

    // 新增变量
    let playMode = 'sequence';        // 播放模式：sequence(顺序), repeat(单曲循环), random(随机)
    let favoriteSongs = [];           // 我喜欢的歌曲列表
    let isPlaylistPanelVisible = false; // 播放列表面板是否显示
    let importPlatform = '';          // 当前选中的导入平台

    /**
     * 初始化播放器
     */
    async function init() {
        if (isInit) return;  // 防止重复初始化
        isInit = true;

        // 加载音乐播放器配置
        await loadMusicConfig();

        // 加载喜欢的歌曲列表
        loadFavoriteSongs();

        audioElement = new Audio();
        audioElement.volume = 0.2; // 默认音量20%

        // 创建预加载音频池
        for (let i = 0; i < PRELOAD_COUNT; i++) {
            const audio = new Audio();
            audio.volume = 0.2;
            audio.preload = 'auto';
            preloadPool.push(audio);
        }

        // 延迟初始化非关键功能 - 拖拽功能在用户首次交互时才初始化
        if ('IntersectionObserver' in window) {
            const observer = new IntersectionObserver((entries) => {
                entries.forEach(entry => {
                    if (entry.isIntersecting) {
                        setupDraggable();
                        observer.disconnect();
                    }
                });
            });
            const player = document.getElementById('music-player');
            if (player) observer.observe(player);
        }

        cacheDomElements();  // 缓存 DOM 元素
        setupEventListeners();
        
        // 页面加载后自动加载音乐列表（异步，不阻塞页面）
        loadMusicList();
    }

    /**
     * 加载喜欢的歌曲列表
     */
    function loadFavoriteSongs() {
        try {
            const saved = localStorage.getItem('musicFavoriteSongs');
            if (saved) {
                favoriteSongs = JSON.parse(saved);
            }
        } catch (error) {
            console.warn('[MusicPlayer] 加载喜欢的歌曲列表失败:', error);
            favoriteSongs = [];
        }
    }

    /**
     * 保存喜欢的歌曲列表
     */
    function saveFavoriteSongs() {
        try {
            localStorage.setItem('musicFavoriteSongs', JSON.stringify(favoriteSongs));
        } catch (error) {
            console.warn('[MusicPlayer] 保存喜欢的歌曲列表失败:', error);
        }
    }

    /**
     * 加载音乐播放器配置
     */
    async function loadMusicConfig() {
        try {
            const response = await fetch('/api/music/config');
            const data = await response.json();
            if (data.success && data.config) {
                PRELOAD_COUNT = data.config.preload_count || 3;
                console.log(`[MusicPlayer] 配置加载成功: 预加载数量 = ${PRELOAD_COUNT}`);
            }
        } catch (error) {
            console.warn('[MusicPlayer] 加载配置失败，使用默认值:', error);
        }
    }

    /**
     * 缓存 DOM 元素
     */
    function cacheDomElements() {
        domCache = {
            playBtn: document.getElementById('music-play-btn'),
            nextBtn: document.getElementById('music-next-btn'),
            prevBtn: document.getElementById('music-prev-btn'),
            volumeBtn: document.getElementById('music-volume-btn'),
            currentTrack: document.getElementById('music-current-track'),
            titleBar: document.querySelector('.music-player-header span'),
            player: document.getElementById('music-player'),
            // 新增元素
            modeBtn: document.getElementById('music-mode-btn'),
            likeBtn: document.getElementById('music-like-btn'),
            playlistBtn: document.getElementById('music-playlist-btn'),
            playlistPanel: document.getElementById('music-playlist-panel'),
            playlist: document.getElementById('music-playlist'),
            favoriteList: document.getElementById('music-favorite-list'),
            listCount: document.getElementById('music-list-count'),
            favoriteCount: document.getElementById('music-favorite-count'),
            // 进度条相关
            progressBar: document.getElementById('music-progress-bar'),
            progress: document.getElementById('music-progress'),
            progressFill: document.getElementById('music-progress-fill'),
            currentTime: document.getElementById('music-current-time'),
            totalTime: document.getElementById('music-total-time'),
            // 导入相关
            importUrl: document.getElementById('music-import-url'),
            importSubmit: document.getElementById('music-import-submit'),
            importResult: document.getElementById('music-import-result'),
            tabs: document.querySelectorAll('.music-playlist-tab'),
            tabContents: document.querySelectorAll('.music-playlist-content'),
            importBtns: document.querySelectorAll('.music-import-btn')
        };
        
        // 验证关键元素是否存在
        if (!domCache.player) {
            return;
        }
        
        const missingElements = [];
        if (!domCache.playBtn) missingElements.push('playBtn');
        if (!domCache.nextBtn) missingElements.push('nextBtn');
        if (!domCache.prevBtn) missingElements.push('prevBtn');
    }

    /**
     * 确保音乐列表已加载(懒加载)
     * @returns {Promise<boolean>} 是否加载成功
     */
    async function ensureMusicListLoaded() {
        if (musicFiles.length === 0) {
            await loadMusicList();
        }
        return musicFiles.length > 0;
    }

    /**
     * 加载音乐列表
     */
    async function loadMusicList() {
        try {
            const response = await fetch('/api/music/list');
            const data = await response.json();

            if (data.success) {
                musicFiles = data.music_files;
                updatePlayerState();
                updatePlaylistDisplay();
            }
        } catch (error) {
            // 静默处理错误
        }
    }

    /**
     * 更新播放列表显示
     */
    function updatePlaylistDisplay() {
        if (!domCache.playlist) return;

        domCache.playlist.innerHTML = '';
        domCache.listCount.textContent = `${musicFiles.length} 首`;

        musicFiles.forEach((file, index) => {
            const item = document.createElement('div');
            item.className = `music-playlist-item ${index === currentTrack ? 'playing' : ''}`;
            item.dataset.index = index;

            const isFavorite = favoriteSongs.includes(file);
            
            item.innerHTML = `
                <div class="music-playlist-item-info">
                    <span class="music-playlist-item-index">${index + 1}</span>
                    <span class="music-playlist-item-name">${escapeHtml(file)}</span>
                    ${isFavorite ? '<i class="bi bi-heart-fill music-playlist-item-favorite"></i>' : ''}
                </div>
            `;

            item.addEventListener('click', () => {
                playTrack(index);
            });

            domCache.playlist.appendChild(item);
        });
    }

    /**
     * 更新喜欢的歌曲列表显示
     */
    function updateFavoriteListDisplay() {
        if (!domCache.favoriteList) return;

        domCache.favoriteList.innerHTML = '';
        domCache.favoriteCount.textContent = `${favoriteSongs.length} 首`;

        favoriteSongs.forEach((file, index) => {
            const item = document.createElement('div');
            item.className = `music-playlist-item ${musicFiles[currentTrack] === file ? 'playing' : ''}`;
            item.dataset.filename = file;

            const trackIndex = musicFiles.indexOf(file);
            
            item.innerHTML = `
                <div class="music-playlist-item-info">
                    <span class="music-playlist-item-index">${index + 1}</span>
                    <span class="music-playlist-item-name">${escapeHtml(file)}</span>
                    <i class="bi bi-heart-fill music-playlist-item-favorite"></i>
                </div>
                <button class="music-playlist-item-remove" title="移除">
                    <i class="bi bi-x"></i>
                </button>
            `;

            item.addEventListener('click', (e) => {
                if (e.target.closest('.music-playlist-item-remove')) {
                    removeFromFavorite(file);
                } else if (trackIndex !== -1) {
                    playTrack(trackIndex);
                }
            });

            domCache.favoriteList.appendChild(item);
        });
    }

    /**
     * 添加到喜欢
     * @param {string} filename - 文件名
     */
    function addToFavorite(filename) {
        if (!favoriteSongs.includes(filename)) {
            favoriteSongs.push(filename);
            saveFavoriteSongs();
            updateLikeButton();
            updatePlaylistDisplay();
            updateFavoriteListDisplay();
        }
    }

    /**
     * 从喜欢中移除
     * @param {string} filename - 文件名
     */
    function removeFromFavorite(filename) {
        const index = favoriteSongs.indexOf(filename);
        if (index !== -1) {
            favoriteSongs.splice(index, 1);
            saveFavoriteSongs();
            updateLikeButton();
            updatePlaylistDisplay();
            updateFavoriteListDisplay();
        }
    }

    /**
     * 切换喜欢状态
     */
    function toggleFavorite() {
        if (musicFiles.length === 0) return;
        const currentFile = musicFiles[currentTrack];
        if (favoriteSongs.includes(currentFile)) {
            removeFromFavorite(currentFile);
        } else {
            addToFavorite(currentFile);
        }
    }

    /**
     * 更新喜欢按钮状态
     */
    function updateLikeButton() {
        if (!domCache.likeBtn) return;
        
        const icon = domCache.likeBtn.querySelector('i');
        if (musicFiles.length > 0 && favoriteSongs.includes(musicFiles[currentTrack])) {
            icon.className = 'bi bi-heart-fill';
            domCache.likeBtn.classList.add('liked');
        } else {
            icon.className = 'bi bi-heart';
            domCache.likeBtn.classList.remove('liked');
        }
    }

    /**
     * 切换播放模式
     */
    function togglePlayMode() {
        const modes = ['sequence', 'repeat', 'random'];
        const currentIndex = modes.indexOf(playMode);
        playMode = modes[(currentIndex + 1) % modes.length];
        updateModeButton();
        savePlayMode();
    }

    /**
     * 保存播放模式
     */
    function savePlayMode() {
        try {
            localStorage.setItem('musicPlayMode', playMode);
        } catch (error) {
            console.warn('[MusicPlayer] 保存播放模式失败:', error);
        }
    }

    /**
     * 加载播放模式
     */
    function loadPlayMode() {
        try {
            const saved = localStorage.getItem('musicPlayMode');
            if (saved && ['sequence', 'repeat', 'random'].includes(saved)) {
                playMode = saved;
            }
        } catch (error) {
            console.warn('[MusicPlayer] 加载播放模式失败:', error);
        }
        updateModeButton();
    }

    /**
     * 更新播放模式按钮
     */
    function updateModeButton() {
        if (!domCache.modeBtn) return;
        
        const icon = domCache.modeBtn.querySelector('i');
        let title = '';
        
        switch (playMode) {
            case 'sequence':
                icon.className = 'bi bi-repeat';
                title = '顺序播放';
                break;
            case 'repeat':
                icon.className = 'bi bi-repeat-1';
                title = '单曲循环';
                break;
            case 'random':
                icon.className = 'bi bi-shuffle';
                title = '随机播放';
                break;
        }
        
        domCache.modeBtn.setAttribute('title', title);
    }

    /**
     * 切换播放列表面板显示
     */
    async function togglePlaylistPanel() {
        if (!domCache.playlistPanel) return;
        
        isPlaylistPanelVisible = !isPlaylistPanelVisible;
        domCache.playlistPanel.style.display = isPlaylistPanelVisible ? 'block' : 'none';
        
        if (isPlaylistPanelVisible) {
            await ensureMusicListLoaded();
            // 确保加载完成后更新显示
            updatePlaylistDisplay();
            updateFavoriteListDisplay();
        }
    }

    /**
     * 播放指定曲目
     * @param {number} index - 曲目索引
     */
    async function playTrack(index) {
        // 确保音乐列表已加载
        const loaded = await ensureMusicListLoaded();
        if (!loaded) {
            return;
        }

        if (index < 0 || index >= musicFiles.length) return;

        // 先暂停所有音频元素，防止双重播放
        audioElement.pause();
        preloadPool.forEach(audio => audio.pause());

        // 检查是否已经预加载了这首曲子
        const preloadedIndex = findPreloadedIndex(index);
        if (preloadedIndex !== -1) {
            // 使用预加载的音频元素，无缝切换
            swapAndPlay(index, preloadedIndex);
            return;
        }

        currentTrack = index;
        const trackUrl = `/api/music/play/${encodeURIComponent(musicFiles[index])}`;

        // 显示加载状态
        const currentTrackElement = domCache.currentTrack;
        if (currentTrackElement) {
            currentTrackElement.textContent = '加载中...';
        }

        // 清理音频元素上的旧事件处理器（如果有）
        if (audioElement._musicPlayerHandlers) {
            const handlers = audioElement._musicPlayerHandlers;
            if (handlers.onEnded) {
                audioElement.removeEventListener('ended', handlers.onEnded);
            }
            if (handlers.onError) {
                audioElement.removeEventListener('error', handlers.onError);
            }
            delete audioElement._musicPlayerHandlers;
        }

        audioElement.src = trackUrl;

        // 移除之前的事件监听器（如果存在）
        if (waitingHandler) {
            audioElement.removeEventListener('waiting', waitingHandler);
        }
        if (playingHandler) {
            audioElement.removeEventListener('playing', playingHandler);
        }

        // 添加新的事件监听器
        waitingHandler = () => {
            if (currentTrackElement) {
                currentTrackElement.textContent = '缓冲中...';
            }
        };
        playingHandler = () => {
            isPlaying = true;
            updateCurrentTrackDisplay();
        };

        audioElement.addEventListener('waiting', waitingHandler, { once: true });
        audioElement.addEventListener('playing', playingHandler, { once: true });

        // 重新绑定 ended 和 error 事件
        setupAudioElementEvents(audioElement);

        // 绑定进度更新事件
        audioElement.addEventListener('timeupdate', updateProgress);
        audioElement.addEventListener('loadedmetadata', updateDuration);

        audioElement.play().then(() => {
            isPlaying = true;
            updatePlayerState();
            // 显示进度条
            if (domCache.progressBar) {
                domCache.progressBar.style.display = 'block';
            }
            // 预加载后续曲目
            preloadMultipleTracks();
        }).catch(error => {
            if (currentTrackElement) {
                currentTrackElement.textContent = '播放失败';
            }
            console.error('[MusicPlayer] 播放失败:', error);
        });
    }

    /**
     * 更新进度条
     */
    function updateProgress() {
        if (!audioElement || !domCache.progressFill) return;
        
        const percent = (audioElement.currentTime / audioElement.duration) * 100 || 0;
        domCache.progressFill.style.width = `${percent}%`;
        
        if (domCache.currentTime) {
            domCache.currentTime.textContent = formatTime(audioElement.currentTime);
        }
    }

    /**
     * 更新总时长
     */
    function updateDuration() {
        if (!audioElement || !domCache.totalTime) return;
        domCache.totalTime.textContent = formatTime(audioElement.duration);
    }

    /**
     * 格式化时间
     * @param {number} seconds - 秒数
     * @returns {string} 格式化后的时间字符串
     */
    function formatTime(seconds) {
        if (isNaN(seconds)) return '0:00';
        const mins = Math.floor(seconds / 60);
        const secs = Math.floor(seconds % 60);
        return `${mins}:${secs.toString().padStart(2, '0')}`;
    }

    /**
     * 交换音频元素并播放（无缝切换）
     * @param {number} index - 曲目索引
     * @param {number} preloadedIndex - 预加载池中的索引
     */
    function swapAndPlay(index, preloadedIndex) {
        // 先保存旧音频元素的引用，用于后续同步
        const oldAudioElement = audioElement;
        const oldVolume = audioElement.volume;

        // 交换音频元素引用
        const tempAudio = audioElement;
        audioElement = preloadPool[preloadedIndex];
        preloadPool[preloadedIndex] = tempAudio;

        // 暂停池中其他所有音频元素，防止双重播放
        preloadPool.forEach((audio, i) => {
            if (i !== preloadedIndex) {
                audio.pause();
                audio.currentTime = 0;
            }
        });

        currentTrack = index;

        // 检查交换后的音频元素是否已准备好播放
        if (audioElement.readyState < 2) { // HAVE_CURRENT_DATA
            playTrack(index);
            return;
        }

        // 同步音量
        audioElement.volume = oldVolume;

        // 重新为新的 audioElement 绑定事件监听器（确保 ended 事件能正确触发）
        setupAudioElementEvents(audioElement);

        // 绑定进度更新事件
        audioElement.addEventListener('timeupdate', updateProgress);
        audioElement.addEventListener('loadedmetadata', updateDuration);

        // 直接播放，无需等待加载
        audioElement.play().then(() => {
            isPlaying = true;
            updatePlayerState();
            // 显示进度条
            if (domCache.progressBar) {
                domCache.progressBar.style.display = 'block';
            }
        }).catch(error => {
            // 播放失败时更新状态
            isPlaying = false;
            updatePlayerState();
        });

        // 更新当前曲目显示
        updateCurrentTrackDisplay();

        // 清空预加载标记
        delete preloadTrackIndices[preloadedIndex];

        // 立即预加载多首曲目
        preloadMultipleTracks();
    }

    /**
     * 查找曲目是否已预加载
     * @param {number} trackIndex - 曲目索引
     * @returns {number} 预加载池中的索引，未找到返回 -1
     */
    function findPreloadedIndex(trackIndex) {
        for (let i = 0; i < preloadPool.length; i++) {
            if (preloadTrackIndices[i] === trackIndex) {
                return i;
            }
        }
        return -1;
    }

    /**
     * 预加载多首曲目（下一曲、下下曲、下下下曲等）
     */
    function preloadMultipleTracks() {
        if (musicFiles.length <= 1) return;

        // 优先级：下一曲 > 下下曲 > 下下下曲
        for (let offset = 1; offset <= PRELOAD_COUNT; offset++) {
            const trackIndex = (currentTrack + offset) % musicFiles.length;
            const trackUrl = `/api/music/play/${encodeURIComponent(musicFiles[trackIndex])}`;

            // 检查是否已预加载
            if (findPreloadedIndex(trackIndex) !== -1) {
                continue;
            }

            // 检查是否是当前正在播放的曲目
            if (trackIndex === currentTrack) {
                continue;
            }

            // 查找可用的预加载槽位
            let availableSlot = -1;
            for (let i = 0; i < preloadPool.length; i++) {
                // 槽位未被使用或已被交换到主播放器
                if (preloadTrackIndices[i] === undefined ||
                    preloadPool[i] === audioElement) {
                    availableSlot = i;
                    break;
                }
            }

            // 如果没有可用槽位，替换最远距离的预加载
            if (availableSlot === -1) {
                let maxDistance = -1;
                for (let i = 0; i < preloadPool.length; i++) {
                    const preloadedTrack = preloadTrackIndices[i];
                    if (preloadedTrack !== undefined) {
                        // 计算预加载曲目距离当前曲目的距离
                        let distance = (preloadedTrack - currentTrack + musicFiles.length) % musicFiles.length;
                        // 找到最远的预加载
                        if (distance > maxDistance) {
                            maxDistance = distance;
                            availableSlot = i;
                        }
                    }
                }
            }

            if (availableSlot !== -1) {
                // 暂停并重置预加载音频元素
                preloadPool[availableSlot].pause();
                preloadPool[availableSlot].currentTime = 0;

                // 加载新曲目
                preloadPool[availableSlot].src = trackUrl;
                preloadPool[availableSlot].volume = audioElement.volume;
                preloadPool[availableSlot].load();

                // 记录预加载的曲目索引
                preloadTrackIndices[availableSlot] = trackIndex;

            }
        }
    }

    /**
     * 播放/暂停
     */
    async function togglePlay() {
        if (isPlaying) {
            audioElement.pause();
            isPlaying = false;
        } else {
            if (audioElement.src) {
                audioElement.play();
                isPlaying = true;
            } else {
                await ensureMusicListLoaded();
                if (musicFiles.length > 0) {
                    playTrack(0);
                } else {
                    // 音乐列表为空或加载失败
                }
            }
        }
        updatePlayerState();
    }

    /**
     * 下一曲
     */
    async function nextTrack() {
        await ensureMusicListLoaded();
        if (musicFiles.length === 0) return;

        let nextIndex;
        
        switch (playMode) {
            case 'repeat':
                // 单曲循环，重新播放当前曲目
                nextIndex = currentTrack;
                break;
            case 'random':
                // 随机播放
                nextIndex = Math.floor(Math.random() * musicFiles.length);
                // 避免重复播放同一首
                if (musicFiles.length > 1 && nextIndex === currentTrack) {
                    nextIndex = (nextIndex + 1) % musicFiles.length;
                }
                break;
            case 'sequence':
            default:
                // 顺序播放
                nextIndex = (currentTrack + 1) % musicFiles.length;
                break;
        }

        try {
            await playTrack(nextIndex);
        } catch (error) {
            console.error('播放下一曲失败:', error);
        }
    }

    /**
     * 上一曲
     */
    async function prevTrack() {
        await ensureMusicListLoaded();
        if (musicFiles.length === 0) return;

        let prevIndex;
        
        switch (playMode) {
            case 'repeat':
                // 单曲循环，重新播放当前曲目
                prevIndex = currentTrack;
                break;
            case 'random':
                // 随机播放
                prevIndex = Math.floor(Math.random() * musicFiles.length);
                // 避免重复播放同一首
                if (musicFiles.length > 1 && prevIndex === currentTrack) {
                    prevIndex = (prevIndex + 1) % musicFiles.length;
                }
                break;
            case 'sequence':
            default:
                // 顺序播放
                prevIndex = (currentTrack - 1 + musicFiles.length) % musicFiles.length;
                break;
        }

        try {
            await playTrack(prevIndex);
        } catch (error) {
            console.error('播放上一曲失败:', error);
        }
    }

    /**
     * 导入歌单
     * @param {string} platform - 平台 (qqmusic, netease)
     * @param {string} urlOrId - 歌单链接或ID
     */
    async function importPlaylist(platform, urlOrId) {
        if (!domCache.importResult) return;

        // 显示加载状态
        domCache.importResult.style.display = 'block';
        domCache.importResult.innerHTML = `
            <div class="music-import-loading">
                <i class="bi bi-arrow-repeat spin"></i> 正在导入...
            </div>
        `;

        try {
            const response = await fetch('/api/music/import', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    platform: platform,
                    url_or_id: urlOrId
                })
            });

            const data = await response.json();

            if (data.success) {
                // 导入成功
                domCache.importResult.innerHTML = `
                    <div class="music-import-success">
                        <i class="bi bi-check-circle-fill"></i> 导入成功！
                        <div>获取到 ${data.songs ? data.songs.length : 0} 首歌曲</div>
                    </div>
                `;

                // 刷新音乐列表
                await loadMusicList();
            } else {
                // 导入失败
                domCache.importResult.innerHTML = `
                    <div class="music-import-error">
                        <i class="bi bi-x-circle-fill"></i> 导入失败：${data.message || '未知错误'}
                    </div>
                `;
            }
        } catch (error) {
            domCache.importResult.innerHTML = `
                <div class="music-import-error">
                    <i class="bi bi-x-circle-fill"></i> 导入失败：网络错误
                </div>
            `;
        }
    }

    /**
     * 设置事件监听器
     */
    function setupEventListeners() {
        // 主播放器事件监听
        setupAudioElementEvents(audioElement);

        // 预加载播放器事件监听 - 但不需要 ended 事件
        preloadPool.forEach(audio => {
            // 只监听错误事件，不需要 ended 事件（预加载池不应该触发播放结束）
            audio.addEventListener('error', () => {
                if (audio === audioElement) {
                    const errorCountKey = 'musicPlayerErrorCount';
                    const errorCount = parseInt(sessionStorage.getItem(errorCountKey) || '0', 10);

                    if (errorCount >= musicFiles.length - 1) {
                        sessionStorage.removeItem(errorCountKey);
                        isPlaying = false;
                        updatePlayerState();
                        return;
                    }

                    sessionStorage.setItem(errorCountKey, String(errorCount + 1));
                    nextTrack();
                }
            });
        });

        // 播放按钮
        const playBtn = document.getElementById('music-play-btn');
        if (playBtn) {
            playBtn.addEventListener('click', togglePlay);
        }

        // 下一曲按钮
        const nextBtn = document.getElementById('music-next-btn');
        if (nextBtn) {
            nextBtn.addEventListener('click', nextTrack);
        }

        // 上一曲按钮
        const prevBtn = document.getElementById('music-prev-btn');
        if (prevBtn) {
            prevBtn.addEventListener('click', prevTrack);
        }

        // 音量按钮
        const volumeBtn = document.getElementById('music-volume-btn');
        if (volumeBtn) {
            volumeBtn.addEventListener('click', toggleMute);
        }

        // 新增事件监听器
        // 播放模式按钮
        if (domCache.modeBtn) {
            domCache.modeBtn.addEventListener('click', togglePlayMode);
        }

        // 喜欢按钮
        if (domCache.likeBtn) {
            domCache.likeBtn.addEventListener('click', toggleFavorite);
        }

        // 播放列表按钮
        if (domCache.playlistBtn) {
            domCache.playlistBtn.addEventListener('click', togglePlaylistPanel);
        }

        // 标签页切换
        if (domCache.tabs) {
            domCache.tabs.forEach(tab => {
                tab.addEventListener('click', () => {
                    const targetTab = tab.dataset.tab;
                    
                    // 更新标签页状态
                    domCache.tabs.forEach(t => t.classList.remove('active'));
                    tab.classList.add('active');
                    
                    // 更新内容区域
                    domCache.tabContents.forEach(content => content.classList.remove('active'));
                    const targetContent = document.getElementById(`playlist-${targetTab}`);
                    if (targetContent) {
                        targetContent.classList.add('active');
                    }

                    // 如果是我喜欢的标签，更新显示
                    if (targetTab === 'favorite') {
                        updateFavoriteListDisplay();
                    }
                });
            });
        }

        // 导入平台选择
        if (domCache.importBtns) {
            domCache.importBtns.forEach(btn => {
                btn.addEventListener('click', () => {
                    domCache.importBtns.forEach(b => b.classList.remove('active'));
                    btn.classList.add('active');
                    importPlatform = btn.dataset.platform;
                });
            });
        }

        // 导入提交
        if (domCache.importSubmit) {
            domCache.importSubmit.addEventListener('click', () => {
                const url = domCache.importUrl.value.trim();
                if (!url) {
                    alert('请输入歌单链接或ID');
                    return;
                }
                if (!importPlatform) {
                    alert('请先选择平台');
                    return;
                }
                importPlaylist(importPlatform, url);
            });
        }

        // 进度条点击跳转
        if (domCache.progress) {
            domCache.progress.addEventListener('click', (e) => {
                if (!audioElement || !audioElement.duration) return;
                const rect = domCache.progress.getBoundingClientRect();
                const percent = (e.clientX - rect.left) / rect.width;
                audioElement.currentTime = percent * audioElement.duration;
            });
        }

        // 加载播放模式
        loadPlayMode();
    }

    /**
     * 为音频元素设置事件监听
     * @param {HTMLAudioElement} audio - 音频元素
     */
    function setupAudioElementEvents(audio) {
        // 先移除可能存在的旧事件监听器（使用命名函数以便移除）
        const onEnded = () => {
            // 只检查当前 audioElement 的 ended 事件
            if (audio === audioElement) {
                console.log('[MusicPlayer] 曲目播放结束，准备播放下一曲');
                nextTrack();
            }
        };

        const onError = () => {
            if (audio === audioElement) {
                console.error('[MusicPlayer] 音频播放错误:', audio.error);
                // 防止无限递归：记录连续错误次数
                const errorCountKey = 'musicPlayerErrorCount';
                const errorCount = parseInt(sessionStorage.getItem(errorCountKey) || '0', 10);

                if (errorCount >= musicFiles.length - 1) {
                    sessionStorage.removeItem(errorCountKey);
                    isPlaying = false;
                    updatePlayerState();
                    console.error('[MusicPlayer] 所有可能的曲目都已播放失败，停止自动播放');
                    return;
                }

                sessionStorage.setItem(errorCountKey, String(errorCount + 1));
                console.log(`[MusicPlayer] 自动跳过到下一曲（连续错误：${errorCount + 1}）`);
                // 自动跳过到下一曲
                nextTrack();
            }
        };

        // 添加事件监听器
        audio.addEventListener('ended', onEnded);
        audio.addEventListener('error', onError);

        // 保存事件处理器引用，以便后续移除
        audio._musicPlayerHandlers = { onEnded, onError };
    }

    /**
     * 设置拖拽功能
     */
    function setupDraggable() {
        const player = domCache.player;
        if (!player) return;

        const header = player.querySelector('.music-player-header');
        if (!header) {
            return;
        }

        header.addEventListener('mousedown', (e) => {
            isDragging = true;
            dragOffsetX = e.clientX - player.getBoundingClientRect().left;
            dragOffsetY = e.clientY - player.getBoundingClientRect().top;
            player.style.cursor = 'grabbing';
        });

        document.addEventListener('mousemove', handleDragMove);

        const stopDragging = () => {
            isDragging = false;
            player.style.cursor = 'grab';
        };
        document.addEventListener('mouseup', stopDragging);
        
        // 保存引用以便清理
        domCache._stopDragging = stopDragging;
    }

    /**
     * 处理拖拽移动
     */
    function handleDragMove(e) {
        if (!isDragging) return;
        const player = domCache.player;
        if (!player) {
            isDragging = false;
            return;
        }

        const x = e.clientX - dragOffsetX;
        const y = e.clientY - dragOffsetY;

        // 限制在窗口范围内
        const maxX = window.innerWidth - player.offsetWidth;
        const maxY = window.innerHeight - player.offsetHeight;

        player.style.left = Math.max(0, Math.min(x, maxX)) + 'px';
        player.style.top = Math.max(0, Math.min(y, maxY)) + 'px';
    }

    /**
     * 更新播放器状态
     */
    function updatePlayerState() {
        updatePlayButton();
        updateCurrentTrackDisplay();
        updateTitleBar();
        updateLikeButton();
        updatePlaylistDisplay();
    }

    /**
     * 更新播放按钮
     */
    function updatePlayButton() {
        const playBtn = domCache.playBtn;
        if (playBtn) {
            playBtn.innerHTML = isPlaying ?
                '<i class="bi bi-pause-fill"></i>' :
                '<i class="bi bi-play-fill"></i>';
        }
    }

    /**
     * 更新当前曲目显示
     */
    function updateCurrentTrackDisplay() {
        const currentTrackElement = domCache.currentTrack;

        if (currentTrackElement && musicFiles.length > 0) {
            const fileName = musicFiles[currentTrack].split('/').pop();
            currentTrackElement.textContent = fileName;
        } else {
            currentTrackElement.textContent = '音乐';
        }
    }

    /**
     * 更新标题栏
     */
    function updateTitleBar() {
        const titleBar = domCache.titleBar;
        if (!titleBar) return;

        if (musicFiles.length > 0 && currentTrack >= 0) {
            const fileName = musicFiles[currentTrack].split('/').pop();
            const shortName = fileName.length > 15 ? fileName.substring(0, 15) + '...' : fileName;
            const escapedName = escapeHtml(shortName);
            titleBar.innerHTML = `<i class="bi ${isPlaying ? 'bi-music-note-beamed' : 'bi-music-note'} me-1"></i>${escapedName}`;
        } else {
            titleBar.innerHTML = '<i class="bi bi-music-note-beamed me-1"></i>音乐';
        }
    }

    /**
     * 设置音量
     * @param {number} volume - 音量 (0-1)
     */
    function setVolume(volume) {
        const newVolume = Math.max(0, Math.min(volume, 1));
        audioElement.volume = newVolume;
        preloadPool.forEach(audio => audio.volume = newVolume);  // 同步所有预加载播放器音量
        updateVolumeIcon();
        saveState();
    }

    /**
     * 更新音量图标
     */
    function updateVolumeIcon() {
        const volumeBtn = domCache.volumeBtn;
        if (!volumeBtn) return;

        const icon = volumeBtn.querySelector('i');
        const volume = audioElement.volume;

        if (volume === 0) {
            icon.className = 'bi bi-volume-mute';
        } else if (volume < 0.5) {
            icon.className = 'bi bi-volume-down';
        } else {
            icon.className = 'bi bi-volume-up';
        }
    }

    /**
     * 静音/恢复音量
     */
    function toggleMute() {
        const volumeBtn = domCache.volumeBtn;

        if (audioElement.volume > 0) {
            // 保存当前音量并静音
            volumeBtn.setAttribute('data-saved-volume', audioElement.volume);
            audioElement.volume = 0;
            preloadPool.forEach(audio => audio.volume = 0);  // 同步所有预加载播放器音量
        } else {
            // 恢复之前保存的音量，默认0.2
            const savedVolume = volumeBtn.getAttribute('data-saved-volume') || '0.2';
            const volume = parseFloat(savedVolume);
            setVolume(isNaN(volume) ? 0.2 : volume);
        }
        updateVolumeIcon();
        saveState();
    }



    /**
     * 保存播放器状态
     */
    function saveState() {
        try {
            const state = {
                currentTrack: currentTrack,
                isPlaying: isPlaying,
                currentTime: audioElement.currentTime,
                volume: audioElement.volume,
                // 只保存文件名而非完整路径，减少存储空间
                musicFiles: musicFiles.map(file => file.split('/').pop())
            };
            localStorage.setItem('musicPlayerState', JSON.stringify(state));
        } catch (error) {
            if (error.name === 'QuotaExceededError') {
                // 降级保存，不保存音乐列表
                const basicState = {
                    currentTrack: currentTrack,
                    isPlaying: isPlaying,
                    currentTime: audioElement.currentTime,
                    volume: audioElement.volume
                };
                localStorage.setItem('musicPlayerState', JSON.stringify(basicState));
            }
        }
    }

    /**
     * 恢复播放器状态
     */
    function restoreState() {
        try {
            const savedState = localStorage.getItem('musicPlayerState');
            if (savedState) {
                const state = JSON.parse(savedState);
                
                // 检查音乐文件列表是否匹配（使用集合比较，忽略顺序）
                const savedFilesMatch = state.musicFiles && 
                                      musicFiles.length > 0 && 
                                      state.musicFiles.length === musicFiles.length &&
                                      state.musicFiles.every(file => musicFiles.includes(file));
                
                if (savedFilesMatch) {
                    currentTrack = Math.min(state.currentTrack || 0, musicFiles.length - 1);
                    setVolume(state.volume || 0.2);
                    
                    // 恢复播放位置但不自动播放
                    if (state.currentTime > 0 && currentTrack >= 0 && currentTrack < musicFiles.length) {
                        const trackUrl = `/api/music/play/${encodeURIComponent(musicFiles[currentTrack])}`;
                        audioElement.src = trackUrl;
                        
                        audioElement.addEventListener('loadedmetadata', () => {
                            audioElement.currentTime = Math.min(state.currentTime, audioElement.duration - 0.1);
                            updatePlayerState();
                            
                            isPlaying = state.isPlaying || false;
                            updatePlayButton();
                        }, { once: true });
                    }
                }
            }
        } catch (error) {
            // 静默处理恢复失败
        }
    }

    /**
     * 获取当前播放时间
     * @returns {number} 当前时间
     */
    function getCurrentTime() {
        return audioElement ? audioElement.currentTime : 0;
    }

    /**
     * 获取是否正在播放
     * @returns {boolean} 播放状态
     */
    function getPlayStatus() {
        try {
            return isPlaying;
        } catch (error) {
            return false;
        }
    }

    /**
     * 获取当前音量
     * @returns {number} 音量值
     */
    function getVolume() {
        return audioElement ? audioElement.volume : 0.2;
    }

    /**
     * 播放音乐
     */
    async function play() {
        if (audioElement && audioElement.src) {
            audioElement.play().then(() => {
                isPlaying = true;
                updatePlayerState();
            }).catch(error => {
                // 静默处理播放失败
            });
        } else {
            await ensureMusicListLoaded();
            if (musicFiles.length > 0) {
                playTrack(0);
            }
        }
    }

    /**
     * HTML转义（使用Core模块，提供后备实现）
     * @param {string} text - 原始文本
     * @returns {string} 转义文本
     */
    function escapeHtml(text) {
        if (window.Core && window.Core.escapeHtml) {
            return window.Core.escapeHtml(text);
        }
        // 后备实现
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    /**
     * 清理资源
     */
    function destroy() {
        if (domCache._stopDragging) {
            document.removeEventListener('mouseup', domCache._stopDragging);
        }
        document.removeEventListener('mousemove', handleDragMove);

        // 清理主播放器的事件监听器
        if (audioElement && audioElement._musicPlayerHandlers) {
            const handlers = audioElement._musicPlayerHandlers;
            if (handlers.onEnded) {
                audioElement.removeEventListener('ended', handlers.onEnded);
            }
            if (handlers.onError) {
                audioElement.removeEventListener('error', handlers.onError);
            }
            delete audioElement._musicPlayerHandlers;
        }

        // 移除 waiting 和 playing 事件监听器
        if (audioElement) {
            if (waitingHandler) {
                audioElement.removeEventListener('waiting', waitingHandler);
            }
            if (playingHandler) {
                audioElement.removeEventListener('playing', playingHandler);
            }
        }

        audioElement = null;
        preloadPool = null;
        waitingHandler = null;
        playingHandler = null;
    }

    // 暴露公共API
    window.MusicPlayer = {
        init: init,
        playTrack: playTrack,
        togglePlay: togglePlay,
        nextTrack: nextTrack,
        prevTrack: prevTrack,
        setVolume: setVolume,
        toggleMute: toggleMute,
        saveState: saveState,
        getCurrentTime: getCurrentTime,
        getPlayStatus: getPlayStatus,
        getVolume: getVolume,
        play: play,
        destroy: destroy,
        // 新增API
        togglePlaylistPanel: togglePlaylistPanel,
        togglePlayMode: togglePlayMode,
        toggleFavorite: toggleFavorite,
        importPlaylist: importPlaylist,
        getPlayMode: () => playMode,
        getFavoriteSongs: () => [...favoriteSongs],
        getCurrentTrack: () => musicFiles[currentTrack] || null,
        getPlaylist: () => [...musicFiles]
    };

    // DOM 加载完成后自动初始化
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
