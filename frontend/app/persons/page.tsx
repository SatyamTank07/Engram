'use client';

import { useState, useEffect, useRef } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { isAuthenticated } from '@/lib/auth';
import {
    Person,
    PersonCreate,
    FaceMatch,
    getPersons,
    createPerson,
    uploadPersonFace,
    identifyPersonFromFace,
} from '@/lib/api';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

function confidenceLabel(score: number): { text: string; color: string } {
    if (score >= 0.85) return { text: 'Strong match', color: 'text-green-600' };
    if (score >= 0.6) return { text: 'Possible match', color: 'text-yellow-600' };
    return { text: 'Weak match', color: 'text-gray-500' };
}

const emptyForm: PersonCreate = { name: '', aliases: [], contacts: {}, short_bio: '', trust_score: 0 };

export default function PersonsPage() {
    const router = useRouter();
    const [persons, setPersons] = useState<Person[]>([]);
    const [loading, setLoading] = useState(true);

    // Add person form
    const [showAddForm, setShowAddForm] = useState(false);
    const [newPerson, setNewPerson] = useState<PersonCreate>(emptyForm);
    const [creating, setCreating] = useState(false);

    // Face identification
    const [identifyResults, setIdentifyResults] = useState<FaceMatch[] | null>(null);
    const [identifying, setIdentifying] = useState(false);
    const [identifyError, setIdentifyError] = useState('');
    const identifyInputRef = useRef<HTMLInputElement>(null);

    // Per-person face upload status
    const [faceUploadStatus, setFaceUploadStatus] = useState<Record<string, 'uploading' | 'done' | 'error'>>({});
    const faceInputRefs = useRef<Record<string, HTMLInputElement | null>>({});

    useEffect(() => {
        if (!isAuthenticated()) {
            router.push('/login');
            return;
        }
        loadPersons();
    }, [router]);

    async function loadPersons() {
        try {
            const data = await getPersons();
            setPersons(data);
        } catch {
            console.error('Failed to load persons');
        } finally {
            setLoading(false);
        }
    }

    async function handleCreatePerson(e: React.FormEvent) {
        e.preventDefault();
        if (!newPerson.name.trim()) return;
        setCreating(true);
        try {
            const created = await createPerson(newPerson);
            setPersons([created, ...persons]);
            setNewPerson(emptyForm);
            setShowAddForm(false);
        } catch (err) {
            console.error('Failed to create person', err);
        } finally {
            setCreating(false);
        }
    }

    async function handleFaceUpload(personId: string, file: File) {
        setFaceUploadStatus(s => ({ ...s, [personId]: 'uploading' }));
        try {
            const result = await uploadPersonFace(personId, file);
            setFaceUploadStatus(s => ({ ...s, [personId]: 'done' }));
            if (result.face_image_url) {
                setPersons(prev => prev.map(p =>
                    p.id === personId ? { ...p, face_image_url: result.face_image_url! } : p
                ));
            }
        } catch {
            setFaceUploadStatus(s => ({ ...s, [personId]: 'error' }));
        }
    }

    async function handleIdentify(file: File) {
        setIdentifying(true);
        setIdentifyError('');
        setIdentifyResults(null);
        try {
            const results = await identifyPersonFromFace(file);
            setIdentifyResults(results);
        } catch {
            setIdentifyError('Failed to identify face. Make sure the backend is running and faces have been uploaded.');
        } finally {
            setIdentifying(false);
        }
    }

    function handleIdentifyDrop(e: React.DragEvent) {
        e.preventDefault();
        const file = e.dataTransfer.files[0];
        if (file) handleIdentify(file);
    }

    if (loading) {
        return (
            <div className="flex h-screen items-center justify-center">
                <div className="text-gray-500">Loading...</div>
            </div>
        );
    }

    return (
        <div className="min-h-screen bg-gray-50">
            {/* Header */}
            <div className="bg-white border-b border-gray-200 px-6 py-4 flex items-center justify-between">
                <div className="flex items-center gap-4">
                    <Link href="/" className="text-gray-500 hover:text-gray-700 transition-colors">
                        ← Chat
                    </Link>
                    <h1 className="text-lg font-semibold text-gray-900">👥 People</h1>
                </div>
                <button
                    onClick={() => setShowAddForm(!showAddForm)}
                    className="bg-blue-500 hover:bg-blue-600 text-white px-4 py-2 rounded-md text-sm transition-colors"
                >
                    {showAddForm ? 'Cancel' : '+ Add Person'}
                </button>
            </div>

            <div className="max-w-3xl mx-auto px-6 py-8 space-y-8">

                {/* Add Person Form */}
                {showAddForm && (
                    <div className="bg-white border border-gray-200 rounded-lg p-6">
                        <h2 className="text-sm font-semibold text-gray-700 mb-4">New Person</h2>
                        <form onSubmit={handleCreatePerson} className="space-y-3">
                            <input
                                type="text"
                                placeholder="Full name *"
                                value={newPerson.name}
                                onChange={e => setNewPerson({ ...newPerson, name: e.target.value })}
                                className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                                required
                            />
                            <input
                                type="text"
                                placeholder="Short bio"
                                value={newPerson.short_bio || ''}
                                onChange={e => setNewPerson({ ...newPerson, short_bio: e.target.value })}
                                className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                            />
                            <input
                                type="text"
                                placeholder="Aliases (comma-separated)"
                                value={newPerson.aliases?.join(', ') || ''}
                                onChange={e => setNewPerson({
                                    ...newPerson,
                                    aliases: e.target.value.split(',').map(s => s.trim()).filter(Boolean),
                                })}
                                className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                            />
                            <button
                                type="submit"
                                disabled={creating}
                                className="bg-blue-500 hover:bg-blue-600 disabled:opacity-50 text-white px-4 py-2 rounded-md text-sm transition-colors"
                            >
                                {creating ? 'Creating...' : 'Create Person'}
                            </button>
                        </form>
                    </div>
                )}

                {/* Face Identification */}
                <div className="bg-white border border-gray-200 rounded-lg p-6">
                    <h2 className="text-sm font-semibold text-gray-700 mb-3">🔍 Face Identification</h2>
                    <p className="text-xs text-gray-500 mb-4">
                        Upload a photo to find out who it is. Only works for people who already have a face photo stored.
                    </p>
                    <div
                        onDrop={handleIdentifyDrop}
                        onDragOver={e => e.preventDefault()}
                        onClick={() => identifyInputRef.current?.click()}
                        className="border-2 border-dashed border-gray-300 hover:border-blue-400 rounded-lg p-8 text-center cursor-pointer transition-colors"
                    >
                        {identifying ? (
                            <p className="text-sm text-gray-500">Identifying...</p>
                        ) : (
                            <p className="text-sm text-gray-500">
                                Drop a photo here or <span className="text-blue-500">click to upload</span>
                            </p>
                        )}
                        <input
                            ref={identifyInputRef}
                            type="file"
                            accept="image/*"
                            className="hidden"
                            onChange={e => { if (e.target.files?.[0]) handleIdentify(e.target.files[0]); }}
                        />
                    </div>

                    {identifyError && (
                        <p className="mt-3 text-sm text-red-500">{identifyError}</p>
                    )}

                    {identifyResults !== null && (
                        <div className="mt-4 space-y-2">
                            {identifyResults.length === 0 ? (
                                <p className="text-sm text-gray-500">No matching faces found.</p>
                            ) : (
                                identifyResults.map(match => {
                                    const label = confidenceLabel(match.confidence_score);
                                    return (
                                        <div key={match.id} className="flex items-center justify-between p-3 bg-gray-50 rounded-md">
                                            <div>
                                                <p className="text-sm font-medium text-gray-900">{match.name}</p>
                                                {match.short_bio && (
                                                    <p className="text-xs text-gray-500 truncate max-w-xs">{match.short_bio}</p>
                                                )}
                                            </div>
                                            <div className="text-right">
                                                <p className={`text-sm font-semibold ${label.color}`}>
                                                    {Math.round(match.confidence_score * 100)}%
                                                </p>
                                                <p className={`text-xs ${label.color}`}>{label.text}</p>
                                            </div>
                                        </div>
                                    );
                                })
                            )}
                        </div>
                    )}
                </div>

                {/* People List */}
                <div>
                    <h2 className="text-sm font-semibold text-gray-700 mb-3">
                        Known People ({persons.length})
                    </h2>

                    {persons.length === 0 ? (
                        <div className="bg-white border border-gray-200 rounded-lg p-8 text-center">
                            <p className="text-gray-500 text-sm">No people added yet.</p>
                            <p className="text-gray-400 text-xs mt-1">
                                Use the chat to tell the AI about someone, or click &ldquo;+ Add Person&rdquo; above.
                            </p>
                        </div>
                    ) : (
                        <div className="space-y-2">
                            {persons.map(person => {
                                const uploadStatus = faceUploadStatus[person.id];
                                return (
                                    <div
                                        key={person.id}
                                        className="bg-white border border-gray-200 rounded-lg p-4 flex items-center justify-between"
                                    >
                                        <div className="flex items-center gap-3 flex-1 min-w-0 mr-4">
                                            {person.face_image_url ? (
                                                <img
                                                    src={`${API_BASE_URL}${person.face_image_url}`}
                                                    alt={person.name}
                                                    className="w-10 h-10 rounded-full object-cover shrink-0"
                                                />
                                            ) : (
                                                <div className="w-10 h-10 rounded-full bg-gray-200 flex items-center justify-center text-gray-400 text-sm shrink-0">
                                                    {person.name.charAt(0).toUpperCase()}
                                                </div>
                                            )}
                                            <div className="min-w-0">
                                            <p className="text-sm font-medium text-gray-900">{person.name}</p>
                                            {person.short_bio && (
                                                <p className="text-xs text-gray-500 truncate">{person.short_bio}</p>
                                            )}
                                            {person.aliases.length > 0 && (
                                                <p className="text-xs text-gray-400">
                                                    aka {person.aliases.join(', ')}
                                                </p>
                                            )}
                                            </div>
                                        </div>

                                        <div className="flex items-center gap-2 shrink-0">
                                            {/* Face upload for this person */}
                                            <button
                                                onClick={() => faceInputRefs.current[person.id]?.click()}
                                                disabled={uploadStatus === 'uploading'}
                                                className="text-xs px-3 py-1.5 border border-gray-300 hover:border-gray-400 rounded-md text-gray-600 hover:text-gray-800 transition-colors disabled:opacity-50"
                                            >
                                                {uploadStatus === 'uploading' ? '⏳ Uploading...'
                                                    : uploadStatus === 'done' ? '✓ Face saved'
                                                    : uploadStatus === 'error' ? '✗ Failed'
                                                    : '📷 Upload Face'}
                                            </button>
                                            <input
                                                type="file"
                                                accept="image/*"
                                                className="hidden"
                                                ref={el => { faceInputRefs.current[person.id] = el; }}
                                                onChange={e => {
                                                    if (e.target.files?.[0]) handleFaceUpload(person.id, e.target.files[0]);
                                                }}
                                            />

                                            <Link
                                                href={`/persons/${person.id}`}
                                                className="text-xs px-3 py-1.5 bg-blue-50 hover:bg-blue-100 text-blue-600 rounded-md transition-colors"
                                            >
                                                View →
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
