'use client';

import { useState, useEffect, useRef, useMemo } from 'react';
import ReactMarkdown from 'react-markdown';
import { Message, getSessionMessages, sendMessage, sendMessageStream, validateImageFile } from '@/lib/api';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

interface ChatInterfaceProps {
    sessionId: number | null;
}

export default function ChatInterface({ sessionId }: ChatInterfaceProps) {
    const [messages, setMessages] = useState<Message[]>([]);
    const [input, setInput] = useState('');
    const [loading, setLoading] = useState(false);
    const [attachedImage, setAttachedImage] = useState<File | null>(null);
    const [imageError, setImageError] = useState('');
    const messagesEndRef = useRef<HTMLDivElement>(null);
    const imageInputRef = useRef<HTMLInputElement>(null);
    // Tracks whether a send is in-flight so loadMessages won't overwrite optimistic updates
    const isSendingRef = useRef(false);

    // Stable preview URL — created once per file, revoked on change/unmount
    const previewUrl = useMemo(() => {
        return attachedImage ? URL.createObjectURL(attachedImage) : null;
    }, [attachedImage]);

    useEffect(() => {
        return () => {
            if (previewUrl) URL.revokeObjectURL(previewUrl);
        };
    }, [previewUrl]);

    const scrollToBottom = () => {
        messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    };

    useEffect(() => {
        scrollToBottom();
    }, [messages]);

    useEffect(() => {
        if (sessionId) {
            loadMessages();
        } else {
            setMessages([]);
        }
    }, [sessionId]);

    const loadMessages = async () => {
        if (!sessionId) return;

        try {
            const data = await getSessionMessages(sessionId);
            // Don't overwrite optimistic messages while a send is in-flight
            if (!isSendingRef.current) {
                setMessages(data);
            }
        } catch (error) {
            console.error('Failed to load messages:', error);
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

        // Create a local preview URL for the image (if any) before clearing state
        const localImageUrl = imageFile ? URL.createObjectURL(imageFile) : null;

        setInput('');
        setAttachedImage(null);
        setImageError('');
        setLoading(true);
        isSendingRef.current = true;

        // Optimistic: show user message immediately
        const tempUserMessage: Message = {
            id: Date.now(),
            session_id: sessionId,
            role: 'user',
            content: userMessage,
            image_url: localImageUrl,
            timestamp: new Date().toISOString(),
        };

        // Placeholder for the streaming assistant response
        const streamingMsgId = Date.now() + 1;
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
                sessionId,
                userMessage,
                imageFile || undefined,
                // onToken — append each chunk to the streaming message
                (token: string) => {
                    setMessages(prev =>
                        prev.map(m =>
                            m.id === streamingMsgId
                                ? { ...m, content: m.content + token }
                                : m
                        )
                    );
                },
                // onDone — replace temp messages with persisted ones
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
                // onError
                (err) => {
                    console.error('Stream error:', err);
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
        } catch (error) {
            // sendMessageStream can throw during image upload (before stream starts)
            console.error('Failed to send message:', error);
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

    if (!sessionId) {
        return (
            <div className="flex-1 flex items-center justify-center bg-white">
                <div className="text-center">
                    <h2 className="text-2xl font-bold text-gray-900 mb-2">Welcome to AI Chat</h2>
                    <p className="text-gray-600">Select a conversation or create a new one to get started</p>
                </div>
            </div>
        );
    }

    return (
        <div className="flex-1 flex flex-col bg-white">
            {/* Messages area */}
            <div className="flex-1 overflow-y-auto p-6 space-y-4">
                {messages.map((message) => (
                    <div
                        key={message.id}
                        className={`flex ${message.role === 'user' ? 'justify-end' : 'justify-start'}`}
                    >
                        <div
                            className={`max-w-[80%] rounded-lg px-4 py-3 ${message.role === 'user'
                                ? 'bg-blue-500 text-white'
                                : 'bg-gray-100 text-gray-900 border border-gray-200'
                                }`}
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
                                    {/* Do NOT add rehypeRaw — raw HTML must stay stripped to prevent XSS */}
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
                                            code: ({ children }) => (
                                                <code className="bg-gray-200 px-1 py-0.5 rounded text-sm font-mono">
                                                    {children}
                                                </code>
                                            ),
                                            pre: ({ children }) => (
                                                <pre className="bg-gray-200 p-2 rounded overflow-x-auto my-2">
                                                    {children}
                                                </pre>
                                            ),
                                        }}
                                    >
                                        {message.content}
                                    </ReactMarkdown>
                                </div>
                            ) : (
                                <p className="whitespace-pre-wrap">{message.content}</p>
                            )}
                        </div>
                    </div>
                ))}

                {loading && (
                    <div className="flex justify-start">
                        <div className="bg-gray-100 border border-gray-200 rounded-lg px-4 py-3">
                            <div className="flex items-center space-x-2">
                                <div className="animate-bounce">●</div>
                                <div className="animate-bounce delay-100">●</div>
                                <div className="animate-bounce delay-200">●</div>
                            </div>
                        </div>
                    </div>
                )}

                <div ref={messagesEndRef} />
            </div>

            {/* Input area */}
            <div className="border-t border-gray-200 p-4">
                {imageError && (
                    <div className="mb-2 px-1 text-xs text-red-500">{imageError}</div>
                )}
                {attachedImage && (
                    <div className="flex items-center gap-3 mb-2 px-1">
                        <img
                            src={previewUrl!}
                            alt="Preview"
                            className="h-16 w-16 object-cover rounded-md border border-gray-200"
                        />
                        <span className="text-xs text-gray-500 truncate max-w-[200px]">
                            {attachedImage.name}
                        </span>
                        <button
                            type="button"
                            onClick={() => { setAttachedImage(null); setImageError(''); }}
                            className="text-xs text-red-400 hover:text-red-600"
                        >
                            Remove
                        </button>
                    </div>
                )}
                <form onSubmit={handleSend} className="flex space-x-2">
                    <button
                        type="button"
                        onClick={() => imageInputRef.current?.click()}
                        disabled={loading}
                        className="px-3 py-3 border border-gray-300 rounded-lg hover:bg-gray-50 disabled:opacity-50 transition-colors text-gray-500"
                        title="Attach a photo for face identification"
                    >
                        📷
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
                        className="flex-1 px-4 py-3 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent disabled:bg-gray-100 text-gray-900"
                    />
                    <button
                        type="submit"
                        disabled={loading || !input.trim()}
                        className="bg-blue-500 hover:bg-blue-600 text-white px-6 py-3 rounded-lg disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                    >
                        Send
                    </button>
                </form>
            </div>
        </div>
    );
}
