const sessionList = document.getElementById('session-list');
const chatFeed = document.getElementById('chat-feed');
const chatInput = document.getElementById('chat-input');
const sendBtn = document.getElementById('send-btn');
const newChatBtn = document.getElementById('new-chat-btn');
const currentSessionTitle = document.getElementById('current-session-title');
const themeToggleBtn = document.getElementById('theme-toggle');

let currentSessionId = null;
let ws = null;
let isGenerating = false;

function setInputState(disabled) {
    isGenerating = disabled;
    chatInput.disabled = disabled;
    sendBtn.disabled = disabled;
    if (disabled) {
        chatInput.classList.add('opacity-50', 'cursor-not-allowed');
        sendBtn.classList.add('opacity-50', 'cursor-not-allowed');
    } else {
        chatInput.classList.remove('opacity-50', 'cursor-not-allowed');
        sendBtn.classList.remove('opacity-50', 'cursor-not-allowed');
        chatInput.focus();
    }
}

function toggleTheme() {
    if (document.documentElement.classList.contains('dark')) {
        document.documentElement.classList.remove('dark');
        localStorage.theme = 'light';
    } else {
        document.documentElement.classList.add('dark');
        localStorage.theme = 'dark';
    }
}
themeToggleBtn.onclick = toggleTheme;

chatInput.addEventListener('input', function () {
    this.style.height = 'auto';
    this.style.height = (this.scrollHeight) + 'px';
});

const emptyStateHTML = `
    <div class="m-auto flex flex-col items-center justify-center h-full">
        <div class="px-10 py-6 border-wavy-bottom flex flex-col items-center">
            <div class="text-[54px] mb-4 font-light text-cozy-accent opacity-90">🌱</div>
            <p class="text-[19px] font-serif italic text-cozy-text dark:text-cozy-darkText">What's on your mind?</p>
        </div>
    </div>
`;

async function loadSessions() {
    try {
        const res = await fetch('/api/sessions');
        const sessions = await res.json();

        sessionList.innerHTML = '';
        sessions.forEach(session => {
            const container = document.createElement('div');
            const isActive = session.id === currentSessionId;

            // Using dashed border for active state
            container.className = `group flex items-center justify-between w-full px-4 py-3 rounded-[16px] text-[14.5px] font-medium transition-colors cursor-pointer border-2
                ${isActive
                    ? 'bg-white dark:bg-cozy-darkBubble text-cozy-text dark:text-cozy-darkText border-dashed border-cozy-terracotta/40 dark:border-cozy-terracotta/30 shadow-sm'
                    : 'border-transparent text-cozy-muted hover:bg-white/50 dark:hover:bg-cozy-darkBubble/50 hover:text-cozy-text dark:hover:text-cozy-darkText'}`;

            const titleSpan = document.createElement('span');
            titleSpan.className = 'truncate flex-1';
            titleSpan.innerText = session.title;
            titleSpan.onclick = () => loadChat(session.id, session.title);

            // Delete button - Terracotta color on hover
            const deleteBtn = document.createElement('button');
            deleteBtn.className = `p-1 opacity-0 group-hover:opacity-100 transition-opacity hover:text-cozy-terracotta text-cozy-muted`;
            deleteBtn.innerHTML = `<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path></svg>`;
            deleteBtn.onclick = (e) => {
                e.stopPropagation();
                deleteSession(session.id);
            };

            container.appendChild(titleSpan);
            container.appendChild(deleteBtn);
            sessionList.appendChild(container);
        });
    } catch (e) {
        console.error("Failed to load sessions", e);
    }
}

const confirmModal = document.getElementById('confirm-modal');
const modalConfirm = document.getElementById('modal-confirm');
const modalCancel = document.getElementById('modal-cancel');
const modalInner = confirmModal.querySelector('div');

function showConfirmModal(onConfirm) {
    confirmModal.classList.remove('hidden');
    // small delay to allow display block to apply before animating opacity
    setTimeout(() => {
        confirmModal.classList.remove('opacity-0');
        modalInner.classList.remove('scale-95');
    }, 10);

    modalCancel.onclick = () => {
        hideConfirmModal();
    };

    modalConfirm.onclick = () => {
        hideConfirmModal();
        onConfirm();
    };
}

