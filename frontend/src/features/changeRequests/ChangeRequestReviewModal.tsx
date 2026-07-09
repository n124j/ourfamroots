import React, { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { get, patch } from '@api/client';
import { PersonAvatar } from '@pages/FamilyTreePage';
import axios from 'axios';

interface PersonConnection {
  relation: 'child_of' | 'parent_of' | 'spouse_of';
  with: string;
}

interface PersonDiffEntry {
  id: string;
  display_given_name: string;
  display_surname: string;
  sex: string;
  is_living: boolean;
  is_deceased: boolean;
  photo_url: string | null;
  birth_date?: string | null;
  death_date?: string | null;
  birth_year?: number | null;
  death_year?: number | null;
  born_city?: string | null;
  born_country?: string | null;
  died_city?: string | null;
  died_country?: string | null;
  notes?: string | null;
  connections?: PersonConnection[];
}

export interface ModifiedPersonEntry {
  id: string;
  /** The person's id within the draft tree — used to highlight it on the tree canvas. */
  draft_id: string;
  display_given_name: string;
  display_surname: string;
  changes: Record<string, { before: unknown; after: unknown }>;
}

interface UnionChange {
  parents: string[];
}

interface LinkChange {
  parents: string[];
  child: string;
}

export interface ChangeRequestDiff {
  added_persons: PersonDiffEntry[];
  removed_persons: PersonDiffEntry[];
  modified_persons: ModifiedPersonEntry[];
  relationship_summary: {
    unions_added: number;
    unions_removed: number;
    parent_child_links_added: number;
    parent_child_links_removed: number;
  };
  relationship_changes?: {
    unions_added: UnionChange[];
    unions_removed: UnionChange[];
    links_added: LinkChange[];
    links_removed: LinkChange[];
  };
  draft_tree_id: string;
  change_request_id?: string | null;
  requester_name: string | null;
  message: string | null;
}

const FIELD_LABELS: Record<string, string> = {
  display_given_name: 'First name',
  display_surname: 'Last name',
  sex: 'Sex',
  is_living: 'Living',
  is_deceased: 'Deceased',
  photo_url: 'Photo',
  birth_date: 'Birth date',
  death_date: 'Death date',
  birth_year: 'Birth year',
  death_year: 'Death year',
  born_city: 'Birth city',
  born_country: 'Birth country',
  died_city: 'Death city',
  died_country: 'Death country',
  notes: 'Notes',
};

function fullName(p: { display_given_name: string; display_surname: string }) {
  return `${p.display_given_name} ${p.display_surname}`.trim() || 'Unnamed';
}

function fieldValue(v: unknown): string {
  if (v === null || v === undefined || v === '') return '—';
  if (typeof v === 'boolean') return v ? 'Yes' : 'No';
  return String(v);
}

const RELATION_LABELS: Record<PersonConnection['relation'], string> = {
  child_of: 'Child of',
  parent_of: 'Parent of',
  spouse_of: 'Partner of',
};

function groupConnections(connections: PersonConnection[] | undefined): [string, string[]][] {
  if (!connections || connections.length === 0) return [];
  const map = new Map<string, string[]>();
  for (const c of connections) {
    const list = map.get(c.relation) ?? [];
    list.push(c.with);
    map.set(c.relation, list);
  }
  return Array.from(map.entries());
}

export function apiErrorMessage(err: unknown, fallback: string): string {
  if (axios.isAxiosError(err)) {
    return (err.response?.data as any)?.detail ?? fallback;
  }
  return err instanceof Error ? err.message : fallback;
}

interface Props {
  treeId: string;
  requestId: string;
  onClose: () => void;
  onResolved: () => void;
}

export function ChangeRequestReviewModal({ treeId, requestId, onClose, onResolved }: Props) {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const [decisionNote, setDecisionNote] = useState('');
  const [submitting, setSubmitting] = useState<'approve' | 'deny' | null>(null);
  const [error, setError] = useState('');
  const [showJson, setShowJson] = useState(false);

  const { data: diff, isLoading } = useQuery<ChangeRequestDiff>({
    queryKey: ['change-request-diff', treeId, requestId],
    queryFn: () => get<ChangeRequestDiff>(`/trees/${treeId}/change-requests/${requestId}/diff`),
  });

  async function handleResolve(action: 'approve' | 'deny') {
    setSubmitting(action);
    setError('');
    try {
      await patch(`/trees/${treeId}/change-requests/${requestId}`, {
        action,
        decision_note: decisionNote.trim() || undefined,
      });
      onResolved();
    } catch (err) {
      setError(apiErrorMessage(err, 'Failed to resolve this proposal'));
    } finally {
      setSubmitting(null);
    }
  }

  const rel = diff?.relationship_summary;
  const relParts: string[] = [];
  if (rel) {
    if (rel.unions_added) relParts.push(`+${rel.unions_added} union${rel.unions_added !== 1 ? 's' : ''}`);
    if (rel.unions_removed) relParts.push(`−${rel.unions_removed} union${rel.unions_removed !== 1 ? 's' : ''}`);
    if (rel.parent_child_links_added) relParts.push(`+${rel.parent_child_links_added} parent-child link${rel.parent_child_links_added !== 1 ? 's' : ''}`);
    if (rel.parent_child_links_removed) relParts.push(`−${rel.parent_child_links_removed} parent-child link${rel.parent_child_links_removed !== 1 ? 's' : ''}`);
  }

  const hasChanges = diff && (
    diff.added_persons.length > 0 || diff.removed_persons.length > 0 ||
    diff.modified_persons.length > 0 || relParts.length > 0
  );

  return (
    <div
      className="fixed inset-0 bg-black/30 z-50 flex items-center justify-center p-4"
      onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}
    >
      <div className="bg-white rounded-2xl shadow-xl w-full max-w-2xl max-h-[85vh] flex flex-col">
        <div className="flex items-center justify-between px-6 pt-6 pb-4 border-b border-slate-100">
          <h2 className="font-bold text-slate-900">{t('changeRequest.reviewTitle')}</h2>
          <div className="flex items-center gap-3">
            {diff?.draft_tree_id && (
              <button
                onClick={() => navigate(`/trees/${diff.draft_tree_id}?review=${requestId}`)}
                className="text-xs font-medium text-brand-600 hover:underline"
              >
                {t('changeRequest.viewInTree')}
              </button>
            )}
            <button onClick={onClose} className="text-slate-400 hover:text-slate-700 text-xl leading-none">✕</button>
          </div>
        </div>

        {isLoading ? (
          <div className="flex justify-center py-16">
            <div className="w-7 h-7 border-2 border-brand-500 border-t-transparent rounded-full animate-spin" />
          </div>
        ) : (
          <div className="flex-1 overflow-y-auto min-h-0 px-6 py-4 space-y-5">
            {!hasChanges && (
              <p className="text-sm text-slate-400 text-center py-6">{t('changeRequest.noChanges')}</p>
            )}

            {relParts.length > 0 && (
              <div className="rounded-lg bg-slate-50 border border-slate-200 px-3 py-2 text-xs text-slate-600">
                {t('changeRequest.relationships')}: {relParts.join(', ')}
              </div>
            )}

            {diff && diff.added_persons.length > 0 && (
              <section>
                <h3 className="text-xs font-semibold text-green-700 uppercase tracking-wide mb-2">
                  {t('changeRequest.added')} ({diff.added_persons.length})
                </h3>
                <div className="space-y-1.5">
                  {diff.added_persons.map((p) => (
                    <div key={p.id} className="rounded-lg bg-green-50 border border-green-100 px-3 py-2">
                      <div className="flex items-center gap-3">
                        <PersonAvatar photoUrl={p.photo_url ?? undefined} name={fullName(p)} sex={p.sex} size={28} />
                        <span className="text-sm text-green-800 font-medium">{fullName(p)}</span>
                      </div>
                      {groupConnections(p.connections).length > 0 && (
                        <div className="mt-1 ml-9 space-y-0.5">
                          {groupConnections(p.connections).map(([relation, names]) => (
                            <p key={relation} className="text-xs text-green-700">
                              {RELATION_LABELS[relation as PersonConnection['relation']]}: {names.join(', ')}
                            </p>
                          ))}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              </section>
            )}

            {diff && diff.removed_persons.length > 0 && (
              <section>
                <h3 className="text-xs font-semibold text-red-700 uppercase tracking-wide mb-2">
                  {t('changeRequest.removed')} ({diff.removed_persons.length})
                </h3>
                <div className="space-y-1.5">
                  {diff.removed_persons.map((p) => (
                    <div key={p.id} className="flex items-center gap-3 rounded-lg bg-red-50 border border-red-100 px-3 py-2">
                      <PersonAvatar photoUrl={p.photo_url ?? undefined} name={fullName(p)} sex={p.sex} size={28} />
                      <span className="text-sm text-red-800 font-medium line-through decoration-red-400">{fullName(p)}</span>
                    </div>
                  ))}
                </div>
              </section>
            )}

            {diff && diff.modified_persons.length > 0 && (
              <section>
                <h3 className="text-xs font-semibold text-amber-700 uppercase tracking-wide mb-2">
                  {t('changeRequest.modified')} ({diff.modified_persons.length})
                </h3>
                <div className="space-y-2">
                  {diff.modified_persons.map((p) => (
                    <div key={p.id} className="rounded-lg bg-amber-50 border border-amber-100 px-3 py-2.5">
                      <p className="text-sm font-medium text-amber-900 mb-1.5">{fullName(p)}</p>
                      <div className="space-y-1">
                        {Object.entries(p.changes).map(([field, { before, after }]) => (
                          <div key={field} className="grid grid-cols-[100px_1fr_auto_1fr] items-center gap-2 text-xs">
                            <span className="text-amber-600 font-medium">{FIELD_LABELS[field] ?? field}</span>
                            {field === 'photo_url' ? (
                              <>
                                <span className="text-slate-500">{before ? 'had a photo' : 'no photo'}</span>
                                <span className="text-amber-400">→</span>
                                <span className="text-slate-700">{after ? 'new photo' : 'removed'}</span>
                              </>
                            ) : (
                              <>
                                <span className="text-slate-500 line-through decoration-slate-300 truncate">{fieldValue(before)}</span>
                                <span className="text-amber-400">→</span>
                                <span className="text-slate-800 truncate">{fieldValue(after)}</span>
                              </>
                            )}
                          </div>
                        ))}
                      </div>
                    </div>
                  ))}
                </div>
              </section>
            )}

            {diff && diff.relationship_changes && (
              diff.relationship_changes.unions_added.length > 0 ||
              diff.relationship_changes.unions_removed.length > 0 ||
              diff.relationship_changes.links_added.length > 0 ||
              diff.relationship_changes.links_removed.length > 0
            ) && (
              <section>
                <h3 className="text-xs font-semibold text-slate-500 uppercase tracking-wide mb-2">
                  {t('changeRequest.relationshipChanges')}
                </h3>
                <div className="space-y-1">
                  {diff.relationship_changes.unions_added.map((u, i) => (
                    <p key={`ua-${i}`} className="text-xs text-slate-600">
                      <span className="text-green-600 font-medium">+</span> {u.parents.join(' & ')}
                    </p>
                  ))}
                  {diff.relationship_changes.unions_removed.map((u, i) => (
                    <p key={`ur-${i}`} className="text-xs text-slate-600">
                      <span className="text-red-600 font-medium">−</span> {u.parents.join(' & ')}
                    </p>
                  ))}
                  {diff.relationship_changes.links_added.map((l, i) => (
                    <p key={`la-${i}`} className="text-xs text-slate-600">
                      <span className="text-green-600 font-medium">+</span> {l.parents.join(' & ')} → {l.child}
                    </p>
                  ))}
                  {diff.relationship_changes.links_removed.map((l, i) => (
                    <p key={`lr-${i}`} className="text-xs text-slate-600">
                      <span className="text-red-600 font-medium">−</span> {l.parents.join(' & ')} → {l.child}
                    </p>
                  ))}
                </div>
              </section>
            )}

            {diff && hasChanges && (
              <section>
                <button
                  type="button"
                  onClick={() => setShowJson((v) => !v)}
                  className="text-xs text-slate-400 hover:text-slate-600 underline"
                >
                  {showJson ? t('changeRequest.hideJson') : t('changeRequest.viewJson')}
                </button>
                {showJson && (
                  <pre className="mt-2 max-h-64 overflow-auto rounded-lg bg-slate-900 text-slate-100 text-[11px] p-3">
                    {JSON.stringify(diff, null, 2)}
                  </pre>
                )}
              </section>
            )}
          </div>
        )}

        <div className="px-6 py-4 border-t border-slate-100 space-y-3">
          <textarea
            value={decisionNote}
            onChange={(e) => setDecisionNote(e.target.value)}
            rows={2}
            maxLength={1000}
            placeholder={t('changeRequest.decisionNotePlaceholder')}
            className="w-full px-3 py-2 text-sm border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-brand-500 resize-none"
          />
          {error && <p className="text-xs text-red-600">{error}</p>}
          <div className="flex gap-2">
            <button
              type="button"
              onClick={() => handleResolve('deny')}
              disabled={submitting !== null}
              className="flex-1 h-9 text-sm border border-red-300 text-red-700 rounded-lg hover:bg-red-50 disabled:opacity-50"
            >
              {submitting === 'deny' ? t('changeRequest.denying') : t('changeRequest.deny')}
            </button>
            <button
              type="button"
              onClick={() => handleResolve('approve')}
              disabled={submitting !== null}
              className="flex-1 h-9 text-sm bg-brand-500 text-white rounded-lg hover:bg-brand-600 disabled:opacity-50"
            >
              {submitting === 'approve' ? t('changeRequest.approving') : t('changeRequest.approve')}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
