'use client';

import { useState, useEffect } from 'react';
import { useRouter, useParams } from 'next/navigation';
import Link from 'next/link';
import toast from 'react-hot-toast';
import { ArrowLeft, Pencil, Trash2, Target, ChevronDown, ChevronUp } from 'lucide-react';
import { isAuthenticated } from '@/lib/auth';
import ConfirmDialog from '@/components/ConfirmDialog';
import Skeleton from '@/components/Skeleton';
import { Project, ProjectCreate, getProject, updateProject, deleteProject } from '@/lib/api';

const TYPE_OPTIONS = ['work', 'side_project', 'learning', 'health', 'financial', 'travel', 'creative', 'career'];
const STATUS_OPTIONS = ['idea', 'planned', 'in_progress', 'paused', 'completed', 'abandoned'];

function statusColor(status: string | null): string {
  switch (status) {
    case 'completed': return 'var(--success)';
    case 'in_progress': return 'var(--accent)';
    case 'planned': return 'var(--warning, #f59e0b)';
    case 'paused': return 'var(--muted-foreground)';
    case 'abandoned': return 'var(--muted)';
    case 'idea': return 'var(--accent)';
    default: return 'var(--muted-foreground)';
  }
}

export default function ProjectDetailPage() {
  const router = useRouter();
  const { id } = useParams<{ id: string }>();

  const [project, setProject] = useState<Project | null>(null);
  const [loading, setLoading] = useState(true);
  const [notFound, setNotFound] = useState(false);

  const [editing, setEditing] = useState(false);
  const [editForm, setEditForm] = useState<Partial<ProjectCreate>>({});
  const [saving, setSaving] = useState(false);
  const [hasChanges, setHasChanges] = useState(false);

  const [expandedSections, setExpandedSections] = useState<Record<string, boolean>>({
    basic: true, details: false,
  });

  const [showDeleteDialog, setShowDeleteDialog] = useState(false);

  useEffect(() => {
    if (!isAuthenticated()) { router.push('/login'); return; }
    loadProject();
  }, [id, router]);

  async function loadProject() {
    try {
      const data = await getProject(id);
      setProject(data);
      setEditForm(projectToForm(data));
    } catch {
      setNotFound(true);
    } finally {
      setLoading(false);
    }
  }

  function projectToForm(p: Project): Partial<ProjectCreate> {
    return {
      name: p.name,
      project_type: p.project_type || '',
      status: p.status || '',
      description: p.description || '',
      goal: p.goal || '',
      target_date: p.target_date || '',
      priority: p.priority,
      tags: p.tags || [],
      notes: p.notes || '',
    };
  }

  function handleEditChange(updates: Partial<ProjectCreate>) {
    setEditForm(prev => ({ ...prev, ...updates }));
    setHasChanges(true);
  }

  function toggleSection(key: string) {
    setExpandedSections(prev => ({ ...prev, [key]: !prev[key] }));
  }

  async function handleSave(e: React.FormEvent) {
    e.preventDefault();
    if (!project) return;
    setSaving(true);
    try {
      const updated = await updateProject(project.id, editForm);
      setProject(updated);
      setEditing(false);
      setHasChanges(false);
      toast.success('Project updated');
    } catch {
      toast.error('Failed to update project');
    } finally {
      setSaving(false);
    }
  }

  async function handleDeleteConfirm() {
    if (!project) return;
    setShowDeleteDialog(false);
    try {
      await deleteProject(project.id);
      toast.success(`"${project.name}" deleted`);
      router.push('/projects');
    } catch {
      toast.error('Failed to delete project');
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

  if (notFound || !project) {
    return (
      <div className="flex h-screen flex-col items-center justify-center gap-4" style={{ background: 'var(--background)' }}>
        <p style={{ color: 'var(--muted)' }}>Project not found.</p>
        <Link href="/projects" className="text-sm" style={{ color: 'var(--accent)' }}>
          <ArrowLeft size={14} className="inline mr-1" /> Back to Projects
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
          <Link href="/projects" className="flex items-center gap-1 text-sm" style={{ color: 'var(--muted)' }}>
            <ArrowLeft size={16} /> Projects
          </Link>
          <h1 className="text-lg font-semibold" style={{ color: 'var(--foreground)' }}>{project.name}</h1>
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
            <Target size={24} style={{ color: 'var(--accent)' }} className="shrink-0 mt-0.5" />
            <div>
              <h2 className="text-xl font-bold" style={{ color: 'var(--foreground)' }}>{project.name}</h2>
              <div className="flex items-center gap-2 mt-1">
                {project.project_type && (
                  <span className="text-xs font-medium capitalize px-2 py-0.5 rounded-full"
                    style={{ background: 'var(--accent-light)', color: 'var(--accent)' }}
                  >{project.project_type.replace('_', ' ')}</span>
                )}
                {project.status && (
                  <span className="text-xs font-medium capitalize px-2 py-0.5 rounded-full"
                    style={{ background: `${statusColor(project.status)}20`, color: statusColor(project.status) }}
                  >{project.status.replace('_', ' ')}</span>
                )}
              </div>
            </div>
          </div>

          {project.priority != null && (
            <div className="flex items-center gap-2 mt-3">
              <span className="text-xs" style={{ color: 'var(--muted)' }}>Priority</span>
              <div className="w-24 h-2 rounded-full overflow-hidden" style={{ background: 'var(--border)' }}>
                <div className="h-full rounded-full" style={{ width: `${(project.priority * 100).toFixed(0)}%`, background: 'var(--accent)' }} />
              </div>
              <span className="text-xs font-medium" style={{ color: 'var(--accent)' }}>{(project.priority * 100).toFixed(0)}%</span>
            </div>
          )}

          {project.tags && project.tags.length > 0 && (
            <div className="flex flex-wrap gap-1.5 mt-3">
              {project.tags.map((tag, i) => (
                <span key={i} className="inline-flex items-center px-2 py-0.5 rounded-full text-[11px] font-medium"
                  style={{ background: 'var(--surface-secondary)', color: 'var(--muted)', border: '1px solid var(--border)' }}
                >{tag}</span>
              ))}
            </div>
          )}

          <div className="flex flex-wrap gap-4 mt-3">
            {project.target_date && (
              <div>
                <span className="text-xs" style={{ color: 'var(--muted)' }}>Target </span>
                <span className="text-xs font-medium" style={{ color: 'var(--foreground)' }}>{project.target_date}</span>
              </div>
            )}
            <div>
              <span className="text-xs" style={{ color: 'var(--muted)' }}>Created </span>
              <span className="text-xs font-medium" style={{ color: 'var(--foreground)' }}>{formatDate(project.first_seen)}</span>
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
                      <select value={editForm.project_type || ''} onChange={e => handleEditChange({ project_type: e.target.value || undefined })}
                        className="w-full rounded-lg px-3.5 py-2.5 text-sm focus:outline-none focus-visible:ring-2"
                        style={{ border: '1px solid var(--input-border)', background: 'var(--input-bg)', color: 'var(--foreground)' }}
                      >
                        <option value="">Not set</option>
                        {TYPE_OPTIONS.map(t => <option key={t} value={t}>{t.replace('_', ' ')}</option>)}
                      </select>
                    </div>
                    <div>
                      <label className="block text-xs mb-1" style={{ color: 'var(--muted)' }}>Status</label>
                      <select value={editForm.status || ''} onChange={e => handleEditChange({ status: e.target.value || undefined })}
                        className="w-full rounded-lg px-3.5 py-2.5 text-sm focus:outline-none focus-visible:ring-2"
                        style={{ border: '1px solid var(--input-border)', background: 'var(--input-bg)', color: 'var(--foreground)' }}
                      >
                        <option value="">Not set</option>
                        {STATUS_OPTIONS.map(s => <option key={s} value={s}>{s.replace('_', ' ')}</option>)}
                      </select>
                    </div>
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

              <SectionHeader label="Goal & Timeline" sectionKey="details" />
              {expandedSections.details && (
                <div className="space-y-3 pb-3">
                  <div>
                    <label className="block text-xs mb-1" style={{ color: 'var(--muted)' }}>Goal</label>
                    <textarea value={editForm.goal || ''} onChange={e => handleEditChange({ goal: e.target.value })}
                      rows={3} className="w-full rounded-lg px-3.5 py-2.5 text-sm focus:outline-none focus-visible:ring-2 resize-y"
                      style={{ border: '1px solid var(--input-border)', background: 'var(--input-bg)', color: 'var(--foreground)' }}
                    />
                  </div>
                  <div>
                    <label className="block text-xs mb-1" style={{ color: 'var(--muted)' }}>Target Date</label>
                    <input type="text" placeholder="e.g. 2026-06-01" value={editForm.target_date || ''}
                      onChange={e => handleEditChange({ target_date: e.target.value })}
                      className="w-full rounded-lg px-3.5 py-2.5 text-sm focus:outline-none focus-visible:ring-2"
                      style={{ border: '1px solid var(--input-border)', background: 'var(--input-bg)', color: 'var(--foreground)' }}
                    />
                  </div>
                  <div>
                    <label className="block text-xs mb-1" style={{ color: 'var(--muted)' }}>Priority (0-1)</label>
                    <input type="number" min="0" max="1" step="0.1" value={editForm.priority ?? ''}
                      onChange={e => handleEditChange({ priority: e.target.value ? parseFloat(e.target.value) : undefined })}
                      className="w-full rounded-lg px-3.5 py-2.5 text-sm focus:outline-none focus-visible:ring-2"
                      style={{ border: '1px solid var(--input-border)', background: 'var(--input-bg)', color: 'var(--foreground)' }}
                    />
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
                <button type="button" onClick={() => { setEditing(false); setHasChanges(false); setEditForm(projectToForm(project)); }}
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
            {project.description && (
              <div className="rounded-xl p-5 sm:p-6" style={{ background: 'var(--surface)', border: '1px solid var(--border)' }}>
                <h3 className="text-xs font-semibold uppercase tracking-wider mb-3" style={{ color: 'var(--muted)' }}>Description</h3>
                <p className="text-sm leading-relaxed whitespace-pre-wrap" style={{ color: 'var(--foreground)' }}>{project.description}</p>
              </div>
            )}

            {project.goal && (
              <div className="rounded-xl p-5 sm:p-6" style={{ background: 'var(--surface)', border: '1px solid var(--border)' }}>
                <h3 className="text-xs font-semibold uppercase tracking-wider mb-3" style={{ color: 'var(--muted)' }}>Goal</h3>
                <p className="text-sm leading-relaxed whitespace-pre-wrap" style={{ color: 'var(--foreground)' }}>{project.goal}</p>
              </div>
            )}

            {project.notes && (
              <div className="rounded-xl p-5 sm:p-6" style={{ background: 'var(--surface)', border: '1px solid var(--border)' }}>
                <h3 className="text-xs font-semibold uppercase tracking-wider mb-3" style={{ color: 'var(--muted)' }}>Notes</h3>
                <p className="text-sm leading-relaxed whitespace-pre-wrap" style={{ color: 'var(--foreground)' }}>{project.notes}</p>
              </div>
            )}
          </>
        )}
      </div>

      <ConfirmDialog
        open={showDeleteDialog}
        title={`Delete "${project.name}"?`}
        message="This action cannot be undone. This project will be permanently removed."
        confirmLabel="Delete"
        destructive
        onConfirm={handleDeleteConfirm}
        onCancel={() => setShowDeleteDialog(false)}
      />
    </div>
  );
}
