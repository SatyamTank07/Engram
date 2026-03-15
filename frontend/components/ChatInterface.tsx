'use client';

import { useState, useEffect, useRef, useMemo } from 'react';
import ReactMarkdown from 'react-markdown';
import toast from 'react-hot-toast';
import { Camera, Send, MessageSquare, Copy, Check, Bot } from 'lucide-react';
import { Message, getSessionMessages, sendMessageStream, validateImageFile } from '@/lib/api';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

interface ChatInterfaceProps {
  sessionId: string | null;
}

function relativeTime(dateStr: string): string {
  const now = Date.now();
  // Handle both UTC (from server, no timezone suffix) and ISO strings
  const normalized = dateStr.endsWith('Z') || dateStr.includes('+') ? dateStr : dateStr + 'Z';
  const then = new Date(normalized).getTime();
  const diff = Math.floor((now - then) / 1000);
  if (diff < 0 || diff < 60) return 'just now';
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
  return `${Math.floor(diff / 86400)}d ago`;
}

function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false);
  const handleCopy = async () => {
    await navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };
  return (
    <button
      onClick={handleCopy}
      className="p-1 rounded transition-colors focus-visible:ring-2"
      style={{ color: 'var(--muted-foreground)' }}
      aria-label="Copy message"
    >
      {copied ? <Check size={14} /> : <Copy size={14} />}
    </button>
  );
}

function CodeBlock({ children, className }: { children: React.ReactNode; className?: string }) {
  const match = /language-(\w+)/.exec(className || '');
  const lang = match ? match[1] : '';
  const code = String(children).replace(/\n$/, '');
  const [copied, setCopied] = useState(false);

  const handleCopy = async () => {
    await navigator.clipboard.writeText(code);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="rounded-lg overflow-hidden my-2" style={{ background: 'var(--code-block-bg)' }}>
      <div className="flex items-center justify-between px-3 py-1.5 text-xs" style={{ borderBottom: '1px solid var(--border)', color: 'var(--muted-foreground)' }}>
        <span>{lang || 'code'}</span>
        <button
          onClick={handleCopy}
          className="flex items-center gap-1 transition-colors hover:opacity-80 focus-visible:ring-2"
          aria-label="Copy code"
        >
          {copied ? <Check size={12} /> : <Copy size={12} />}
          {copied ? 'Copied' : 'Copy'}
        </button>
      </div>
      <pre className="p-3 overflow-x-auto text-sm" style={{ color: 'var(--code-block-text)' }}>
        <code>{children}</code>
      </pre>
    </div>
  );
}

