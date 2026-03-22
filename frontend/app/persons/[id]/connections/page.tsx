'use client';

import { useState, useEffect } from 'react';
import { useRouter, useParams } from 'next/navigation';
import Link from 'next/link';
import toast from 'react-hot-toast';
import { ArrowLeft, Share2, X, ExternalLink } from 'lucide-react';
import { isAuthenticated } from '@/lib/auth';
import Skeleton from '@/components/Skeleton';
import ConnectionsGraph from '@/components/ConnectionsGraph';
import { Person, PersonConnectionsResponse, getPersonConnections, getPerson } from '@/lib/api';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

function getTrustColor(score: number) {
  if (score >= 0.7) return 'var(--success)';
  if (score >= 0.4) return 'var(--warning, #f59e0b)';
  return 'var(--destructive)';
}

function formatDate(dateStr: string) {
  return new Date(dateStr).toLocaleDateString('en-US', {
    year: 'numeric', month: 'short', day: 'numeric',
  });
}

export default function PersonConnectionsPage() {
  const router = useRouter();
  const { id } = useParams<{ id: string }>();

  const [data, setData] = useState<PersonConnectionsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);

  // Side panel state
  const [selectedPerson, setSelectedPerson] = useState<Person | null>(null);
  const [selectedRelationship, setSelectedRelationship] = useState<string | null>(null);
  const [panelLoading, setPanelLoading] = useState(false);

  useEffect(() => {
    if (!isAuthenticated()) { router.push('/login'); return; }
    loadConnections();
  }, [id, router]);

  async function loadConnections() {
    try {
      const result = await getPersonConnections(id);
      setData(result);
    } catch {
      setError(true);
      toast.error('Failed to load connections');
    } finally {
      setLoading(false);
    }
  }

  async function handlePersonClick(personId: string) {
    // Fetch full person data and show in side panel
    setPanelLoading(true);
    setSelectedRelationship(null);
    try {
      const person = await getPerson(personId);
      setSelectedPerson(person);

      // Find the relationship type for this person (if not the center)
      if (personId !== id && data) {
        const conn = data.connections.find(c => c.person.id === personId);
        setSelectedRelationship(conn?.relationship || null);
      }
    } catch {
      toast.error('Failed to load person details');
    } finally {
      setPanelLoading(false);
    }
  }

  if (loading) {
    return (
      <div className="min-h-screen flex flex-col" style={{ background: 'var(--background)' }}>
        <div className="px-4 sm:px-6 py-4" style={{ background: 'var(--surface)', borderBottom: '1px solid var(--border)' }}>
          <Skeleton className="h-8 w-48" />
        </div>
        <div className="flex-1 flex items-center justify-center">
          <div className="text-center space-y-3">
            <div
              className="w-12 h-12 rounded-full mx-auto animate-spin"
              style={{ border: '3px solid var(--border)', borderTopColor: 'var(--accent)' }}
            />
            <p className="text-sm" style={{ color: 'var(--muted)' }}>Loading connections...</p>
          </div>
        </div>
      </div>
    );
  }

  if (error || !data?.person) {
    return (
      <div className="flex h-screen flex-col items-center justify-center gap-4" style={{ background: 'var(--background)' }}>
        <p style={{ color: 'var(--muted)' }}>
          {error ? 'Failed to load connections.' : 'Person not found.'}
        </p>
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

  const panelOpen = selectedPerson !== null || panelLoading;

  return (
    <div className="h-screen flex flex-col animate-fadeIn" style={{ background: 'var(--background)' }}>
      {/* Header */}
      <div
        className="px-4 sm:px-6 py-3 flex items-center justify-between shrink-0"
        style={{ background: 'var(--surface)', borderBottom: '1px solid var(--border)' }}
      >
        <div className="flex items-center gap-4">
          <Link
            href={`/persons/${id}`}
            className="flex items-center gap-1 text-sm transition-colors focus-visible:ring-2"
            style={{ color: 'var(--muted)' }}
            aria-label="Back to person detail"
          >
            <ArrowLeft size={16} /> {data.person.name}
          </Link>
          <h1 className="text-lg font-semibold flex items-center gap-2" style={{ color: 'var(--foreground)' }}>
            <Share2 size={18} /> Connections
          </h1>
        </div>
        <span
          className="text-xs px-2.5 py-1 rounded-full font-medium"
          style={{ background: 'var(--accent-light)', color: 'var(--accent)' }}
        >
          {data.connections.length} connection{data.connections.length !== 1 ? 's' : ''}
        </span>
      </div>

      {/* Graph + Side Panel */}
      <div className="flex-1 min-h-0 flex relative">
        {/* Graph */}
        <div className="flex-1 min-w-0">
          <ConnectionsGraph data={data} onPersonClick={handlePersonClick} />
        </div>

        {/* Mobile: backdrop overlay */}
        {panelOpen && (
          <div
            className="sm:hidden fixed inset-0 z-40 bg-black/40 transition-opacity"
            onClick={() => setSelectedPerson(null)}
          />
        )}

        {/* Profile Side Panel — mobile: bottom sheet overlay, desktop: inline side panel */}
        <div
          className={[
            'overflow-y-auto transition-all duration-300 ease-in-out',
            // Mobile: fixed bottom sheet
            'fixed inset-x-0 bottom-0 z-50 rounded-t-2xl max-h-[85vh]',
            // Desktop: inline side panel
            'sm:relative sm:inset-auto sm:z-auto sm:rounded-none sm:max-h-none sm:shrink-0',
            panelOpen ? 'translate-y-0 sm:translate-y-0 sm:border-l' : 'translate-y-full sm:translate-y-0',
          ].join(' ')}
          style={{
            background: 'var(--surface)',
            borderColor: 'var(--border)',
          }}
        >
          {/* Desktop width handled via inner content + sm:w-[360px] */}
          <div className={panelOpen ? 'w-full sm:w-[360px]' : 'w-0 sm:w-0 overflow-hidden'}>
            {panelLoading && (
              <div className="p-5 space-y-4">
                <Skeleton className="h-48 w-full" />
                <Skeleton className="h-6 w-40" />
                <Skeleton className="h-4 w-full" />
                <Skeleton className="h-4 w-3/4" />
              </div>
            )}

            {selectedPerson && !panelLoading && (
              <div>
                {/* Panel Header */}
                <div
                  className="px-4 py-3 flex items-center justify-between sticky top-0 z-10"
                  style={{ background: 'var(--surface)', borderBottom: '1px solid var(--border)' }}
                >
                  {/* Mobile drag handle */}
                  <div className="absolute top-1.5 left-1/2 -translate-x-1/2 sm:hidden">
                    <div className="w-10 h-1 rounded-full" style={{ background: 'var(--border)' }} />
                  </div>
                  <span className="text-sm font-semibold truncate" style={{ color: 'var(--foreground)' }}>
                    Profile
                  </span>
                  <button
                    onClick={() => setSelectedPerson(null)}
                    className="p-1 rounded-md hover:opacity-70 transition-opacity"
                    style={{ color: 'var(--muted)' }}
                    aria-label="Close panel"
                  >
                    <X size={16} />
                  </button>
                </div>

                {/* Photo */}
                {selectedPerson.face_image_url ? (
                  <img
                    src={`${API_BASE_URL}${selectedPerson.face_image_url}`}
                    alt={`${selectedPerson.name}'s photo`}
                    className="w-full h-48 object-cover"
                  />
                ) : (
                  <div
                    className="w-full h-48 flex items-center justify-center"
                    style={{ background: 'var(--accent-light)' }}
                  >
                    <span className="text-5xl font-semibold" style={{ color: 'var(--accent)' }}>
                      {selectedPerson.name.charAt(0).toUpperCase()}
                    </span>
                  </div>
                )}

                <div className="p-4 space-y-4">
                  {/* Name + Relationship badge */}
                  <div>
                    <h3 className="text-lg font-bold" style={{ color: 'var(--foreground)' }}>
                      {selectedPerson.name}
                    </h3>
                    {selectedPerson.aliases.length > 0 && (
                      <div className="flex flex-wrap gap-1.5 mt-1.5">
                        {selectedPerson.aliases.map((alias, i) => (
                          <span
                            key={i}
                            className="inline-flex items-center px-2 py-0.5 rounded-full text-[11px] font-medium"
                            style={{ background: 'var(--accent-light)', color: 'var(--accent)' }}
                          >
                            {alias}
                          </span>
                        ))}
                      </div>
                    )}
                    {selectedRelationship && (
                      <span
                        className="inline-flex items-center gap-1.5 mt-2 px-2.5 py-1 rounded-full text-xs font-medium"
                        style={{ background: 'var(--accent-light)', color: 'var(--accent)' }}
                      >
                        {selectedRelationship.replace(/_/g, ' ')}
                      </span>
                    )}
                  </div>

                  {/* Trust score */}
                  <div className="flex items-center gap-2">
                    <span className="text-xs" style={{ color: 'var(--muted)' }}>Trust</span>
                    <div
                      className="flex-1 h-2 rounded-full overflow-hidden"
                      style={{ background: 'var(--border)' }}
                    >
                      <div
                        className="h-full rounded-full transition-all"
                        style={{
                          width: `${(selectedPerson.trust_score * 100).toFixed(0)}%`,
                          background: getTrustColor(selectedPerson.trust_score),
                        }}
                      />
                    </div>
                    <span className="text-xs font-medium" style={{ color: getTrustColor(selectedPerson.trust_score) }}>
                      {(selectedPerson.trust_score * 100).toFixed(0)}%
                    </span>
                  </div>

                  {/* Occupation / Company */}
                  {(selectedPerson.occupation || selectedPerson.company || selectedPerson.location) && (
                    <div className="space-y-1">
                      {(selectedPerson.occupation || selectedPerson.company) && (
                        <p className="text-sm" style={{ color: 'var(--muted)' }}>
                          {selectedPerson.occupation}{selectedPerson.occupation && selectedPerson.company ? ' at ' : ''}{selectedPerson.company}
                        </p>
                      )}
                      {selectedPerson.location && (
                        <p className="text-xs" style={{ color: 'var(--muted-foreground)' }}>{selectedPerson.location}</p>
                      )}
                    </div>
                  )}

                  {/* Tags */}
                  {selectedPerson.tags && selectedPerson.tags.length > 0 && (
                    <div className="flex flex-wrap gap-1">
                      {selectedPerson.tags.map((tag, i) => (
                        <span
                          key={i}
                          className="inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-medium"
                          style={{ background: 'var(--surface-secondary)', color: 'var(--muted)', border: '1px solid var(--border)' }}
                        >
                          {tag}
                        </span>
                      ))}
                    </div>
                  )}

                  {/* Relationship properties */}
                  {selectedRelationship && data && (() => {
                    const conn = data.connections.find(c => c.person.id === selectedPerson.id);
                    const props = conn?.properties || {};
                    const hasProps = Object.keys(props).some(k => k !== 'created_at' && props[k]);
                    if (!hasProps) return null;
                    return (
                      <div>
                        <h4 className="text-[11px] font-semibold uppercase tracking-wider mb-1.5" style={{ color: 'var(--muted)' }}>
                          Relationship Details
                        </h4>
                        <div className="space-y-1">
                          {props.strength && (
                            <div className="flex items-center gap-2">
                              <span className="text-[11px]" style={{ color: 'var(--muted)' }}>Strength</span>
                              <div className="flex-1 h-1.5 rounded-full overflow-hidden" style={{ background: 'var(--border)' }}>
                                <div className="h-full rounded-full" style={{ width: `${Number(props.strength) * 100}%`, background: 'var(--accent)' }} />
                              </div>
                              <span className="text-[10px]" style={{ color: 'var(--foreground)' }}>{(Number(props.strength) * 100).toFixed(0)}%</span>
                            </div>
                          )}
                          {props.context && (
                            <div className="flex items-baseline gap-2">
                              <span className="text-[11px] font-medium shrink-0" style={{ color: 'var(--muted)' }}>Context</span>
                              <span className="text-xs" style={{ color: 'var(--foreground)' }}>{props.context}</span>
                            </div>
                          )}
                          {props.started_at && (
                            <div className="flex items-baseline gap-2">
                              <span className="text-[11px] font-medium shrink-0" style={{ color: 'var(--muted)' }}>Since</span>
                              <span className="text-xs" style={{ color: 'var(--foreground)' }}>{props.started_at}</span>
                            </div>
                          )}
                          {props.notes && (
                            <div className="flex items-baseline gap-2">
                              <span className="text-[11px] font-medium shrink-0" style={{ color: 'var(--muted)' }}>Notes</span>
                              <span className="text-xs" style={{ color: 'var(--foreground)' }}>{props.notes}</span>
                            </div>
                          )}
                        </div>
                      </div>
                    );
                  })()}

                  {/* Bio */}
                  {selectedPerson.short_bio && (
                    <div>
                      <h4 className="text-[11px] font-semibold uppercase tracking-wider mb-1.5" style={{ color: 'var(--muted)' }}>
                        About
                      </h4>
                      <p
                        className="text-sm leading-relaxed whitespace-pre-wrap"
                        style={{ color: 'var(--foreground)' }}
                      >
                        {selectedPerson.short_bio}
                      </p>
                    </div>
                  )}

                  {/* Contacts */}
                  {Object.keys(selectedPerson.contacts).length > 0 && (
                    <div>
                      <h4 className="text-[11px] font-semibold uppercase tracking-wider mb-1.5" style={{ color: 'var(--muted)' }}>
                        Contacts
                      </h4>
                      <div className="space-y-1.5">
                        {Object.entries(selectedPerson.contacts).map(([key, value]) => (
                          <div key={key} className="flex items-baseline gap-2">
                            <span className="text-[11px] font-medium capitalize shrink-0" style={{ color: 'var(--muted)' }}>{key}</span>
                            <span className="text-sm truncate" style={{ color: 'var(--foreground)' }}>{value}</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Dates */}
                  <div className="flex gap-4">
                    <div>
                      <span className="text-[11px]" style={{ color: 'var(--muted)' }}>First seen </span>
                      <span className="text-[11px] font-medium" style={{ color: 'var(--foreground)' }}>{formatDate(selectedPerson.first_seen)}</span>
                    </div>
                    <div>
                      <span className="text-[11px]" style={{ color: 'var(--muted)' }}>Last seen </span>
                      <span className="text-[11px] font-medium" style={{ color: 'var(--foreground)' }}>{formatDate(selectedPerson.last_seen)}</span>
                    </div>
                  </div>

                  {/* View full profile link */}
                  <Link
                    href={`/persons/${selectedPerson.id}`}
                    className="flex items-center justify-center gap-1.5 w-full py-2.5 rounded-lg text-sm font-medium transition-colors hover:opacity-90"
                    style={{ background: 'var(--accent)', color: 'white' }}
                  >
                    <ExternalLink size={14} /> View Full Profile
                  </Link>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