function hideConfirmModal() {
    confirmModal.classList.add('opacity-0');
    modalInner.classList.add('scale-95');
    setTimeout(() => {
        confirmModal.classList.add('hidden');
    }, 300);
}

async function deleteSession(id) {
    showConfirmModal(async () => {
        await fetch(`/api/sessions/${id}`, { method: 'DELETE' });

        if (currentSessionId === id) {
            currentSessionId = null;
            currentSessionTitle.innerText = "";
            chatFeed.innerHTML = emptyStateHTML;
            if (ws) ws.close();
        }

        await loadSessions();
    });
}

async function createSession() {
    const res = await fetch('/api/sessions', { method: 'POST' });
    const data = await res.json();
    await loadSessions();
    loadChat(data.id, 'New Chat');
}

async function loadChat(sessionId, title) {
    currentSessionId = sessionId;
    currentSessionTitle.innerText = title;

    await loadSessions();

    const res = await fetch(`/api/sessions/${sessionId}`);
    const messages = await res.json();

    chatFeed.innerHTML = '';

    if (messages.length === 0) {
        chatFeed.innerHTML = emptyStateHTML;
    } else {
        messages.forEach(msg => {
            if (msg.role === 'tool_execution') {
                const block = appendToolExecution(msg.content);
                const statusSpan = block.querySelector('.tool-status');
                statusSpan.innerHTML = 'done <span class="text-[14px]">✦</span>';
                statusSpan.classList.replace('text-cozy-muted', 'text-cozy-terracotta');
            } else {
                appendMessage(msg.role, msg.content);
                const block = chatFeed.lastElementChild;
                if (msg.role === 'assistant') parseWidgetsAndMarkdown(block);
            }
        });
        scrollToBottom();
    }

    connectWebSocket(sessionId);
}

function connectWebSocket(sessionId) {
    if (ws) ws.close();
    ws = new WebSocket(`ws://${window.location.host}/ws/${sessionId}`);

    let currentBotMessageDiv = null;
    let toolBlockDiv = null;
    let statusBlockDiv = null;

    ws.onmessage = (event) => {
        const data = JSON.parse(event.data);

        if (data.type === 'tool_execution') {
            if (data.status === 'running') {
                toolBlockDiv = appendToolExecution(data.tool, data.args);
            } else if (data.status === 'completed' && toolBlockDiv) {
                const statusSpan = toolBlockDiv.querySelector('.tool-status');
                statusSpan.innerHTML = 'done <span class="text-[14px]">✦</span>';
                statusSpan.classList.replace('text-cozy-muted', 'text-cozy-terracotta');
                toolBlockDiv = null; // Clear it so it doesn't get messed up later
            }
            scrollToBottom();
        } else if (data.type === 'status') {
            if (data.status === 'running') {
                statusBlockDiv = appendStatusMessage(data.message);
            } else if (data.status === 'completed' && statusBlockDiv) {
                statusBlockDiv.parentElement.remove();
                statusBlockDiv = null;
            }
            scrollToBottom();
        } else if (data.type === 'token') {
            if (!currentBotMessageDiv) {
                currentBotMessageDiv = createMessageDiv('assistant');
                currentBotMessageDiv.dataset.rawText = '';
                chatFeed.appendChild(currentBotMessageDiv);
            }
            currentBotMessageDiv.dataset.rawText += data.content;
            
            updateEmpathyEngine(currentBotMessageDiv, currentBotMessageDiv.dataset.rawText);
            parseWidgetsAndMarkdown(currentBotMessageDiv);
            
            scrollToBottom();
        } else if (data.type === 'done') {
            currentBotMessageDiv = null;
            setInputState(false);
        }
    };
}

