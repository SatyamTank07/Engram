'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import toast from 'react-hot-toast';
import { ArrowLeft, Lightbulb, Search, Plus, ChevronDown } from 'lucide-react';
import { isAuthenticated } from '@/lib/auth';
import Skeleton from '@/components/Skeleton';
import {
  Idea, IdeaCreate, PaginatedIdeasResponse,
  getIdeas, createIdea,
} from '@/lib/api';

const PAGE_SIZE = 50;

const TYPE_TABS = [
  { label: 'All', value: '' },
  { label: 'Prediction', value: 'prediction' },
  { label: 'Opinion', value: 'opinion' },
  { label: 'Decision', value: 'decision' },
  { label: 'Question', value: 'question' },
  { label: 'Hypothesis', value: 'hypothesis' },
  { label: 'Lesson', value: 'lesson_learned' },
];

const STATUS_OPTIONS = ['active', 'validated', 'invalidated', 'evolved', 'abandoned'];

const emptyForm: IdeaCreate = { name: '' };

function statusColor(status: string | null): string {
  switch (status) {
    case 'validated': return 'var(--success)';
    case 'invalidated': return 'var(--destructive)';
    case 'evolved': return 'var(--accent)';
    case 'abandoned': return 'var(--muted)';
    default: return 'var(--warning, #f59e0b)';
  }
}

