'use client';

import { useState, useEffect, useRef } from 'react';
import { useRouter, useParams } from 'next/navigation';
import Link from 'next/link';
import toast from 'react-hot-toast';
import { ArrowLeft, Camera, Pencil, Trash2, User } from 'lucide-react';
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
      setEditForm({
        name: data.name,
        short_bio: data.short_bio || '',
        aliases: data.aliases,
        contacts: data.contacts,
        trust_score: data.trust_score,
      });
    } catch {
      setNotFound(true);
    } finally {
      setLoading(false);
    }
  }

  function handleEditChange(updates: Partial<PersonCreate>) {
    setEditForm(prev => ({ ...prev, ...updates }));
    setHasChanges(true);
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

  if (loading) {
    return (
      <div className="min-h-screen" style={{ background: 'var(--background)' }}>
        <div className="px-4 sm:px-6 py-4" style={{ background: 'var(--surface)', borderBottom: '1px solid var(--border)' }}>
          <Skeleton className="h-8 w-48" />
        </div>
        <div className="max-w-3xl mx-auto px-4 sm:px-6 py-8 space-y-6">
          {/* Profile header skeleton */}
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
              {/* Camera overlay - only in edit mode */}
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

        {/* Edit Form - only in edit mode */}
        {editing && (
          <div
            className="rounded-xl p-5 sm:p-6"
            style={{ background: 'var(--surface)', border: '1px solid var(--border)' }}
          >
            <h3 className="text-sm font-semibold mb-4 flex items-center gap-2" style={{ color: 'var(--foreground)' }}>
              <Pencil size={14} /> Edit Details
            </h3>
            <form onSubmit={handleSave} className="space-y-4">
              <div>
                <label className="block text-xs mb-1" style={{ color: 'var(--muted)' }}>Name</label>
                <input
                  type="text"
                  value={editForm.name || ''}
                  onChange={e => handleEditChange({ name: e.target.value })}
                  className="w-full rounded-lg px-3.5 py-2.5 text-sm focus:outline-none focus-visible:ring-2 transition-colors"
                  style={{ border: '1px solid var(--input-border)', background: 'var(--input-bg)', color: 'var(--foreground)' }}
                  required
                />
              </div>
              <div>
                <label className="block text-xs mb-1" style={{ color: 'var(--muted)' }}>Bio</label>
                <textarea
                  value={editForm.short_bio || ''}
                  onChange={e => handleEditChange({ short_bio: e.target.value })}
                  rows={6}
                  className="w-full rounded-lg px-3.5 py-2.5 text-sm focus:outline-none focus-visible:ring-2 transition-colors resize-y"
                  style={{ border: '1px solid var(--input-border)', background: 'var(--input-bg)', color: 'var(--foreground)', minHeight: '120px' }}
                />
              </div>
              <div>
                <label className="block text-xs mb-1" style={{ color: 'var(--muted)' }}>Aliases (comma-separated)</label>
                <input
                  type="text"
                  value={editForm.aliases?.join(', ') || ''}
                  onChange={e => handleEditChange({
                    aliases: e.target.value.split(',').map(s => s.trim()).filter(Boolean),
                  })}
                  className="w-full rounded-lg px-3.5 py-2.5 text-sm focus:outline-none focus-visible:ring-2 transition-colors"
                  style={{ border: '1px solid var(--input-border)', background: 'var(--input-bg)', color: 'var(--foreground)' }}
                />
              </div>
              <div className="flex gap-2 pt-2">
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
                  onClick={() => { setEditing(false); setHasChanges(false); }}
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

        {/* Bio Card - only in view mode when bio exists */}
        {!editing && person.short_bio && (
          <div
            className="rounded-xl p-5 sm:p-6"
            style={{ background: 'var(--surface)', border: '1px solid var(--border)' }}
          >
            <h3 className="text-xs font-semibold uppercase tracking-wider mb-3" style={{ color: 'var(--muted)' }}>
              About
            </h3>
            <p
              className="text-sm leading-relaxed whitespace-pre-wrap"
              style={{ color: 'var(--foreground)', maxHeight: '320px', overflowY: 'auto' }}
            >
              {person.short_bio}
            </p>
          </div>
        )}

        {/* Contacts Card - only in view mode when contacts exist */}
        {!editing && Object.keys(person.contacts).length > 0 && (
          <div
            className="rounded-xl p-5 sm:p-6"
            style={{ background: 'var(--surface)', border: '1px solid var(--border)' }}
          >
            <h3 className="text-xs font-semibold uppercase tracking-wider mb-3" style={{ color: 'var(--muted)' }}>
              Contacts
            </h3>
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

        {/* Face Upload - only in edit mode */}
        {editing && (
          <div
            className="rounded-xl p-5 sm:p-6"
            style={{ background: 'var(--surface)', border: '1px solid var(--border)' }}
          >
            <h3 className="text-sm font-semibold mb-1 flex items-center gap-2" style={{ color: 'var(--foreground)' }}>
              <Camera size={16} /> Face Photo
            </h3>
            <p className="text-xs mb-4" style={{ color: 'var(--muted)' }}>
              Upload a clear face photo. This enables face identification — you can later upload any photo to identify this person.
            </p>

            {person.face_image_url && (
              <div className="mb-4">
                <img
                  src={`${API_BASE_URL}${person.face_image_url}`}
                  alt={`${person.name}'s face`}
                  className="w-32 h-32 rounded-xl object-cover"
                  style={{ border: '1px solid var(--border)' }}
                />
              </div>
            )}

            <div className="flex items-center gap-3">
              <button
                onClick={() => faceInputRef.current?.click()}
                className="text-sm px-3 py-2 rounded-lg transition-colors focus-visible:ring-2"
                style={{
                  border: '1px solid var(--border)',
                  color: 'var(--muted)',
                  background: 'var(--surface)',
                }}
                aria-label="Choose face photo"
              >
                {faceFile ? faceFile.name : 'Choose photo'}
              </button>
              {faceFile && (
                <button
                  onClick={handleFaceUpload}
                  disabled={faceStatus === 'uploading'}
                  className="px-4 py-2 rounded-lg text-sm font-medium text-white disabled:opacity-50 transition-colors active:scale-95 focus-visible:ring-2"
                  style={{ background: 'var(--accent)' }}
                >
                  {faceStatus === 'uploading' ? 'Uploading...' : 'Upload Face'}
                </button>
              )}
            </div>

            {faceStatus === 'success' && (
              <p className="mt-3 text-sm" style={{ color: 'var(--success)' }}>Face photo stored successfully.</p>
            )}
            {faceStatus === 'error' && (
              <p className="mt-3 text-sm" style={{ color: 'var(--destructive)' }} role="alert">
                {faceError || 'Upload failed. Please try again.'}
              </p>
            )}
            {faceStatus === 'idle' && faceError && (
              <p className="mt-3 text-sm" style={{ color: 'var(--destructive)' }} role="alert">{faceError}</p>
            )}
            <p className="mt-2 text-xs" style={{ color: 'var(--muted-foreground)' }}>JPEG, PNG, or WebP (max 10MB)</p>
          </div>
        )}

        {/* Hidden file input - always available for the camera overlay button */}
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