function createMessageDiv(role) {
    const isUser = role === 'user';
    const wrapper = document.createElement('div');
    wrapper.className = `w-full max-w-3xl mx-auto flex mb-8 ${isUser ? 'justify-end' : 'justify-start'} relative z-10`;

    const bubble = document.createElement('div');

    if (isUser) {
        bubble.className = 'max-w-[75%] bg-white dark:bg-cozy-darkBubble border-2 border-cozy-border dark:border-cozy-darkBorder text-cozy-text dark:text-cozy-darkText px-6 py-4 rounded-[28px] rounded-br-[8px] text-[15.5px] leading-relaxed shadow-sm font-medium';
    } else {
        bubble.className = 'w-full flex gap-4 text-cozy-text dark:text-cozy-darkText text-[15.5px] leading-relaxed font-medium relative';

        const avatar = document.createElement('div');
        avatar.className = 'kiko-avatar w-10 h-10 rounded-[16px] bg-cozy-accent flex items-center justify-center shrink-0 mt-0.5 text-white shadow-sm relative transition-colors duration-500';
        avatar.innerHTML = `
            <span class="avatar-icon text-[16px] animate-pulse font-sans">❀</span>
            <span class="absolute -bottom-1 -right-1 w-3.5 h-3.5 bg-cozy-terracotta border-2 border-cozy-bg dark:border-cozy-darkBg rounded-full"></span>
        `;
        bubble.appendChild(avatar);
    }

    const content = document.createElement('div');
    content.className = 'prose flex-1 pt-1';
    bubble.appendChild(content);

    wrapper.appendChild(bubble);
    return wrapper;
}

function appendMessage(role, text) {
    const emptyState = chatFeed.querySelector('.m-auto');
    if (emptyState) emptyState.remove();

    const wrapper = createMessageDiv(role);
    wrapper.dataset.rawText = text;
    
    if (role === 'assistant') {
        updateEmpathyEngine(wrapper, text);
        parseWidgetsAndMarkdown(wrapper);
    } else {
        wrapper.querySelector('.prose').innerText = text;
    }
    chatFeed.appendChild(wrapper);
}

function updateEmpathyEngine(wrapper, text) {
    const icon = wrapper.querySelector('.avatar-icon');
    const avatar = wrapper.querySelector('.kiko-avatar');
    if (!icon || !avatar) return;

    if (text.includes('(>_<)') || text.includes('⚠️') || text.includes('error')) {
        icon.innerText = '>_<';
        icon.className = 'avatar-icon text-[12px] font-bold tracking-tighter';
        avatar.classList.remove('bg-cozy-accent');
        avatar.classList.add('bg-cozy-terracotta');
    } else if (text.includes('(๑>ᴗ<๑)') || text.includes('Yay') || text.includes('hihi') || text.includes('❤️') || text.includes('✨')) {
        icon.innerText = '^‿^';
        icon.className = 'avatar-icon text-[14px] font-bold tracking-tighter';
        avatar.classList.remove('bg-cozy-terracotta');
        avatar.classList.add('bg-cozy-accent');
    } else if (text.includes('?')) {
        icon.innerText = 'O_o';
        icon.className = 'avatar-icon text-[12px] font-bold tracking-tighter';
        avatar.classList.remove('bg-cozy-terracotta');
        avatar.classList.add('bg-cozy-accent');
    } else {
        icon.innerText = '❀';
        icon.className = 'avatar-icon text-[16px] animate-pulse font-sans';
        avatar.classList.remove('bg-cozy-terracotta');
        avatar.classList.add('bg-cozy-accent');
    }
}

