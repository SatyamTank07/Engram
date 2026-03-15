'use client';

import { useState, useEffect, useRef } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import toast from 'react-hot-toast';
import { ArrowLeft, Users, Search, Upload, UserPlus, Share2 } from 'lucide-react';
import { isAuthenticated } from '@/lib/auth';
import Skeleton from '@/components/Skeleton';
import {
  Person,
  PersonCreate,
  FaceIdentifyResponse,
  getPersons,
  createPerson,
  uploadPersonFace,
  identifyPersonFromFace,
  validateImageFile,
} from '@/lib/api';
import FaceOverlay from '@/components/FaceOverlay';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

function confidenceLabel(score: number): { text: string; color: string } {
  if (score >= 0.85) return { text: 'Strong match', color: 'var(--success)' };
  if (score >= 0.6) return { text: 'Possible match', color: 'var(--warning)' };
  return { text: 'Weak match', color: 'var(--muted)' };
}

const emptyForm: PersonCreate = { name: '', aliases: [], contacts: {}, short_bio: '', trust_score: 0 };

export default function PersonsPage() {
  const router = useRouter();
  const [persons, setPersons] = useState<Person[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');

  const [showAddForm, setShowAddForm] = useState(false);
  const [newPerson, setNewPerson] = useState<PersonCreate>(emptyForm);
  const [creating, setCreating] = useState(false);
  const [nameError, setNameError] = useState(false);

  const [identifyResults, setIdentifyResults] = useState<FaceIdentifyResponse | null>(null);
  const [identifying, setIdentifying] = useState(false);
  const [identifyError, setIdentifyError] = useState('');
  const [identifyImageUrl, setIdentifyImageUrl] = useState<string | null>(null);
  const [highlightedFace, setHighlightedFace] = useState<number | null>(null);
  const identifyInputRef = useRef<HTMLInputElement>(null);

  const [faceUploadStatus, setFaceUploadStatus] = useState<Record<string, 'uploading' | 'done' | 'error'>>({});
  const [faceUploadError, setFaceUploadError] = useState<Record<string, string>>({});
  const faceInputRefs = useRef<Record<string, HTMLInputElement | null>>({});

  useEffect(() => {
    if (!isAuthenticated()) { router.push('/login'); return; }
    loadPersons();
  }, [router]);

  async function loadPersons() {
    try {
      const data = await getPersons();
      setPersons(data);
    } catch {
      toast.error('Failed to load people');
    } finally {
      setLoading(false);
    }
  }

  async function handleCreatePerson(e: React.FormEvent) {
    e.preventDefault();
    if (!newPerson.name.trim()) { setNameError(true); return; }
    setNameError(false);
    setCreating(true);
    try {
      const created = await createPerson(newPerson);
      setPersons([created, ...persons]);
      setNewPerson(emptyForm);
      setShowAddForm(false);
      toast.success(`${created.name} added`);
    } catch {
      toast.error('Failed to create person');
    } finally {
      setCreating(false);
    }
  }

  async function handleFaceUpload(personId: string, file: File) {
    try { validateImageFile(file); } catch (err: any) {
      setFaceUploadError(s => ({ ...s, [personId]: err.message }));
      setFaceUploadStatus(s => ({ ...s, [personId]: 'error' }));
      return;
    }
    setFaceUploadError(s => ({ ...s, [personId]: '' }));
    setFaceUploadStatus(s => ({ ...s, [personId]: 'uploading' }));
    try {
      const result = await uploadPersonFace(personId, file);
      setFaceUploadStatus(s => ({ ...s, [personId]: 'done' }));
      toast.success('Face photo saved');
      if (result.face_image_url) {
        setPersons(prev => prev.map(p =>
          p.id === personId ? { ...p, face_image_url: result.face_image_url! } : p
        ));
      }
    } catch (err: any) {
      setFaceUploadStatus(s => ({ ...s, [personId]: 'error' }));
      setFaceUploadError(s => ({ ...s, [personId]: err.message }));
      toast.error('Face upload failed');
    }
  }

  async function handleIdentify(file: File) {
    setIdentifyError('');
    try { validateImageFile(file); } catch (err: any) { setIdentifyError(err.message); return; }
    setIdentifying(true);
    setIdentifyResults(null);
    setHighlightedFace(null);
    const previewUrl = URL.createObjectURL(file);
    setIdentifyImageUrl(previewUrl);
    try {
      const results = await identifyPersonFromFace(file);
      setIdentifyResults(results);
    } catch {
      setIdentifyError('Failed to identify face. Make sure the backend is running and faces have been uploaded.');
      setIdentifyImageUrl(null);
      toast.error('Face identification failed');
    } finally {
      setIdentifying(false);
    }
  }

  function handleIdentifyDrop(e: React.DragEvent) {
    e.preventDefault();
    const file = e.dataTransfer.files[0];
    if (file) handleIdentify(file);
  }

  const filteredPersons = persons.filter(p => {
    const q = searchQuery.toLowerCase();
    return p.name.toLowerCase().includes(q) ||
      p.aliases.some(a => a.toLowerCase().includes(q)) ||
      (p.short_bio || '').toLowerCase().includes(q);
  });

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
      {/* Header */}
      <div
        className="px-4 sm:px-6 py-4 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3"
        style={{ background: 'var(--surface)', borderBottom: '1px solid var(--border)' }}
      >
        <div className="flex items-center gap-4">
          <Link
            href="/"
            className="flex items-center gap-1 text-sm transition-colors focus-visible:ring-2"
            style={{ color: 'var(--muted)' }}
            aria-label="Back to chat"
          >
            <ArrowLeft size={16} /> Chat
          </Link>
          <h1 className="text-lg font-semibold flex items-center gap-2" style={{ color: 'var(--foreground)' }}>
            <Users size={20} /> People
          </h1>
        </div>
        <button
          onClick={() => setShowAddForm(!showAddForm)}
          className="flex items-center justify-center gap-1.5 px-4 py-2 rounded-lg text-sm font-medium text-white transition-colors active:scale-95 focus-visible:ring-2"
          style={{ background: 'var(--accent)' }}
        >
          {showAddForm ? 'Cancel' : <><UserPlus size={16} /> Add Person</>}
        </button>
      </div>

      <div className="max-w-3xl mx-auto px-4 sm:px-6 py-6 sm:py-8 space-y-6 sm:space-y-8">

        {/* Add Person Form */}
        {showAddForm && (
          <div
            className="rounded-xl p-5 sm:p-6 animate-scaleIn"
            style={{ background: 'var(--surface)', border: '1px solid var(--border)' }}
          >
            <h2 className="text-sm font-semibold mb-4" style={{ color: 'var(--foreground)' }}>New Person</h2>
            <form onSubmit={handleCreatePerson} className="space-y-3">
              <input
                type="text"
                placeholder="Full name *"
                value={newPerson.name}
                onChange={e => { setNewPerson({ ...newPerson, name: e.target.value }); setNameError(false); }}
                className="w-full rounded-lg px-3.5 py-2.5 text-sm focus:outline-none focus-visible:ring-2 transition-colors"
                style={{
                  border: `1px solid ${nameError ? 'var(--destructive)' : 'var(--input-border)'}`,
                  background: 'var(--input-bg)',
                  color: 'var(--foreground)',
                }}
                required
                aria-invalid={nameError}
              />
              {nameError && (
                <p className="text-xs" style={{ color: 'var(--destructive)' }} role="alert">Name is required</p>
              )}
              <input
                type="text"
                placeholder="Short bio"
                value={newPerson.short_bio || ''}
                onChange={e => setNewPerson({ ...newPerson, short_bio: e.target.value })}
                className="w-full rounded-lg px-3.5 py-2.5 text-sm focus:outline-none focus-visible:ring-2 transition-colors"
                style={{ border: '1px solid var(--input-border)', background: 'var(--input-bg)', color: 'var(--foreground)' }}
              />
              <input
                type="text"
                placeholder="Aliases (comma-separated)"
                value={newPerson.aliases?.join(', ') || ''}
                onChange={e => setNewPerson({
                  ...newPerson,
                  aliases: e.target.value.split(',').map(s => s.trim()).filter(Boolean),
                })}
                className="w-full rounded-lg px-3.5 py-2.5 text-sm focus:outline-none focus-visible:ring-2 transition-colors"
                style={{ border: '1px solid var(--input-border)', background: 'var(--input-bg)', color: 'var(--foreground)' }}
              />
              <button
                type="submit"
                disabled={creating}
                className="px-4 py-2.5 rounded-lg text-sm font-medium text-white disabled:opacity-50 transition-colors active:scale-95 focus-visible:ring-2"
                style={{ background: 'var(--accent)' }}
              >
                {creating ? 'Creating...' : 'Create Person'}
              </button>
            </form>
          </div>
        )}

        {/* Face Identification */}
        <div
          className="rounded-xl p-5 sm:p-6"
          style={{ background: 'var(--surface)', border: '1px solid var(--border)' }}
        >
          <h2 className="text-sm font-semibold mb-1 flex items-center gap-2" style={{ color: 'var(--foreground)' }}>
            <Search size={16} /> Face Identification
          </h2>
          <p className="text-xs mb-4" style={{ color: 'var(--muted)' }}>
            Upload a photo to find out who it is. Only works for people who already have a face photo stored.
          </p>
          <div
            onDrop={handleIdentifyDrop}
            onDragOver={e => e.preventDefault()}
            onClick={() => identifyInputRef.current?.click()}
            className="border-2 border-dashed rounded-xl p-6 sm:p-8 text-center cursor-pointer transition-colors"
            style={{ borderColor: 'var(--border)' }}
            role="button"
            aria-label="Upload photo for face identification"
            tabIndex={0}
            onKeyDown={e => { if (e.key === 'Enter') identifyInputRef.current?.click(); }}
          >
            {identifying ? (
              <p className="text-sm" style={{ color: 'var(--muted)' }}>Identifying...</p>
            ) : (
              <>
                <Upload size={24} className="mx-auto mb-2" style={{ color: 'var(--muted-foreground)' }} />
                <p className="text-sm" style={{ color: 'var(--muted)' }}>
                  Drop a photo here or <span style={{ color: 'var(--accent)' }}>click to upload</span>
                </p>
                <p className="text-xs mt-1" style={{ color: 'var(--muted-foreground)' }}>JPEG, PNG, or WebP (max 10MB)</p>
              </>
            )}
            <input
              ref={identifyInputRef}
              type="file"
              accept="image/jpeg,image/png,image/webp"
              className="hidden"
              onChange={e => { if (e.target.files?.[0]) handleIdentify(e.target.files[0]); }}
            />
          </div>

          {identifyError && (
            <p className="mt-3 text-sm" style={{ color: 'var(--destructive)' }} role="alert">{identifyError}</p>
          )}

          {identifyResults !== null && (
            <div className="mt-4 space-y-4 animate-slideInUp">
              {identifyResults.faces_detected === 0 ? (
                <p className="text-sm" style={{ color: 'var(--muted)' }}>No faces detected in the image.</p>
              ) : (
                <>
                  <div className="flex items-center gap-2 text-sm">
                    <span className="font-medium" style={{ color: 'var(--foreground)' }}>
                      {identifyResults.faces_detected} face{identifyResults.faces_detected !== 1 ? 's' : ''} detected
                    </span>
                    <span style={{ color: 'var(--muted-foreground)' }}>—</span>
                    <span style={{ color: 'var(--success)' }}>
                      {identifyResults.faces.filter(f => f.match_status === 'matched').length} identified
                    </span>
                    <span style={{ color: 'var(--warning)' }}>
                      {identifyResults.faces.filter(f => f.match_status === 'unknown').length} unknown
                    </span>
                  </div>

                  {identifyImageUrl && (
                    <FaceOverlay
                      imageSrc={identifyImageUrl}
                      faces={identifyResults.faces}
                      highlightedFace={highlightedFace}
                      onFaceHover={setHighlightedFace}
                    />
                  )}

                  <div className="space-y-2">
                    {identifyResults.faces.map(face => {
                      const isHighlighted = highlightedFace === face.face_index;
                      return (
                        <div
                          key={face.face_index}
                          onMouseEnter={() => setHighlightedFace(face.face_index)}
                          onMouseLeave={() => setHighlightedFace(null)}
                          className="p-3 rounded-lg transition-all duration-150"
                          style={{
                            border: `1px solid ${isHighlighted ? 'var(--accent-border)' : 'var(--border)'}`,
                            background: isHighlighted ? 'var(--accent-light)' : 'var(--surface-secondary)',
                            boxShadow: isHighlighted ? 'var(--shadow-sm)' : 'none',
                          }}
                        >
                          <div className="flex items-center justify-between">
                            <div className="flex items-center gap-2">
                              <span
                                className="inline-flex items-center justify-center w-5 h-5 rounded-full text-[10px] font-bold text-white"
                                style={{ background: face.match_status === 'matched' ? 'var(--success)' : 'var(--warning)' }}
                              >
                                {face.face_index + 1}
                              </span>
                              {face.match_status === 'matched' && face.matches.length > 0 ? (
                                <div>
                                  <p className="text-sm font-medium" style={{ color: 'var(--foreground)' }}>
                                    {face.matches[0].name}
                                  </p>
                                  {face.matches[0].short_bio && (
                                    <p className="text-xs truncate max-w-xs" style={{ color: 'var(--muted)' }}>
                                      {face.matches[0].short_bio}
                                    </p>
                                  )}
                                </div>
                              ) : (
                                <p className="text-sm font-medium" style={{ color: 'var(--warning)' }}>Unknown person</p>
                              )}
                            </div>
                            <div className="flex items-center gap-3">
                              {face.match_status === 'matched' && face.matches.length > 0 && (
                                <div className="text-right">
                                  {(() => {
                                    const label = confidenceLabel(face.matches[0].confidence_score);
                                    return (
                                      <>
                                        <p className="text-sm font-semibold" style={{ color: label.color }}>
                                          {Math.round(face.matches[0].confidence_score * 100)}%
                                        </p>
                                        <p className="text-xs" style={{ color: label.color }}>{label.text}</p>
                                      </>
                                    );
                                  })()}
                                </div>
                              )}
                              {face.match_status === 'unknown' && (
                                <button
                                  onClick={() => { setShowAddForm(true); window.scrollTo({ top: 0, behavior: 'smooth' }); }}
                                  className="text-xs px-2 py-1 rounded transition-colors"
                                  style={{
                                    background: 'var(--warning-light)',
                                    color: 'var(--warning)',
                                  }}
                                >
                                  + Add Person
                                </button>
                              )}
                            </div>
                          </div>

                          {face.matches.length > 1 && (
                            <div className="mt-2 pl-7 space-y-1">
                              <p className="text-[10px] uppercase tracking-wide" style={{ color: 'var(--muted-foreground)' }}>Other possible matches</p>
                              {face.matches.slice(1).map(match => {
                                const label = confidenceLabel(match.confidence_score);
                                return (
                                  <div key={match.id} className="flex items-center justify-between text-xs">
                                    <span style={{ color: 'var(--muted)' }}>{match.name}</span>
                                    <span style={{ color: label.color }}>
                                      {Math.round(match.confidence_score * 100)}%
                                    </span>
                                  </div>
                                );
                              })}
                            </div>
                          )}
                        </div>
                      );
                    })}
                  </div>
                </>
              )}
            </div>
          )}
        </div>

        {/* Search People */}
        <div className="relative">
          <Search
            size={14}
            className="absolute left-3 top-1/2 -translate-y-1/2"
            style={{ color: 'var(--muted-foreground)' }}
          />
          <input
            type="text"
            placeholder="Search people..."
            value={searchQuery}
            onChange={e => setSearchQuery(e.target.value)}
            className="w-full pl-8 pr-3 py-2.5 rounded-lg text-sm focus:outline-none focus-visible:ring-2 transition-colors"
            style={{
              background: 'var(--input-bg)',
              border: '1px solid var(--border)',
              color: 'var(--foreground)',
            }}
            aria-label="Search people by name, alias, or bio"
          />
        </div>

        {/* People List */}
        <div>
          <h2 className="text-sm font-semibold mb-3" style={{ color: 'var(--foreground)' }}>
            Known People ({filteredPersons.length})
          </h2>

          {filteredPersons.length === 0 ? (
            <div
              className="rounded-xl p-8 text-center animate-fadeIn"
              style={{ background: 'var(--surface)', border: '1px solid var(--border)' }}
            >
              <UserPlus size={32} className="mx-auto mb-2" style={{ color: 'var(--muted-foreground)' }} />
              <p className="text-sm" style={{ color: 'var(--muted)' }}>
                {searchQuery ? 'No matching people found' : 'No people added yet.'}
              </p>
              {!searchQuery && (
                <p className="text-xs mt-1" style={{ color: 'var(--muted-foreground)' }}>
                  Use the chat to tell the AI about someone, or click &ldquo;Add Person&rdquo; above.
                </p>
              )}
            </div>
          ) : (
            <div className="space-y-2">
              {filteredPersons.map(person => {
                const uploadStatus = faceUploadStatus[person.id];
                const uploadError = faceUploadError[person.id];
                return (
                  <div
                    key={person.id}
                    className="rounded-xl p-4 flex flex-col sm:flex-row sm:items-center justify-between gap-3 transition-shadow hover:shadow-md"
                    style={{
                      background: 'var(--surface)',
                      border: '1px solid var(--border)',
                      boxShadow: 'var(--shadow-sm)',
                    }}
                  >
                    <div className="flex items-center gap-3 flex-1 min-w-0">
                      {person.face_image_url ? (
                        <img
                          src={`${API_BASE_URL}${person.face_image_url}`}
                          alt={person.name}
                          className="w-10 h-10 rounded-full object-cover shrink-0"
                        />
                      ) : (
                        <div
                          className="w-10 h-10 rounded-full flex items-center justify-center text-sm font-medium shrink-0"
                          style={{ background: 'var(--accent-light)', color: 'var(--accent)' }}
                        >
                          {person.name.charAt(0).toUpperCase()}
                        </div>
                      )}
                      <div className="min-w-0">
                        <p className="text-sm font-medium" style={{ color: 'var(--foreground)' }}>{person.name}</p>
                        {person.short_bio && (
                          <p className="text-xs truncate" style={{ color: 'var(--muted)' }}>{person.short_bio}</p>
                        )}
                        {person.aliases.length > 0 && (
                          <p className="text-xs" style={{ color: 'var(--muted-foreground)' }}>
                            aka {person.aliases.join(', ')}
                          </p>
                        )}
                        {uploadStatus === 'error' && uploadError && (
                          <p className="text-xs" style={{ color: 'var(--destructive)' }} role="alert">{uploadError}</p>
                        )}
                      </div>
                    </div>

                    <div className="flex items-center gap-2 shrink-0 sm:ml-4">
                      <Link
                        href={`/persons/${person.id}/connections`}
                        className="text-xs px-3 py-1.5 rounded-lg transition-colors focus-visible:ring-2 flex items-center gap-1"
                        style={{
                          border: '1px solid var(--border)',
                          color: 'var(--muted)',
                          background: 'var(--surface)',
                        }}
                        title="View connections"
                      >
                        <Share2 size={12} /> Connections
                      </Link>
                      <Link
                        href={`/persons/${person.id}`}
                        className="text-xs px-3 py-1.5 rounded-lg transition-colors focus-visible:ring-2"
                        style={{
                          background: 'var(--accent-light)',
                          color: 'var(--accent)',
                        }}
                      >
                        View
                      </Link>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