export default function IdeasPage() {
  const router = useRouter();
  const [ideas, setIdeas] = useState<Idea[]>([]);
  const [totalCount, setTotalCount] = useState(0);
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [offset, setOffset] = useState(0);
  const [searchQuery, setSearchQuery] = useState('');

  const [filterType, setFilterType] = useState('');
  const [filterStatus, setFilterStatus] = useState('');

  const [showAddForm, setShowAddForm] = useState(false);
  const [newIdea, setNewIdea] = useState<IdeaCreate>(emptyForm);
  const [creating, setCreating] = useState(false);
  const [nameError, setNameError] = useState(false);
  const [showAdvanced, setShowAdvanced] = useState(false);

  useEffect(() => {
    if (!isAuthenticated()) { router.push('/login'); return; }
    loadIdeas(true);
  }, [router]);

  useEffect(() => {
    if (!loading) loadIdeas(true);
  }, [filterType, filterStatus]);

  async function loadIdeas(reset = false) {
    const newOffset = reset ? 0 : offset;
    if (reset) setLoading(true); else setLoadingMore(true);
    try {
      const params: Record<string, any> = { limit: PAGE_SIZE, offset: newOffset };
      if (filterType) params.idea_type = filterType;
      if (filterStatus) params.status = filterStatus;
      const data: PaginatedIdeasResponse = await getIdeas(params);
      if (reset) setIdeas(data.items); else setIdeas(prev => [...prev, ...data.items]);
      setTotalCount(data.total);
      setOffset(newOffset + data.items.length);
    } catch {
      toast.error('Failed to load ideas');
    } finally {
      setLoading(false);
      setLoadingMore(false);
    }
  }

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    if (!newIdea.name.trim()) { setNameError(true); return; }
    setNameError(false);
    setCreating(true);
    try {
      const created = await createIdea(newIdea);
      setIdeas([created, ...ideas]);
      setTotalCount(prev => prev + 1);
      setNewIdea(emptyForm);
      setShowAddForm(false);
      setShowAdvanced(false);
      toast.success(`"${created.name}" added`);
    } catch {
      toast.error('Failed to create idea');
    } finally {
      setCreating(false);
    }
  }

  const filteredIdeas = ideas.filter(i => {
    const q = searchQuery.toLowerCase();
    return i.name.toLowerCase().includes(q) ||
      (i.description || '').toLowerCase().includes(q) ||
      (i.notes || '').toLowerCase().includes(q);
  });

  const hasMore = ideas.length < totalCount;

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
            <Lightbulb size={20} /> Ideas
          </h1>
        </div>
        <button
          onClick={() => setShowAddForm(!showAddForm)}
          className="flex items-center justify-center gap-1.5 px-4 py-2 rounded-lg text-sm font-medium text-white transition-colors active:scale-95"
          style={{ background: 'var(--accent)' }}
        >
          {showAddForm ? 'Cancel' : <><Plus size={16} /> New Idea</>}
        </button>
      </div>

      <div className="max-w-3xl mx-auto px-4 sm:px-6 py-6 sm:py-8 space-y-6 sm:space-y-8">
        {showAddForm && (
          <div className="rounded-xl p-5 sm:p-6 animate-scaleIn" style={{ background: 'var(--surface)', border: '1px solid var(--border)' }}>
            <h2 className="text-sm font-semibold mb-4" style={{ color: 'var(--foreground)' }}>New Idea</h2>
            <form onSubmit={handleCreate} className="space-y-3">
              <input
                type="text"
                placeholder="Idea name *"
                value={newIdea.name}
                onChange={e => { setNewIdea({ ...newIdea, name: e.target.value }); setNameError(false); }}
                className="w-full rounded-lg px-3.5 py-2.5 text-sm focus:outline-none focus-visible:ring-2"
                style={{ border: `1px solid ${nameError ? 'var(--destructive)' : 'var(--input-border)'}`, background: 'var(--input-bg)', color: 'var(--foreground)' }}
                required
              />
              {nameError && <p className="text-xs" style={{ color: 'var(--destructive)' }}>Name is required</p>}
              <textarea
                placeholder="Description"
                value={newIdea.description || ''}
                onChange={e => setNewIdea({ ...newIdea, description: e.target.value })}
                rows={3}
                className="w-full rounded-lg px-3.5 py-2.5 text-sm focus:outline-none focus-visible:ring-2 resize-y"
                style={{ border: '1px solid var(--input-border)', background: 'var(--input-bg)', color: 'var(--foreground)' }}
              />
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <select
                  value={newIdea.idea_type || ''}
                  onChange={e => setNewIdea({ ...newIdea, idea_type: e.target.value || undefined })}
                  className="w-full rounded-lg px-3.5 py-2.5 text-sm focus:outline-none focus-visible:ring-2"
                  style={{ border: '1px solid var(--input-border)', background: 'var(--input-bg)', color: 'var(--foreground)' }}
                >
                  <option value="">Type (optional)</option>
                  {TYPE_TABS.filter(t => t.value).map(t => <option key={t.value} value={t.value}>{t.label}</option>)}
                </select>
                <select
                  value={newIdea.status || ''}
                  onChange={e => setNewIdea({ ...newIdea, status: e.target.value || undefined })}
                  className="w-full rounded-lg px-3.5 py-2.5 text-sm focus:outline-none focus-visible:ring-2"
                  style={{ border: '1px solid var(--input-border)', background: 'var(--input-bg)', color: 'var(--foreground)' }}
                >
                  <option value="">Status (optional)</option>
                  {STATUS_OPTIONS.map(s => <option key={s} value={s}>{s}</option>)}
                </select>
              </div>
              <input
                type="text"
                placeholder="Tags (comma-separated)"
                value={newIdea.tags?.join(', ') || ''}
                onChange={e => setNewIdea({ ...newIdea, tags: e.target.value.split(',').map(s => s.trim()).filter(Boolean) })}
                className="w-full rounded-lg px-3.5 py-2.5 text-sm focus:outline-none focus-visible:ring-2"
                style={{ border: '1px solid var(--input-border)', background: 'var(--input-bg)', color: 'var(--foreground)' }}
              />

              <button type="button" onClick={() => setShowAdvanced(!showAdvanced)} className="flex items-center gap-1 text-xs" style={{ color: 'var(--accent)' }}>
                <ChevronDown size={12} className={showAdvanced ? 'rotate-180 transition-transform' : 'transition-transform'} />
                {showAdvanced ? 'Hide advanced' : 'Show advanced'}
              </button>

              {showAdvanced && (
                <div className="space-y-3 pt-2">
                  <div>
                    <label className="block text-xs mb-1" style={{ color: 'var(--muted)' }}>Confidence (0-1)</label>
                    <input
                      type="number" min="0" max="1" step="0.1"
                      value={newIdea.confidence ?? ''}
                      onChange={e => setNewIdea({ ...newIdea, confidence: e.target.value ? parseFloat(e.target.value) : undefined })}
                      className="w-full rounded-lg px-3.5 py-2.5 text-sm focus:outline-none focus-visible:ring-2"
                      style={{ border: '1px solid var(--input-border)', background: 'var(--input-bg)', color: 'var(--foreground)' }}
                    />
                  </div>
                  <textarea
                    placeholder="Notes"
                    value={newIdea.notes || ''}
                    onChange={e => setNewIdea({ ...newIdea, notes: e.target.value })}
                    rows={3}
                    className="w-full rounded-lg px-3.5 py-2.5 text-sm focus:outline-none focus-visible:ring-2 resize-y"
                    style={{ border: '1px solid var(--input-border)', background: 'var(--input-bg)', color: 'var(--foreground)' }}
                  />
                </div>
              )}

              <button
                type="submit" disabled={creating}
                className="px-4 py-2.5 rounded-lg text-sm font-medium text-white disabled:opacity-50 transition-colors active:scale-95"
                style={{ background: 'var(--accent)' }}
              >
                {creating ? 'Creating...' : 'Create Idea'}
              </button>
            </form>
          </div>
        )}

        {/* Search + Filters */}
        <div className="space-y-3">
          <div className="relative">
            <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2" style={{ color: 'var(--muted-foreground)' }} />
            <input
              type="text" placeholder="Search ideas..."
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

        {/* Ideas List */}
        <div>
          <h2 className="text-sm font-semibold mb-3" style={{ color: 'var(--foreground)' }}>
            Ideas ({totalCount})
          </h2>
          {filteredIdeas.length === 0 ? (
            <div className="rounded-xl p-8 text-center" style={{ background: 'var(--surface)', border: '1px solid var(--border)' }}>
              <Lightbulb size={32} className="mx-auto mb-2" style={{ color: 'var(--muted-foreground)' }} />
              <p className="text-sm" style={{ color: 'var(--muted)' }}>
                {searchQuery ? 'No matching ideas found' : 'No ideas yet.'}
              </p>
              {!searchQuery && (
                <p className="text-xs mt-1" style={{ color: 'var(--muted-foreground)' }}>
                  Use the chat to share your thoughts, or click &ldquo;New Idea&rdquo; above.
                </p>
              )}
            </div>
          ) : (
            <div className="space-y-2">
              {filteredIdeas.map(idea => (
                <Link key={idea.id} href={`/ideas/${idea.id}`}
                  className="block rounded-xl p-4 transition-shadow hover:shadow-md"
                  style={{ background: 'var(--surface)', border: '1px solid var(--border)', boxShadow: 'var(--shadow-sm)' }}
                >
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center gap-2 mb-1">
                        <p className="text-sm font-medium truncate" style={{ color: 'var(--foreground)' }}>{idea.name}</p>
                        {idea.status && (
                          <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-medium capitalize shrink-0"
                            style={{ background: `${statusColor(idea.status)}20`, color: statusColor(idea.status) }}
                          >{idea.status}</span>
                        )}
                      </div>
                      {idea.description && (
                        <p className="text-xs truncate" style={{ color: 'var(--muted)' }}>{idea.description}</p>
                      )}
                      <div className="flex items-center gap-3 mt-1.5">
                        {idea.idea_type && (
                          <span className="text-[10px] font-medium capitalize" style={{ color: 'var(--muted-foreground)' }}>{idea.idea_type}</span>
                        )}
                        {idea.confidence != null && (
                          <span className="text-[10px]" style={{ color: 'var(--muted-foreground)' }}>
                            Confidence: {(idea.confidence * 100).toFixed(0)}%
                          </span>
                        )}
                      </div>
                      {idea.tags && idea.tags.length > 0 && (
                        <div className="flex flex-wrap gap-1 mt-1.5">
                          {idea.tags.slice(0, 3).map((tag, i) => (
                            <span key={i} className="inline-flex items-center px-1.5 py-0 rounded text-[10px] font-medium"
                              style={{ background: 'var(--surface-secondary)', color: 'var(--muted)', border: '1px solid var(--border)' }}
                            >{tag}</span>
                          ))}
                          {idea.tags.length > 3 && <span className="text-[10px]" style={{ color: 'var(--muted)' }}>+{idea.tags.length - 3}</span>}
                        </div>
                      )}
                    </div>
                  </div>
                </Link>
              ))}

              {hasMore && (
                <div className="text-center pt-4">
                  <button onClick={() => loadIdeas(false)} disabled={loadingMore}
                    className="px-6 py-2 rounded-lg text-sm font-medium transition-colors disabled:opacity-50"
                    style={{ border: '1px solid var(--border)', color: 'var(--accent)', background: 'var(--surface)' }}
                  >
                    {loadingMore ? 'Loading...' : `Load More (${totalCount - ideas.length} remaining)`}
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