function parseWidgetsAndMarkdown(wrapper) {
    const prose = wrapper.querySelector('.prose');
    if (!prose) return;

    let text = wrapper.dataset.rawText || '';
    const widgetRegex = /\[WIDGET:\s*([^\]]+)\]/g;
    let match;
    let widgetHTML = '';

    while ((match = widgetRegex.exec(text)) !== null) {
        const payload = match[1].split('|').map(s => s.trim());
        const type = payload[0].toUpperCase();

        if (type === 'WEATHER') {
            const city = payload[1] || 'Unknown';
            const temp = payload[2] || '--';
            const condition = payload[3] || 'Clear';
            const emoji = condition.toLowerCase().includes('cloud') ? '⛅' : (condition.toLowerCase().includes('rain') ? '🌧️' : '☀️');
            
            widgetHTML += `
                <div class="not-prose mt-4 mb-2 bg-[#F9F8F6] dark:bg-[#222222] border border-[#E5E2DB] dark:border-[#333333] rounded-[20px] p-4 inline-flex items-center shadow-sm">
                    <div class="w-16 flex items-center justify-center text-[42px] leading-none shrink-0">
                        ${emoji}
                    </div>
                    <div class="flex flex-col border-l border-[#E5E2DB] dark:border-[#383838] pl-5 pr-2 py-1 ml-2">
                        <div class="text-[10px] font-bold text-cozy-muted uppercase tracking-widest mb-1.5">${city}</div>
                        <div class="text-[26px] font-black text-cozy-text dark:text-cozy-darkText tracking-tighter leading-none">${temp}</div>
                        <div class="text-[13px] font-medium text-cozy-muted mt-1.5 capitalize">${condition}</div>
                    </div>
                </div>
            `;
        } else if (type === 'SPOTIFY') {
            const song = payload[1] || 'Unknown Song';
            const artist = payload[2] || 'Unknown Artist';
            
            widgetHTML += `
                <div class="not-prose mt-4 mb-2 bg-[#F9F8F6] dark:bg-[#222222] border border-[#E5E2DB] dark:border-[#333333] rounded-[20px] p-4 pr-10 inline-flex items-center gap-4 relative overflow-hidden shadow-sm">
                    <div class="absolute left-0 top-0 bottom-0 w-1.5 bg-[#1DB954]"></div>
                    <div class="w-12 h-12 rounded-full bg-[#1DB954] text-[#F9F8F6] flex items-center justify-center text-2xl shadow-md ml-3 shrink-0">
                        <span>♪</span>
                    </div>
                    <div class="flex flex-col pl-2">
                        <div class="text-[10px] font-bold text-[#1DB954] uppercase tracking-widest mb-1.5 flex items-center gap-1.5">
                            <span class="w-1.5 h-1.5 rounded-full bg-[#1DB954]"></span> NOW PLAYING
                        </div>
                        <div class="text-[18px] font-black text-cozy-text dark:text-cozy-darkText tracking-tight leading-none mb-1">${song}</div>
                        <div class="text-[13px] font-medium text-cozy-muted">${artist}</div>
                    </div>
                </div>
            `;
        } else if (type === 'SYSTEM') {
            const cpu = payload[1] || 'CPU: --';
            const gpu = payload[2] || 'GPU: --';
            const ram = payload[3] || 'RAM: --';
            
            widgetHTML += `
                <div class="not-prose mt-4 mb-2 bg-[#F9F8F6] dark:bg-[#222222] border border-[#E5E2DB] dark:border-[#333333] rounded-[20px] p-4 inline-flex items-center shadow-sm">
                    <div class="w-16 flex items-center justify-center text-[36px] leading-none shrink-0">
                        🖥️
                    </div>
                    <div class="flex flex-col border-l border-[#E5E2DB] dark:border-[#383838] pl-5 pr-4 py-1 ml-2">
                        <div class="text-[10px] font-bold text-cozy-muted uppercase tracking-widest mb-1.5">SYSTEM STATUS</div>
                        <div class="flex items-center gap-3 text-[13.5px] font-black text-cozy-text dark:text-cozy-darkText tracking-tight">
                            <span>${cpu}</span>
                            <span class="text-[#E5E2DB] dark:text-[#383838]">|</span>
                            <span>${gpu}</span>
                            <span class="text-[#E5E2DB] dark:text-[#383838]">|</span>
                            <span>${ram}</span>
                        </div>
                    </div>
                </div>
            `;
        }
    }

    // Strip complete widget tags from text
    const cleanText = text.replace(/\[WIDGET:[^\]]+\]/g, '');
    
    // Configure marked to use line breaks and smartypants
    marked.setOptions({
        breaks: true,
        gfm: true,
    });
    
    const parsedHTML = marked.parse(cleanText);
    prose.innerHTML = parsedHTML + widgetHTML;
}

