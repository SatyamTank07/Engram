'use client';

import { useState, useEffect, useRef } from 'react';
import ReactMarkdown from 'react-markdown';
import { Message, getSessionMessages, sendMessage } from '@/lib/api';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

interface ChatInterfaceProps {
    sessionId: number | null;
}

export default function ChatInterface({ sessionId }: ChatInterfaceProps) {
    const [messages, setMessages] = useState<Message[]>([]);
    const [input, setInput] = useState('');
    const [loading, setLoading] = useState(false);
    const [attachedImage, setAttachedImage] = useState<File | null>(null);
    const messagesEndRef = useRef<HTMLDivElement>(null);
    const imageInputRef = useRef<HTMLInputElement>(null);

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
            setMessages(data);
        } catch (error) {
            console.error('Failed to load messages:', error);
        }
    };

    const handleSend = async (e: React.FormEvent) => {
        e.preventDefault();

        if (!input.trim() || !sessionId || loading) return;

        const userMessage = input.trim();
        const imageFile = attachedImage;
        setInput('');
        setAttachedImage(null);
        setLoading(true);

        try {
            const response = await sendMessage(sessionId, userMessage, imageFile || undefined);
            setMessages([...messages, response.user_message, response.assistant_message]);
        } catch (error) {
            console.error('Failed to send message:', error);
            const errorMessage = error instanceof Error ? error.message : 'An unknown error occurred';
            console.error(`Failed to send message: ${errorMessage}`);
        } finally {
            setLoading(false);
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
                                    src={`${API_BASE_URL}${message.image_url}`}
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
                                                    src={src?.startsWith('/') ? `${API_BASE_URL}${src}` : src}
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
                {attachedImage && (
                    <div className="flex items-center gap-3 mb-2 px-1">
                        <img
                            src={URL.createObjectURL(attachedImage)}
                            alt="Preview"
                            className="h-16 w-16 object-cover rounded-md border border-gray-200"
                        />
                        <span className="text-xs text-gray-500 truncate max-w-[200px]">
                            {attachedImage.name}
                        </span>
                        <button
                            type="button"
                            onClick={() => setAttachedImage(null)}
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
                        accept="image/*"
                        className="hidden"
                        onChange={(e) => {
                            if (e.target.files?.[0]) setAttachedImage(e.target.files[0]);
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
