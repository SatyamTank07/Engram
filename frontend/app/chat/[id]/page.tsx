'use client';

import { useParams } from 'next/navigation';
import ChatLayout from '@/components/ChatLayout';

export default function ChatPage() {
  const { id } = useParams<{ id: string }>();

  return <ChatLayout sessionId={id || null} />;
}