function appendToolExecution(toolData, args) {
    const emptyState = chatFeed.querySelector('.m-auto');
    if (emptyState) emptyState.remove();

    let toolName = typeof toolData === 'string' ? toolData : toolData.name;
    let toolArgs = args || (typeof toolData === 'object' ? toolData.args : {});

    // For backwards compatibility with old SQLite rows where content is just "perform_web_search"
    if (typeof toolData === 'string' && toolData.startsWith('{')) {
        try {
            const parsed = JSON.parse(toolData);
            toolName = parsed.name;
            toolArgs = parsed.args;
        } catch (e) {
            // it's just a raw string
        }
    }

    const wrapper = document.createElement('div');
    wrapper.className = 'w-full max-w-3xl mx-auto flex mb-6 justify-start pl-[56px] relative z-10';

    const block = document.createElement('div');
    block.className = 'flex items-center gap-2 bg-white/70 dark:bg-cozy-darkBubble/70 backdrop-blur-sm border border-dashed border-cozy-border dark:border-cozy-darkBorder rounded-[16px] px-4 py-2 font-mono text-[12.5px] text-cozy-muted w-fit shadow-sm';
    
    let displayString = `Looking at <span class="font-semibold text-cozy-text dark:text-cozy-darkText">${toolName}</span>`;
    
    if (toolName === 'perform_web_search' && toolArgs.query) {
        displayString = `Performing web search for <span class="font-semibold text-cozy-text dark:text-cozy-darkText">"${toolArgs.query}"</span>`;
    } else if (toolName === 'get_current_weather' && toolArgs.city_name) {
        displayString = `Checking the weather in <span class="font-semibold text-cozy-text dark:text-cozy-darkText">${toolArgs.city_name}</span>`;
    } else if (toolName === 'spotify_search_and_play' && toolArgs.query) {
        displayString = `Playing <span class="font-semibold text-cozy-text dark:text-cozy-darkText">"${toolArgs.query}"</span> on Spotify`;
    }

    block.innerHTML = `
        <span>✐</span>
        <span>${displayString}</span>
        <span class="tool-status ml-1 text-cozy-muted">...</span>
    `;

    wrapper.appendChild(block);
    chatFeed.appendChild(wrapper);
    return block;
}

function appendStatusMessage(message) {
    const emptyState = chatFeed.querySelector('.m-auto');
    if (emptyState) emptyState.remove();

    const wrapper = document.createElement('div');
    wrapper.className = 'w-full max-w-3xl mx-auto flex mb-6 justify-start pl-[56px] relative z-10';

    const block = document.createElement('div');
    block.className = 'flex items-center gap-2 bg-white/70 dark:bg-cozy-darkBubble/70 backdrop-blur-sm border border-dashed border-cozy-border dark:border-cozy-darkBorder rounded-[16px] px-4 py-2 font-mono text-[12.5px] text-cozy-muted w-fit shadow-sm';
    
    const isWarning = message.includes('⚠️');
    block.innerHTML = `
        <span class="${isWarning ? 'text-cozy-terracotta' : 'animate-spin-slow origin-center'}">${isWarning ? '⚠️' : '❀'}</span>
        <span class="${isWarning ? 'text-cozy-terracotta font-semibold' : 'text-cozy-text dark:text-cozy-darkText font-semibold'}">${message}</span>
        <span class="tool-status ml-1 text-cozy-muted">...</span>
    `;

    wrapper.appendChild(block);
    chatFeed.appendChild(wrapper);
    return block;
}

function scrollToBottom() {
    chatFeed.scrollTop = chatFeed.scrollHeight;
}

async function sendMessage() {
    if (isGenerating) return;
    const text = chatInput.value.trim();
    if (!text) return;

    if (!currentSessionId) {
        const res = await fetch('/api/sessions', { method: 'POST' });
        const data = await res.json();
        await loadChat(data.id, 'New Chat');
        await loadSessions();

        let retries = 0;
        while (ws.readyState !== 1 && retries < 10) {
            await new Promise(r => setTimeout(r, 100));
            retries++;
        }
    } else if (!ws || ws.readyState !== 1) {
        return;
    }

    appendMessage('user', text);
    scrollToBottom();

    ws.send(text);

    chatInput.value = '';
    chatInput.style.height = 'auto';
    setInputState(true);
}

sendBtn.onclick = sendMessage;
chatInput.onkeydown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        sendMessage();
    }
};
newChatBtn.onclick = createSession;

loadSessions();
