'use client';

import { useState, useEffect, useRef } from 'react';
import { useRouter, useParams } from 'next/navigation';
import Link from 'next/link';
import toast from 'react-hot-toast';
import { ArrowLeft, Camera, Pencil, Trash2, User, Share2, ChevronDown, ChevronUp } from 'lucide-react';
import { isAuthenticated } from '@/lib/auth';
import ConfirmDialog from '@/components/ConfirmDialog';
import Skeleton from '@/components/Skeleton';
import {
  Person,
  PersonCreate,
  getPerson,
  updatePerson,
  deletePerson,
  uploadPersonFace,
  validateImageFile,
} from '@/lib/api';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

const FREQ_OPTIONS = ['daily', 'weekly', 'monthly', 'quarterly', 'yearly', 'rarely'];
const SCOPE_OPTIONS = ['private', 'public', 'both'];

export default function PersonDetailPage() {
  const router = useRouter();
  const { id } = useParams<{ id: string }>();

  const [person, setPerson] = useState<Person | null>(null);
  const [loading, setLoading] = useState(true);
  const [notFound, setNotFound] = useState(false);

  const [editing, setEditing] = useState(false);
  const [editForm, setEditForm] = useState<Partial<PersonCreate>>({});
  const [saving, setSaving] = useState(false);
  const [hasChanges, setHasChanges] = useState(false);

  // Collapsible sections in edit mode
  const [expandedSections, setExpandedSections] = useState<Record<string, boolean>>({
    basic: true, professional: false, context: false, personality: false,
    social: false, organization: false, publicProfile: false,
  });

  const [faceFile, setFaceFile] = useState<File | null>(null);
  const [faceStatus, setFaceStatus] = useState<'idle' | 'uploading' | 'success' | 'error'>('idle');
  const [faceError, setFaceError] = useState('');
  const faceInputRef = useRef<HTMLInputElement>(null);

  const [showDeleteDialog, setShowDeleteDialog] = useState(false);

  useEffect(() => {
    if (!isAuthenticated()) { router.push('/login'); return; }
    loadPerson();
  }, [id, router]);

  async function loadPerson() {
    try {
      const data = await getPerson(id);
      setPerson(data);
      setEditForm(personToEditForm(data));
    } catch {
      setNotFound(true);
    } finally {
      setLoading(false);
    }
  }

  function personToEditForm(p: Person): Partial<PersonCreate> {
    return {
      name: p.name,
      short_bio: p.short_bio || '',
      aliases: p.aliases,
      contacts: p.contacts,
      trust_score: p.trust_score,
      date_of_birth: p.date_of_birth || '',
      gender: p.gender || '',
      nationality: p.nationality || '',
      languages: p.languages || [],
      occupation: p.occupation || '',
      company: p.company || '',
      location: p.location || '',
      met_through: p.met_through || '',
      met_date: p.met_date || '',
      interaction_frequency: p.interaction_frequency || '',
      emotional_closeness: p.emotional_closeness ?? undefined,
      reliability_score: p.reliability_score ?? undefined,
      interests: p.interests || [],
      personality_traits: p.personality_traits || [],
      communication_style: p.communication_style || '',
      social_media: p.social_media || {},
      important_dates: p.important_dates || {},
      notes: p.notes || '',
      tags: p.tags || [],
      person_scope: p.person_scope || '',
      public_role: p.public_role || '',
      known_for: p.known_for || [],
      public_bio: p.public_bio || '',
    };
  }

  function handleEditChange(updates: Partial<PersonCreate>) {
    setEditForm(prev => ({ ...prev, ...updates }));
    setHasChanges(true);
  }

  function toggleSection(key: string) {
    setExpandedSections(prev => ({ ...prev, [key]: !prev[key] }));
  }

  async function handleSave(e: React.FormEvent) {
    e.preventDefault();
    if (!person) return;
    setSaving(true);
    try {
      const updated = await updatePerson(person.id, editForm);
      setPerson(updated);
      setEditing(false);
      setHasChanges(false);
      toast.success('Person updated');
    } catch {
      toast.error('Failed to update person');
    } finally {
      setSaving(false);
    }
  }

  async function handleDeleteConfirm() {
    if (!person) return;
    setShowDeleteDialog(false);
    try {
      await deletePerson(person.id);
      toast.success(`${person.name} deleted`);
      router.push('/persons');
    } catch {
      toast.error('Failed to delete person');
    }
  }

  function handleFaceSelect(file: File) {
    setFaceError('');
    setFaceStatus('idle');
    try {
      validateImageFile(file);
      setFaceFile(file);
    } catch (err: any) {
      setFaceError(err.message);
    }
  }

  async function handleFaceUpload() {
    if (!person || !faceFile) return;
    setFaceError('');
    setFaceStatus('uploading');
    try {
      const result = await uploadPersonFace(person.id, faceFile);
      setFaceStatus('success');
      setFaceFile(null);
      toast.success('Face photo saved');
      if (result.face_image_url) {
        setPerson({ ...person, face_image_url: result.face_image_url });
      }
    } catch (err: any) {
      setFaceStatus('error');
      setFaceError(err.message);
      toast.error('Face upload failed');
    }
  }

  function formatDate(dateStr: string) {
    return new Date(dateStr).toLocaleDateString('en-US', {
      year: 'numeric', month: 'short', day: 'numeric',
    });
  }

  function getTrustColor(score: number) {
    if (score >= 0.7) return 'var(--success)';
    if (score >= 0.4) return 'var(--warning, #f59e0b)';
    return 'var(--destructive)';
  }

  function SectionHeader({ label, sectionKey }: { label: string; sectionKey: string }) {
    const expanded = expandedSections[sectionKey];
    return (
      <button
        type="button"
        onClick={() => toggleSection(sectionKey)}
        className="flex items-center justify-between w-full text-xs font-semibold uppercase tracking-wider py-2"
        style={{ color: 'var(--muted)' }}
      >
        {label}
        {expanded ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
      </button>
    );
  }

  function InputField({ label, value, onChange, type = 'text', placeholder }: {
    label: string; value: string; onChange: (v: string) => void; type?: string; placeholder?: string;
  }) {
    return (
      <div>
        <label className="block text-xs mb-1" style={{ color: 'var(--muted)' }}>{label}</label>
        <input
          type={type}
          value={value}
          onChange={e => onChange(e.target.value)}
          placeholder={placeholder}
          className="w-full rounded-lg px-3.5 py-2.5 text-sm focus:outline-none focus-visible:ring-2 transition-colors"
          style={{ border: '1px solid var(--input-border)', background: 'var(--input-bg)', color: 'var(--foreground)' }}
        />
      </div>
    );
  }

  // Render pills
  function Pills({ items, color }: { items: string[]; color?: string }) {
    if (!items || items.length === 0) return null;
    return (
      <div className="flex flex-wrap gap-1.5">
        {items.map((item, i) => (
          <span
            key={i}
            className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium"
            style={{ background: color || 'var(--accent-light)', color: color ? 'white' : 'var(--accent)' }}
          >
            {item}
          </span>
        ))}
      </div>
    );
  }

  // View-mode info row
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
          <div className="rounded-xl p-6" style={{ background: 'var(--surface)', border: '1px solid var(--border)' }}>
            <div className="flex flex-col sm:flex-row items-center sm:items-start gap-6">
              <Skeleton className="w-32 h-32 sm:w-36 sm:h-36 rounded-full shrink-0" />
              <div className="flex-1 space-y-3 w-full">
                <Skeleton className="h-7 w-48" />
                <Skeleton className="h-4 w-32" />
                <Skeleton className="h-3 w-64" />
              </div>
            </div>
          </div>
          <Skeleton className="h-32 w-full" />
        </div>
      </div>
    );
  }

  if (notFound || !person) {
    return (
      <div className="flex h-screen flex-col items-center justify-center gap-4" style={{ background: 'var(--background)' }}>
        <p style={{ color: 'var(--muted)' }}>Person not found.</p>
        <Link
          href="/persons"
          className="text-sm transition-colors focus-visible:ring-2"
          style={{ color: 'var(--accent)' }}
        >
          <ArrowLeft size={14} className="inline mr-1" />
          Back to People
        </Link>
      </div>
    );
  }

  const hasProfessionalInfo = person.occupation || person.company || person.location || person.nationality || person.gender || person.date_of_birth;
  const hasContextInfo = person.met_through || person.met_date || person.interaction_frequency || person.emotional_closeness != null || person.reliability_score != null;
  const hasPersonalityInfo = (person.interests && person.interests.length > 0) || (person.personality_traits && person.personality_traits.length > 0) || person.communication_style || (person.languages && person.languages.length > 0);
  const hasSocialMedia = person.social_media && Object.keys(person.social_media).length > 0;
  const hasTags = person.tags && person.tags.length > 0;
  const hasPendingActions = person.pending_actions && person.pending_actions.length > 0;
  const hasPublicProfile = person.person_scope && person.person_scope !== 'private' && (person.public_role || (person.known_for && person.known_for.length > 0) || person.public_bio);
  const hasImportantDates = person.important_dates && Object.keys(person.important_dates).length > 0;

  return (
    <div className="min-h-screen animate-fadeIn" style={{ background: 'var(--background)' }}>
      {/* Header */}
      <div
        className="px-4 sm:px-6 py-4 flex items-center justify-between"
        style={{ background: 'var(--surface)', borderBottom: '1px solid var(--border)' }}
      >
        <div className="flex items-center gap-4">
          <Link
            href="/persons"
            className="flex items-center gap-1 text-sm transition-colors focus-visible:ring-2"
            style={{ color: 'var(--muted)' }}
            aria-label="Back to people list"
          >
            <ArrowLeft size={16} /> People
          </Link>
          <h1 className="text-lg font-semibold" style={{ color: 'var(--foreground)' }}>
            {person.name}
          </h1>
        </div>
        <div className="flex items-center gap-2">
          <Link
            href={`/persons/${id}/connections`}
            className="flex items-center gap-1.5 text-sm px-3 py-1.5 rounded-lg transition-colors focus-visible:ring-2"
            style={{
              border: '1px solid var(--accent-border)',
              color: 'var(--accent)',
              background: 'var(--surface)',
            }}
            aria-label="View connections"
          >
            <Share2 size={14} /> Connections
          </Link>
          {!editing && (
            <button
              onClick={() => setEditing(true)}
              className="flex items-center gap-1.5 text-sm px-3 py-1.5 rounded-lg transition-colors focus-visible:ring-2"
              style={{
                border: '1px solid var(--border)',
                color: 'var(--muted)',
                background: 'var(--surface)',
              }}
              aria-label="Edit person"
            >
              <Pencil size={14} /> Edit
            </button>
          )}
          <button
            onClick={() => setShowDeleteDialog(true)}
            className="flex items-center gap-1.5 text-sm px-3 py-1.5 rounded-lg transition-colors focus-visible:ring-2"
            style={{
              border: '1px solid var(--destructive-border)',
              color: 'var(--destructive)',
              background: 'var(--surface)',
            }}
            aria-label="Delete person"
          >
            <Trash2 size={14} /> Delete
          </button>
        </div>
      </div>

      <div className="max-w-3xl mx-auto px-4 sm:px-6 py-6 sm:py-8 space-y-6">

        {/* Profile Header Card */}
        <div
          className="rounded-xl overflow-hidden"
          style={{ background: 'var(--surface)', border: '1px solid var(--border)' }}
        >
          <div className="flex flex-col sm:flex-row">
            {/* Info - Left Side */}
            <div className="flex-1 p-5 sm:p-6 flex flex-col justify-center order-2 sm:order-1">
              <h2 className="text-xl sm:text-2xl font-bold" style={{ color: 'var(--foreground)' }}>
                {person.name}
              </h2>

              {/* Occupation/Company subtitle */}
              {(person.occupation || person.company) && (
                <p className="text-sm mt-1" style={{ color: 'var(--muted)' }}>
                  {person.occupation}{person.occupation && person.company ? ' at ' : ''}{person.company}
                  {person.location ? ` · ${person.location}` : ''}
                </p>
              )}

              {/* Aliases as pills */}
              {person.aliases.length > 0 && (
                <div className="flex flex-wrap gap-1.5 mt-2">
                  {person.aliases.map((alias, i) => (
                    <span
                      key={i}
                      className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium"
                      style={{ background: 'var(--accent-light)', color: 'var(--accent)' }}
                    >
                      {alias}
                    </span>
                  ))}
                </div>
              )}

              {/* Tags */}
              {hasTags && (
                <div className="flex flex-wrap gap-1.5 mt-2">
                  {person.tags!.map((tag, i) => (
                    <span
                      key={i}
                      className="inline-flex items-center px-2 py-0.5 rounded-full text-[11px] font-medium"
                      style={{ background: 'var(--surface-secondary)', color: 'var(--muted)', border: '1px solid var(--border)' }}
                    >
                      {tag}
                    </span>
                  ))}
                </div>
              )}

              {/* Trust score bar */}
              <div className="mt-4 flex items-center gap-2">
                <span className="text-xs" style={{ color: 'var(--muted)' }}>Trust</span>
                <div
                  className="w-24 h-2 rounded-full overflow-hidden"
                  style={{ background: 'var(--border)' }}
                >
                  <div
                    className="h-full rounded-full transition-all"
                    style={{
                      width: `${(person.trust_score * 100).toFixed(0)}%`,
                      background: getTrustColor(person.trust_score),
                    }}
                  />
                </div>
                <span className="text-xs font-medium" style={{ color: getTrustColor(person.trust_score) }}>
                  {(person.trust_score * 100).toFixed(0)}%
                </span>
              </div>

              {/* Dates */}
              <div className="flex flex-wrap gap-4 mt-3">
                <div>
                  <span className="text-xs" style={{ color: 'var(--muted)' }}>First seen </span>
                  <span className="text-xs font-medium" style={{ color: 'var(--foreground)' }}>{formatDate(person.first_seen)}</span>
                </div>
                <div>
                  <span className="text-xs" style={{ color: 'var(--muted)' }}>Last seen </span>
                  <span className="text-xs font-medium" style={{ color: 'var(--foreground)' }}>{formatDate(person.last_seen)}</span>
                </div>
              </div>
            </div>

            {/* Photo - Right Side */}
            <div className="relative shrink-0 order-1 sm:order-2">
              {person.face_image_url ? (
                <img
                  src={`${API_BASE_URL}${person.face_image_url}`}
                  alt={`${person.name}'s photo`}
                  className="w-full sm:w-56 md:w-64 h-48 sm:h-full object-cover"
                />
              ) : (
                <div
                  className="w-full sm:w-56 md:w-64 h-48 sm:h-full flex items-center justify-center"
                  style={{ background: 'var(--accent-light)' }}
                >
                  <span className="text-6xl font-semibold" style={{ color: 'var(--accent)' }}>
                    {person.name.charAt(0).toUpperCase()}
                  </span>
                </div>
              )}
              {editing && (
                <button
                  onClick={() => faceInputRef.current?.click()}
                  className="absolute bottom-3 right-3 w-9 h-9 rounded-full flex items-center justify-center transition-transform hover:scale-110 focus-visible:ring-2"
                  style={{
                    background: 'var(--accent)',
                    color: 'white',
                    boxShadow: '0 2px 8px rgba(0,0,0,0.2)',
                  }}
                  aria-label="Change face photo"
                  title="Change photo"
                >
                  <Camera size={16} />
                </button>
              )}
            </div>
          </div>
        </div>

        {/* Edit Form */}
        {editing && (
          <div
            className="rounded-xl p-5 sm:p-6"
            style={{ background: 'var(--surface)', border: '1px solid var(--border)' }}
          >
            <h3 className="text-sm font-semibold mb-4 flex items-center gap-2" style={{ color: 'var(--foreground)' }}>
              <Pencil size={14} /> Edit Details
            </h3>
            <form onSubmit={handleSave} className="space-y-2">

              {/* Basic */}
              <SectionHeader label="Basic Info" sectionKey="basic" />
              {expandedSections.basic && (
                <div className="space-y-3 pb-3">
                  <InputField label="Name" value={editForm.name || ''} onChange={v => handleEditChange({ name: v })} />
                  <div>
                    <label className="block text-xs mb-1" style={{ color: 'var(--muted)' }}>Bio</label>
                    <textarea
                      value={editForm.short_bio || ''}
                      onChange={e => handleEditChange({ short_bio: e.target.value })}
                      rows={4}
                      className="w-full rounded-lg px-3.5 py-2.5 text-sm focus:outline-none focus-visible:ring-2 transition-colors resize-y"
                      style={{ border: '1px solid var(--input-border)', background: 'var(--input-bg)', color: 'var(--foreground)' }}
                    />
                  </div>
                  <InputField label="Aliases (comma-separated)" value={editForm.aliases?.join(', ') || ''} onChange={v => handleEditChange({ aliases: v.split(',').map(s => s.trim()).filter(Boolean) })} />
                  <InputField label="Date of Birth" value={editForm.date_of_birth || ''} onChange={v => handleEditChange({ date_of_birth: v })} placeholder="e.g. 1990-03-15" />
                  <InputField label="Gender" value={editForm.gender || ''} onChange={v => handleEditChange({ gender: v })} />
                  <InputField label="Nationality" value={editForm.nationality || ''} onChange={v => handleEditChange({ nationality: v })} />
                  <InputField label="Languages (comma-separated)" value={editForm.languages?.join(', ') || ''} onChange={v => handleEditChange({ languages: v.split(',').map(s => s.trim()).filter(Boolean) })} />
                </div>
              )}

              {/* Professional */}
              <SectionHeader label="Professional" sectionKey="professional" />
              {expandedSections.professional && (
                <div className="space-y-3 pb-3">
                  <InputField label="Occupation" value={editForm.occupation || ''} onChange={v => handleEditChange({ occupation: v })} />
                  <InputField label="Company" value={editForm.company || ''} onChange={v => handleEditChange({ company: v })} />
                  <InputField label="Location" value={editForm.location || ''} onChange={v => handleEditChange({ location: v })} />
                </div>
              )}

              {/* Relationship Context */}
              <SectionHeader label="Relationship Context" sectionKey="context" />
              {expandedSections.context && (
                <div className="space-y-3 pb-3">
                  <InputField label="Met Through" value={editForm.met_through || ''} onChange={v => handleEditChange({ met_through: v })} />
                  <InputField label="Met Date" value={editForm.met_date || ''} onChange={v => handleEditChange({ met_date: v })} placeholder="e.g. 2023-06" />
                  <div>
                    <label className="block text-xs mb-1" style={{ color: 'var(--muted)' }}>Interaction Frequency</label>
                    <select
                      value={editForm.interaction_frequency || ''}
                      onChange={e => handleEditChange({ interaction_frequency: e.target.value || undefined })}
                      className="w-full rounded-lg px-3.5 py-2.5 text-sm focus:outline-none focus-visible:ring-2 transition-colors"
                      style={{ border: '1px solid var(--input-border)', background: 'var(--input-bg)', color: 'var(--foreground)' }}
                    >
                      <option value="">Not set</option>
                      {FREQ_OPTIONS.map(f => <option key={f} value={f}>{f}</option>)}
                    </select>
                  </div>
                </div>
              )}

              {/* Personality */}
              <SectionHeader label="Interests & Traits" sectionKey="personality" />
              {expandedSections.personality && (
                <div className="space-y-3 pb-3">
                  <InputField label="Interests (comma-separated)" value={editForm.interests?.join(', ') || ''} onChange={v => handleEditChange({ interests: v.split(',').map(s => s.trim()).filter(Boolean) })} />
                  <InputField label="Personality Traits (comma-separated)" value={editForm.personality_traits?.join(', ') || ''} onChange={v => handleEditChange({ personality_traits: v.split(',').map(s => s.trim()).filter(Boolean) })} />
                  <InputField label="Communication Style" value={editForm.communication_style || ''} onChange={v => handleEditChange({ communication_style: v })} />
                </div>
              )}

              {/* Social */}
              <SectionHeader label="Social Media" sectionKey="social" />
              {expandedSections.social && (
                <div className="space-y-3 pb-3">
                  <p className="text-xs" style={{ color: 'var(--muted)' }}>Add platform handles (JSON format for now)</p>
                  <textarea
                    value={JSON.stringify(editForm.social_media || {}, null, 2)}
                    onChange={e => {
                      try { handleEditChange({ social_media: JSON.parse(e.target.value) }); } catch {}
                    }}
                    rows={3}
                    className="w-full rounded-lg px-3.5 py-2.5 text-sm font-mono focus:outline-none focus-visible:ring-2 transition-colors resize-y"
                    style={{ border: '1px solid var(--input-border)', background: 'var(--input-bg)', color: 'var(--foreground)' }}
                  />
                  <p className="text-xs" style={{ color: 'var(--muted)' }}>Important Dates (JSON)</p>
                  <textarea
                    value={JSON.stringify(editForm.important_dates || {}, null, 2)}
                    onChange={e => {
                      try { handleEditChange({ important_dates: JSON.parse(e.target.value) }); } catch {}
                    }}
                    rows={3}
                    className="w-full rounded-lg px-3.5 py-2.5 text-sm font-mono focus:outline-none focus-visible:ring-2 transition-colors resize-y"
                    style={{ border: '1px solid var(--input-border)', background: 'var(--input-bg)', color: 'var(--foreground)' }}
                  />
                </div>
              )}

              {/* Organization */}
              <SectionHeader label="Notes & Tags" sectionKey="organization" />
              {expandedSections.organization && (
                <div className="space-y-3 pb-3">
                  <div>
                    <label className="block text-xs mb-1" style={{ color: 'var(--muted)' }}>Notes</label>
                    <textarea
                      value={editForm.notes || ''}
                      onChange={e => handleEditChange({ notes: e.target.value })}
                      rows={4}
                      className="w-full rounded-lg px-3.5 py-2.5 text-sm focus:outline-none focus-visible:ring-2 transition-colors resize-y"
                      style={{ border: '1px solid var(--input-border)', background: 'var(--input-bg)', color: 'var(--foreground)' }}
                    />
                  </div>
                  <InputField label="Tags (comma-separated)" value={editForm.tags?.join(', ') || ''} onChange={v => handleEditChange({ tags: v.split(',').map(s => s.trim()).filter(Boolean) })} />
                </div>
              )}

              {/* Public Profile */}
              <SectionHeader label="Public Profile" sectionKey="publicProfile" />
              {expandedSections.publicProfile && (
                <div className="space-y-3 pb-3">
                  <div>
                    <label className="block text-xs mb-1" style={{ color: 'var(--muted)' }}>Scope</label>
                    <select
                      value={editForm.person_scope || ''}
                      onChange={e => handleEditChange({ person_scope: e.target.value || undefined })}
                      className="w-full rounded-lg px-3.5 py-2.5 text-sm focus:outline-none focus-visible:ring-2 transition-colors"
                      style={{ border: '1px solid var(--input-border)', background: 'var(--input-bg)', color: 'var(--foreground)' }}
                    >
                      <option value="">Not set</option>
                      {SCOPE_OPTIONS.map(s => <option key={s} value={s}>{s}</option>)}
                    </select>
                  </div>
                  <InputField label="Public Role" value={editForm.public_role || ''} onChange={v => handleEditChange({ public_role: v })} />
                  <InputField label="Known For (comma-separated)" value={editForm.known_for?.join(', ') || ''} onChange={v => handleEditChange({ known_for: v.split(',').map(s => s.trim()).filter(Boolean) })} />
                  <div>
                    <label className="block text-xs mb-1" style={{ color: 'var(--muted)' }}>Public Bio</label>
                    <textarea
                      value={editForm.public_bio || ''}
                      onChange={e => handleEditChange({ public_bio: e.target.value })}
                      rows={3}
                      className="w-full rounded-lg px-3.5 py-2.5 text-sm focus:outline-none focus-visible:ring-2 transition-colors resize-y"
                      style={{ border: '1px solid var(--input-border)', background: 'var(--input-bg)', color: 'var(--foreground)' }}
                    />
                  </div>
                </div>
              )}

              <div className="flex gap-2 pt-4">
                <button
                  type="submit"
                  disabled={saving || !hasChanges}
                  className="px-4 py-2 rounded-lg text-sm font-medium text-white disabled:opacity-50 transition-colors active:scale-95 focus-visible:ring-2"
                  style={{ background: 'var(--accent)' }}
                >
                  {saving ? 'Saving...' : 'Save'}
                </button>
                <button
                  type="button"
                  onClick={() => { setEditing(false); setHasChanges(false); setEditForm(personToEditForm(person)); }}
                  className="px-4 py-2 rounded-lg text-sm transition-colors focus-visible:ring-2"
                  style={{
                    border: '1px solid var(--border)',
                    color: 'var(--muted)',
                    background: 'var(--surface)',
                  }}
                >
                  Cancel
                </button>
              </div>
            </form>
          </div>
        )}

        {/* VIEW MODE SECTIONS */}
        {!editing && (
          <>
            {/* Bio */}
            {person.short_bio && (
              <div
                className="rounded-xl p-5 sm:p-6"
                style={{ background: 'var(--surface)', border: '1px solid var(--border)' }}
              >
                <h3 className="text-xs font-semibold uppercase tracking-wider mb-3" style={{ color: 'var(--muted)' }}>About</h3>
                <p className="text-sm leading-relaxed whitespace-pre-wrap" style={{ color: 'var(--foreground)', maxHeight: '320px', overflowY: 'auto' }}>
                  {person.short_bio}
                </p>
              </div>
            )}

            {/* Personal Info */}
            {hasProfessionalInfo && (
              <div
                className="rounded-xl p-5 sm:p-6"
                style={{ background: 'var(--surface)', border: '1px solid var(--border)' }}
              >
                <h3 className="text-xs font-semibold uppercase tracking-wider mb-3" style={{ color: 'var(--muted)' }}>Personal Info</h3>
                <div className="space-y-1.5">
                  <InfoRow label="Occupation" value={person.occupation} />
                  <InfoRow label="Company" value={person.company} />
                  <InfoRow label="Location" value={person.location} />
                  <InfoRow label="Nationality" value={person.nationality} />
                  <InfoRow label="Gender" value={person.gender} />
                  <InfoRow label="Date of Birth" value={person.date_of_birth} />
                </div>
              </div>
            )}

            {/* Relationship Context */}
            {hasContextInfo && (
              <div
                className="rounded-xl p-5 sm:p-6"
                style={{ background: 'var(--surface)', border: '1px solid var(--border)' }}
              >
                <h3 className="text-xs font-semibold uppercase tracking-wider mb-3" style={{ color: 'var(--muted)' }}>Relationship Context</h3>
                <div className="space-y-1.5">
                  <InfoRow label="Met Through" value={person.met_through} />
                  <InfoRow label="Met Date" value={person.met_date} />
                  <InfoRow label="Interaction" value={person.interaction_frequency} />
                  {person.emotional_closeness != null && (
                    <div className="flex items-center gap-2">
                      <span className="text-xs font-medium" style={{ color: 'var(--muted)' }}>Closeness</span>
                      <div className="w-20 h-1.5 rounded-full overflow-hidden" style={{ background: 'var(--border)' }}>
                        <div className="h-full rounded-full" style={{ width: `${(person.emotional_closeness * 100)}%`, background: 'var(--accent)' }} />
                      </div>
                      <span className="text-xs" style={{ color: 'var(--foreground)' }}>{(person.emotional_closeness * 100).toFixed(0)}%</span>
                    </div>
                  )}
                  {person.reliability_score != null && (
                    <div className="flex items-center gap-2">
                      <span className="text-xs font-medium" style={{ color: 'var(--muted)' }}>Reliability</span>
                      <div className="w-20 h-1.5 rounded-full overflow-hidden" style={{ background: 'var(--border)' }}>
                        <div className="h-full rounded-full" style={{ width: `${(person.reliability_score * 100)}%`, background: getTrustColor(person.reliability_score) }} />
                      </div>
                      <span className="text-xs" style={{ color: 'var(--foreground)' }}>{(person.reliability_score * 100).toFixed(0)}%</span>
                    </div>
                  )}
                </div>
              </div>
            )}

            {/* Interests & Traits */}
            {hasPersonalityInfo && (
              <div
                className="rounded-xl p-5 sm:p-6"
                style={{ background: 'var(--surface)', border: '1px solid var(--border)' }}
              >
                <h3 className="text-xs font-semibold uppercase tracking-wider mb-3" style={{ color: 'var(--muted)' }}>Interests & Traits</h3>
                <div className="space-y-3">
                  {person.interests && person.interests.length > 0 && (
                    <div>
                      <span className="text-xs font-medium" style={{ color: 'var(--muted)' }}>Interests</span>
                      <div className="mt-1"><Pills items={person.interests} /></div>
                    </div>
                  )}
                  {person.personality_traits && person.personality_traits.length > 0 && (
                    <div>
                      <span className="text-xs font-medium" style={{ color: 'var(--muted)' }}>Traits</span>
                      <div className="mt-1"><Pills items={person.personality_traits} /></div>
                    </div>
                  )}
                  {person.languages && person.languages.length > 0 && (
                    <div>
                      <span className="text-xs font-medium" style={{ color: 'var(--muted)' }}>Languages</span>
                      <div className="mt-1"><Pills items={person.languages} /></div>
                    </div>
                  )}
                  <InfoRow label="Communication" value={person.communication_style} />
                </div>
              </div>
            )}

            {/* Social Media */}
            {hasSocialMedia && (
              <div
                className="rounded-xl p-5 sm:p-6"
                style={{ background: 'var(--surface)', border: '1px solid var(--border)' }}
              >
                <h3 className="text-xs font-semibold uppercase tracking-wider mb-3" style={{ color: 'var(--muted)' }}>Social Media</h3>
                <div className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-2">
                  {Object.entries(person.social_media!).map(([platform, handle]) => (
                    <div key={platform} className="contents">
                      <span className="text-xs font-medium capitalize" style={{ color: 'var(--muted)' }}>{platform}</span>
                      <span className="text-sm" style={{ color: 'var(--foreground)' }}>{handle}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Important Dates */}
            {hasImportantDates && (
              <div
                className="rounded-xl p-5 sm:p-6"
                style={{ background: 'var(--surface)', border: '1px solid var(--border)' }}
              >
                <h3 className="text-xs font-semibold uppercase tracking-wider mb-3" style={{ color: 'var(--muted)' }}>Important Dates</h3>
                <div className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-2">
                  {Object.entries(person.important_dates!).map(([label, date]) => (
                    <div key={label} className="contents">
                      <span className="text-xs font-medium capitalize" style={{ color: 'var(--muted)' }}>{label}</span>
                      <span className="text-sm" style={{ color: 'var(--foreground)' }}>{date}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Contacts */}
            {Object.keys(person.contacts).length > 0 && (
              <div
                className="rounded-xl p-5 sm:p-6"
                style={{ background: 'var(--surface)', border: '1px solid var(--border)' }}
              >
                <h3 className="text-xs font-semibold uppercase tracking-wider mb-3" style={{ color: 'var(--muted)' }}>Contacts</h3>
                <div className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-2">
                  {Object.entries(person.contacts).map(([key, value]) => (
                    <div key={key} className="contents">
                      <span className="text-xs font-medium capitalize" style={{ color: 'var(--muted)' }}>{key}</span>
                      <span className="text-sm" style={{ color: 'var(--foreground)' }}>{value}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Notes */}
            {person.notes && (
              <div
                className="rounded-xl p-5 sm:p-6"
                style={{ background: 'var(--surface)', border: '1px solid var(--border)' }}
              >
                <h3 className="text-xs font-semibold uppercase tracking-wider mb-3" style={{ color: 'var(--muted)' }}>Notes</h3>
                <p className="text-sm leading-relaxed whitespace-pre-wrap" style={{ color: 'var(--foreground)' }}>
                  {person.notes}
                </p>
              </div>
            )}

            {/* Pending Actions */}
            {hasPendingActions && (
              <div
                className="rounded-xl p-5 sm:p-6"
                style={{ background: 'var(--surface)', border: '1px solid var(--border)' }}
              >
                <h3 className="text-xs font-semibold uppercase tracking-wider mb-3" style={{ color: 'var(--muted)' }}>Pending Actions</h3>
                <ul className="space-y-1.5">
                  {person.pending_actions!.map((action, i) => (
                    <li key={i} className="flex items-start gap-2 text-sm" style={{ color: 'var(--foreground)' }}>
                      <span className="mt-1 w-1.5 h-1.5 rounded-full shrink-0" style={{ background: 'var(--warning)' }} />
                      {action}
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {/* Public Profile */}
            {hasPublicProfile && (
              <div
                className="rounded-xl p-5 sm:p-6"
                style={{ background: 'var(--surface)', border: '1px solid var(--border)' }}
              >
                <h3 className="text-xs font-semibold uppercase tracking-wider mb-3" style={{ color: 'var(--muted)' }}>Public Profile</h3>
                <div className="space-y-2">
                  <InfoRow label="Role" value={person.public_role} />
                  {person.known_for && person.known_for.length > 0 && (
                    <div>
                      <span className="text-xs font-medium" style={{ color: 'var(--muted)' }}>Known For</span>
                      <div className="mt-1"><Pills items={person.known_for} /></div>
                    </div>
                  )}
                  {person.public_bio && (
                    <p className="text-sm leading-relaxed whitespace-pre-wrap mt-2" style={{ color: 'var(--foreground)' }}>
                      {person.public_bio}
                    </p>
                  )}
                </div>
              </div>
            )}
          </>
        )}

        {/* Face upload status messages */}
        {editing && (faceFile || faceStatus !== 'idle' || faceError) && (
          <div
            className="rounded-xl p-4"
            style={{ background: 'var(--surface)', border: '1px solid var(--border)' }}
          >
            {faceFile && (
              <div className="flex items-center gap-3">
                <span className="text-sm" style={{ color: 'var(--foreground)' }}>{faceFile.name}</span>
                <button
                  onClick={handleFaceUpload}
                  disabled={faceStatus === 'uploading'}
                  className="px-4 py-1.5 rounded-lg text-sm font-medium text-white disabled:opacity-50 transition-colors active:scale-95 focus-visible:ring-2"
                  style={{ background: 'var(--accent)' }}
                >
                  {faceStatus === 'uploading' ? 'Uploading...' : 'Upload Face'}
                </button>
              </div>
            )}
            {faceStatus === 'success' && (
              <p className="text-sm" style={{ color: 'var(--success)' }}>Face photo stored successfully.</p>
            )}
            {faceStatus === 'error' && (
              <p className="text-sm" style={{ color: 'var(--destructive)' }} role="alert">
                {faceError || 'Upload failed. Please try again.'}
              </p>
            )}
            {faceStatus === 'idle' && faceError && (
              <p className="text-sm" style={{ color: 'var(--destructive)' }} role="alert">{faceError}</p>
            )}
          </div>
        )}

        <input
          ref={faceInputRef}
          type="file"
          accept="image/jpeg,image/png,image/webp"
          className="hidden"
          onChange={e => {
            if (e.target.files?.[0]) handleFaceSelect(e.target.files[0]);
            e.target.value = '';
          }}
        />
      </div>

      <ConfirmDialog
        open={showDeleteDialog}
        title={`Delete ${person.name}?`}
        message="This action cannot be undone. All data associated with this person will be permanently removed."
        confirmLabel="Delete"
        destructive
        onConfirm={handleDeleteConfirm}
        onCancel={() => setShowDeleteDialog(false)}
      />
    </div>
  );
}
