'use client';

import { useState, useEffect } from 'react';
import { useRouter, useParams } from 'next/navigation';
import Link from 'next/link';
import toast from 'react-hot-toast';
import { ArrowLeft, Pencil, Trash2, Lightbulb, ChevronDown, ChevronUp } from 'lucide-react';
import { isAuthenticated } from '@/lib/auth';
import ConfirmDialog from '@/components/ConfirmDialog';
import Skeleton from '@/components/Skeleton';
import { Idea, IdeaCreate, getIdea, updateIdea, deleteIdea } from '@/lib/api';

const TYPE_OPTIONS = ['prediction', 'opinion', 'decision', 'question', 'realization', 'hypothesis', 'lesson_learned'];
const STATUS_OPTIONS = ['active', 'validated', 'invalidated', 'evolved', 'abandoned'];

function statusColor(status: string | null): string {
  switch (status) {
    case 'validated': return 'var(--success)';
    case 'invalidated': return 'var(--destructive)';
    case 'evolved': return 'var(--accent)';
    case 'abandoned': return 'var(--muted)';
    default: return 'var(--warning, #f59e0b)';
  }
}

export default function IdeaDetailPage() {
  const router = useRouter();
  const { id } = useParams<{ id: string }>();

  const [idea, setIdea] = useState<Idea | null>(null);
  const [loading, setLoading] = useState(true);
  const [notFound, setNotFound] = useState(false);

  const [editing, setEditing] = useState(false);
  const [editForm, setEditForm] = useState<Partial<IdeaCreate>>({});
  const [saving, setSaving] = useState(false);
  const [hasChanges, setHasChanges] = useState(false);

  const [expandedSections, setExpandedSections] = useState<Record<string, boolean>>({
    basic: true, evidence: false, meta: false,
  });

  const [showDeleteDialog, setShowDeleteDialog] = useState(false);

  useEffect(() => {
    if (!isAuthenticated()) { router.push('/login'); return; }
    loadIdea();
  }, [id, router]);

  async function loadIdea() {
    try {
      const data = await getIdea(id);
      setIdea(data);
      setEditForm(ideaToForm(data));
    } catch {
      setNotFound(true);
    } finally {
      setLoading(false);
    }
  }

  function ideaToForm(i: Idea): Partial<IdeaCreate> {
    return {
      name: i.name,
      idea_type: i.idea_type || '',
      description: i.description || '',
      confidence: i.confidence,
      status: i.status || '',
      evidence_for: i.evidence_for || [],
      evidence_against: i.evidence_against || [],
      date_formed: i.date_formed || '',
      revisit_date: i.revisit_date || '',
      tags: i.tags || [],
      notes: i.notes || '',
    };
  }

  function handleEditChange(updates: Partial<IdeaCreate>) {
    setEditForm(prev => ({ ...prev, ...updates }));
    setHasChanges(true);
  }

  function toggleSection(key: string) {
    setExpandedSections(prev => ({ ...prev, [key]: !prev[key] }));
  }

  async function handleSave(e: React.FormEvent) {
    e.preventDefault();
    if (!idea) return;
    setSaving(true);
    try {
      const updated = await updateIdea(idea.id, editForm);
      setIdea(updated);
      setEditing(false);
      setHasChanges(false);
      toast.success('Idea updated');
    } catch {
      toast.error('Failed to update idea');
    } finally {
      setSaving(false);
    }
  }

  async function handleDeleteConfirm() {
    if (!idea) return;
    setShowDeleteDialog(false);
    try {
      await deleteIdea(idea.id);
      toast.success(`"${idea.name}" deleted`);
      router.push('/ideas');
    } catch {
      toast.error('Failed to delete idea');
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

  if (notFound || !idea) {
    return (
      <div className="flex h-screen flex-col items-center justify-center gap-4" style={{ background: 'var(--background)' }}>
        <p style={{ color: 'var(--muted)' }}>Idea not found.</p>
        <Link href="/ideas" className="text-sm" style={{ color: 'var(--accent)' }}>
          <ArrowLeft size={14} className="inline mr-1" /> Back to Ideas
        </Link>
      </div>
    );
  }

  return (
    <div className="min-h-screen animate-fadeIn" style={{ background: 'var(--background)' }}>
      {/* Header */}
      <div className="px-4 sm:px-6 py-4 flex items-center justify-between"
        style={{ background: 'var(--surface)', borderBottom: '1px solid var(--border)' }}
      >
        <div className="flex items-center gap-4">
          <Link href="/ideas" className="flex items-center gap-1 text-sm" style={{ color: 'var(--muted)' }}>
            <ArrowLeft size={16} /> Ideas
          </Link>
          <h1 className="text-lg font-semibold" style={{ color: 'var(--foreground)' }}>{idea.name}</h1>
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
            <Lightbulb size={24} style={{ color: 'var(--accent)' }} className="shrink-0 mt-0.5" />
            <div>
              <h2 className="text-xl font-bold" style={{ color: 'var(--foreground)' }}>{idea.name}</h2>
              <div className="flex items-center gap-2 mt-1">
                {idea.idea_type && (
                  <span className="text-xs font-medium capitalize px-2 py-0.5 rounded-full"
                    style={{ background: 'var(--accent-light)', color: 'var(--accent)' }}
                  >{idea.idea_type}</span>
                )}
                {idea.status && (
                  <span className="text-xs font-medium capitalize px-2 py-0.5 rounded-full"
                    style={{ background: `${statusColor(idea.status)}20`, color: statusColor(idea.status) }}
                  >{idea.status}</span>
                )}
              </div>
            </div>
          </div>

          {/* Confidence bar */}
          {idea.confidence != null && (
            <div className="flex items-center gap-2 mt-3">
              <span className="text-xs" style={{ color: 'var(--muted)' }}>Confidence</span>
              <div className="w-24 h-2 rounded-full overflow-hidden" style={{ background: 'var(--border)' }}>
                <div className="h-full rounded-full" style={{ width: `${(idea.confidence * 100).toFixed(0)}%`, background: 'var(--accent)' }} />
              </div>
              <span className="text-xs font-medium" style={{ color: 'var(--accent)' }}>{(idea.confidence * 100).toFixed(0)}%</span>
            </div>
          )}

          {idea.tags && idea.tags.length > 0 && (
            <div className="flex flex-wrap gap-1.5 mt-3">
              {idea.tags.map((tag, i) => (
                <span key={i} className="inline-flex items-center px-2 py-0.5 rounded-full text-[11px] font-medium"
                  style={{ background: 'var(--surface-secondary)', color: 'var(--muted)', border: '1px solid var(--border)' }}
                >{tag}</span>
              ))}
            </div>
          )}

          <div className="flex flex-wrap gap-4 mt-3">
            <div>
              <span className="text-xs" style={{ color: 'var(--muted)' }}>First seen </span>
              <span className="text-xs font-medium" style={{ color: 'var(--foreground)' }}>{formatDate(idea.first_seen)}</span>
            </div>
            <div>
              <span className="text-xs" style={{ color: 'var(--muted)' }}>Last seen </span>
              <span className="text-xs font-medium" style={{ color: 'var(--foreground)' }}>{formatDate(idea.last_seen)}</span>
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
                    <label className="block text-xs mb-1" style={{ color: 'var(--muted)' }}>Name</label>
                    <input type="text" value={editForm.name || ''} onChange={e => handleEditChange({ name: e.target.value })}
                      className="w-full rounded-lg px-3.5 py-2.5 text-sm focus:outline-none focus-visible:ring-2"
                      style={{ border: '1px solid var(--input-border)', background: 'var(--input-bg)', color: 'var(--foreground)' }}
                    />
                  </div>
                  <div>
                    <label className="block text-xs mb-1" style={{ color: 'var(--muted)' }}>Description</label>
                    <textarea value={editForm.description || ''} onChange={e => handleEditChange({ description: e.target.value })}
                      rows={4} className="w-full rounded-lg px-3.5 py-2.5 text-sm focus:outline-none focus-visible:ring-2 resize-y"
                      style={{ border: '1px solid var(--input-border)', background: 'var(--input-bg)', color: 'var(--foreground)' }}
                    />
                  </div>
                  <div className="grid grid-cols-2 gap-3">
                    <div>
                      <label className="block text-xs mb-1" style={{ color: 'var(--muted)' }}>Type</label>
                      <select value={editForm.idea_type || ''} onChange={e => handleEditChange({ idea_type: e.target.value || undefined })}
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
                    <label className="block text-xs mb-1" style={{ color: 'var(--muted)' }}>Confidence (0-1)</label>
                    <input type="number" min="0" max="1" step="0.1" value={editForm.confidence ?? ''}
                      onChange={e => handleEditChange({ confidence: e.target.value ? parseFloat(e.target.value) : undefined })}
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

              <SectionHeader label="Evidence" sectionKey="evidence" />
              {expandedSections.evidence && (
                <div className="space-y-3 pb-3">
                  <div>
                    <label className="block text-xs mb-1" style={{ color: 'var(--muted)' }}>Evidence For (one per line)</label>
                    <textarea value={editForm.evidence_for?.join('\n') || ''}
                      onChange={e => handleEditChange({ evidence_for: e.target.value.split('\n').filter(Boolean) })}
                      rows={3} className="w-full rounded-lg px-3.5 py-2.5 text-sm focus:outline-none focus-visible:ring-2 resize-y"
                      style={{ border: '1px solid var(--input-border)', background: 'var(--input-bg)', color: 'var(--foreground)' }}
                    />
                  </div>
                  <div>
                    <label className="block text-xs mb-1" style={{ color: 'var(--muted)' }}>Evidence Against (one per line)</label>
                    <textarea value={editForm.evidence_against?.join('\n') || ''}
                      onChange={e => handleEditChange({ evidence_against: e.target.value.split('\n').filter(Boolean) })}
                      rows={3} className="w-full rounded-lg px-3.5 py-2.5 text-sm focus:outline-none focus-visible:ring-2 resize-y"
                      style={{ border: '1px solid var(--input-border)', background: 'var(--input-bg)', color: 'var(--foreground)' }}
                    />
                  </div>
                </div>
              )}

              <SectionHeader label="Dates & Notes" sectionKey="meta" />
              {expandedSections.meta && (
                <div className="space-y-3 pb-3">
                  <div className="grid grid-cols-2 gap-3">
                    <div>
                      <label className="block text-xs mb-1" style={{ color: 'var(--muted)' }}>Date Formed</label>
                      <input type="text" placeholder="e.g. 2025-01-15" value={editForm.date_formed || ''}
                        onChange={e => handleEditChange({ date_formed: e.target.value })}
                        className="w-full rounded-lg px-3.5 py-2.5 text-sm focus:outline-none focus-visible:ring-2"
                        style={{ border: '1px solid var(--input-border)', background: 'var(--input-bg)', color: 'var(--foreground)' }}
                      />
                    </div>
                    <div>
                      <label className="block text-xs mb-1" style={{ color: 'var(--muted)' }}>Revisit Date</label>
                      <input type="text" placeholder="e.g. 2026-06-01" value={editForm.revisit_date || ''}
                        onChange={e => handleEditChange({ revisit_date: e.target.value })}
                        className="w-full rounded-lg px-3.5 py-2.5 text-sm focus:outline-none focus-visible:ring-2"
                        style={{ border: '1px solid var(--input-border)', background: 'var(--input-bg)', color: 'var(--foreground)' }}
                      />
                    </div>
                  </div>
                  <div>
                    <label className="block text-xs mb-1" style={{ color: 'var(--muted)' }}>Notes</label>
                    <textarea value={editForm.notes || ''} onChange={e => handleEditChange({ notes: e.target.value })}
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
                <button type="button" onClick={() => { setEditing(false); setHasChanges(false); setEditForm(ideaToForm(idea)); }}
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
            {idea.description && (
              <div className="rounded-xl p-5 sm:p-6" style={{ background: 'var(--surface)', border: '1px solid var(--border)' }}>
                <h3 className="text-xs font-semibold uppercase tracking-wider mb-3" style={{ color: 'var(--muted)' }}>Description</h3>
                <p className="text-sm leading-relaxed whitespace-pre-wrap" style={{ color: 'var(--foreground)' }}>{idea.description}</p>
              </div>
            )}

            {(idea.evidence_for.length > 0 || idea.evidence_against.length > 0) && (
              <div className="rounded-xl p-5 sm:p-6" style={{ background: 'var(--surface)', border: '1px solid var(--border)' }}>
                <h3 className="text-xs font-semibold uppercase tracking-wider mb-3" style={{ color: 'var(--muted)' }}>Evidence</h3>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                  {idea.evidence_for.length > 0 && (
                    <div>
                      <span className="text-xs font-medium" style={{ color: 'var(--success)' }}>For</span>
                      <ul className="mt-1 space-y-1">
                        {idea.evidence_for.map((e, i) => (
                          <li key={i} className="flex items-start gap-2 text-sm" style={{ color: 'var(--foreground)' }}>
                            <span className="mt-1.5 w-1.5 h-1.5 rounded-full shrink-0" style={{ background: 'var(--success)' }} />
                            {e}
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}
                  {idea.evidence_against.length > 0 && (
                    <div>
                      <span className="text-xs font-medium" style={{ color: 'var(--destructive)' }}>Against</span>
                      <ul className="mt-1 space-y-1">
                        {idea.evidence_against.map((e, i) => (
                          <li key={i} className="flex items-start gap-2 text-sm" style={{ color: 'var(--foreground)' }}>
                            <span className="mt-1.5 w-1.5 h-1.5 rounded-full shrink-0" style={{ background: 'var(--destructive)' }} />
                            {e}
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}
                </div>
              </div>
            )}

            {(idea.date_formed || idea.revisit_date) && (
              <div className="rounded-xl p-5 sm:p-6" style={{ background: 'var(--surface)', border: '1px solid var(--border)' }}>
                <h3 className="text-xs font-semibold uppercase tracking-wider mb-3" style={{ color: 'var(--muted)' }}>Dates</h3>
                <div className="space-y-1.5">
                  <InfoRow label="Date Formed" value={idea.date_formed} />
                  <InfoRow label="Revisit Date" value={idea.revisit_date} />
                </div>
              </div>
            )}

            {idea.notes && (
              <div className="rounded-xl p-5 sm:p-6" style={{ background: 'var(--surface)', border: '1px solid var(--border)' }}>
                <h3 className="text-xs font-semibold uppercase tracking-wider mb-3" style={{ color: 'var(--muted)' }}>Notes</h3>
                <p className="text-sm leading-relaxed whitespace-pre-wrap" style={{ color: 'var(--foreground)' }}>{idea.notes}</p>
              </div>
            )}
          </>
        )}
      </div>

      <ConfirmDialog
        open={showDeleteDialog}
        title={`Delete "${idea.name}"?`}
        message="This action cannot be undone. This idea will be permanently removed."
        confirmLabel="Delete"
        destructive
        onConfirm={handleDeleteConfirm}
        onCancel={() => setShowDeleteDialog(false)}
      />
    </div>
  );
}
