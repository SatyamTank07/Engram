'use client';

import { useState, useEffect } from 'react';
import { useRouter, useParams } from 'next/navigation';
import Link from 'next/link';
import toast from 'react-hot-toast';
import { ArrowLeft, Pencil, Trash2, BookOpen, ChevronDown, ChevronUp } from 'lucide-react';
import { isAuthenticated } from '@/lib/auth';
import ConfirmDialog from '@/components/ConfirmDialog';
import Skeleton from '@/components/Skeleton';
import { Content, ContentCreate, getContent, updateContent, deleteContent } from '@/lib/api';

const TYPE_OPTIONS = ['book', 'article', 'video', 'podcast', 'paper', 'course', 'movie', 'tweet', 'talk'];
const STATUS_OPTIONS = ['want', 'reading', 'completed', 'abandoned'];

function statusColor(status: string | null): string {
  switch (status) {
    case 'completed': return 'var(--success)';
    case 'reading': return 'var(--accent)';
    case 'want': return 'var(--warning, #f59e0b)';
    case 'abandoned': return 'var(--muted)';
    default: return 'var(--muted-foreground)';
  }
}

export default function ContentDetailPage() {
  const router = useRouter();
  const { id } = useParams<{ id: string }>();

  const [content, setContent] = useState<Content | null>(null);
  const [loading, setLoading] = useState(true);
  const [notFound, setNotFound] = useState(false);

  const [editing, setEditing] = useState(false);
  const [editForm, setEditForm] = useState<Partial<ContentCreate>>({});
  const [saving, setSaving] = useState(false);
  const [hasChanges, setHasChanges] = useState(false);

  const [expandedSections, setExpandedSections] = useState<Record<string, boolean>>({
    basic: true, details: false,
  });

  const [showDeleteDialog, setShowDeleteDialog] = useState(false);

  useEffect(() => {
    if (!isAuthenticated()) { router.push('/login'); return; }
    loadContent();
  }, [id, router]);

  async function loadContent() {
    try {
      const data = await getContent(id);
      setContent(data);
      setEditForm(contentToForm(data));
    } catch {
      setNotFound(true);
    } finally {
      setLoading(false);
    }
  }

  function contentToForm(c: Content): Partial<ContentCreate> {
    return {
      title: c.title,
      content_type: c.content_type || '',
      author: c.author || '',
      source_url: c.source_url || '',
      status: c.status || '',
      your_rating: c.your_rating ?? undefined,
      personal_notes: c.personal_notes || '',
      recommended_by: c.recommended_by || '',
      tags: c.tags || [],
    };
  }

  function handleEditChange(updates: Partial<ContentCreate>) {
    setEditForm(prev => ({ ...prev, ...updates }));
    setHasChanges(true);
  }

  function toggleSection(key: string) {
    setExpandedSections(prev => ({ ...prev, [key]: !prev[key] }));
  }

  async function handleSave(e: React.FormEvent) {
    e.preventDefault();
    if (!content) return;
    setSaving(true);
    try {
      const updated = await updateContent(content.id, editForm);
      setContent(updated);
      setEditing(false);
      setHasChanges(false);
      toast.success('Content updated');
    } catch {
      toast.error('Failed to update content');
    } finally {
      setSaving(false);
    }
  }

  async function handleDeleteConfirm() {
    if (!content) return;
    setShowDeleteDialog(false);
    try {
      await deleteContent(content.id);
      toast.success(`"${content.title}" deleted`);
      router.push('/content');
    } catch {
      toast.error('Failed to delete content');
    }
  }

  function formatDate(dateStr: string) {
    return new Date(dateStr).toLocaleDateString('en-US', { year: 'numeric', month: 'short', day: 'numeric' });
  }

  function SectionHeader({ label, sectionKey }: { label: string; sectionKey: string }) {
    const expanded = expandedSections[sectionKey];
    return (
      <button type="button" onClick={() => toggleSection(sectionKey)}
        className="flex items-center justify-between w-full text-xs font-semibold uppercase tracking-wider py-2"
        style={{ color: 'var(--muted)' }}
      >
        {label}
        {expanded ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
      </button>
    );
  }

  function InfoRow({ label, value }: { label: string; value: string | null | undefined }) {
    if (!value) return null;
    return (
      <div className="flex items-baseline gap-2">
        <span className="text-xs font-medium capitalize shrink-0" style={{ color: 'var(--muted)' }}>{label}</span>
        <span className="text-sm" style={{ color: 'var(--foreground)' }}>{value}</span>
      </div>
    );
  }

  if (loading) {
    return (
      <div className="min-h-screen" style={{ background: 'var(--background)' }}>
        <div className="px-4 sm:px-6 py-4" style={{ background: 'var(--surface)', borderBottom: '1px solid var(--border)' }}>
          <Skeleton className="h-8 w-48" />
        </div>
        <div className="max-w-3xl mx-auto px-4 sm:px-6 py-8 space-y-6">
          <Skeleton className="h-32 w-full" />
          <Skeleton className="h-32 w-full" />
        </div>
      </div>
    );
  }

  if (notFound || !content) {
    return (
      <div className="flex h-screen flex-col items-center justify-center gap-4" style={{ background: 'var(--background)' }}>
        <p style={{ color: 'var(--muted)' }}>Content not found.</p>
        <Link href="/content" className="text-sm" style={{ color: 'var(--accent)' }}>
          <ArrowLeft size={14} className="inline mr-1" /> Back to Content
        </Link>
      </div>
    );
  }

  return (
    <div className="min-h-screen animate-fadeIn" style={{ background: 'var(--background)' }}>
      <div className="px-4 sm:px-6 py-4 flex items-center justify-between"
        style={{ background: 'var(--surface)', borderBottom: '1px solid var(--border)' }}
      >
        <div className="flex items-center gap-4">
          <Link href="/content" className="flex items-center gap-1 text-sm" style={{ color: 'var(--muted)' }}>
            <ArrowLeft size={16} /> Content
          </Link>
          <h1 className="text-lg font-semibold" style={{ color: 'var(--foreground)' }}>{content.title}</h1>
        </div>
        <div className="flex items-center gap-2">
          {!editing && (
            <button onClick={() => setEditing(true)}
              className="flex items-center gap-1.5 text-sm px-3 py-1.5 rounded-lg"
              style={{ border: '1px solid var(--border)', color: 'var(--muted)', background: 'var(--surface)' }}
            ><Pencil size={14} /> Edit</button>
          )}
          <button onClick={() => setShowDeleteDialog(true)}
            className="flex items-center gap-1.5 text-sm px-3 py-1.5 rounded-lg"
            style={{ border: '1px solid var(--destructive-border)', color: 'var(--destructive)', background: 'var(--surface)' }}
          ><Trash2 size={14} /> Delete</button>
        </div>
      </div>

      <div className="max-w-3xl mx-auto px-4 sm:px-6 py-6 sm:py-8 space-y-6">
        {/* Header Card */}
        <div className="rounded-xl p-5 sm:p-6" style={{ background: 'var(--surface)', border: '1px solid var(--border)' }}>
          <div className="flex items-start gap-3 mb-3">
            <BookOpen size={24} style={{ color: 'var(--accent)' }} className="shrink-0 mt-0.5" />
            <div>
              <h2 className="text-xl font-bold" style={{ color: 'var(--foreground)' }}>{content.title}</h2>
              <div className="flex items-center gap-2 mt-1">
                {content.content_type && (
                  <span className="text-xs font-medium capitalize px-2 py-0.5 rounded-full"
                    style={{ background: 'var(--accent-light)', color: 'var(--accent)' }}
                  >{content.content_type}</span>
                )}
                {content.status && (
                  <span className="text-xs font-medium capitalize px-2 py-0.5 rounded-full"
                    style={{ background: `${statusColor(content.status)}20`, color: statusColor(content.status) }}
                  >{content.status}</span>
                )}
              </div>
              {content.author && (
                <p className="text-sm mt-1" style={{ color: 'var(--muted)' }}>by {content.author}</p>
              )}
            </div>
          </div>

          {content.your_rating != null && (
            <div className="flex items-center gap-2 mt-3">
              <span className="text-xs" style={{ color: 'var(--muted)' }}>Rating</span>
              <div className="w-24 h-2 rounded-full overflow-hidden" style={{ background: 'var(--border)' }}>
                <div className="h-full rounded-full" style={{ width: `${(content.your_rating * 100).toFixed(0)}%`, background: 'var(--accent)' }} />
              </div>
              <span className="text-xs font-medium" style={{ color: 'var(--accent)' }}>{(content.your_rating * 100).toFixed(0)}%</span>
            </div>
          )}

          {content.tags && content.tags.length > 0 && (
            <div className="flex flex-wrap gap-1.5 mt-3">
              {content.tags.map((tag, i) => (
                <span key={i} className="inline-flex items-center px-2 py-0.5 rounded-full text-[11px] font-medium"
                  style={{ background: 'var(--surface-secondary)', color: 'var(--muted)', border: '1px solid var(--border)' }}
                >{tag}</span>
              ))}
            </div>
          )}

          <div className="flex flex-wrap gap-4 mt-3">
            <div>
              <span className="text-xs" style={{ color: 'var(--muted)' }}>Added </span>
              <span className="text-xs font-medium" style={{ color: 'var(--foreground)' }}>{formatDate(content.first_seen)}</span>
            </div>
          </div>
        </div>

        {/* Edit Form */}
        {editing && (
          <div className="rounded-xl p-5 sm:p-6" style={{ background: 'var(--surface)', border: '1px solid var(--border)' }}>
            <h3 className="text-sm font-semibold mb-4 flex items-center gap-2" style={{ color: 'var(--foreground)' }}>
              <Pencil size={14} /> Edit Details
            </h3>
            <form onSubmit={handleSave} className="space-y-2">
              <SectionHeader label="Basic Info" sectionKey="basic" />
              {expandedSections.basic && (
                <div className="space-y-3 pb-3">
                  <div>
                    <label className="block text-xs mb-1" style={{ color: 'var(--muted)' }}>Title</label>
                    <input type="text" value={editForm.title || ''} onChange={e => handleEditChange({ title: e.target.value })}
                      className="w-full rounded-lg px-3.5 py-2.5 text-sm focus:outline-none focus-visible:ring-2"
                      style={{ border: '1px solid var(--input-border)', background: 'var(--input-bg)', color: 'var(--foreground)' }}
                    />
                  </div>
                  <div className="grid grid-cols-2 gap-3">
                    <div>
                      <label className="block text-xs mb-1" style={{ color: 'var(--muted)' }}>Type</label>
                      <select value={editForm.content_type || ''} onChange={e => handleEditChange({ content_type: e.target.value || undefined })}
                        className="w-full rounded-lg px-3.5 py-2.5 text-sm focus:outline-none focus-visible:ring-2"
                        style={{ border: '1px solid var(--input-border)', background: 'var(--input-bg)', color: 'var(--foreground)' }}
                      >
                        <option value="">Not set</option>
                        {TYPE_OPTIONS.map(t => <option key={t} value={t}>{t}</option>)}
                      </select>
                    </div>
                    <div>
                      <label className="block text-xs mb-1" style={{ color: 'var(--muted)' }}>Status</label>
                      <select value={editForm.status || ''} onChange={e => handleEditChange({ status: e.target.value || undefined })}
                        className="w-full rounded-lg px-3.5 py-2.5 text-sm focus:outline-none focus-visible:ring-2"
                        style={{ border: '1px solid var(--input-border)', background: 'var(--input-bg)', color: 'var(--foreground)' }}
                      >
                        <option value="">Not set</option>
                        {STATUS_OPTIONS.map(s => <option key={s} value={s}>{s}</option>)}
                      </select>
                    </div>
                  </div>
                  <div>
                    <label className="block text-xs mb-1" style={{ color: 'var(--muted)' }}>Author</label>
                    <input type="text" value={editForm.author || ''} onChange={e => handleEditChange({ author: e.target.value })}
                      className="w-full rounded-lg px-3.5 py-2.5 text-sm focus:outline-none focus-visible:ring-2"
                      style={{ border: '1px solid var(--input-border)', background: 'var(--input-bg)', color: 'var(--foreground)' }}
                    />
                  </div>
                  <div>
                    <label className="block text-xs mb-1" style={{ color: 'var(--muted)' }}>Tags (comma-separated)</label>
                    <input type="text" value={editForm.tags?.join(', ') || ''}
                      onChange={e => handleEditChange({ tags: e.target.value.split(',').map(s => s.trim()).filter(Boolean) })}
                      className="w-full rounded-lg px-3.5 py-2.5 text-sm focus:outline-none focus-visible:ring-2"
                      style={{ border: '1px solid var(--input-border)', background: 'var(--input-bg)', color: 'var(--foreground)' }}
                    />
                  </div>
                </div>
              )}

              <SectionHeader label="Details" sectionKey="details" />
              {expandedSections.details && (
                <div className="space-y-3 pb-3">
                  <div>
                    <label className="block text-xs mb-1" style={{ color: 'var(--muted)' }}>Source URL</label>
                    <input type="text" value={editForm.source_url || ''} onChange={e => handleEditChange({ source_url: e.target.value })}
                      className="w-full rounded-lg px-3.5 py-2.5 text-sm focus:outline-none focus-visible:ring-2"
                      style={{ border: '1px solid var(--input-border)', background: 'var(--input-bg)', color: 'var(--foreground)' }}
                    />
                  </div>
                  <div>
                    <label className="block text-xs mb-1" style={{ color: 'var(--muted)' }}>Recommended By</label>
                    <input type="text" value={editForm.recommended_by || ''} onChange={e => handleEditChange({ recommended_by: e.target.value })}
                      className="w-full rounded-lg px-3.5 py-2.5 text-sm focus:outline-none focus-visible:ring-2"
                      style={{ border: '1px solid var(--input-border)', background: 'var(--input-bg)', color: 'var(--foreground)' }}
                    />
                  </div>
                  <div>
                    <label className="block text-xs mb-1" style={{ color: 'var(--muted)' }}>Rating (0-1)</label>
                    <input type="number" min="0" max="1" step="0.1" value={editForm.your_rating ?? ''}
                      onChange={e => handleEditChange({ your_rating: e.target.value ? parseFloat(e.target.value) : undefined })}
                      className="w-full rounded-lg px-3.5 py-2.5 text-sm focus:outline-none focus-visible:ring-2"
                      style={{ border: '1px solid var(--input-border)', background: 'var(--input-bg)', color: 'var(--foreground)' }}
                    />
                  </div>
                  <div>
                    <label className="block text-xs mb-1" style={{ color: 'var(--muted)' }}>Personal Notes</label>
                    <textarea value={editForm.personal_notes || ''} onChange={e => handleEditChange({ personal_notes: e.target.value })}
                      rows={4} className="w-full rounded-lg px-3.5 py-2.5 text-sm focus:outline-none focus-visible:ring-2 resize-y"
                      style={{ border: '1px solid var(--input-border)', background: 'var(--input-bg)', color: 'var(--foreground)' }}
                    />
                  </div>
                </div>
              )}

              <div className="flex gap-2 pt-4">
                <button type="submit" disabled={saving || !hasChanges}
                  className="px-4 py-2 rounded-lg text-sm font-medium text-white disabled:opacity-50 active:scale-95"
                  style={{ background: 'var(--accent)' }}
                >{saving ? 'Saving...' : 'Save'}</button>
                <button type="button" onClick={() => { setEditing(false); setHasChanges(false); setEditForm(contentToForm(content)); }}
                  className="px-4 py-2 rounded-lg text-sm"
                  style={{ border: '1px solid var(--border)', color: 'var(--muted)', background: 'var(--surface)' }}
                >Cancel</button>
              </div>
            </form>
          </div>
        )}

        {/* View Mode */}
        {!editing && (
          <>
            {(content.source_url || content.recommended_by) && (
              <div className="rounded-xl p-5 sm:p-6" style={{ background: 'var(--surface)', border: '1px solid var(--border)' }}>
                <h3 className="text-xs font-semibold uppercase tracking-wider mb-3" style={{ color: 'var(--muted)' }}>Details</h3>
                <div className="space-y-1.5">
                  {content.source_url && (
                    <div className="flex items-baseline gap-2">
                      <span className="text-xs font-medium shrink-0" style={{ color: 'var(--muted)' }}>Source</span>
                      <span className="text-sm truncate" style={{ color: 'var(--accent)' }}>{content.source_url}</span>
                    </div>
                  )}
                  <InfoRow label="Recommended By" value={content.recommended_by} />
                </div>
              </div>
            )}

            {content.personal_notes && (
              <div className="rounded-xl p-5 sm:p-6" style={{ background: 'var(--surface)', border: '1px solid var(--border)' }}>
                <h3 className="text-xs font-semibold uppercase tracking-wider mb-3" style={{ color: 'var(--muted)' }}>Personal Notes</h3>
                <p className="text-sm leading-relaxed whitespace-pre-wrap" style={{ color: 'var(--foreground)' }}>{content.personal_notes}</p>
              </div>
            )}
          </>
        )}
      </div>

      <ConfirmDialog
        open={showDeleteDialog}
        title={`Delete "${content.title}"?`}
        message="This action cannot be undone. This content will be permanently removed."
        confirmLabel="Delete"
        destructive
        onConfirm={handleDeleteConfirm}
        onCancel={() => setShowDeleteDialog(false)}
      />
    </div>
  );
}
