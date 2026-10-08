const sessionList = document.getElementById('session-list');
const chatFeed = document.getElementById('chat-feed');
const chatInput = document.getElementById('chat-input');
const sendBtn = document.getElementById('send-btn');
const newChatBtn = document.getElementById('new-chat-btn');
const currentSessionTitle = document.getElementById('current-session-title');
const themeToggleBtn = document.getElementById('theme-toggle');

let currentSessionId = null;
let ws = null;

// Elegant Theme Logic
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

// Auto-resize textarea
chatInput.addEventListener('input', function() {
    this.style.height = 'auto';
    this.style.height = (this.scrollHeight) + 'px';
});

async function loadSessions() {
    try {
        const res = await fetch('/api/sessions');
        const sessions = await res.json();
        
        sessionList.innerHTML = '';
        sessions.forEach(session => {
            const btn = document.createElement('button');
            const isActive = session.id === currentSessionId;
            btn.className = `w-full text-left px-3 py-2.5 rounded-lg text-sm truncate transition-all mb-1 
                ${isActive 
                    ? 'bg-white dark:bg-zinc-800 text-zinc-900 dark:text-zinc-100 font-medium shadow-sm border border-zinc-200 dark:border-zinc-700' 
                    : 'text-zinc-600 dark:text-zinc-400 hover:bg-zinc-200/50 dark:hover:bg-zinc-800/50 border border-transparent'}`;
            btn.innerText = session.title;
            btn.onclick = () => loadChat(session.id, session.title);
            sessionList.appendChild(btn);
        });
    } catch (e) {
        console.error("Failed to load sessions", e);
    }
}

async function createSession() {
    const res = await fetch('/api/sessions', { method: 'POST' });
    const data = await res.json();
    await loadSessions();
    loadChat(data.id, 'New Arc');
}

async function loadChat(sessionId, title) {
    currentSessionId = sessionId;
    currentSessionTitle.innerText = title;
    
    await loadSessions(); // refresh active state
    
    const res = await fetch(`/api/sessions/${sessionId}`);
    const messages = await res.json();
    
    chatFeed.innerHTML = ''; 
    
    if (messages.length === 0) {
        chatFeed.innerHTML = `
            <div class="m-auto flex flex-col items-center justify-center text-zinc-400 dark:text-zinc-600">
                <div class="text-3xl mb-3 font-light">( ˘ ▽ ˘ )</div>
                <p class="text-sm font-medium tracking-wide">Awaiting command, Senpai...</p>
            </div>
        `;
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
                toolBlockDiv.querySelector('.tool-status').innerText = 'Executed successfully';
                toolBlockDiv.querySelector('.tool-status').classList.replace('text-zinc-400', 'text-teal-600');
                toolBlockDiv.querySelector('.tool-status').classList.replace('dark:text-zinc-500', 'dark:text-teal-400');
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
    wrapper.className = `flex w-full max-w-4xl mx-auto ${isUser ? 'justify-end' : 'justify-start'}`;
    
    const bubble = document.createElement('div');
    
    // Extremely aesthetic, refined flat styling
    if (isUser) {
        bubble.className = 'max-w-[85%] bg-zinc-100 dark:bg-zinc-800 text-zinc-900 dark:text-zinc-100 px-5 py-3.5 rounded-2xl rounded-tr-sm text-[15px] leading-relaxed shadow-sm border border-zinc-200/50 dark:border-zinc-700/50';
    } else {
        // Kiko's message floats cleanly without a background box, purely typography driven
        bubble.className = 'max-w-[90%] text-zinc-800 dark:text-zinc-200 px-2 py-2 text-[15px] leading-relaxed';
    }
    
    if (!isUser) {
        const header = document.createElement('div');
        header.className = 'flex items-center gap-2 mb-2';
        header.innerHTML = `
            <div class="w-1.5 h-1.5 rounded-full bg-teal-500"></div>
            <span class="font-semibold text-[11px] text-zinc-500 dark:text-zinc-400 tracking-widest uppercase">Kiko</span>
        `;
        bubble.appendChild(header);
    }
    
    const content = document.createElement('div');
    content.className = 'prose whitespace-pre-wrap';
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
    wrapper.className = 'flex w-full max-w-4xl mx-auto justify-start my-2';
    
    const block = document.createElement('div');
    // Elegant, flat execution block with monospace font
    block.className = 'bg-zinc-50 dark:bg-zinc-900/50 border border-zinc-200 dark:border-zinc-800 rounded-xl p-3 font-mono text-[11px] text-zinc-600 dark:text-zinc-400 flex flex-col gap-1.5 ml-2';
    block.innerHTML = `
        <div class="flex items-center gap-2">
            <svg class="w-3.5 h-3.5 text-teal-500 animate-spin" fill="none" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"></path></svg>
            <span class="font-medium text-zinc-800 dark:text-zinc-200">os.execute('${toolName}')</span>
        </div>
        <div class="tool-status text-zinc-400 dark:text-zinc-500 ml-5.5">Running native hook...</div>
    `;
    
    wrapper.appendChild(block);
    chatFeed.appendChild(wrapper);
    return block;
}

function scrollToBottom() {
    chatFeed.scrollTop = chatFeed.scrollHeight;
}

function sendMessage() {
    const text = chatInput.value.trim();
    if (!text || !ws || !currentSessionId) return;
    
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

// Init
loadSessions();
