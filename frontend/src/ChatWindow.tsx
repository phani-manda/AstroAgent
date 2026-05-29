import { useRef, useEffect, useState, KeyboardEvent } from 'react';
import { ChatMessage, resetSession } from './api';

interface ChatWindowProps {
  messages: ChatMessage[];
  streamingText: string;
  toolActivity: { tool: string; status: 'active' | 'done' } | null;
  error: string | null;
  onClearError: () => void;
  onRetry: () => void;
  sessionId: string | null;
  onNewSession: () => void;
  onSendMessage: (content: string) => void;
  loading: boolean;
  userName?: string;
}

const SUGGESTIONS = [
  "What does my rising sign reveal?",
  "What energy surrounds me today?",
  "Which houses are most active?",
];

const TOOL_LABELS: Record<string, string> = {
  geocode_place: 'Locating your birthplace\u2026',
  compute_birth_chart: 'Computing birth chart\u2026',
  get_daily_transits: 'Fetching transits\u2026',
  knowledge_lookup: 'Consulting the stars\u2026',
};

function renderMarkdown(text: string): string {
  return text
    // Headers
    .replace(/^### (.+)$/gm, '<h3>$1</h3>')
    .replace(/^## (.+)$/gm, '<h2>$1</h2>')
    .replace(/^# (.+)$/gm, '<h1>$1</h1>')
    // Bold & italic
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/\*(.+?)\*/g, '<em>$1</em>')
    // Horizontal rules
    .replace(/^---$/gm, '<hr/>')
    // Tables
    .replace(/^\|(.*)\|$/gm, (match: string) => {
      const cells = match.split('|').filter(c => c.trim()).map((c: string) => `<td>${c.trim()}</td>`).join('');
      return cells ? `<tr>${cells}</tr>` : '';
    })
    // List items
    .replace(/^- (.+)$/gm, '<li>$1</li>')
    // Newlines
    .replace(/\n\n/g, '<br/><br/>')
    .replace(/\n/g, '<br/>');
}

export default function ChatWindow({
  messages,
  streamingText,
  toolActivity,
  error,
  onClearError,
  onRetry,
  sessionId,
  onNewSession,
  onSendMessage,
  loading,
  userName,
}: ChatWindowProps) {
  const bottomRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const [inputValue, setInputValue] = useState('');

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, streamingText, toolActivity, error]);

  async function handleNewSession() {
    if (sessionId) {
      await resetSession(sessionId);
    }
    setInputValue('');
    onNewSession();
  }

  function handleSend() {
    const trimmed = inputValue.trim();
    if (!trimmed || loading) return;
    onSendMessage(trimmed);
    setInputValue('');
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
    }
  }

  function handleKeyDown(e: KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  }

  function handleInputChange(e: React.ChangeEvent<HTMLTextAreaElement>) {
    setInputValue(e.target.value);
    const ta = e.target;
    ta.style.height = 'auto';
    ta.style.height = Math.min(ta.scrollHeight, 120) + 'px';
  }

  const showEmptyState = messages.length === 0 && !streamingText;

  return (
    <div className="flex flex-col h-full min-h-0">
      {/* Header */}
      <header className="flex items-center justify-between py-4 px-1 mx-4 border-b border-[var(--border-watermark)] mb-4 flex-shrink-0">
        <div>
          <h1 className="text-[1.4rem] font-display font-medium text-[var(--text-heading)] leading-tight">
            AstroAgent
          </h1>
          <p className="text-[0.8rem] font-body text-[var(--text-muted)] italic">Your AI Astrology Companion</p>
        </div>
        <button
          onClick={handleNewSession}
          className="px-3 py-1.5 rounded-lg text-[0.65rem] font-label uppercase tracking-[0.2em] text-[var(--text-muted)] border border-[var(--border-watermark)] hover:border-[var(--gold)] transition-colors duration-150"
        >
          New Session
        </button>
      </header>

      {/* Messages area */}
      <div className="flex-1 overflow-y-auto scrollbar-thin min-h-0 mb-4 px-4">
        {showEmptyState && (
          <div className="flex flex-col items-center justify-center py-12 text-center">
            <svg width="80" height="80" viewBox="0 0 80 80" className="mb-6 opacity-[0.06] max-sm:opacity-[0.04]" fill="var(--accent)">
              <path d="M40 8c-2 0-4 1-5 3l-10 20c-1 2-1 4 0 6l10 20c1 2 3 3 5 3s4-1 5-3l10-20c1-2 1-4 0-6L45 11c-1-2-3-3-5-3zm0 8a2 2 0 110 4 2 2 0 010-4zm-6 10a2 2 0 110 4 2 2 0 010-4zm12 0a2 2 0 110 4 2 2 0 010-4zm-6 8a2 2 0 110 4 2 2 0 010-4z" />
              <circle cx="28" cy="22" r="3" opacity="0.5" />
              <circle cx="52" cy="22" r="3" opacity="0.5" />
              <circle cx="40" cy="34" r="3" opacity="0.5" />
              <circle cx="28" cy="42" r="2" opacity="0.3" />
              <circle cx="52" cy="42" r="2" opacity="0.3" />
            </svg>
            <h2 className="text-[1.6rem] font-display font-medium text-[var(--text-heading)] mb-1">
              {userName ? `Namaste, ${userName}` : 'Namaste'}
            </h2>
            <p className="text-[1rem] font-body italic text-[var(--text-muted)] mb-6">Your chart is ready.</p>
            <div className="flex flex-wrap gap-2 justify-center max-w-md">
              {SUGGESTIONS.map((s, i) => (
                <button
                  key={i}
                  onClick={() => onSendMessage(s)}
                  disabled={loading}
                  className="px-4 py-2 rounded-full text-[0.9rem] font-body text-[var(--text-primary)] bg-[var(--input-bg)] border border-[var(--border-watermark)] hover:border-[var(--gold)] hover:bg-[var(--card-bg)] transition-all duration-150 disabled:opacity-40"
                >
                  {s}
                </button>
              ))}
            </div>
          </div>
        )}

        {messages.map((msg, i) => (
          <div
            key={i}
            className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'} mb-4 animate-fade-in`}
          >
            <div
              className={`max-w-[82%] px-4 py-3.5 text-[1rem] leading-[1.75] ${
                msg.role === 'user'
                  ? 'bg-[var(--user-bubble-bg)] border border-[var(--user-bubble-border)] rounded-[16px_4px_16px_16px] text-[var(--text-primary)]'
                  : 'bg-[var(--agent-bubble-bg)] border border-[var(--agent-bubble-border)] rounded-[4px_16px_16px_16px] text-[var(--text-primary)] font-body chart-response'
              }`}
            >
              {msg.role === 'assistant' ? (
                <div
                  className="chart-response"
                  dangerouslySetInnerHTML={{ __html: renderMarkdown(msg.content) }}
                />
              ) : (
                msg.content
              )}
            </div>
          </div>
        ))}

        {streamingText && (
          <div className="flex justify-start mb-4">
            <div className="max-w-[82%] px-4 py-3.5 bg-[var(--agent-bubble-bg)] border border-[var(--agent-bubble-border)] rounded-[4px_16px_16px_16px] text-[1rem] leading-[1.75] text-[var(--text-primary)] font-body chart-response">
              <div dangerouslySetInnerHTML={{ __html: renderMarkdown(streamingText) }} />
              <span className="inline-block w-[2px] h-[1.1em] bg-[var(--accent)] ml-0.5 align-middle animate-[blink_1s_step-end_infinite]" />
            </div>
          </div>
        )}

        {toolActivity && (
          <div className="flex justify-start mb-4 animate-fade-in">
            <div className="flex items-center gap-2.5 px-4 py-2 bg-[var(--tool-bg)] border border-dashed border-[var(--tool-border)] rounded-lg">
              <span className="text-base">🔭</span>
              <span className="text-[0.7rem] font-label uppercase tracking-[0.15em] text-[var(--text-muted)]">
                {toolActivity.status === 'active'
                  ? (TOOL_LABELS[toolActivity.tool] || `Running: ${toolActivity.tool}`)
                  : `${toolActivity.tool} — Done`}
              </span>
            </div>
          </div>
        )}

        {error && (
          <div className="flex justify-start mb-4">
            <div className="flex items-start gap-2 max-w-[80%] px-4 py-3 rounded-xl bg-[var(--user-bubble-bg)] border border-[var(--user-bubble-border)] text-[var(--accent)] text-[0.95rem]">
              <span className="text-lg flex-shrink-0">⚠</span>
              <div className="flex-1">
                <p>{error}</p>
                <button
                  onClick={() => { onClearError(); onRetry(); }}
                  className="mt-2 text-[0.85rem] text-[var(--accent)] underline underline-offset-2 hover:text-[var(--accent-soft)]"
                >
                  Retry
                </button>
              </div>
            </div>
          </div>
        )}

        <div ref={bottomRef} />
      </div>

      {/* Input bar */}
      <div className="flex-shrink-0 bg-[var(--input-bar-bg)] border-t border-[var(--input-bar-border)] py-3.5 px-4 transition-colors duration-300">
        <div className="relative">
          <textarea
            ref={textareaRef}
            value={inputValue}
            onChange={handleInputChange}
            onKeyDown={handleKeyDown}
            placeholder="Ask about your chart, transits, or the cosmos\u2026"
            disabled={loading}
            rows={1}
            className="w-full resize-none bg-[var(--input-bg)] border-[1.5px] border-transparent rounded-xl py-[11px] pr-12 pl-4 font-body text-[1rem] text-[var(--text-primary)] placeholder-[var(--text-muted)] focus:outline-none focus:border-[rgba(201,75,31,0.4)] focus:shadow-[0_0_0_3px_rgba(201,75,31,0.08)] transition-all duration-200 disabled:opacity-50 max-h-[120px]"
          />
          <button
            onClick={handleSend}
            disabled={loading || !inputValue.trim()}
            className="absolute right-2 top-1/2 -translate-y-1/2 w-8 h-8 flex items-center justify-center rounded-lg bg-[var(--accent)] text-white hover:bg-[var(--accent-soft)] disabled:opacity-35 disabled:cursor-not-allowed transition-colors duration-150"
          >
            <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
              <path d="M8 2v10M4 6l4-4 4 4" />
            </svg>
          </button>
        </div>
      </div>
    </div>
  );
}
