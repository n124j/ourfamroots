import React, { useState } from 'react';
import { useTranslation } from 'react-i18next';
import axios from 'axios';
import { PersonAvatar } from '@pages/FamilyTreePage';
import type { ApiPerson } from '@features/tree/types';
import { createRelationship } from './api';
import { relationshipDirectionOptions } from './labels';

function apiErrorMessage(err: unknown, fallback: string): string {
  if (axios.isAxiosError(err)) {
    return (err.response?.data as any)?.detail ?? fallback;
  }
  return err instanceof Error ? err.message : fallback;
}

interface AddRelationshipModalProps {
  treeId: string;
  anchorPersonId: string;
  anchorName: string;
  candidates: ApiPerson[];
  onClose: () => void;
  onAdded: () => void;
}

export function AddRelationshipModal({
  treeId, anchorPersonId, anchorName, candidates, onClose, onAdded,
}: AddRelationshipModalProps) {
  const { t } = useTranslation();
  const directionOptions = relationshipDirectionOptions(t);
  const [directionKey, setDirectionKey] = useState(directionOptions[0].key);
  const [search, setSearch] = useState('');
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [customLabel, setCustomLabel] = useState('');
  const [notes, setNotes] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const direction = directionOptions.find((o) => o.key === directionKey) ?? directionOptions[0];
  const isCustom = direction.relationshipType === 'CUSTOM';

  const filtered = candidates.filter((p) =>
    `${p.displayGivenName} ${p.displaySurname}`.toLowerCase().includes(search.toLowerCase())
  );

  async function handleSubmit() {
    if (!selectedId) return;
    const trimmedLabel = customLabel.trim();
    if (isCustom && !trimmedLabel) {
      setError(t('treeForm.customLabelRequired'));
      return;
    }
    setLoading(true);
    setError('');
    try {
      const person1_id = direction.anchorIsPerson1 ? anchorPersonId : selectedId;
      const person2_id = direction.anchorIsPerson1 ? selectedId : anchorPersonId;
      await createRelationship(treeId, {
        person1_id,
        person2_id,
        relationship_type: direction.relationshipType,
        custom_label: isCustom ? trimmedLabel : null,
        notes: notes.trim() || null,
      });
      onAdded();
    } catch (err) {
      setError(apiErrorMessage(err, t('treeForm.failedToAddRelationship')));
    } finally {
      setLoading(false);
    }
  }

  return (
    <div
      className="fixed inset-0 bg-black/30 z-50 flex items-center justify-center p-4"
      onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}
    >
      <div className="bg-white rounded-2xl shadow-xl w-full max-w-sm p-6">
        <h2 className="font-bold text-slate-900 mb-0.5">{t('treeForm.addRelationship')}</h2>
        {anchorName && <p className="text-xs text-slate-400 mb-4">for {anchorName}</p>}

        <div className="space-y-3">
          <div>
            <label htmlFor="relationship-type" className="block text-xs font-medium text-slate-600 mb-1">{t('treeForm.relationshipType')}</label>
            <select
              id="relationship-type"
              value={directionKey}
              onChange={(e) => { setDirectionKey(e.target.value); setError(''); }}
              className="w-full h-9 px-2 text-sm border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-brand-500"
            >
              {directionOptions.map((o) => (
                <option key={o.key} value={o.key}>{o.label}</option>
              ))}
            </select>
          </div>

          {isCustom && (
            <div>
              <label className="block text-xs font-medium text-slate-600 mb-1">{t('treeForm.customLabel')}</label>
              <input
                type="text"
                value={customLabel}
                onChange={(e) => setCustomLabel(e.target.value)}
                maxLength={100}
                placeholder={t('treeForm.customLabelPlaceholder')}
                className="w-full h-9 px-3 text-sm border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-brand-500"
              />
            </div>
          )}

          <input
            autoFocus
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search by name…"
            className="w-full h-9 px-3 text-sm border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-brand-500"
          />
          <div className="max-h-52 overflow-y-auto rounded-lg border border-slate-200 divide-y divide-slate-100">
            {filtered.length === 0 && (
              <p className="px-3 py-4 text-xs text-slate-400 text-center">
                {candidates.length === 0 ? t('treeForm.noOtherMembers') : t('treeForm.noMatches')}
              </p>
            )}
            {filtered.map((p) => {
              const name = `${p.displayGivenName} ${p.displaySurname}`.trim() || t('treeForm.unknown');
              const isSelected = selectedId === p.id;
              return (
                <button
                  key={p.id}
                  type="button"
                  onClick={() => setSelectedId(p.id)}
                  className={`flex items-center gap-3 w-full px-3 py-2 text-left transition-colors ${
                    isSelected ? 'bg-brand-50' : 'hover:bg-slate-50'
                  }`}
                >
                  <PersonAvatar photoUrl={p.photoUrl} name={name} sex={p.sex} size={28} />
                  <span className={`text-sm flex-1 truncate ${isSelected ? 'text-brand-700 font-medium' : 'text-slate-700'}`}>
                    {name}
                  </span>
                  {isSelected && <span className="text-brand-500 text-xs">✓</span>}
                </button>
              );
            })}
          </div>

          <div>
            <label className="block text-xs font-medium text-slate-600 mb-1">{t('treeForm.notesOptional')}</label>
            <textarea
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              rows={2}
              maxLength={2000}
              className="w-full px-3 py-2 text-sm border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-brand-500 resize-none"
            />
          </div>

          {error && <p className="text-xs text-red-600">{error}</p>}
          <div className="flex gap-2">
            <button
              type="button"
              onClick={onClose}
              className="flex-1 h-9 text-sm border border-slate-300 rounded-lg hover:bg-slate-50"
            >
              {t('treeForm.cancel')}
            </button>
            <button
              type="button"
              onClick={handleSubmit}
              disabled={loading || !selectedId}
              className="flex-1 h-9 text-sm bg-brand-500 text-white rounded-lg hover:bg-brand-600 disabled:opacity-50"
            >
              {loading ? t('treeForm.adding') : t('treeForm.addRelationship')}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
