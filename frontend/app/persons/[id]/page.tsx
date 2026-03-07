'use client';

import { useState, useEffect, useRef } from 'react';
import { useRouter, useParams } from 'next/navigation';
import Link from 'next/link';
import { isAuthenticated } from '@/lib/auth';
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

    // Edit mode
    const [editing, setEditing] = useState(false);
    const [editForm, setEditForm] = useState<Partial<PersonCreate>>({});
    const [saving, setSaving] = useState(false);

    // Face upload
    const [faceFile, setFaceFile] = useState<File | null>(null);
    const [faceStatus, setFaceStatus] = useState<'idle' | 'uploading' | 'success' | 'error'>('idle');
    const [faceError, setFaceError] = useState('');
    const faceInputRef = useRef<HTMLInputElement>(null);

    useEffect(() => {
        if (!isAuthenticated()) {
            router.push('/login');
            return;
        }
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

    async function handleSave(e: React.FormEvent) {
        e.preventDefault();
        if (!person) return;
        setSaving(true);
        try {
            const updated = await updatePerson(person.id, editForm);
            setPerson(updated);
            setEditing(false);
        } catch (err) {
            console.error('Failed to update person', err);
        } finally {
            setSaving(false);
        }
    }

    async function handleDelete() {
        if (!person) return;
        if (!confirm(`Delete ${person.name}? This cannot be undone.`)) return;
        try {
            await deletePerson(person.id);
            router.push('/persons');
        } catch (err) {
            console.error('Failed to delete person', err);
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
            if (result.face_image_url) {
                setPerson({ ...person, face_image_url: result.face_image_url });
            }
        } catch (err: any) {
            setFaceStatus('error');
            setFaceError(err.message);
        }
    }

    function formatDate(dateStr: string) {
        return new Date(dateStr).toLocaleDateString('en-US', {
            year: 'numeric', month: 'short', day: 'numeric',
        });
    }

    if (loading) {
        return (
            <div className="flex h-screen items-center justify-center">
                <div className="text-gray-500">Loading...</div>
            </div>
        );
    }

    if (notFound || !person) {
        return (
            <div className="flex h-screen flex-col items-center justify-center gap-4">
                <p className="text-gray-500">Person not found.</p>
                <Link href="/persons" className="text-blue-500 hover:underline text-sm">← Back to People</Link>
            </div>
        );
    }

    return (
        <div className="min-h-screen bg-gray-50">
            {/* Header */}
            <div className="bg-white border-b border-gray-200 px-6 py-4 flex items-center justify-between">
                <div className="flex items-center gap-4">
                    <Link href="/persons" className="text-gray-500 hover:text-gray-700 transition-colors text-sm">
                        ← People
                    </Link>
                    <h1 className="text-lg font-semibold text-gray-900">{person.name}</h1>
                </div>
                <div className="flex items-center gap-2">
                    {!editing && (
                        <button
                            onClick={() => setEditing(true)}
                            className="text-sm px-3 py-1.5 border border-gray-300 hover:border-gray-400 rounded-md text-gray-600 transition-colors"
                        >
                            Edit
                        </button>
                    )}
                    <button
                        onClick={handleDelete}
                        className="text-sm px-3 py-1.5 border border-red-200 hover:border-red-400 rounded-md text-red-500 hover:text-red-600 transition-colors"
                    >
                        Delete
                    </button>
                </div>
            </div>

            <div className="max-w-2xl mx-auto px-6 py-8 space-y-6">

                {/* Person Info */}
                <div className="bg-white border border-gray-200 rounded-lg p-6">
                    {editing ? (
                        <form onSubmit={handleSave} className="space-y-4">
                            <div>
                                <label className="block text-xs text-gray-500 mb-1">Name</label>
                                <input
                                    type="text"
                                    value={editForm.name || ''}
                                    onChange={e => setEditForm({ ...editForm, name: e.target.value })}
                                    className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                                    required
                                />
                            </div>
                            <div>
                                <label className="block text-xs text-gray-500 mb-1">Bio</label>
                                <textarea
                                    value={editForm.short_bio || ''}
                                    onChange={e => setEditForm({ ...editForm, short_bio: e.target.value })}
                                    rows={3}
                                    className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                                />
                            </div>
                            <div>
                                <label className="block text-xs text-gray-500 mb-1">Aliases (comma-separated)</label>
                                <input
                                    type="text"
                                    value={editForm.aliases?.join(', ') || ''}
                                    onChange={e => setEditForm({
                                        ...editForm,
                                        aliases: e.target.value.split(',').map(s => s.trim()).filter(Boolean),
                                    })}
                                    className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                                />
                            </div>
                            <div className="flex gap-2 pt-2">
                                <button
                                    type="submit"
                                    disabled={saving}
                                    className="bg-blue-500 hover:bg-blue-600 disabled:opacity-50 text-white px-4 py-2 rounded-md text-sm transition-colors"
                                >
                                    {saving ? 'Saving...' : 'Save'}
                                </button>
                                <button
                                    type="button"
                                    onClick={() => setEditing(false)}
                                    className="px-4 py-2 border border-gray-300 rounded-md text-sm text-gray-600 hover:border-gray-400 transition-colors"
                                >
                                    Cancel
                                </button>
                            </div>
                        </form>
                    ) : (
                        <dl className="space-y-3">
                            <div>
                                <dt className="text-xs text-gray-500">Name</dt>
                                <dd className="text-sm font-medium text-gray-900">{person.name}</dd>
                            </div>
                            {person.short_bio && (
                                <div>
                                    <dt className="text-xs text-gray-500">Bio</dt>
                                    <dd className="text-sm text-gray-700">{person.short_bio}</dd>
                                </div>
                            )}
                            {person.aliases.length > 0 && (
                                <div>
                                    <dt className="text-xs text-gray-500">Aliases</dt>
                                    <dd className="text-sm text-gray-700">{person.aliases.join(', ')}</dd>
                                </div>
                            )}
                            {Object.keys(person.contacts).length > 0 && (
                                <div>
                                    <dt className="text-xs text-gray-500">Contacts</dt>
                                    <dd className="text-sm text-gray-700">
                                        {Object.entries(person.contacts).map(([k, v]) => (
                                            <div key={k}>{k}: {v}</div>
                                        ))}
                                    </dd>
                                </div>
                            )}
                            <div className="flex gap-8 pt-2 border-t border-gray-100">
                                <div>
                                    <dt className="text-xs text-gray-500">First seen</dt>
                                    <dd className="text-xs text-gray-600">{formatDate(person.first_seen)}</dd>
                                </div>
                                <div>
                                    <dt className="text-xs text-gray-500">Last seen</dt>
                                    <dd className="text-xs text-gray-600">{formatDate(person.last_seen)}</dd>
                                </div>
                                <div>
                                    <dt className="text-xs text-gray-500">Trust score</dt>
                                    <dd className="text-xs text-gray-600">{(person.trust_score * 100).toFixed(0)}%</dd>
                                </div>
                            </div>
                        </dl>
                    )}
                </div>

                {/* Face Upload */}
                <div className="bg-white border border-gray-200 rounded-lg p-6">
                    <h2 className="text-sm font-semibold text-gray-700 mb-1">📷 Face Photo</h2>
                    <p className="text-xs text-gray-500 mb-4">
                        Upload a clear face photo. This enables face identification — you can later upload any photo to identify this person.
                    </p>

                    {person.face_image_url && (
                        <div className="mb-4">
                            <img
                                src={`${API_BASE_URL}${person.face_image_url}`}
                                alt={`${person.name}'s face`}
                                className="w-32 h-32 rounded-lg object-cover border border-gray-200"
                            />
                        </div>
                    )}

                    <div className="flex items-center gap-3">
                        <button
                            onClick={() => faceInputRef.current?.click()}
                            className="text-sm px-3 py-2 border border-gray-300 hover:border-gray-400 rounded-md text-gray-600 transition-colors"
                        >
                            {faceFile ? faceFile.name : 'Choose photo'}
                        </button>
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
                        {faceFile && (
                            <button
                                onClick={handleFaceUpload}
                                disabled={faceStatus === 'uploading'}
                                className="bg-blue-500 hover:bg-blue-600 disabled:opacity-50 text-white px-4 py-2 rounded-md text-sm transition-colors"
                            >
                                {faceStatus === 'uploading' ? 'Uploading...' : 'Upload Face'}
                            </button>
                        )}
                    </div>

                    {faceStatus === 'success' && (
                        <p className="mt-3 text-sm text-green-600">✓ Face photo stored successfully.</p>
                    )}
                    {faceStatus === 'error' && (
                        <p className="mt-3 text-sm text-red-500">✗ {faceError || 'Upload failed. Please try again.'}</p>
                    )}
                    {faceStatus === 'idle' && faceError && (
                        <p className="mt-3 text-sm text-red-500">{faceError}</p>
                    )}
                    <p className="mt-2 text-xs text-gray-400">JPEG, PNG, or WebP (max 10MB)</p>
                </div>

            </div>
        </div>
    );
}
