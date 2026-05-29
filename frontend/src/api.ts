export interface ChatMessage {
  role: 'user' | 'assistant' | 'system';
  content: string;
  created_at?: string;
}

export interface BirthInfo {
  date: string;
  time: string;
  place: string;
}

export interface SSEEvent {
  type: 'session' | 'token' | 'tool_start' | 'tool_end' | 'error' | 'debug';
  session_id?: string;
  content?: string;
  tool?: string;
  result?: unknown;
  latency_ms?: number;
  intent?: string;
}

const API_BASE = '';

export async function fetchHealth(): Promise<boolean> {
  try {
    const res = await fetch(`${API_BASE}/health`);
    const data = await res.json();
    return data.status === 'ok';
  } catch {
    return false;
  }
}

export function connectChatStream(
  message: ChatMessage,
  sessionId: string | null
): { stream: ReadableStream<Uint8Array>; sessionId: string } {
  const params = new URLSearchParams();
  const body = JSON.stringify(message);
  params.set('body', body);
  if (sessionId) {
    params.set('session_id', sessionId);
  }
  // Generate localStorage-based session if none
  const storageKey = 'astroagent_session_id';
  let sid = sessionId || localStorage.getItem(storageKey);
  if (!sid) {
    sid = crypto.randomUUID();
    localStorage.setItem(storageKey, sid);
    params.set('session_id', sid);
  }
  const url = `${API_BASE}/chat/stream?${params.toString()}`;

  const controller = new AbortController();
  const promise = fetch(url, {
    signal: controller.signal,
    headers: { Accept: 'text/event-stream' },
  }).then((response) => {
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    if (!response.body) throw new Error('No response body');
    return response.body;
  });

  const stream = new ReadableStream<Uint8Array>({
    start(ctrl) {
      promise.then((body) => {
        const reader = body.getReader();
        function pump(): void {
          reader.read().then(({ done, value }) => {
            if (done) { ctrl.close(); return; }
            ctrl.enqueue(value);
            pump();
          }).catch(() => ctrl.close());
        }
        pump();
      }).catch((err) => ctrl.error(err));
    },
    cancel() { controller.abort(); },
  });

  return { stream, sessionId: sid || '' };
}

export async function resetSession(sessionId: string): Promise<void> {
  await fetch(`${API_BASE}/reset`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ session_id: sessionId }),
  });
  localStorage.removeItem('astroagent_session_id');
}

export function parseSSELine(line: string): SSEEvent | null {
  if (!line.startsWith('data: ')) return null;
  const payload = line.slice(6).trim();
  if (payload === '[DONE]') return { type: 'token', content: '' };
  try {
    return JSON.parse(payload) as SSEEvent;
  } catch {
    return null;
  }
}
