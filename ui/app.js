const sessionList = document.getElementById('session-list');
const chatFeed = document.getElementById('chat-feed');
const chatInput = document.getElementById('chat-input');
const sendBtn = document.getElementById('send-btn');
const newChatBtn = document.getElementById('new-chat-btn');
const currentSessionTitle = document.getElementById('current-session-title');

let currentSessionId = null;
let ws = null;

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
            btn.className = `w-full text-left px-3 py-2 rounded-md text-sm truncate transition-colors mb-1 ${session.id === currentSessionId ? 'bg-gray-100 text-gray-900 font-medium' : 'text-gray-600 hover:bg-gray-50'}`;
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
    
    // Update active state in sidebar
    await loadSessions(); 
    
    // Fetch history
    const res = await fetch(`/api/sessions/${sessionId}`);
    const messages = await res.json();
    
    chatFeed.innerHTML = ''; // Clear feed
    
    if (messages.length === 0) {
        chatFeed.innerHTML = `
            <div class="h-full flex flex-col items-center justify-center text-gray-400">
                <div class="text-4xl mb-4">( ˘ ▽ ˘ )</div>
                <p>Awaiting your command, Senpai...</p>
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
                toolBlockDiv.querySelector('.tool-status').innerText = '✓ Completed';
                toolBlockDiv.querySelector('.tool-status').classList.replace('text-gray-400', 'text-teal-600');
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
    
    ws.onclose = () => {
        console.log("WebSocket disconnected.");
    };
}

function createMessageDiv(role) {
    const isUser = role === 'user';
    const wrapper = document.createElement('div');
    wrapper.className = `flex w-full ${isUser ? 'justify-end' : 'justify-start'}`;
    
    const bubble = document.createElement('div');
    // Muted teal/mint accent for user, crisp white for assistant
    bubble.className = `max-w-[80%] rounded-2xl px-5 py-3 ${isUser ? 'bg-teal-50 border border-teal-100 text-gray-800 rounded-br-none' : 'bg-white border border-gray-100 text-gray-700 rounded-bl-none shadow-sm'}`;
    
    if (!isUser) {
        const header = document.createElement('div');
        header.className = 'font-semibold text-[10px] text-gray-400 mb-1 tracking-widest uppercase';
        header.innerText = 'KIKO SYSTEM';
        bubble.appendChild(header);
    }
    
    const content = document.createElement('div');
    content.className = 'prose text-sm leading-relaxed whitespace-pre-wrap';
    bubble.appendChild(content);
    
    wrapper.appendChild(bubble);
    return wrapper;
}

function appendMessage(role, text) {
    const emptyState = chatFeed.querySelector('.h-full.flex');
    if (emptyState) emptyState.remove();
    
    const wrapper = createMessageDiv(role);
    wrapper.querySelector('.prose').innerText = text;
    chatFeed.appendChild(wrapper);
}

function appendToolExecution(toolName) {
    const emptyState = chatFeed.querySelector('.h-full.flex');
    if (emptyState) emptyState.remove();

    const wrapper = document.createElement('div');
    wrapper.className = 'flex w-full justify-start';
    
    const block = document.createElement('div');
    block.className = 'max-w-[80%] bg-gray-50 border border-gray-200 rounded-lg p-3 font-mono text-xs text-gray-600 flex flex-col gap-2 shadow-sm';
    block.innerHTML = `
        <div class="flex items-center gap-2">
            <svg class="w-3 h-3 text-teal-500 animate-spin" fill="none" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"></path></svg>
            <span class="font-semibold text-gray-800">> OS_HOOK: ${toolName}</span>
        </div>
        <div class="tool-status text-gray-400 ml-5">Executing native function...</div>
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
