'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import toast from 'react-hot-toast';
import { ArrowLeft, BookOpen, Search, Plus, ChevronDown } from 'lucide-react';
import { isAuthenticated } from '@/lib/auth';
import Skeleton from '@/components/Skeleton';
import {
  Content, ContentCreate, PaginatedContentResponse,
  getContentList, createContent,
} from '@/lib/api';

const PAGE_SIZE = 50;

const TYPE_TABS = [
  { label: 'All', value: '' },
  { label: 'Book', value: 'book' },
  { label: 'Article', value: 'article' },
  { label: 'Video', value: 'video' },
  { label: 'Podcast', value: 'podcast' },
  { label: 'Paper', value: 'paper' },
  { label: 'Course', value: 'course' },
  { label: 'Movie', value: 'movie' },
];

const STATUS_OPTIONS = ['want', 'reading', 'completed', 'abandoned'];

const emptyForm: ContentCreate = { title: '' };

function statusColor(status: string | null): string {
  switch (status) {
    case 'completed': return 'var(--success)';
    case 'reading': return 'var(--accent)';
    case 'want': return 'var(--warning, #f59e0b)';
    case 'abandoned': return 'var(--muted)';
    default: return 'var(--muted-foreground)';
  }
}

export default function ContentPage() {
  const router = useRouter();
  const [items, setItems] = useState<Content[]>([]);
  const [totalCount, setTotalCount] = useState(0);
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [offset, setOffset] = useState(0);
  const [searchQuery, setSearchQuery] = useState('');

  const [filterType, setFilterType] = useState('');
  const [filterStatus, setFilterStatus] = useState('');

  const [showAddForm, setShowAddForm] = useState(false);
  const [newContent, setNewContent] = useState<ContentCreate>(emptyForm);
  const [creating, setCreating] = useState(false);
  const [titleError, setTitleError] = useState(false);
  const [showAdvanced, setShowAdvanced] = useState(false);

  useEffect(() => {
    if (!isAuthenticated()) { router.push('/login'); return; }
    loadContent(true);
  }, [router]);

  useEffect(() => {
    if (!loading) loadContent(true);
  }, [filterType, filterStatus]);

  async function loadContent(reset = false) {
    const newOffset = reset ? 0 : offset;
    if (reset) setLoading(true); else setLoadingMore(true);
    try {
      const params: Record<string, any> = { limit: PAGE_SIZE, offset: newOffset };
      if (filterType) params.content_type = filterType;
      if (filterStatus) params.status = filterStatus;
      const data: PaginatedContentResponse = await getContentList(params);
      if (reset) setItems(data.items); else setItems(prev => [...prev, ...data.items]);
      setTotalCount(data.total);
      setOffset(newOffset + data.items.length);
    } catch {
      toast.error('Failed to load content');
    } finally {
      setLoading(false);
      setLoadingMore(false);
    }
  }

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    if (!newContent.title.trim()) { setTitleError(true); return; }
    setTitleError(false);
    setCreating(true);
    try {
      const created = await createContent(newContent);
      setItems([created, ...items]);
      setTotalCount(prev => prev + 1);
      setNewContent(emptyForm);
      setShowAddForm(false);
      setShowAdvanced(false);
      toast.success(`"${created.title}" added`);
    } catch {
      toast.error('Failed to create content');
    } finally {
      setCreating(false);
    }
  }

  const filtered = items.filter(c => {
    const q = searchQuery.toLowerCase();
    return c.title.toLowerCase().includes(q) ||
      (c.author || '').toLowerCase().includes(q) ||
      (c.personal_notes || '').toLowerCase().includes(q);
  });

  const hasMore = items.length < totalCount;

  if (loading) {
    return (
      <div className="min-h-screen" style={{ background: 'var(--background)' }}>
        <div className="px-4 sm:px-6 py-4" style={{ background: 'var(--surface)', borderBottom: '1px solid var(--border)' }}>
          <Skeleton className="h-8 w-32" />
        </div>
        <div className="max-w-3xl mx-auto px-4 sm:px-6 py-8 space-y-4">
          {[...Array(4)].map((_, i) => <Skeleton key={i} className="h-20 w-full" />)}
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen animate-fadeIn" style={{ background: 'var(--background)' }}>
      <div
        className="px-4 sm:px-6 py-4 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3"
        style={{ background: 'var(--surface)', borderBottom: '1px solid var(--border)' }}
      >
        <div className="flex items-center gap-4">
          <Link href="/" className="flex items-center gap-1 text-sm transition-colors" style={{ color: 'var(--muted)' }}>
            <ArrowLeft size={16} /> Chat
          </Link>
          <h1 className="text-lg font-semibold flex items-center gap-2" style={{ color: 'var(--foreground)' }}>
            <BookOpen size={20} /> Content
          </h1>
        </div>
        <button
          onClick={() => setShowAddForm(!showAddForm)}
          className="flex items-center justify-center gap-1.5 px-4 py-2 rounded-lg text-sm font-medium text-white transition-colors active:scale-95"
          style={{ background: 'var(--accent)' }}
        >
          {showAddForm ? 'Cancel' : <><Plus size={16} /> Add Content</>}
        </button>
      </div>

      <div className="max-w-3xl mx-auto px-4 sm:px-6 py-6 sm:py-8 space-y-6 sm:space-y-8">
        {showAddForm && (
          <div className="rounded-xl p-5 sm:p-6 animate-scaleIn" style={{ background: 'var(--surface)', border: '1px solid var(--border)' }}>
            <h2 className="text-sm font-semibold mb-4" style={{ color: 'var(--foreground)' }}>Add Content</h2>
            <form onSubmit={handleCreate} className="space-y-3">
              <input
                type="text" placeholder="Title *"
                value={newContent.title}
                onChange={e => { setNewContent({ ...newContent, title: e.target.value }); setTitleError(false); }}
                className="w-full rounded-lg px-3.5 py-2.5 text-sm focus:outline-none focus-visible:ring-2"
                style={{ border: `1px solid ${titleError ? 'var(--destructive)' : 'var(--input-border)'}`, background: 'var(--input-bg)', color: 'var(--foreground)' }}
                required
              />
              {titleError && <p className="text-xs" style={{ color: 'var(--destructive)' }}>Title is required</p>}
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <input
                  type="text" placeholder="Author"
                  value={newContent.author || ''}
                  onChange={e => setNewContent({ ...newContent, author: e.target.value })}
                  className="w-full rounded-lg px-3.5 py-2.5 text-sm focus:outline-none focus-visible:ring-2"
                  style={{ border: '1px solid var(--input-border)', background: 'var(--input-bg)', color: 'var(--foreground)' }}
                />
                <select
                  value={newContent.content_type || ''}
                  onChange={e => setNewContent({ ...newContent, content_type: e.target.value || undefined })}
                  className="w-full rounded-lg px-3.5 py-2.5 text-sm focus:outline-none focus-visible:ring-2"
                  style={{ border: '1px solid var(--input-border)', background: 'var(--input-bg)', color: 'var(--foreground)' }}
                >
                  <option value="">Type (optional)</option>
                  {TYPE_TABS.filter(t => t.value).map(t => <option key={t.value} value={t.value}>{t.label}</option>)}
                </select>
              </div>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <select
                  value={newContent.status || ''}
                  onChange={e => setNewContent({ ...newContent, status: e.target.value || undefined })}
                  className="w-full rounded-lg px-3.5 py-2.5 text-sm focus:outline-none focus-visible:ring-2"
                  style={{ border: '1px solid var(--input-border)', background: 'var(--input-bg)', color: 'var(--foreground)' }}
                >
                  <option value="">Status (optional)</option>
                  {STATUS_OPTIONS.map(s => <option key={s} value={s} className="capitalize">{s}</option>)}
                </select>
                <input
                  type="text" placeholder="Tags (comma-separated)"
                  value={newContent.tags?.join(', ') || ''}
                  onChange={e => setNewContent({ ...newContent, tags: e.target.value.split(',').map(s => s.trim()).filter(Boolean) })}
                  className="w-full rounded-lg px-3.5 py-2.5 text-sm focus:outline-none focus-visible:ring-2"
                  style={{ border: '1px solid var(--input-border)', background: 'var(--input-bg)', color: 'var(--foreground)' }}
                />
              </div>

              <button type="button" onClick={() => setShowAdvanced(!showAdvanced)} className="flex items-center gap-1 text-xs" style={{ color: 'var(--accent)' }}>
                <ChevronDown size={12} className={showAdvanced ? 'rotate-180 transition-transform' : 'transition-transform'} />
                {showAdvanced ? 'Hide advanced' : 'Show advanced'}
              </button>

              {showAdvanced && (
                <div className="space-y-3 pt-2">
                  <input
                    type="text" placeholder="Source URL"
                    value={newContent.source_url || ''}
                    onChange={e => setNewContent({ ...newContent, source_url: e.target.value })}
                    className="w-full rounded-lg px-3.5 py-2.5 text-sm focus:outline-none focus-visible:ring-2"
                    style={{ border: '1px solid var(--input-border)', background: 'var(--input-bg)', color: 'var(--foreground)' }}
                  />
                  <input
                    type="text" placeholder="Recommended by"
                    value={newContent.recommended_by || ''}
                    onChange={e => setNewContent({ ...newContent, recommended_by: e.target.value })}
                    className="w-full rounded-lg px-3.5 py-2.5 text-sm focus:outline-none focus-visible:ring-2"
                    style={{ border: '1px solid var(--input-border)', background: 'var(--input-bg)', color: 'var(--foreground)' }}
                  />
                  <textarea
                    placeholder="Personal notes"
                    value={newContent.personal_notes || ''}
                    onChange={e => setNewContent({ ...newContent, personal_notes: e.target.value })}
                    rows={3}
                    className="w-full rounded-lg px-3.5 py-2.5 text-sm focus:outline-none focus-visible:ring-2 resize-y"
                    style={{ border: '1px solid var(--input-border)', background: 'var(--input-bg)', color: 'var(--foreground)' }}
                  />
                </div>
              )}

              <button type="submit" disabled={creating}
                className="px-4 py-2.5 rounded-lg text-sm font-medium text-white disabled:opacity-50 transition-colors active:scale-95"
                style={{ background: 'var(--accent)' }}
              >
                {creating ? 'Adding...' : 'Add Content'}
              </button>
            </form>
          </div>
        )}

        {/* Search + Filters */}
        <div className="space-y-3">
          <div className="relative">
            <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2" style={{ color: 'var(--muted-foreground)' }} />
            <input
              type="text" placeholder="Search content..."
              value={searchQuery} onChange={e => setSearchQuery(e.target.value)}
              className="w-full pl-8 pr-3 py-2.5 rounded-lg text-sm focus:outline-none focus-visible:ring-2"
              style={{ background: 'var(--input-bg)', border: '1px solid var(--border)', color: 'var(--foreground)' }}
            />
          </div>
          <div className="flex flex-wrap gap-1.5">
            {TYPE_TABS.map(tab => (
              <button key={tab.value} onClick={() => setFilterType(tab.value)}
                className="px-3 py-1 rounded-full text-xs font-medium transition-colors"
                style={{
                  background: filterType === tab.value ? 'var(--accent)' : 'var(--surface)',
                  color: filterType === tab.value ? 'white' : 'var(--muted)',
                  border: `1px solid ${filterType === tab.value ? 'var(--accent)' : 'var(--border)'}`,
                }}
              >{tab.label}</button>
            ))}
          </div>
          <div className="flex flex-wrap gap-1.5">
            <button onClick={() => setFilterStatus('')}
              className="px-3 py-1 rounded-full text-xs font-medium transition-colors"
              style={{
                background: !filterStatus ? 'var(--accent)' : 'var(--surface)',
                color: !filterStatus ? 'white' : 'var(--muted)',
                border: `1px solid ${!filterStatus ? 'var(--accent)' : 'var(--border)'}`,
              }}
            >All Status</button>
            {STATUS_OPTIONS.map(s => (
              <button key={s} onClick={() => setFilterStatus(s)}
                className="px-3 py-1 rounded-full text-xs font-medium transition-colors capitalize"
                style={{
                  background: filterStatus === s ? 'var(--accent)' : 'var(--surface)',
                  color: filterStatus === s ? 'white' : 'var(--muted)',
                  border: `1px solid ${filterStatus === s ? 'var(--accent)' : 'var(--border)'}`,
                }}
              >{s}</button>
            ))}
          </div>
        </div>

        {/* Content List */}
        <div>
          <h2 className="text-sm font-semibold mb-3" style={{ color: 'var(--foreground)' }}>
            Content ({totalCount})
          </h2>
          {filtered.length === 0 ? (
            <div className="rounded-xl p-8 text-center" style={{ background: 'var(--surface)', border: '1px solid var(--border)' }}>
              <BookOpen size={32} className="mx-auto mb-2" style={{ color: 'var(--muted-foreground)' }} />
              <p className="text-sm" style={{ color: 'var(--muted)' }}>
                {searchQuery ? 'No matching content found' : 'No content tracked yet.'}
              </p>
              {!searchQuery && (
                <p className="text-xs mt-1" style={{ color: 'var(--muted-foreground)' }}>
                  Tell the chat about books, articles, or videos you&apos;re consuming.
                </p>
              )}
            </div>
          ) : (
            <div className="space-y-2">
              {filtered.map(item => (
                <Link key={item.id} href={`/content/${item.id}`}
                  className="block rounded-xl p-4 transition-shadow hover:shadow-md"
                  style={{ background: 'var(--surface)', border: '1px solid var(--border)', boxShadow: 'var(--shadow-sm)' }}
                >
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center gap-2 mb-1">
                        <p className="text-sm font-medium truncate" style={{ color: 'var(--foreground)' }}>{item.title}</p>
                        {item.status && (
                          <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-medium capitalize shrink-0"
                            style={{ background: `${statusColor(item.status)}20`, color: statusColor(item.status) }}
                          >{item.status}</span>
                        )}
                      </div>
                      <div className="flex items-center gap-3 text-xs" style={{ color: 'var(--muted)' }}>
                        {item.author && <span>by {item.author}</span>}
                        {item.content_type && <span className="capitalize">{item.content_type}</span>}
                        {item.your_rating != null && <span>Rating: {(item.your_rating * 100).toFixed(0)}%</span>}
                      </div>
                      {item.tags && item.tags.length > 0 && (
                        <div className="flex flex-wrap gap-1 mt-1.5">
                          {item.tags.slice(0, 3).map((tag, i) => (
                            <span key={i} className="inline-flex items-center px-1.5 py-0 rounded text-[10px] font-medium"
                              style={{ background: 'var(--surface-secondary)', color: 'var(--muted)', border: '1px solid var(--border)' }}
                            >{tag}</span>
                          ))}
                          {item.tags.length > 3 && <span className="text-[10px]" style={{ color: 'var(--muted)' }}>+{item.tags.length - 3}</span>}
                        </div>
                      )}
                    </div>
                  </div>
                </Link>
              ))}

              {hasMore && (
                <div className="text-center pt-4">
                  <button onClick={() => loadContent(false)} disabled={loadingMore}
                    className="px-6 py-2 rounded-lg text-sm font-medium transition-colors disabled:opacity-50"
                    style={{ border: '1px solid var(--border)', color: 'var(--accent)', background: 'var(--surface)' }}
                  >
                    {loadingMore ? 'Loading...' : `Load More (${totalCount - items.length} remaining)`}
                  </button>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
