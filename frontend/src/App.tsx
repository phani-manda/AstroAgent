import { useState, useCallback, useEffect } from 'react';
import BirthForm from './BirthForm';
import ChatWindow from './ChatWindow';
import { ChatMessage, BirthInfo, connectChatStream, parseSSELine } from './api';

const THEME_KEY = 'astroagent-theme';

export default function App() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [streamingText, setStreamingText] = useState('');
  const [toolActivity, setToolActivity] = useState<{
    tool: string;
    status: 'active' | 'done';
  } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [lastBirthInfo, setLastBirthInfo] = useState<BirthInfo | null>(null);
  const [mobilePanelOpen, setMobilePanelOpen] = useState(false);
  const [dark, setDark] = useState(() => {
    const stored = localStorage.getItem(THEME_KEY);
    if (stored !== null) return stored === 'dark';
    return window.matchMedia('(prefers-color-scheme: dark)').matches;
  });

  useEffect(() => {
    document.documentElement.classList.toggle('dark', dark);
    localStorage.setItem(THEME_KEY, dark ? 'dark' : 'light');
  }, [dark]);

  const processStream = useCallback(
    async (stream: ReadableStream<Uint8Array>, sid: string) => {
      const reader = stream.getReader();
      const decoder = new TextDecoder();
      let buffer = '';
      setStreamingText('');
      setError(null);

      try {
        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split('\n');
          buffer = lines.pop() || '';

          for (const line of lines) {
            const event = parseSSELine(line);
            if (!event) continue;

            if (event.type === 'session') {
              setSessionId(event.session_id || sid);
            } else if (event.type === 'token') {
              setStreamingText((prev) => prev + (event.content || ''));
            } else if (event.type === 'tool_start') {
              setToolActivity({ tool: event.tool || '', status: 'active' });
            } else if (event.type === 'tool_end') {
              setToolActivity({ tool: event.tool || '', status: 'done' });
              setTimeout(() => setToolActivity(null), 1500);
            } else if (event.type === 'error') {
              setError(event.content || 'Something went wrong');
              setToolActivity(null);
            }
          }
        }
      } catch (err: unknown) {
        if ((err as Error)?.name !== 'AbortError') {
          setError('Connection lost. Please try again.');
        }
      } finally {
        reader.releaseLock();
        setLoading(false);

        setStreamingText((current) => {
          if (current) {
            const finalMsg: ChatMessage = { role: 'assistant', content: current };
            setMessages((prev) => [...prev, finalMsg]);
          }
          return '';
        });
        setToolActivity(null);
      }
    },
    []
  );

  const sendMessage = useCallback(
    async (content: string) => {
      if (loading) return;

      const userMsg: ChatMessage = { role: 'user', content };
      const newMessages = [...messages, userMsg];
      setMessages(newMessages);
      setLoading(true);

      try {
        const { stream, sessionId: sid } = connectChatStream(userMsg, sessionId);
        processStream(stream, sid);
      } catch {
        setError('Failed to connect. Is the backend running?');
        setLoading(false);
      }
    },
    [messages, sessionId, loading, processStream]
  );

  const handleBirthSubmit = useCallback(
    (info: BirthInfo) => {
      setLastBirthInfo(info);
      setMobilePanelOpen(false);
      const birthStr = `My birth: ${info.date} ${info.time} ${info.place}`;
      sendMessage(birthStr);
    },
    [sendMessage]
  );

  const handleClearError = useCallback(() => setError(null), []);
  const handleRetry = useCallback(() => {
    const lastMsg = messages[messages.length - 1];
    if (lastMsg && lastMsg.role === 'user') {
      sendMessage(lastMsg.content);
    }
  }, [messages, sendMessage]);
  const handleNewSession = useCallback(() => {
    setMessages([]);
    setStreamingText('');
    setToolActivity(null);
    setError(null);
    setSessionId(null);
    setLastBirthInfo(null);
  }, []);

  return (
    <div className="min-h-screen bg-[var(--page-bg)] flex flex-col transition-colors duration-300">
      {/* Navbar */}
      <nav className="h-14 bg-[var(--card-bg)] border-b border-[var(--border-subtle)] flex items-center justify-between px-5 flex-shrink-0 z-10 transition-colors duration-300">
        <div className="flex items-center gap-2.5">
          <svg width="22" height="22" viewBox="0 0 22 22" className="flex-shrink-0" fill="var(--accent)">
            <path d="M11 2c-1 0-2 .5-2.5 1.5L4 13c-.5 1-.5 2 0 3l4.5 9.5c.5 1 1.5 1.5 2.5 1.5s2-.5 2.5-1.5L18 16c.5-1 .5-2 0-3L13.5 3.5C13 2.5 12 2 11 2z" opacity="0.9" />
          </svg>
          <span className="font-display font-medium text-[1.05rem] text-[var(--text-heading)] tracking-tight">
            AstroAgent <span className="font-label text-[0.65rem] uppercase tracking-[0.2em] text-[var(--text-muted)] ml-1">by Aradhana</span>
          </span>
        </div>

        <div className="flex items-center gap-3">
          {/* Theme toggle */}
          <button
            onClick={() => setDark(!dark)}
            className="w-8 h-8 flex items-center justify-center rounded-lg border border-[var(--border-subtle)] hover:border-[var(--accent)] transition-all duration-200"
            aria-label="Toggle theme"
            title={dark ? 'Switch to light mode' : 'Switch to dark mode'}
          >
            {dark ? (
              <svg width="14" height="14" viewBox="0 0 14 14" fill="none" stroke="#D4A94B" strokeWidth="1.5" strokeLinecap="round">
                <circle cx="7" cy="7" r="3.5" />
                <path d="M7 1v1.5M7 11.5V13M1 7h1.5M11.5 7H13M2.5 2.5l1 1M10.5 10.5l1 1M2.5 11.5l1-1M10.5 3.5l1-1" />
              </svg>
            ) : (
              <svg width="14" height="14" viewBox="0 0 14 14" fill="none" stroke="#C94B1F" strokeWidth="1.5" strokeLinecap="round">
                <path d="M7 1C4.5 1 2.5 3.5 2.5 7s2 6 4.5 6c-.5-1-.5-2.5 0-4 1-2.5 3-4 5.5-4-.5-2-3-4-5.5-4z" />
              </svg>
            )}
          </button>

          <span className="text-[0.65rem] font-label uppercase tracking-[0.2em] text-[var(--text-muted)] hidden sm:block">
            ASTRO AGENT · BETA
          </span>

          {/* Mobile hamburger */}
          <button
            className="sm:hidden flex items-center justify-center w-8 h-8 rounded-lg hover:bg-[var(--input-bg)] transition-colors"
            onClick={() => setMobilePanelOpen(!mobilePanelOpen)}
            aria-label="Toggle birth form"
          >
            <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="var(--text-muted)" strokeWidth="1.5" strokeLinecap="round">
              <path d="M2 4h12M2 8h12M2 12h12" />
            </svg>
          </button>
        </div>
      </nav>

      {/* Main content */}
      <div className="flex-1 flex min-h-0">
        {/* Left panel — desktop sidebar */}
        <aside className="hidden sm:flex flex-col w-80 bg-[var(--card-bg)] border-r border-[var(--border-subtle)] flex-shrink-0 overflow-y-auto transition-colors duration-300">
          <BirthForm
            onSubmit={handleBirthSubmit}
            disabled={loading}
            collapsed={!!lastBirthInfo}
            onExpand={() => setLastBirthInfo(null)}
            summary={lastBirthInfo}
          />
        </aside>

        {/* Mobile panel overlay */}
        {mobilePanelOpen && (
          <div className="sm:hidden fixed inset-0 z-20">
            <div className="absolute inset-0 bg-[rgba(0,0,0,0.4)]" onClick={() => setMobilePanelOpen(false)} />
            <div className="absolute left-0 top-0 bottom-0 w-80 bg-[var(--card-bg)] shadow-lg overflow-y-auto animate-slide-up">
              <div className="flex justify-end p-3">
                <button
                  onClick={() => setMobilePanelOpen(false)}
                  className="w-7 h-7 flex items-center justify-center rounded-lg hover:bg-[var(--input-bg)] transition-colors"
                >
                  <svg width="14" height="14" viewBox="0 0 14 14" fill="none" stroke="var(--text-muted)" strokeWidth="1.5" strokeLinecap="round">
                    <path d="M2 2l10 10M12 2L2 12" />
                  </svg>
                </button>
              </div>
              <BirthForm
                onSubmit={handleBirthSubmit}
                disabled={loading}
              />
            </div>
          </div>
        )}

        {/* Chat area */}
        <main className="flex-1 min-w-0 flex flex-col min-h-0">
          <ChatWindow
            messages={messages}
            streamingText={streamingText}
            toolActivity={toolActivity}
            error={error}
            onClearError={handleClearError}
            onRetry={handleRetry}
            sessionId={sessionId}
            onNewSession={handleNewSession}
            onSendMessage={sendMessage}
            loading={loading}
          />
        </main>
      </div>
    </div>
  );
}