export default function ChatInterface({ sessionId }: ChatInterfaceProps) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [attachedImage, setAttachedImage] = useState<File | null>(null);
  const [imageError, setImageError] = useState('');
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const imageInputRef = useRef<HTMLInputElement>(null);
  const isSendingRef = useRef(false);

  const previewUrl = useMemo(() => {
    return attachedImage ? URL.createObjectURL(attachedImage) : null;
  }, [attachedImage]);

  useEffect(() => {
    return () => { if (previewUrl) URL.revokeObjectURL(previewUrl); };
  }, [previewUrl]);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => { scrollToBottom(); }, [messages]);

  useEffect(() => {
    if (sessionId) { loadMessages(); } else { setMessages([]); }
  }, [sessionId]);

  const loadMessages = async () => {
    if (!sessionId) return;
    try {
      const data = await getSessionMessages(sessionId);
      if (!isSendingRef.current) setMessages(data);
    } catch {
      toast.error('Failed to load messages');
    }
  };

  const handleImageSelect = (file: File) => {
    setImageError('');
    try {
      validateImageFile(file);
      setAttachedImage(file);
    } catch (err: any) {
      setImageError(err.message);
    }
  };

  const handleSend = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim() || !sessionId || loading) return;

    const userMessage = input.trim();
    const imageFile = attachedImage;
    const localImageUrl = imageFile ? URL.createObjectURL(imageFile) : null;

    setInput('');
    setAttachedImage(null);
    setImageError('');
    setLoading(true);
    isSendingRef.current = true;

    const tempUserMessage: Message = {
      id: `temp-${Date.now()}`,
      session_id: sessionId,
      role: 'user',
      content: userMessage,
      image_url: localImageUrl,
      timestamp: new Date().toISOString(),
    };

    const streamingMsgId = `temp-${Date.now() + 1}`;
    const streamingMessage: Message = {
      id: streamingMsgId,
      session_id: sessionId,
      role: 'assistant',
      content: '',
      image_url: null,
      timestamp: new Date().toISOString(),
    };

    setMessages(prev => [...prev, tempUserMessage, streamingMessage]);

    try {
      await sendMessageStream(
        sessionId, userMessage, imageFile || undefined,
        (token: string) => {
          setMessages(prev =>
            prev.map(m => m.id === streamingMsgId ? { ...m, content: m.content + token } : m)
          );
        },
        (data) => {
          setMessages(prev => [
            ...prev.filter(m => m.id !== tempUserMessage.id && m.id !== streamingMsgId),
            data.user_message,
            data.assistant_message,
          ]);
          isSendingRef.current = false;
          setLoading(false);
          if (localImageUrl) URL.revokeObjectURL(localImageUrl);
        },
        (err) => {
          console.error('Stream error:', err);
          toast.error('Failed to get response');
          setMessages(prev =>
            prev.map(m =>
              m.id === streamingMsgId
                ? { ...m, content: m.content || 'Sorry, something went wrong. Please try again.' }
                : m
            )
          );
          isSendingRef.current = false;
          setLoading(false);
          if (localImageUrl) URL.revokeObjectURL(localImageUrl);
        },
      );
    } catch {
      toast.error('Failed to send message');
      setMessages(prev =>
        prev.map(m =>
          m.id === streamingMsgId
            ? { ...m, content: 'Sorry, something went wrong. Please try again.' }
            : m
        )
      );
      isSendingRef.current = false;
      setLoading(false);
      if (localImageUrl) URL.revokeObjectURL(localImageUrl);
    }
  };

  // Welcome / empty state
  if (!sessionId) {
    return (
      <div
        className="flex-1 flex items-center justify-center animate-fadeIn"
        style={{ background: 'var(--background)' }}
      >
        <div className="text-center max-w-md px-6">
          <div
            className="w-16 h-16 rounded-2xl flex items-center justify-center mx-auto mb-4"
            style={{ background: 'var(--accent-light)', color: 'var(--accent)' }}
          >
            <MessageSquare size={28} />
          </div>
          <h2 className="text-2xl font-bold mb-2" style={{ color: 'var(--foreground)' }}>
            Welcome to Engram
          </h2>
          <p className="mb-6" style={{ color: 'var(--muted)' }}>
            Select a conversation or create a new one to get started
          </p>
          <div className="flex flex-wrap justify-center gap-2">
            {['Tell me about yourself', 'Help me brainstorm', 'Analyze an image'].map(chip => (
              <span
                key={chip}
                className="text-xs px-3 py-1.5 rounded-full"
                style={{
                  background: 'var(--surface-secondary)',
                  color: 'var(--muted)',
                  border: '1px solid var(--border)',
                }}
              >
                {chip}
              </span>
            ))}
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="flex-1 flex flex-col" style={{ background: 'var(--background)' }}>
      {/* Messages area */}
      <div className="flex-1 overflow-y-auto p-3 sm:p-4 md:p-6 space-y-4" aria-live="polite">
        {messages.map((message) => {
          // Hide the streaming placeholder when it has no content yet (loading dots shown separately)
          if (message.role === 'assistant' && !message.content && !message.image_url) return null;

          return (
          <div
            key={message.id}
            className={`flex ${message.role === 'user' ? 'justify-end' : 'justify-start'} animate-slideInUp`}
          >
            {/* Avatar for assistant */}
            {message.role === 'assistant' && (
              <div
                className="w-7 h-7 rounded-full flex items-center justify-center shrink-0 mr-2 mt-1"
                style={{ background: 'var(--accent-light)', color: 'var(--accent)' }}
              >
                <Bot size={14} />
              </div>
            )}

            <div className="flex flex-col max-w-[90%] sm:max-w-[80%] md:max-w-[70%]">
              <div
                className={`rounded-xl px-4 py-3 ${message.role === 'user' ? 'rounded-br-sm' : 'rounded-bl-sm'}`}
                style={{
                  background: message.role === 'user' ? 'var(--chat-user-bg)' : 'var(--chat-assistant-bg)',
                  color: message.role === 'user' ? 'var(--chat-user-text)' : 'var(--chat-assistant-text)',
                  border: message.role === 'assistant' ? '1px solid var(--chat-assistant-border)' : 'none',
                }}
              >
                {message.image_url && (
                  <img
                    src={message.image_url.startsWith('blob:') ? message.image_url : `${API_BASE_URL}${message.image_url}`}
                    alt="Attached"
                    className="max-w-[240px] rounded-md mb-2"
                  />
                )}
                {message.role === 'assistant' ? (
                  <div className="prose prose-sm max-w-none">
                    <ReactMarkdown
                      components={{
                        p: ({ children }) => <p className="mb-2 last:mb-0">{children}</p>,
                        ul: ({ children }) => <ul className="list-disc ml-4 mb-2 space-y-1">{children}</ul>,
                        ol: ({ children }) => <ol className="list-decimal ml-4 mb-2 space-y-1">{children}</ol>,
                        li: ({ children }) => <li className="ml-1">{children}</li>,
                        strong: ({ children }) => <strong className="font-bold">{children}</strong>,
                        em: ({ children }) => <em className="italic">{children}</em>,
                        img: ({ src, alt }) => (
                          <img
                            src={typeof src === 'string' && src.startsWith('/') ? `${API_BASE_URL}${src}` : String(src ?? '')}
                            alt={alt || ''}
                            className="max-w-[200px] rounded-lg my-2"
                          />
                        ),
                        code: ({ children, className }) => {
                          const isBlock = className?.includes('language-') || (typeof children === 'string' && children.includes('\n'));
                          if (isBlock) return <CodeBlock className={className}>{children}</CodeBlock>;
                          return (
                            <code
                              className="px-1.5 py-0.5 rounded text-sm font-mono"
                              style={{ background: 'var(--code-bg)' }}
                            >
                              {children}
                            </code>
                          );
                        },
                        pre: ({ children }) => <>{children}</>,
                      }}
                    >
                      {message.content}
                    </ReactMarkdown>
                  </div>
                ) : (
                  <p className="whitespace-pre-wrap">{message.content}</p>
                )}
              </div>

              {/* Timestamp + copy */}
              <div className={`flex items-center gap-2 mt-1 px-1 ${message.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                <span className="text-[11px]" style={{ color: 'var(--muted-foreground)' }}>
                  {relativeTime(message.timestamp)}
                </span>
                {message.role === 'assistant' && message.content && (
                  <CopyButton text={message.content} />
                )}
              </div>
            </div>

            {/* Avatar for user */}
            {message.role === 'user' && (
              <div
                className="w-7 h-7 rounded-full flex items-center justify-center shrink-0 ml-2 mt-1 text-xs font-bold text-white"
                style={{ background: 'var(--accent)' }}
              >
                U
              </div>
            )}
          </div>
          );
        })}

        {loading && (
          <div className="flex justify-start animate-fadeIn">
            <div
              className="w-7 h-7 rounded-full flex items-center justify-center shrink-0 mr-2 mt-1"
              style={{ background: 'var(--accent-light)', color: 'var(--accent)' }}
            >
              <Bot size={14} />
            </div>
            <div
              className="rounded-xl rounded-bl-sm px-4 py-3"
              style={{
                background: 'var(--chat-assistant-bg)',
                border: '1px solid var(--chat-assistant-border)',
              }}
            >
              <div className="flex items-center space-x-1.5">
                <span className="w-2 h-2 rounded-full animate-dot-1" style={{ background: 'var(--accent)' }} />
                <span className="w-2 h-2 rounded-full animate-dot-2" style={{ background: 'var(--accent)' }} />
                <span className="w-2 h-2 rounded-full animate-dot-3" style={{ background: 'var(--accent)' }} />
              </div>
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Input area */}
      <div className="p-3 sm:p-4" style={{ borderTop: '1px solid var(--border)' }}>
        {imageError && (
          <div className="mb-2 px-1 text-xs" style={{ color: 'var(--destructive)' }} role="alert">
            {imageError}
          </div>
        )}
        {attachedImage && (
          <div className="flex items-center gap-3 mb-2 px-1">
            <img
              src={previewUrl!}
              alt="Preview"
              className="h-16 w-16 object-cover rounded-md"
              style={{ border: '1px solid var(--border)' }}
            />
            <span className="text-xs truncate max-w-[200px]" style={{ color: 'var(--muted)' }}>
              {attachedImage.name}
            </span>
            <button
              type="button"
              onClick={() => { setAttachedImage(null); setImageError(''); }}
              className="text-xs transition-colors"
              style={{ color: 'var(--destructive)' }}
            >
              Remove
            </button>
          </div>
        )}
        <form onSubmit={handleSend} className="flex gap-2">
          <button
            type="button"
            onClick={() => imageInputRef.current?.click()}
            disabled={loading}
            className="px-3 py-3 rounded-lg disabled:opacity-50 transition-colors active:scale-95 focus-visible:ring-2"
            style={{
              border: '1px solid var(--input-border)',
              color: 'var(--muted)',
              background: 'var(--input-bg)',
            }}
            title="Attach a photo for face identification"
            aria-label="Attach image"
          >
            <Camera size={18} />
          </button>
          <input
            ref={imageInputRef}
            type="file"
            accept="image/jpeg,image/png,image/webp"
            className="hidden"
            onChange={(e) => {
              if (e.target.files?.[0]) handleImageSelect(e.target.files[0]);
              e.target.value = '';
            }}
          />
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder={attachedImage ? "Ask about this photo..." : "Type your message here..."}
            disabled={loading}
            className="flex-1 px-4 py-3 rounded-lg text-sm focus:outline-none focus-visible:ring-2 disabled:opacity-60 transition-colors"
            style={{
              border: '1px solid var(--input-border)',
              background: 'var(--input-bg)',
              color: 'var(--foreground)',
            }}
          />
          <button
            type="submit"
            disabled={loading || !input.trim()}
            className="px-4 sm:px-6 py-3 rounded-lg text-sm font-medium text-white disabled:opacity-50 disabled:cursor-not-allowed transition-colors active:scale-95 focus-visible:ring-2"
            style={{ background: 'var(--accent)' }}
            aria-label="Send message"
          >
            <span className="hidden sm:inline">Send</span>
            <Send size={18} className="sm:hidden" />
          </button>
        </form>
      </div>
    </div>
  );
}
