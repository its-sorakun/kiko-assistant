const sessionList = document.getElementById('session-list');
const chatFeed = document.getElementById('chat-feed');
const chatInput = document.getElementById('chat-input');
const sendBtn = document.getElementById('send-btn');
const newChatBtn = document.getElementById('new-chat-btn');
const currentSessionTitle = document.getElementById('current-session-title');
const themeToggleBtn = document.getElementById('theme-toggle');

let currentSessionId = null;
let ws = null;

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

chatInput.addEventListener('input', function() {
    this.style.height = 'auto';
    this.style.height = (this.scrollHeight) + 'px';
});

const emptyStateHTML = `
    <div class="m-auto flex flex-col items-center justify-center h-full">
        <div class="px-10 py-6 border-wavy-bottom flex flex-col items-center">
            <div class="text-[54px] mb-4 font-light text-cozy-accent opacity-90 animate-float-slow">🪴</div>
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

async function deleteSession(id) {
    if(!confirm("Erase this memory?")) return;
    
    await fetch(`/api/sessions/${id}`, { method: 'DELETE' });
    
    if (currentSessionId === id) {
        currentSessionId = null;
        currentSessionTitle.innerText = "";
        chatFeed.innerHTML = emptyStateHTML;
        if (ws) ws.close();
    }
    
    await loadSessions();
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
            appendMessage(msg.role, msg.content);
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
    
    ws.onmessage = (event) => {
        const data = JSON.parse(event.data);
        
        if (data.type === 'tool_execution') {
            if (data.status === 'running') {
                toolBlockDiv = appendToolExecution(data.tool);
            } else if (data.status === 'completed' && toolBlockDiv) {
                const statusSpan = toolBlockDiv.querySelector('.tool-status');
                statusSpan.innerHTML = 'done <span class="text-[14px]">✦</span>';
                statusSpan.classList.replace('text-cozy-muted', 'text-cozy-terracotta');
            }
            scrollToBottom();
        } else if (data.type === 'token') {
            if (!currentBotMessageDiv) {
                currentBotMessageDiv = createMessageDiv('assistant');
                chatFeed.appendChild(currentBotMessageDiv);
            }
            currentBotMessageDiv.querySelector('.prose').innerHTML += data.content;
            scrollToBottom();
        } else if (data.type === 'done') {
            currentBotMessageDiv = null;
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
        // Cozy Kiko Avatar with terracotta dot
        avatar.className = 'w-10 h-10 rounded-[16px] bg-cozy-accent flex items-center justify-center shrink-0 mt-0.5 text-white shadow-sm relative';
        avatar.innerHTML = `
            <span class="text-[16px] animate-pulse">❀</span>
            <span class="absolute -bottom-1 -right-1 w-3.5 h-3.5 bg-cozy-terracotta border-2 border-cozy-bg dark:border-cozy-darkBg rounded-full"></span>
        `;
        bubble.appendChild(avatar);
    }
    
    const content = document.createElement('div');
    content.className = 'prose whitespace-pre-wrap flex-1 pt-1';
    bubble.appendChild(content);
    
    wrapper.appendChild(bubble);
    return wrapper;
}

function appendMessage(role, text) {
    const emptyState = chatFeed.querySelector('.m-auto');
    if (emptyState) emptyState.remove();
    
    const wrapper = createMessageDiv(role);
    wrapper.querySelector('.prose').innerText = text;
    chatFeed.appendChild(wrapper);
}

function appendToolExecution(toolName) {
    const emptyState = chatFeed.querySelector('.m-auto');
    if (emptyState) emptyState.remove();

    const wrapper = document.createElement('div');
    wrapper.className = 'w-full max-w-3xl mx-auto flex mb-6 justify-start pl-[56px] relative z-10';
    
    const block = document.createElement('div');
    block.className = 'flex items-center gap-2 bg-white/70 dark:bg-cozy-darkBubble/70 backdrop-blur-sm border border-dashed border-cozy-border dark:border-cozy-darkBorder rounded-[16px] px-4 py-2 font-mono text-[12.5px] text-cozy-muted w-fit shadow-sm';
    block.innerHTML = `
        <span>✐</span>
        <span>Looking at <span class="font-semibold text-cozy-text dark:text-cozy-darkText">${toolName}</span></span>
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
