/**
 * FamilyTreePage — full-screen canvas route.
 *
 * Route: /trees/:treeId
 */

import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { SEO } from '@shared/components/SEO';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { TreeCanvas, type TreeCanvasHandle } from '@features/tree/canvas/TreeCanvas';
import { useThemeStore, THEME_PRESETS, PRESET_LABEL, type CanvasTheme } from '@store/theme.store';
import { AVATAR_PRESETS, isPreset, presetDataUri } from '@features/tree/avatarPresets';
import { useCanvasStore, type SelectedEdge } from '@store/canvas.store';
import { useAuthStore } from '@store/auth.store';
import { queryKeys } from '@queries/keys';
import { apiClient, get, post, patch, del } from '@api/client';
import axios from 'axios';
import type { ApiTreeGraph } from '@features/tree/types';
import { AuditLogModal } from '@features/audit/AuditLogModal';

/** Extracts the backend's `detail` message from an axios error, falling back otherwise. */
function apiErrorMessage(err: unknown, fallback: string): string {
  if (axios.isAxiosError(err)) {
    return (err.response?.data as any)?.detail ?? fallback;
  }
  return err instanceof Error ? err.message : fallback;
}

async function fetchTreeGraph(treeId: string): Promise<ApiTreeGraph> {
  return get<ApiTreeGraph>(`/trees/${treeId}/graph`);
}

async function createPerson(
  treeId: string,
  fields: PersonFields,
): Promise<string> {
  if (!fields.givenName.trim() && !fields.surname.trim()) {
    throw new Error('Please enter at least a first name or last name.');
  }
  const body: Record<string, unknown> = {
    given_name:  fields.givenName,
    surname:     fields.surname,
    sex:         fields.sex,
    is_living:   fields.isLiving,
    is_deceased: !fields.isLiving,
  };
  if (fields.birthDate)      body.birth_date       = fields.birthDate;
  if (fields.deathDate)      body.death_date       = fields.deathDate;
  if (fields.birthYear)      body.birth_year       = parseInt(fields.birthYear, 10);
  if (fields.deathYear)      body.death_year       = parseInt(fields.deathYear, 10);
  if (fields.bornCity)         body.born_city        = fields.bornCity.trim();
  if (fields.bornCountry)     body.born_country     = fields.bornCountry.trim();
  if (fields.diedCity)         body.died_city        = fields.diedCity.trim();
  if (fields.diedCountry)     body.died_country     = fields.diedCountry.trim();
  if (fields.notes)           body.notes            = fields.notes.trim();
  try {
    const data = await post<{ id: string }>(`/trees/${treeId}/persons`, body);
    return data.id;
  } catch (err) {
    throw new Error(apiErrorMessage(err, 'Failed to create person'));
  }
}

// ── Shared person fields ───────────────────────────────────────────────────

interface PersonFields {
  givenName: string;
  surname: string;
  sex: string;
  isLiving: boolean;
  // Optional extra details
  birthDate: string;
  deathDate: string;
  birthYear: string;
  deathYear: string;
  bornCity: string;
  bornCountry: string;
  diedCity: string;
  diedCountry: string;
  notes: string;
}

const EMPTY_FIELDS: PersonFields = {
  givenName: '', surname: '', sex: 'UNKNOWN', isLiving: true,
  birthDate: '', deathDate: '', birthYear: '', deathYear: '',
  bornCity: '', bornCountry: '', diedCity: '', diedCountry: '',
  notes: '',
};

/** Returns an error message if birth or death date/year are both set but disagree, else null. */
function validateDates(fields: {
  birthDate?: string; birthYear?: string;
  deathDate?: string; deathYear?: string;
}): string | null {
  const bd = fields.birthDate?.trim();
  const by = fields.birthYear?.trim();
  if (bd && by) {
    const yearFromDate = new Date(bd + 'T00:00:00').getFullYear();
    const yearOnly     = parseInt(by, 10);
    if (!isNaN(yearOnly) && yearFromDate !== yearOnly) {
      return `Birth date year (${yearFromDate}) doesn't match "Birth year only" (${yearOnly}). Make them consistent or clear one field.`;
    }
  }
  const dd = fields.deathDate?.trim();
  const dy = fields.deathYear?.trim();
  if (dd && dy) {
    const yearFromDate = new Date(dd + 'T00:00:00').getFullYear();
    const yearOnly     = parseInt(dy, 10);
    if (!isNaN(yearOnly) && yearFromDate !== yearOnly) {
      return `Death date year (${yearFromDate}) doesn't match "Death year only" (${yearOnly}). Make them consistent or clear one field.`;
    }
  }
  return null;
}

function PersonFormFields({
  values,
  onChange,
  autoFocus = false,
  givenNameRef,
}: {
  values: PersonFields;
  onChange: (v: PersonFields) => void;
  autoFocus?: boolean;
  givenNameRef?: React.Ref<HTMLInputElement>;
}) {
  const { t } = useTranslation();
  const [showExtra, setShowExtra] = React.useState(false);

  return (
    <>
      {/* ── Core fields (always visible) ── */}
      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className="text-xs font-medium text-slate-600 mb-1 block">{t('treeForm.firstName')}</label>
          <input
            ref={givenNameRef}
            autoFocus={autoFocus}
            value={values.givenName}
            onChange={(e) => onChange({ ...values, givenName: e.target.value })}
            className="w-full h-9 px-3 text-sm border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-brand-500"
            placeholder="Given name"
          />
        </div>
        <div>
          <label className="text-xs font-medium text-slate-600 mb-1 block">{t('treeForm.lastName')}</label>
          <input
            value={values.surname}
            onChange={(e) => onChange({ ...values, surname: e.target.value })}
            className="w-full h-9 px-3 text-sm border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-brand-500"
            placeholder="Surname"
          />
        </div>
      </div>
      <div>
        <label className="text-xs font-medium text-slate-600 mb-1 block">{t('treeForm.sex')}</label>
        <select
          value={values.sex}
          onChange={(e) => onChange({ ...values, sex: e.target.value })}
          className="w-full h-9 px-3 text-sm border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-brand-500"
        >
          <option value="UNKNOWN">{t('treeForm.unknown')}</option>
          <option value="MALE">{t('treeForm.male')}</option>
          <option value="FEMALE">{t('treeForm.female')}</option>
          <option value="OTHER">{t('treeForm.other')}</option>
        </select>
      </div>
      <label className="flex items-center gap-2 text-sm text-slate-700 cursor-pointer">
        <input
          type="checkbox"
          checked={values.isLiving}
          onChange={(e) => onChange({ ...values, isLiving: e.target.checked })}
          className="rounded border-slate-300"
        />
        {t('treeForm.living')}
      </label>

      {/* ── More details (collapsed by default) ── */}
      <div className="border border-slate-200 rounded-lg overflow-hidden">
        <button
          type="button"
          onClick={() => setShowExtra((v) => !v)}
          className="flex items-center justify-between w-full px-3 py-2 text-xs font-medium text-slate-500 hover:bg-slate-50 transition-colors"
        >
          <span>{t('treeForm.moreDetails')} <span className="text-slate-400 font-normal">({t('treeForm.optional')})</span></span>
          <span className="text-slate-400 text-[10px]">{showExtra ? '▲ less' : '▼ more'}</span>
        </button>

        {showExtra && (
          <div className="px-3 pb-3 space-y-3 border-t border-slate-100 pt-3">
            {/* Life dates */}
            <p className="text-[10px] font-semibold uppercase tracking-wider text-slate-400">Life dates</p>
            <div className="grid grid-cols-2 gap-2">
              <div>
                <label className="text-xs text-slate-500 mb-1 block">{t('treeForm.birthDate')}</label>
                <input
                  type="date"
                  value={values.birthDate}
                  onChange={(e) => onChange({ ...values, birthDate: e.target.value })}
                  className="w-full h-8 px-2 text-xs border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-brand-500"
                />
              </div>
              <div>
                <label className="text-xs text-slate-500 mb-1 block">{t('treeForm.birthYear')}</label>
                <input
                  type="number"
                  min={1}
                  max={9999}
                  placeholder="e.g. 1950"
                  value={values.birthYear}
                  onChange={(e) => onChange({ ...values, birthYear: e.target.value })}
                  className="w-full h-8 px-2 text-xs border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-brand-500"
                />
              </div>
              <div>
                <label className="text-xs text-slate-500 mb-1 block">{t('treeForm.deathDate')}</label>
                <input
                  type="date"
                  value={values.deathDate}
                  onChange={(e) => onChange({ ...values, deathDate: e.target.value })}
                  className="w-full h-8 px-2 text-xs border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-brand-500"
                />
              </div>
              <div>
                <label className="text-xs text-slate-500 mb-1 block">{t('treeForm.deathYear')}</label>
                <input
                  type="number"
                  min={1}
                  max={9999}
                  placeholder="e.g. 2005"
                  value={values.deathYear}
                  onChange={(e) => onChange({ ...values, deathYear: e.target.value })}
                  className="w-full h-8 px-2 text-xs border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-brand-500"
                />
              </div>
            </div>

            {/* Date consistency error */}
            {(() => {
              const msg = validateDates(values);
              if (!msg) return null;
              return (
                <p className="text-xs text-red-600 bg-red-50 border border-red-200 rounded-lg px-3 py-2">
                  {msg}
                </p>
              );
            })()}

            {/* Born location */}
            <p className="text-[10px] font-semibold uppercase tracking-wider text-slate-400 pt-1">{t('treeForm.bornCity')}</p>
            <div className="grid grid-cols-2 gap-2">
              <div>
                <label className="text-xs text-slate-500 mb-1 block">{t('treeForm.bornCity')}</label>
                <input
                  type="text"
                  placeholder="e.g. London"
                  value={values.bornCity}
                  onChange={(e) => onChange({ ...values, bornCity: e.target.value })}
                  className="w-full h-8 px-2 text-xs border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-brand-500"
                />
              </div>
              <div>
                <label className="text-xs text-slate-500 mb-1 block">{t('treeForm.bornCountry')}</label>
                <input
                  type="text"
                  placeholder="e.g. United Kingdom"
                  value={values.bornCountry}
                  onChange={(e) => onChange({ ...values, bornCountry: e.target.value })}
                  className="w-full h-8 px-2 text-xs border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-brand-500"
                />
              </div>
            </div>

            {/* Died/Buried location */}
            <p className="text-[10px] font-semibold uppercase tracking-wider text-slate-400 pt-1">{t('treeForm.diedCity')}</p>
            <div className="grid grid-cols-2 gap-2">
              <div>
                <label className="text-xs text-slate-500 mb-1 block">{t('treeForm.diedCity')}</label>
                <input
                  type="text"
                  placeholder="e.g. Manchester"
                  value={values.diedCity}
                  onChange={(e) => onChange({ ...values, diedCity: e.target.value })}
                  className="w-full h-8 px-2 text-xs border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-brand-500"
                />
              </div>
              <div>
                <label className="text-xs text-slate-500 mb-1 block">{t('treeForm.diedCountry')}</label>
                <input
                  type="text"
                  placeholder="e.g. United Kingdom"
                  value={values.diedCountry}
                  onChange={(e) => onChange({ ...values, diedCountry: e.target.value })}
                  className="w-full h-8 px-2 text-xs border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-brand-500"
                />
              </div>
            </div>

            {/* Notes */}
            <p className="text-[10px] font-semibold uppercase tracking-wider text-slate-400 pt-1">{t('treeForm.notes')}</p>
            <div>
              <textarea
                placeholder="Add notes about this person (max 250 characters)"
                maxLength={250}
                value={values.notes}
                onChange={(e) => onChange({ ...values, notes: e.target.value })}
                className="w-full h-20 px-2 py-1.5 text-xs border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-brand-500 resize-none"
              />
              <p className="text-[10px] text-slate-400 text-right">{values.notes.length}/250</p>
            </div>
          </div>
        )}
      </div>
    </>
  );
}

// ── Add Person Modal (standalone, from top bar) ────────────────────────────

interface AddPersonModalProps {
  treeId: string;
  token: string | null;
  onClose: () => void;
  onAdded: () => void;
}

function AddPersonModal({ treeId, token, onClose, onAdded }: AddPersonModalProps) {
  const { t } = useTranslation();
  const [fields,  setFields]  = useState<PersonFields>(EMPTY_FIELDS);
  const [loading, setLoading] = useState(false);
  const [error,   setError]   = useState('');
  const givenNameRef = React.useRef<HTMLInputElement>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const dateErr = validateDates(fields);
    if (dateErr) { setError(dateErr); return; }
    setLoading(true);
    setError('');
    try {
      await createPerson(treeId, fields);
      onAdded();
      onClose();
    } catch (err) {
      setError((err as Error).message);
      givenNameRef.current?.focus();
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
        <h2 className="font-bold text-slate-900 mb-4">{t('treeForm.addPerson')}</h2>
        <form onSubmit={handleSubmit} className="space-y-3">
          <PersonFormFields values={fields} onChange={setFields} autoFocus givenNameRef={givenNameRef} />
          {error && <p className="text-xs text-red-600">{error}</p>}
          <div className="flex gap-2 pt-1">
            <button type="button" onClick={onClose}
              className="flex-1 h-9 text-sm border border-slate-300 rounded-lg hover:bg-slate-50">
              {t('treeForm.cancel')}
            </button>
            <button type="submit" disabled={loading}
              className="flex-1 h-9 text-sm bg-brand-500 text-white rounded-lg hover:bg-brand-600 disabled:opacity-50">
              {loading ? 'Adding…' : t('treeForm.addPerson')}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

// ── Add Relation Modal (Add Parent / Child / Spouse) ───────────────────────

type RelationMode = 'parent' | 'child' | 'spouse' | 'bothParents';

const RELATION_CONFIG: Record<'parent' | 'child' | 'spouse', { labelKey: string; linkBody: (id: string) => Record<string, unknown>; linkPath: (anchor: string) => string }> = {
  parent: {
    labelKey: 'treeForm.addParent',
    linkPath: (anchor) => `parents`,
    linkBody: (newId) => ({ parent_id: newId, parentage_type: 'BIOLOGICAL', union_type: 'UNKNOWN' }),
  },
  child: {
    labelKey: 'treeForm.addChild',
    linkPath: (anchor) => `children`,
    linkBody: (newId) => ({ child_id: newId, parentage_type: 'BIOLOGICAL', union_type: 'UNKNOWN' }),
  },
  spouse: {
    labelKey: 'treeForm.addSpouse',
    linkPath: (anchor) => `spouses`,
    linkBody: (newId) => ({ spouse_id: newId, union_type: 'MARRIAGE' }),
  },
};

interface AddRelationModalProps {
  mode: 'parent' | 'child' | 'spouse';
  anchorPersonId: string;
  anchorName: string;
  treeId: string;
  token: string | null;
  candidates: CandidatePerson[];
  onClose: () => void;
  onAdded: () => void;
}

const SEX_INITIAL_COLOR: Record<string, string> = {
  MALE:    'bg-blue-100 text-blue-600',
  FEMALE:  'bg-pink-100 text-pink-600',
  OTHER:   'bg-purple-100 text-purple-600',
  UNKNOWN: 'bg-gray-100 text-gray-500',
};

function AddRelationModal({
  mode, anchorPersonId, anchorName, treeId, token, candidates, onClose, onAdded,
}: AddRelationModalProps) {
  const { t } = useTranslation();
  const [inputMode,     setInputMode]     = useState<'new' | 'existing'>('new');
  const [fields,        setFields]        = useState<PersonFields>(EMPTY_FIELDS);
  const [search,        setSearch]        = useState('');
  const [selectedId,    setSelectedId]    = useState<string | null>(null);
  const [loading,       setLoading]       = useState(false);
  const [error,         setError]         = useState('');
  const [parentageType, setParentageType] = useState('BIOLOGICAL');
  const givenNameRef = React.useRef<HTMLInputElement>(null);

  const cfg = RELATION_CONFIG[mode];
  const cfgLabel = t(cfg.labelKey);

  async function link(personId: string, force = false) {
    const suffix = force ? '?force=true' : '';
    const body = cfg.linkBody(personId);
    if (mode === 'child') {
      body.parentage_type = parentageType;
    }
    try {
      await post(
        `/trees/${treeId}/persons/${anchorPersonId}/${cfg.linkPath(anchorPersonId)}${suffix}`,
        body,
      );
    } catch (err) {
      throw new Error(apiErrorMessage(err, 'Failed to link relationship'));
    }
  }

  async function handleNewSubmit(e: React.FormEvent) {
    e.preventDefault();
    const dateErr = validateDates(fields);
    if (dateErr) { setError(dateErr); return; }
    setLoading(true); setError('');
    try {
      const newId = await createPerson(treeId, fields);
      await link(newId);
      onAdded();
    } catch (err) { setError((err as Error).message); givenNameRef.current?.focus(); }
    finally { setLoading(false); }
  }

  async function handleExistingSubmit() {
    if (!selectedId) return;
    const candidate = candidates.find((c) => c.id === selectedId);
    const force = mode === 'child' && (candidate?.hasParents ?? false);
    setLoading(true); setError('');
    try {
      await link(selectedId, force);
      onAdded();
    } catch (err) { setError((err as Error).message); }
    finally { setLoading(false); }
  }

  const filtered = candidates.filter((p) =>
    `${p.displayGivenName} ${p.displaySurname}`.toLowerCase().includes(search.toLowerCase())
  );

  const selectedCandidate = candidates.find((c) => c.id === selectedId);

  return (
    <div
      className="fixed inset-0 bg-black/30 z-50 flex items-center justify-center p-4"
      onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}
    >
      <div className="bg-white rounded-2xl shadow-xl w-full max-w-sm p-6">
        <h2 className="font-bold text-slate-900 mb-0.5">{cfgLabel}</h2>
        {anchorName && <p className="text-xs text-slate-400 mb-4">for {anchorName}</p>}

        {/* Mode toggle */}
        <div className="flex rounded-lg border border-slate-200 overflow-hidden mb-4">
          {(['new', 'existing'] as const).map((m) => (
            <button
              key={m}
              type="button"
              onClick={() => { setInputMode(m); setError(''); setSelectedId(null); setSearch(''); }}
              className={`flex-1 py-1.5 text-xs font-medium transition-colors ${
                inputMode === m ? 'bg-brand-500 text-white' : 'text-slate-500 hover:bg-slate-50'
              }`}
            >
              {m === 'new' ? t('treeForm.createNew') : t('treeForm.selectExisting')}
            </button>
          ))}
        </div>

        {inputMode === 'new' ? (
          <form onSubmit={handleNewSubmit} className="space-y-3">
            <PersonFormFields values={fields} onChange={setFields} autoFocus givenNameRef={givenNameRef} />
            {mode === 'child' && (
              <div>
                <label className="block text-xs font-medium text-slate-600 mb-1">{t('treeForm.parentage')}</label>
                <select
                  value={parentageType}
                  onChange={(e) => setParentageType(e.target.value)}
                  className="w-full h-9 px-2 text-sm border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-brand-500"
                >
                  <option value="BIOLOGICAL">{t('treeForm.biological')}</option>
                  <option value="ADOPTIVE">{t('treeForm.adopted')}</option>
                  <option value="STEP">{t('treeForm.step')}</option>
                  <option value="FOSTER">{t('treeForm.foster')}</option>
                  <option value="UNKNOWN">{t('treeForm.unknown')}</option>
                </select>
              </div>
            )}
            {error && <p className="text-xs text-red-600">{error}</p>}
            <div className="flex gap-2 pt-1">
              <button type="button" onClick={onClose}
                className="flex-1 h-9 text-sm border border-slate-300 rounded-lg hover:bg-slate-50">
                {t('treeForm.cancel')}
              </button>
              <button type="submit" disabled={loading}
                className="flex-1 h-9 text-sm bg-brand-500 text-white rounded-lg hover:bg-brand-600 disabled:opacity-50">
                {loading ? 'Adding…' : cfgLabel}
              </button>
            </div>
          </form>
        ) : (
          <div className="space-y-3">
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
                    <div className={`w-7 h-7 rounded-full flex items-center justify-center text-xs font-semibold flex-shrink-0 ${SEX_INITIAL_COLOR[p.sex] ?? SEX_INITIAL_COLOR.UNKNOWN}`}>
                      {name[0]?.toUpperCase() ?? '?'}
                    </div>
                    <span className={`text-sm flex-1 truncate ${isSelected ? 'text-brand-700 font-medium' : 'text-slate-700'}`}>
                      {name}
                    </span>
                    {p.hasParents && mode === 'child' && (
                      <span className="text-[10px] text-amber-600 bg-amber-50 border border-amber-200 px-1.5 py-0.5 rounded flex-shrink-0">
                        has parents
                      </span>
                    )}
                    {isSelected && !p.hasParents && <span className="text-brand-500 text-xs">✓</span>}
                  </button>
                );
              })}
            </div>
            {mode === 'child' && (
              <div>
                <label className="block text-xs font-medium text-slate-600 mb-1">{t('treeForm.parentage')}</label>
                <select
                  value={parentageType}
                  onChange={(e) => setParentageType(e.target.value)}
                  className="w-full h-9 px-2 text-sm border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-brand-500"
                >
                  <option value="BIOLOGICAL">{t('treeForm.biological')}</option>
                  <option value="ADOPTIVE">{t('treeForm.adopted')}</option>
                  <option value="STEP">{t('treeForm.step')}</option>
                  <option value="FOSTER">{t('treeForm.foster')}</option>
                  <option value="UNKNOWN">{t('treeForm.unknown')}</option>
                </select>
              </div>
            )}
            {selectedCandidate?.hasParents && mode === 'child' && (
              <p className="text-xs text-amber-700 bg-amber-50 border border-amber-200 rounded-lg px-3 py-2">
                This person already has parents recorded. Linking here will replace their existing parent connection.
              </p>
            )}
            {error && <p className="text-xs text-red-600">{error}</p>}
            <div className="flex gap-2">
              <button type="button" onClick={onClose}
                className="flex-1 h-9 text-sm border border-slate-300 rounded-lg hover:bg-slate-50">
                {t('treeForm.cancel')}
              </button>
              <button
                type="button"
                onClick={handleExistingSubmit}
                disabled={loading || !selectedId}
                className="flex-1 h-9 text-sm bg-brand-500 text-white rounded-lg hover:bg-brand-600 disabled:opacity-50"
              >
                {loading ? 'Linking…' : `Link as ${mode}`}
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

// ── Add Both Parents Modal ────────────────────────────────────────────────

interface AddBothParentsModalProps {
  anchorPersonId: string;
  anchorName: string;
  anchorHasParents: boolean;
  treeId: string;
  token: string | null;
  candidates: CandidatePerson[];
  familyGroups: { parentIds: string[] }[];
  onClose: () => void;
  onAdded: () => void;
}

function PersonPicker({
  label, search, onSearch, selected, onSelect, candidates, emptyConstrainedMsg,
}: {
  label: string;
  search: string;
  onSearch: (v: string) => void;
  selected: string | null;
  onSelect: (id: string | null) => void;
  candidates: CandidatePerson[];
  emptyConstrainedMsg?: string;
}) {
  const filtered = candidates.filter(
    (p) => `${p.displayGivenName} ${p.displaySurname}`.toLowerCase().includes(search.toLowerCase()),
  );
  const selectedPerson = candidates.find((c) => c.id === selected)
    ?? (selected ? { displayGivenName: selected, displaySurname: '', sex: 'UNKNOWN' } as CandidatePerson : undefined);
  const selectedName = selectedPerson
    ? `${selectedPerson.displayGivenName} ${selectedPerson.displaySurname}`.trim() || 'Unknown'
    : null;

  return (
    <div className="space-y-1.5">
      <p className="text-xs font-semibold text-slate-500 uppercase tracking-wide">{label}</p>
      {selected && selectedPerson ? (
        <div className="flex items-center gap-2 px-3 py-2 rounded-lg bg-brand-50 border border-brand-200">
          <div className={`w-6 h-6 rounded-full flex items-center justify-center text-xs font-semibold flex-shrink-0 ${SEX_INITIAL_COLOR[selectedPerson.sex ?? 'UNKNOWN'] ?? SEX_INITIAL_COLOR.UNKNOWN}`}>
            {selectedName?.[0]?.toUpperCase() ?? '?'}
          </div>
          <span className="text-sm text-brand-700 font-medium flex-1 truncate">{selectedName}</span>
          <button type="button" onClick={() => { onSelect(null); onSearch(''); }} className="text-slate-400 hover:text-slate-600 text-xs">✕</button>
        </div>
      ) : (
        <>
          <input
            type="text"
            value={search}
            onChange={(e) => onSearch(e.target.value)}
            placeholder={`Search for ${label.toLowerCase()}…`}
            className="w-full h-8 px-3 text-sm border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-brand-500"
          />
          <div className="max-h-36 overflow-y-auto rounded-lg border border-slate-200 divide-y divide-slate-100">
            {filtered.length === 0 ? (
              <p className="px-3 py-2 text-xs text-slate-400 text-center">
                {emptyConstrainedMsg ?? 'No members found'}
              </p>
            ) : filtered.map((p) => {
              const name = `${p.displayGivenName} ${p.displaySurname}`.trim() || 'Unknown';
              return (
                <button
                  key={p.id}
                  type="button"
                  onClick={() => { onSelect(p.id); onSearch(''); }}
                  className="flex items-center gap-2 w-full px-3 py-2 text-left hover:bg-slate-50"
                >
                  <div className={`w-6 h-6 rounded-full flex items-center justify-center text-xs font-semibold flex-shrink-0 ${SEX_INITIAL_COLOR[p.sex] ?? SEX_INITIAL_COLOR.UNKNOWN}`}>
                    {name[0]?.toUpperCase() ?? '?'}
                  </div>
                  <span className="text-sm text-slate-700 truncate">{name}</span>
                </button>
              );
            })}
          </div>
        </>
      )}
    </div>
  );
}

function AddBothParentsModal({
  anchorPersonId, anchorName, anchorHasParents, treeId, token, candidates, familyGroups, onClose, onAdded,
}: AddBothParentsModalProps) {
  const { t } = useTranslation();
  const [fatherSearch, setFatherSearch] = useState('');
  const [motherSearch, setMotherSearch] = useState('');
  const [fatherId,     setFatherId]     = useState<string | null>(null);
  const [motherId,     setMotherId]     = useState<string | null>(null);
  const [loading,      setLoading]      = useState(false);
  const [error,        setError]        = useState('');

  // Partners of selected father in the tree (people already in a union with him)
  const fatherPartnerIds = useMemo(() => {
    if (!fatherId) return null;
    return new Set(
      familyGroups
        .filter((fg) => fg.parentIds.includes(fatherId))
        .flatMap((fg) => fg.parentIds.filter((id) => id !== fatherId)),
    );
  }, [fatherId, familyGroups]);

  // Partners of selected mother in the tree
  const motherPartnerIds = useMemo(() => {
    if (!motherId) return null;
    return new Set(
      familyGroups
        .filter((fg) => fg.parentIds.includes(motherId))
        .flatMap((fg) => fg.parentIds.filter((id) => id !== motherId)),
    );
  }, [motherId, familyGroups]);

  // Mother candidates: FEMALE only; if a father is selected, further narrow to his known partners
  const motherCandidates = useMemo(
    () => fatherPartnerIds
      ? candidates.filter((c) => c.sex === 'FEMALE' && fatherPartnerIds.has(c.id))
      : candidates.filter((c) => c.sex === 'FEMALE' && c.id !== fatherId),
    [fatherPartnerIds, candidates, fatherId],
  );

  // Father candidates: MALE only; if a mother is selected, further narrow to her known partners
  const fatherCandidates = useMemo(
    () => motherPartnerIds
      ? candidates.filter((c) => c.sex === 'MALE' && motherPartnerIds.has(c.id))
      : candidates.filter((c) => c.sex === 'MALE' && c.id !== motherId),
    [motherPartnerIds, candidates, motherId],
  );

  function handleSetFather(id: string | null) {
    setFatherId(id);
    setFatherSearch('');
    // If the current mother is no longer a valid partner of the new father, clear her
    if (id && motherId) {
      const newPartners = new Set(
        familyGroups
          .filter((fg) => fg.parentIds.includes(id))
          .flatMap((fg) => fg.parentIds.filter((pid) => pid !== id)),
      );
      if (newPartners.size > 0 && !newPartners.has(motherId)) setMotherId(null);
    }
  }

  function handleSetMother(id: string | null) {
    setMotherId(id);
    setMotherSearch('');
    // If the current father is no longer a valid partner of the new mother, clear him
    if (id && fatherId) {
      const newPartners = new Set(
        familyGroups
          .filter((fg) => fg.parentIds.includes(id))
          .flatMap((fg) => fg.parentIds.filter((pid) => pid !== id)),
      );
      if (newPartners.size > 0 && !newPartners.has(fatherId)) setFatherId(null);
    }
  }

  async function handleSubmit() {
    if (!fatherId || !motherId) return;
    setLoading(true); setError('');
    try {
      await post(`/trees/${treeId}/persons/${anchorPersonId}/parents/pair`, {
        father_id: fatherId, mother_id: motherId, parentage_type: 'BIOLOGICAL', union_type: 'MARRIAGE',
      });
      onAdded();
    } catch (err) { setError(apiErrorMessage(err, 'Failed to link parents')); }
    finally { setLoading(false); }
  }

  const fatherName = candidates.find((c) => c.id === fatherId);
  const motherName = candidates.find((c) => c.id === motherId);
  const fatherLabel = fatherName
    ? `${fatherName.displayGivenName} ${fatherName.displaySurname}`.trim() || 'Selected father'
    : null;
  const motherLabel = motherName
    ? `${motherName.displayGivenName} ${motherName.displaySurname}`.trim() || 'Selected mother'
    : null;

  return (
    <div
      className="fixed inset-0 bg-black/30 z-50 flex items-center justify-center p-4"
      onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}
    >
      <div className="bg-white rounded-2xl shadow-xl w-full max-w-sm p-6 space-y-4">
        <div>
          <h2 className="font-bold text-slate-900">{t('treeForm.addFatherMother')}</h2>
          {anchorName && <p className="text-xs text-slate-400 mt-0.5">for {anchorName}</p>}
        </div>

        {anchorHasParents && (
          <p className="text-xs text-amber-700 bg-amber-50 border border-amber-200 rounded-lg px-3 py-2">
            {anchorName} already has parents recorded. Linking new parents will replace the existing ones.
          </p>
        )}

        <PersonPicker
          label="Father"
          search={fatherSearch}
          onSearch={setFatherSearch}
          selected={fatherId}
          onSelect={handleSetFather}
          candidates={fatherCandidates}
          emptyConstrainedMsg={
            motherPartnerIds && motherPartnerIds.size === 0
              ? `${motherLabel ?? 'Selected mother'} has no known partners in this tree`
              : 'No matches'
          }
        />

        <PersonPicker
          label="Mother"
          search={motherSearch}
          onSearch={setMotherSearch}
          selected={motherId}
          onSelect={handleSetMother}
          candidates={motherCandidates}
          emptyConstrainedMsg={
            fatherPartnerIds && fatherPartnerIds.size === 0
              ? `${fatherLabel ?? 'Selected father'} has no known partners in this tree`
              : 'No matches'
          }
        />

        {error && <p className="text-xs text-red-600">{error}</p>}

        <div className="flex gap-2 pt-1">
          <button type="button" onClick={onClose}
            className="flex-1 h-9 text-sm border border-slate-300 rounded-lg hover:bg-slate-50">
            {t('treeForm.cancel')}
          </button>
          <button
            type="button"
            onClick={handleSubmit}
            disabled={loading || !fatherId || !motherId}
            className="flex-1 h-9 text-sm bg-brand-500 text-white rounded-lg hover:bg-brand-600 disabled:opacity-50"
          >
            {loading ? 'Linking…' : 'Link parents'}
          </button>
        </div>
      </div>
    </div>
  );
}

// ── Add Child to union modal ───────────────────────────────────────────────

interface CandidatePerson {
  id: string;
  displayGivenName: string;
  displaySurname: string;
  sex: string;
  hasParents: boolean; // already a child in another family group
}

interface AddChildToUnionModalProps {
  fgId: string;
  parent1Id: string;
  parent2Id: string | null;
  parent1Name: string;
  parent2Name: string;
  treeId: string;
  token: string | null;
  candidates: CandidatePerson[]; // existing persons that can be linked
  onClose: () => void;
  onAdded: () => void;
  onRemoved: () => void;
}

function AddChildToUnionModal({
  fgId, parent1Id, parent2Id, parent1Name, parent2Name,
  treeId, token, candidates, onClose, onAdded, onRemoved,
}: AddChildToUnionModalProps) {
  const { t } = useTranslation();
  const [mode,          setMode]          = useState<'new' | 'existing'>('new');
  const [fields,        setFields]        = useState<PersonFields>(EMPTY_FIELDS);
  const [search,        setSearch]        = useState('');
  const [selectedId,    setSelectedId]    = useState<string | null>(null);
  const [loading,       setLoading]       = useState(false);
  const [error,         setError]         = useState('');
  const [confirmRemove, setConfirmRemove] = useState(false);
  const [removing,      setRemoving]      = useState(false);
  const [parentageType, setParentageType] = useState('BIOLOGICAL');
  const givenNameRef = React.useRef<HTMLInputElement>(null);

  const unionLabel = parent2Id
    ? `${parent1Name} & ${parent2Name}`
    : parent1Name;

  async function handleRemoveUnion() {
    setRemoving(true);
    try {
      await del(`/trees/${treeId}/family-groups/${fgId}`);
      onRemoved();
    } catch (err) {
      setError(apiErrorMessage(err, 'Failed to remove union'));
      setRemoving(false);
      setConfirmRemove(false);
    }
  }

  async function linkChild(childId: string, force = false) {
    const body: Record<string, unknown> = {
      child_id: childId,
      parentage_type: parentageType,
      union_type: 'UNKNOWN',
    };
    if (parent2Id) body.other_parent_id = parent2Id;
    const suffix = force ? '?force=true' : '';
    try {
      await post(`/trees/${treeId}/persons/${parent1Id}/children${suffix}`, body);
    } catch (err) {
      throw new Error(apiErrorMessage(err, 'Failed to link child'));
    }
  }

  async function handleNewSubmit(e: React.FormEvent) {
    e.preventDefault();
    const dateErr = validateDates(fields);
    if (dateErr) { setError(dateErr); return; }
    setLoading(true);
    setError('');
    try {
      const newId = await createPerson(treeId, fields);
      await linkChild(newId);
      onAdded();
    } catch (err) {
      setError((err as Error).message);
      givenNameRef.current?.focus();
    } finally {
      setLoading(false);
    }
  }

  async function handleExistingSubmit() {
    if (!selectedId) return;
    const candidate = candidates.find((c) => c.id === selectedId);
    setLoading(true);
    setError('');
    try {
      await linkChild(selectedId, candidate?.hasParents ?? false);
      onAdded();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setLoading(false);
    }
  }

  const filtered = candidates.filter((p) => {
    const name = `${p.displayGivenName} ${p.displaySurname}`.toLowerCase();
    return name.includes(search.toLowerCase());
  });


  return (
    <div
      className="fixed inset-0 bg-black/30 z-50 flex items-center justify-center p-4"
      onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}
    >
      <div className="bg-white rounded-2xl shadow-xl w-full max-w-sm p-6">
        <div className="flex items-start justify-between mb-0.5">
          <h2 className="font-bold text-slate-900">{t('treeForm.addChild')}</h2>
          <button
            type="button"
            onClick={() => setConfirmRemove(true)}
            className="text-xs text-red-500 hover:text-red-700 px-2 py-0.5 rounded hover:bg-red-50 transition-colors"
            title="Remove this union"
          >
            Remove union
          </button>
        </div>
        <p className="text-xs text-slate-400 mb-4">for {unionLabel}</p>

        {/* Mode tabs */}
        <div className="flex rounded-lg border border-slate-200 overflow-hidden mb-4">
          {(['new', 'existing'] as const).map((m) => (
            <button
              key={m}
              type="button"
              onClick={() => { setMode(m); setError(''); setSelectedId(null); }}
              className={`flex-1 py-1.5 text-xs font-medium transition-colors ${
                mode === m
                  ? 'bg-brand-500 text-white'
                  : 'text-slate-500 hover:bg-slate-50'
              }`}
            >
              {m === 'new' ? t('treeForm.createNew') : t('treeForm.selectExisting')}
            </button>
          ))}
        </div>

        {/* Remove union confirmation */}
        {confirmRemove && (
          <div className="mb-4 rounded-xl border border-red-200 bg-red-50 p-4 space-y-3">
            <p className="text-sm font-medium text-red-800">Remove this union?</p>
            <p className="text-xs text-red-600">
              This removes the <span className="font-semibold">{unionLabel}</span> union and all its
              parent/child links. The people themselves stay in the tree.
            </p>
            <div className="flex gap-2">
              <button
                type="button"
                onClick={() => setConfirmRemove(false)}
                disabled={removing}
                className="flex-1 h-8 text-xs border border-red-300 text-red-700 rounded-lg hover:bg-red-100 disabled:opacity-50"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handleRemoveUnion}
                disabled={removing}
                className="flex-1 h-8 text-xs bg-red-600 text-white rounded-lg hover:bg-red-700 disabled:opacity-50"
              >
                {removing ? 'Removing…' : 'Yes, remove'}
              </button>
            </div>
          </div>
        )}

        {/* Parentage type (shared across both tabs) */}
        <div className="mb-4">
          <label className="block text-xs font-medium text-slate-600 mb-1">{t('treeForm.parentage')}</label>
          <select
            value={parentageType}
            onChange={(e) => setParentageType(e.target.value)}
            className="w-full h-9 px-2 text-sm border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-brand-500"
          >
            <option value="BIOLOGICAL">{t('treeForm.biological')}</option>
            <option value="ADOPTIVE">{t('treeForm.adopted')}</option>
            <option value="STEP">{t('treeForm.step')}</option>
            <option value="FOSTER">{t('treeForm.foster')}</option>
            <option value="UNKNOWN">{t('treeForm.unknown')}</option>
          </select>
        </div>

        {mode === 'new' ? (
          <form onSubmit={handleNewSubmit} className="space-y-3">
            <PersonFormFields values={fields} onChange={setFields} autoFocus givenNameRef={givenNameRef} />
            {error && <p className="text-xs text-red-600">{error}</p>}
            <div className="flex gap-2 pt-1">
              <button type="button" onClick={onClose}
                className="flex-1 h-9 text-sm border border-slate-300 rounded-lg hover:bg-slate-50">
                {t('treeForm.cancel')}
              </button>
              <button type="submit" disabled={loading}
                className="flex-1 h-9 text-sm bg-brand-500 text-white rounded-lg hover:bg-brand-600 disabled:opacity-50">
                {loading ? 'Adding…' : t('treeForm.addChild')}
              </button>
            </div>
          </form>
        ) : (
          <div className="space-y-3">
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
                const name = `${p.displayGivenName} ${p.displaySurname}`.trim() || 'Unknown';
                const initial = name[0]?.toUpperCase() ?? '?';
                const colorCls = SEX_INITIAL_COLOR[p.sex] ?? SEX_INITIAL_COLOR.UNKNOWN;
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
                    <div className={`w-7 h-7 rounded-full flex items-center justify-center text-xs font-semibold flex-shrink-0 ${colorCls}`}>
                      {initial}
                    </div>
                    <span className={`text-sm flex-1 truncate ${isSelected ? 'text-brand-700 font-medium' : 'text-slate-700'}`}>
                      {name}
                    </span>
                    {p.hasParents && (
                      <span className="text-[10px] text-amber-600 bg-amber-50 border border-amber-200 px-1.5 py-0.5 rounded flex-shrink-0">
                        has parents
                      </span>
                    )}
                    {isSelected && !p.hasParents && <span className="text-brand-500 text-xs">✓</span>}
                  </button>
                );
              })}
            </div>
            {selectedId && candidates.find((c) => c.id === selectedId)?.hasParents && (
              <p className="text-xs text-amber-700 bg-amber-50 border border-amber-200 rounded-lg px-3 py-2">
                This person already has parents recorded. Linking here will
                replace their existing parent connection.
              </p>
            )}
            {error && <p className="text-xs text-red-600">{error}</p>}
            <div className="flex gap-2">
              <button type="button" onClick={onClose}
                className="flex-1 h-9 text-sm border border-slate-300 rounded-lg hover:bg-slate-50">
                {t('treeForm.cancel')}
              </button>
              <button
                type="button"
                onClick={handleExistingSubmit}
                disabled={loading || !selectedId}
                className="flex-1 h-9 text-sm bg-brand-500 text-white rounded-lg hover:bg-brand-600 disabled:opacity-50"
              >
                {loading ? 'Linking…' : 'Link as child'}
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

// ── Profile photo upload helper ───────────────────────────────────────────

async function uploadPersonPhoto(
  file: File,
  treeId: string,
  personId: string,
): Promise<string> {
  const form = new FormData();
  form.append('file', file);
  try {
    const data = await post<{ photo_url: string }>(`/trees/${treeId}/persons/${personId}/photo`, form);
    return data.photo_url;
  } catch (err) {
    throw new Error(apiErrorMessage(err, 'Upload failed'));
  }
}

// ── Edit person modal ──────────────────────────────────────────────────────

interface EditPersonFields {
  givenName: string;
  surname: string;
  sex: string;
  status: 'living' | 'deceased' | 'unknown';
  birthDate: string;
  deathDate: string;
  birthYear: string;
  deathYear: string;
  bornCity: string;
  bornCountry: string;
  diedCity: string;
  diedCountry: string;
  notes: string;
}

interface EditPersonModalProps {
  personId: string;
  initial: EditPersonFields;
  initialPhotoUrl?: string;
  treeId: string;
  token: string | null;
  onClose: () => void;
  onSaved: () => void;
  onRefresh?: () => void;
}

interface GalleryPhoto {
  id: string;
  photoUrl: string;
  caption: string | null;
  position: number;
}

function EditPersonModal({ personId, initial, initialPhotoUrl, treeId, token, onClose, onSaved, onRefresh }: EditPersonModalProps) {
  const { t } = useTranslation();
  const [fields,       setFields]       = useState<EditPersonFields>(initial);
  const [loading,      setLoading]      = useState(false);
  const [error,        setError]        = useState('');
  const editGivenNameRef = React.useRef<HTMLInputElement>(null);
  const [photoUrl,     setPhotoUrl]     = useState<string | undefined>(initialPhotoUrl);
  const [photoLoading, setPhotoLoading] = useState(false);
  const [photoError,   setPhotoError]   = useState('');
  const [showPresets,  setShowPresets]  = useState(false);
  const [showExtra,    setShowExtra]    = useState(false);
  const fileInputRef = React.useRef<HTMLInputElement>(null);

  // Gallery photos state
  const [galleryPhotos, setGalleryPhotos] = useState<GalleryPhoto[]>([]);
  const [galleryLoading, setGalleryLoading] = useState(false);
  const [galleryError, setGalleryError] = useState('');
  const [hoveredGallery, setHoveredGallery] = useState<string | null>(null);
  const [editingCaption, setEditingCaption] = useState<string | null>(null);
  const [captionDraft, setCaptionDraft] = useState('');
  const galleryInputRef = React.useRef<HTMLInputElement>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const photos = await get<GalleryPhoto[]>(`/trees/${treeId}/persons/${personId}/gallery`);
        if (!cancelled) setGalleryPhotos(photos);
      } catch { /* ignore */ }
    })();
    return () => { cancelled = true; };
  }, [treeId, personId]);

  async function handleGalleryUpload(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    if (!file.type.startsWith('image/')) { setGalleryError('Please select an image file.'); return; }
    if (galleryPhotos.length >= 3) { setGalleryError('Maximum 3 gallery photos allowed.'); return; }

    setGalleryLoading(true);
    setGalleryError('');
    try {
      const form = new FormData();
      form.append('file', file);
      const data = await post<GalleryPhoto>(`/trees/${treeId}/persons/${personId}/gallery?caption=`, form);
      setGalleryPhotos((prev) => [...prev, data]);
    } catch (err) {
      setGalleryError(apiErrorMessage(err, 'Upload failed'));
    } finally {
      setGalleryLoading(false);
      if (galleryInputRef.current) galleryInputRef.current.value = '';
    }
  }

  async function handleGalleryDelete(photoId: string) {
    setGalleryLoading(true);
    try {
      await del(`/trees/${treeId}/persons/${personId}/gallery/${photoId}`);
      setGalleryPhotos((prev) => prev.filter((p) => p.id !== photoId));
    } catch (err) {
      setGalleryError(apiErrorMessage(err, 'Delete failed'));
    } finally {
      setGalleryLoading(false);
    }
  }

  async function handleCaptionSave(photoId: string) {
    try {
      await patch(`/trees/${treeId}/persons/${personId}/gallery/${photoId}?caption=${encodeURIComponent(captionDraft)}`, {});
      setGalleryPhotos((prev) => prev.map((p) => p.id === photoId ? { ...p, caption: captionDraft.trim() || null } : p));
      setEditingCaption(null);
    } catch (err) {
      setGalleryError(apiErrorMessage(err, 'Failed to save caption'));
    }
  }

  async function handlePhotoChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    if (!file.type.startsWith('image/')) { setPhotoError('Please select an image file.'); return; }

    setPhotoLoading(true);
    setPhotoError('');
    try {
      const url = await uploadPersonPhoto(file, treeId, personId);
      setPhotoUrl(url);
      onRefresh?.();
    } catch (err) {
      setPhotoError((err as Error).message);
    } finally {
      setPhotoLoading(false);
      if (fileInputRef.current) fileInputRef.current.value = '';
    }
  }

  async function handleSelectPreset(presetId: string) {
    setPhotoLoading(true);
    setPhotoError('');
    try {
      await patch(`/trees/${treeId}/persons/${personId}`, { photo_url: presetId });
      setPhotoUrl(presetId);
      setShowPresets(false);
      onRefresh?.();
    } catch (err) {
      setPhotoError(apiErrorMessage(err, 'Failed to set avatar'));
    } finally {
      setPhotoLoading(false);
    }
  }

  async function handleRemovePhoto() {
    setPhotoLoading(true);
    setPhotoError('');
    try {
      await del(`/trees/${treeId}/persons/${personId}/photo`);
      setPhotoUrl(undefined);
      setShowPresets(false);
      onRefresh?.();
    } catch (err) {
      setPhotoError(apiErrorMessage(err, 'Failed to remove photo'));
    } finally {
      setPhotoLoading(false);
    }
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!fields.givenName.trim() && !fields.surname.trim()) {
      setError('Please enter at least a first name or last name.');
      editGivenNameRef.current?.focus();
      return;
    }
    const dateErr = validateDates(fields);
    if (dateErr) { setError(dateErr); return; }
    setLoading(true);
    setError('');
    try {
      const body: Record<string, unknown> = {
        given_name:  fields.givenName,
        surname:     fields.surname,
        sex:         fields.sex,
        is_living:   fields.status === 'living',
        is_deceased: fields.status === 'deceased',
      };
      if (fields.birthDate)       body.birth_date       = fields.birthDate;
      if (fields.deathDate)       body.death_date       = fields.deathDate;
      if (fields.birthYear)       body.birth_year       = parseInt(fields.birthYear, 10);
      if (fields.deathYear)       body.death_year       = parseInt(fields.deathYear, 10);
      if (fields.bornCity)          body.born_city        = fields.bornCity.trim();
      if (fields.bornCountry)      body.born_country     = fields.bornCountry.trim();
      if (fields.diedCity)          body.died_city        = fields.diedCity.trim();
      if (fields.diedCountry)      body.died_country     = fields.diedCountry.trim();
      if (fields.notes)            body.notes            = fields.notes.trim();
      await patch(`/trees/${treeId}/persons/${personId}`, body);
      onSaved();
    } catch (err) {
      setError(apiErrorMessage(err, 'Failed to save'));
    } finally {
      setLoading(false);
    }
  }

  const initials = [fields.givenName[0], fields.surname[0]].filter(Boolean).join('').toUpperCase() || '?';

  return (
    <div
      className="fixed inset-0 bg-black/30 z-50 flex items-center justify-center p-4"
      onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}
    >
      <div className="bg-white rounded-2xl shadow-xl w-full max-w-sm p-6">
        <h2 className="font-bold text-slate-900 mb-4">{t('treeForm.editPerson')}</h2>

        {/* Photo section */}
        <div className="mb-5 pb-4 border-b border-slate-100">
          <div className="flex items-center gap-4">
            <div className="relative flex-shrink-0">
              <div className="w-16 h-16 rounded-full overflow-hidden bg-slate-100 flex items-center justify-center text-slate-500 font-semibold text-lg">
                {photoLoading ? (
                  <div className="w-5 h-5 border-2 border-brand-500 border-t-transparent rounded-full animate-spin" />
                ) : photoUrl ? (
                  <img
                    src={isPreset(photoUrl) ? presetDataUri(photoUrl)! : photoUrl}
                    alt="Profile"
                    className="w-full h-full object-cover"
                  />
                ) : (
                  initials
                )}
              </div>
              <button
                type="button"
                onClick={() => fileInputRef.current?.click()}
                disabled={photoLoading}
                className="absolute -bottom-1 -right-1 w-6 h-6 bg-brand-500 text-white rounded-full flex items-center justify-center hover:bg-brand-600 disabled:opacity-50 shadow"
                title="Upload photo"
              >
                <svg width="12" height="12" viewBox="0 0 12 12" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M6 1v10M1 6h10" />
                </svg>
              </button>
            </div>
            <div className="min-w-0 flex-1">
              <p className="text-sm font-medium text-slate-700">{t('treeForm.profilePhoto')}</p>
              <p className="text-xs text-slate-400 mt-0.5">{t('treeForm.photoHint')}</p>
              <div className="flex gap-3 mt-1">
                <button
                  type="button"
                  onClick={() => setShowPresets((v) => !v)}
                  disabled={photoLoading}
                  className="text-xs text-brand-600 hover:text-brand-700 disabled:opacity-50"
                >
                  {showPresets ? t('treeForm.hidePresets') : t('treeForm.chooseAvatar')}
                </button>
                {photoUrl && (
                  <button
                    type="button"
                    onClick={handleRemovePhoto}
                    disabled={photoLoading}
                    className="text-xs text-red-500 hover:text-red-700 disabled:opacity-50"
                  >
                    Remove
                  </button>
                )}
              </div>
              {photoError && <p className="text-xs text-red-600 mt-1">{photoError}</p>}
            </div>
            <input
              ref={fileInputRef}
              type="file"
              accept="image/*"
              className="hidden"
              onChange={handlePhotoChange}
            />
          </div>

          {/* Preset avatar grid */}
          {showPresets && (
            <div className="mt-3 grid grid-cols-4 gap-2">
              {AVATAR_PRESETS.map((preset) => (
                <button
                  key={preset.id}
                  type="button"
                  onClick={() => handleSelectPreset(preset.id)}
                  disabled={photoLoading}
                  className={`rounded-full overflow-hidden w-12 h-12 mx-auto ring-2 transition-all disabled:opacity-50 ${
                    photoUrl === preset.id ? 'ring-brand-500 scale-110' : 'ring-transparent hover:ring-slate-300'
                  }`}
                  title={preset.label}
                >
                  <img src={presetDataUri(preset.id)!} alt={preset.label} className="w-full h-full" />
                </button>
              ))}
            </div>
          )}

          {/* Gallery photos */}
          <div className="mt-3 pt-3 border-t border-slate-100">
            <div className="flex items-center justify-between mb-2">
              <p className="text-xs font-medium text-slate-600">{t('treeForm.photos')} <span className="text-slate-400 font-normal">({galleryPhotos.length}/3)</span></p>
              {galleryPhotos.length < 3 && (
                <button
                  type="button"
                  onClick={() => galleryInputRef.current?.click()}
                  disabled={galleryLoading}
                  className="text-xs text-brand-600 hover:text-brand-700 disabled:opacity-50"
                >
                  {t('treeForm.addPhoto')}
                </button>
              )}
            </div>
            <input
              ref={galleryInputRef}
              type="file"
              accept="image/*"
              className="hidden"
              onChange={handleGalleryUpload}
            />
            {galleryPhotos.length > 0 && (
              <div className="flex gap-2">
                {galleryPhotos.map((gp) => (
                  <div key={gp.id} className="relative group">
                    <div
                      className="w-16 h-16 rounded-lg overflow-hidden bg-slate-100 cursor-pointer relative"
                      onMouseEnter={() => setHoveredGallery(gp.id)}
                      onMouseLeave={() => setHoveredGallery(null)}
                    >
                      <img src={gp.photoUrl} alt={gp.caption || 'Gallery'} className="w-full h-full object-cover" />
                      {/* Hover overlay with enlarged view */}
                      {hoveredGallery === gp.id && (
                        <div className="fixed inset-0 z-[60] flex items-center justify-center pointer-events-none">
                          <div className="bg-white rounded-xl shadow-2xl p-2 max-w-xs pointer-events-auto">
                            <img src={gp.photoUrl} alt={gp.caption || 'Gallery'} className="w-64 h-64 object-cover rounded-lg" />
                            {gp.caption && (
                              <p className="text-xs text-slate-600 mt-1.5 px-1 text-center">{gp.caption}</p>
                            )}
                          </div>
                        </div>
                      )}
                    </div>
                    {/* Delete button */}
                    <button
                      type="button"
                      onClick={() => handleGalleryDelete(gp.id)}
                      disabled={galleryLoading}
                      className="absolute -top-1.5 -right-1.5 w-5 h-5 bg-red-500 text-white rounded-full flex items-center justify-center text-[10px] opacity-0 group-hover:opacity-100 transition-opacity disabled:opacity-50 shadow"
                      title="Remove"
                    >
                      ×
                    </button>
                    {/* Caption */}
                    {editingCaption === gp.id ? (
                      <div className="mt-1">
                        <input
                          type="text"
                          maxLength={200}
                          value={captionDraft}
                          onChange={(e) => setCaptionDraft(e.target.value)}
                          onBlur={() => handleCaptionSave(gp.id)}
                          onKeyDown={(e) => { if (e.key === 'Enter') handleCaptionSave(gp.id); }}
                          autoFocus
                          className="w-16 h-5 px-1 text-[9px] border border-slate-300 rounded focus:outline-none focus:ring-1 focus:ring-brand-500"
                          placeholder="Caption"
                        />
                      </div>
                    ) : (
                      <button
                        type="button"
                        onClick={() => { setEditingCaption(gp.id); setCaptionDraft(gp.caption || ''); }}
                        className="mt-1 w-16 text-[9px] text-slate-400 hover:text-slate-600 truncate block text-center"
                        title={gp.caption || 'Add caption'}
                      >
                        {gp.caption || 'caption'}
                      </button>
                    )}
                  </div>
                ))}
              </div>
            )}
            {galleryLoading && <p className="text-xs text-slate-400 mt-1">Uploading...</p>}
            {galleryError && <p className="text-xs text-red-600 mt-1">{galleryError}</p>}
          </div>
        </div>

        <form onSubmit={handleSubmit} className="space-y-3">
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="text-xs font-medium text-slate-600 mb-1 block">{t('treeForm.firstName')}</label>
              <input
                ref={editGivenNameRef}
                autoFocus
                value={fields.givenName}
                onChange={(e) => setFields((f) => ({ ...f, givenName: e.target.value }))}
                className="w-full h-9 px-3 text-sm border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-brand-500"
                placeholder="Given name"
              />
            </div>
            <div>
              <label className="text-xs font-medium text-slate-600 mb-1 block">{t('treeForm.lastName')}</label>
              <input
                value={fields.surname}
                onChange={(e) => setFields((f) => ({ ...f, surname: e.target.value }))}
                className="w-full h-9 px-3 text-sm border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-brand-500"
                placeholder="Surname"
              />
            </div>
          </div>
          <div>
            <label className="text-xs font-medium text-slate-600 mb-1 block">{t('treeForm.sex')}</label>
            <select
              value={fields.sex}
              onChange={(e) => setFields((f) => ({ ...f, sex: e.target.value }))}
              className="w-full h-9 px-3 text-sm border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-brand-500"
            >
              <option value="UNKNOWN">{t('treeForm.unknown')}</option>
              <option value="MALE">{t('treeForm.male')}</option>
              <option value="FEMALE">{t('treeForm.female')}</option>
              <option value="OTHER">{t('treeForm.other')}</option>
            </select>
          </div>
          <div>
            <label className="text-xs font-medium text-slate-600 mb-1 block">{t('treeForm.status')}</label>
            <div className="flex rounded-lg border border-slate-200 overflow-hidden">
              {(['living', 'deceased', 'unknown'] as const).map((s) => (
                <button
                  key={s}
                  type="button"
                  onClick={() => setFields((f) => ({ ...f, status: s }))}
                  className={`flex-1 py-1.5 text-xs font-medium capitalize transition-colors ${
                    fields.status === s ? 'bg-brand-500 text-white' : 'text-slate-500 hover:bg-slate-50'
                  }`}
                >
                  {t(`treeForm.${s}`)}
                </button>
              ))}
            </div>
          </div>
          {/* ── Extra details collapsible ── */}
          <div className="border border-slate-200 rounded-lg overflow-hidden">
            <button
              type="button"
              onClick={() => setShowExtra((v) => !v)}
              className="flex items-center justify-between w-full px-3 py-2 text-xs font-medium text-slate-600 hover:bg-slate-50 transition-colors"
            >
              <span>{t('treeForm.moreDetails')}</span>
              <span className="text-slate-400">{showExtra ? '▲' : '▼'}</span>
            </button>

            {showExtra && (
              <div className="px-3 pb-3 space-y-3 border-t border-slate-100 pt-3">
                {/* Dates */}
                <p className="text-[10px] font-semibold uppercase tracking-wider text-slate-400">Life dates</p>
                <div className="grid grid-cols-2 gap-2">
                  <div>
                    <label className="text-xs text-slate-500 mb-1 block">{t('treeForm.birthDate')}</label>
                    <input
                      type="date"
                      value={fields.birthDate}
                      onChange={(e) => setFields((f) => ({ ...f, birthDate: e.target.value }))}
                      className="w-full h-8 px-2 text-xs border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-brand-500"
                    />
                  </div>
                  <div>
                    <label className="text-xs text-slate-500 mb-1 block">{t('treeForm.birthYear')}</label>
                    <input
                      type="number"
                      min={1}
                      max={9999}
                      placeholder="e.g. 1950"
                      value={fields.birthYear}
                      onChange={(e) => setFields((f) => ({ ...f, birthYear: e.target.value }))}
                      className="w-full h-8 px-2 text-xs border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-brand-500"
                    />
                  </div>
                  <div>
                    <label className="text-xs text-slate-500 mb-1 block">{t('treeForm.deathDate')}</label>
                    <input
                      type="date"
                      value={fields.deathDate}
                      onChange={(e) => setFields((f) => ({ ...f, deathDate: e.target.value }))}
                      className="w-full h-8 px-2 text-xs border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-brand-500"
                    />
                  </div>
                  <div>
                    <label className="text-xs text-slate-500 mb-1 block">{t('treeForm.deathYear')}</label>
                    <input
                      type="number"
                      min={1}
                      max={9999}
                      placeholder="e.g. 2005"
                      value={fields.deathYear}
                      onChange={(e) => setFields((f) => ({ ...f, deathYear: e.target.value }))}
                      className="w-full h-8 px-2 text-xs border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-brand-500"
                    />
                  </div>
                </div>

                {/* Date consistency error */}
                {(() => {
                  const msg = validateDates(fields);
                  if (!msg) return null;
                  return (
                    <p className="text-xs text-red-600 bg-red-50 border border-red-200 rounded-lg px-3 py-2">
                      {msg}
                    </p>
                  );
                })()}

                {/* Born location */}
                <p className="text-[10px] font-semibold uppercase tracking-wider text-slate-400 pt-1">{t('treeForm.bornCity')}</p>
                <div className="grid grid-cols-2 gap-2">
                  <div>
                    <label className="text-xs text-slate-500 mb-1 block">{t('treeForm.bornCity')}</label>
                    <input
                      type="text"
                      placeholder="e.g. London"
                      value={fields.bornCity}
                      onChange={(e) => setFields((f) => ({ ...f, bornCity: e.target.value }))}
                      className="w-full h-8 px-2 text-xs border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-brand-500"
                    />
                  </div>
                  <div>
                    <label className="text-xs text-slate-500 mb-1 block">{t('treeForm.bornCountry')}</label>
                    <input
                      type="text"
                      placeholder="e.g. United Kingdom"
                      value={fields.bornCountry}
                      onChange={(e) => setFields((f) => ({ ...f, bornCountry: e.target.value }))}
                      className="w-full h-8 px-2 text-xs border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-brand-500"
                    />
                  </div>
                </div>

                {/* Died/Buried location */}
                <p className="text-[10px] font-semibold uppercase tracking-wider text-slate-400 pt-1">{t('treeForm.diedCity')}</p>
                <div className="grid grid-cols-2 gap-2">
                  <div>
                    <label className="text-xs text-slate-500 mb-1 block">{t('treeForm.diedCity')}</label>
                    <input
                      type="text"
                      placeholder="e.g. Manchester"
                      value={fields.diedCity}
                      onChange={(e) => setFields((f) => ({ ...f, diedCity: e.target.value }))}
                      className="w-full h-8 px-2 text-xs border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-brand-500"
                    />
                  </div>
                  <div>
                    <label className="text-xs text-slate-500 mb-1 block">{t('treeForm.diedCountry')}</label>
                    <input
                      type="text"
                      placeholder="e.g. United Kingdom"
                      value={fields.diedCountry}
                      onChange={(e) => setFields((f) => ({ ...f, diedCountry: e.target.value }))}
                      className="w-full h-8 px-2 text-xs border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-brand-500"
                    />
                  </div>
                </div>

                {/* Notes */}
                <p className="text-[10px] font-semibold uppercase tracking-wider text-slate-400 pt-1">{t('treeForm.notes')}</p>
                <div>
                  <textarea
                    placeholder="Add notes about this person (max 250 characters)"
                    maxLength={250}
                    value={fields.notes}
                    onChange={(e) => setFields((f) => ({ ...f, notes: e.target.value }))}
                    className="w-full h-20 px-2 py-1.5 text-xs border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-brand-500 resize-none"
                  />
                  <p className="text-[10px] text-slate-400 text-right">{fields.notes.length}/250</p>
                </div>
              </div>
            )}
          </div>

          {error && <p className="text-xs text-red-600">{error}</p>}
          <div className="flex gap-2 pt-1">
            <button type="button" onClick={onClose}
              className="flex-1 h-9 text-sm border border-slate-300 rounded-lg hover:bg-slate-50">
              {t('treeForm.cancel')}
            </button>
            <button type="submit" disabled={loading || photoLoading}
              className="flex-1 h-9 text-sm bg-brand-500 text-white rounded-lg hover:bg-brand-600 disabled:opacity-50">
              {loading ? t('treeForm.saving') : t('treeForm.saveChanges')}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

// ── Person Profile Modal ───────────────────────────────────────────────────

interface PersonDetailFull {
  id: string;
  display_given_name: string;
  display_surname: string;
  sex: string;
  is_living: boolean;
  is_deceased: boolean;
  photo_url?: string | null;
  birth_date?: string | null;
  death_date?: string | null;
  birth_year?: number | null;
  death_year?: number | null;
  born_city?: string | null;
  born_country?: string | null;
  died_city?: string | null;
  died_country?: string | null;
  notes?: string | null;
  parents: string[];
  children: string[];
  spouses: string[];
  siblings: string[];
}

const PROFILE_SEX_LABEL: Record<string, string> = {
  MALE: 'Male', FEMALE: 'Female', OTHER: 'Other', UNKNOWN: 'Unknown',
};
const PROFILE_SEX_BADGE: Record<string, string> = {
  MALE: 'bg-blue-100 text-blue-700', FEMALE: 'bg-pink-100 text-pink-700',
  OTHER: 'bg-purple-100 text-purple-700', UNKNOWN: 'bg-gray-100 text-gray-600',
};
const PROFILE_SEX_AVATAR: Record<string, string> = {
  MALE: 'bg-blue-100 text-blue-600', FEMALE: 'bg-pink-100 text-pink-600',
  OTHER: 'bg-purple-100 text-purple-600', UNKNOWN: 'bg-gray-100 text-gray-500',
};

function fmtDate(iso?: string | null): string {
  if (!iso) return '';
  try {
    return new Date(iso + 'T00:00:00').toLocaleDateString(undefined, {
      year: 'numeric', month: 'long', day: 'numeric',
    });
  } catch { return iso; }
}

interface PersonProfileModalProps {
  initialPersonId: string;
  treeId: string;
  token: string | null;
  graph: import('@features/tree/types').ApiTreeGraph | null;
  onClose: () => void;
}

function PersonProfileModal({ initialPersonId, treeId, token, graph, onClose }: PersonProfileModalProps) {
  const { t } = useTranslation();
  // Navigation history within the modal — allows clicking relatives to browse
  const [history, setHistory] = useState<string[]>([initialPersonId]);
  const personId = history[history.length - 1];

  const [detail,  setDetail]  = useState<PersonDetailFull | null>(null);
  const [loading, setLoading] = useState(false);
  const [fetchErr, setFetchErr] = useState('');
  const [profileGallery, setProfileGallery] = useState<GalleryPhoto[]>([]);
  const [profileHoveredGallery, setProfileHoveredGallery] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    setFetchErr('');
    setDetail(null);
    setProfileGallery([]);
    get<PersonDetailFull>(`/trees/${treeId}/persons/${personId}`)
      .then(setDetail)
      .catch(() => setFetchErr(t('treeForm.failedToLoadProfile')))
      .finally(() => setLoading(false));
    get<GalleryPhoto[]>(`/trees/${treeId}/persons/${personId}/gallery`)
      .then(setProfileGallery)
      .catch(() => {});
  }, [personId, treeId]);

  // Build name + photo maps from the already-loaded graph (zero extra requests)
  const nameMap = useMemo(() => {
    const m: Record<string, string> = {};
    graph?.persons.forEach((p) => { m[p.id] = `${p.displayGivenName} ${p.displaySurname}`.trim() || 'Unknown'; });
    return m;
  }, [graph]);

  const graphPersonMap = useMemo(() => {
    const m: Record<string, import('@features/tree/types').ApiPerson> = {};
    graph?.persons.forEach((p) => { m[p.id] = p; });
    return m;
  }, [graph]);

  const navigateTo  = (id: string) => setHistory((h) => [...h, id]);
  const navigateBack = () => setHistory((h) => h.length > 1 ? h.slice(0, -1) : h);

  const fullName  = detail
    ? `${detail.display_given_name} ${detail.display_surname}`.trim() || 'Unknown'
    : (nameMap[personId] ?? '…');
  const initial   = (fullName[0] ?? '?').toUpperCase();
  const sex       = detail?.sex ?? 'UNKNOWN';
  const avatarCls = PROFILE_SEX_AVATAR[sex] ?? PROFILE_SEX_AVATAR.UNKNOWN;
  const badgeCls  = PROFILE_SEX_BADGE[sex]  ?? PROFILE_SEX_BADGE.UNKNOWN;

  const hasRelatives = detail && (
    detail.parents.length + detail.spouses.length + detail.children.length + detail.siblings.length > 0
  );

  function RelGroup({ ids, label, showUnionDates = false }: { ids: string[]; label: string; showUnionDates?: boolean }) {
    if (!ids.length) return null;
    return (
      <div>
        <p className="text-[10px] font-semibold uppercase tracking-wider text-gray-400 px-3 pb-1">{label}</p>
        {ids.map((id) => {
          const gp   = graphPersonMap[id];
          const name = nameMap[id] ?? 'Unknown';
          const photo = gp?.photoUrl;
          const aCls = PROFILE_SEX_AVATAR[gp?.sex ?? 'UNKNOWN'] ?? PROFILE_SEX_AVATAR.UNKNOWN;
          let unionInfo: import('@features/tree/types').ApiFamilyGroup | undefined;
          if (showUnionDates && graph) {
            unionInfo = graph.familyGroups.find((fg) =>
              fg.parentIds.includes(personId) && fg.parentIds.includes(id)
            );
          }
          const unionDateStr = unionInfo?.unionDate ? fmtDate(unionInfo.unionDate) : unionInfo?.unionDateYear != null ? String(unionInfo.unionDateYear) : null;
          const unionEndDateStr = unionInfo?.unionEndDate ? fmtDate(unionInfo.unionEndDate) : unionInfo?.unionEndDateYear != null ? String(unionInfo.unionEndDateYear) : null;
          const unionLabelMap: Record<string, string> = { MARRIAGE: t('treeForm.marriageLabel'), PARTNERSHIP: t('treeForm.partnershipLabel'), COHABITATION: t('treeForm.cohabitation'), UNKNOWN: t('treeForm.union') };
          const unionLabel = unionInfo ? unionLabelMap[unionInfo.unionType] ?? t('treeForm.union') : null;
          return (
            <button
              key={id}
              type="button"
              onClick={() => navigateTo(id)}
              className="flex items-center gap-3 w-full px-3 py-2 rounded-lg hover:bg-gray-50 group transition-colors text-left"
            >
              {photo ? (
                <img
                  src={isPreset(photo) ? presetDataUri(photo)! : photo}
                  alt={name}
                  className="w-7 h-7 rounded-full object-cover flex-shrink-0"
                />
              ) : (
                <span className={`w-7 h-7 rounded-full flex items-center justify-center text-xs font-semibold flex-shrink-0 ${aCls}`}>
                  {name[0]?.toUpperCase() ?? '?'}
                </span>
              )}
              <div className="flex-1 min-w-0">
                <span className="text-sm text-gray-800 group-hover:text-brand-600 transition-colors truncate block">{name}</span>
                {unionInfo && (unionDateStr || unionEndDateStr || unionInfo.isDivorced) && (
                  <span className="text-[10px] text-gray-400 block truncate">
                    {unionLabel}
                    {unionInfo.isDivorced ? ` (${t('treeForm.divorced')})` : ''}
                    {unionDateStr ? ` · ${unionDateStr}` : ''}
                    {unionEndDateStr ? ` – ${unionEndDateStr}` : ''}
                  </span>
                )}
              </div>
              <span className="text-gray-300 group-hover:text-brand-400 text-xs">›</span>
            </button>
          );
        })}
      </div>
    );
  }

  return (
    <div
      className="fixed inset-0 bg-black/30 z-50 flex items-center justify-center p-4"
      onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}
    >
      <div className="bg-white rounded-2xl shadow-xl w-full max-w-md flex flex-col max-h-[85vh]">

        {/* Header */}
        <div className="flex items-center justify-between px-5 py-3 border-b border-gray-100 shrink-0">
          <div className="flex items-center gap-2 min-w-0">
            {history.length > 1 && (
              <button
                onClick={navigateBack}
                className="text-sm text-gray-400 hover:text-gray-700 transition-colors shrink-0"
              >
                ←
              </button>
            )}
            <span className="text-sm font-semibold text-gray-900 truncate">{fullName}</span>
          </div>
          <button
            onClick={onClose}
            className="ml-3 w-7 h-7 shrink-0 flex items-center justify-center rounded-lg hover:bg-gray-100 text-gray-400"
          >
            ✕
          </button>
        </div>

        {/* Body */}
        <div className="flex-1 overflow-y-auto">

          {loading && (
            <div className="flex justify-center py-12">
              <div className="w-6 h-6 border-2 border-brand-500 border-t-transparent rounded-full animate-spin" />
            </div>
          )}

          {fetchErr && <p className="p-6 text-sm text-red-600">{fetchErr}</p>}

          {!loading && detail && (
            <div className="p-5 space-y-4">

              {/* Person header */}
              <div className="flex items-start gap-4">
                {detail.photo_url ? (
                  <img
                    src={isPreset(detail.photo_url) ? presetDataUri(detail.photo_url)! : detail.photo_url}
                    alt={fullName}
                    className="w-14 h-14 rounded-xl object-cover flex-shrink-0"
                  />
                ) : (
                  <div className={`w-14 h-14 rounded-xl flex items-center justify-center text-xl font-bold flex-shrink-0 ${avatarCls}`}>
                    {initial}
                  </div>
                )}
                <div className="flex-1 min-w-0">
                  <h2 className="text-lg font-bold text-gray-900 leading-tight break-words">{fullName}</h2>
                  <div className="flex flex-wrap items-center gap-1.5 mt-1.5">
                    <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${badgeCls}`}>
                      {t('treeForm.' + detail.sex.toLowerCase()) ?? detail.sex}
                    </span>
                    {detail.is_deceased ? (
                      <span className="text-xs font-medium px-2 py-0.5 rounded-full bg-gray-100 text-gray-600">{t('treeForm.deceased')}</span>
                    ) : detail.is_living ? (
                      <span className="text-xs font-medium px-2 py-0.5 rounded-full bg-green-100 text-green-700">{t('treeForm.living')}</span>
                    ) : null}
                  </div>
                </div>
              </div>

              {/* Gallery photos */}
              {profileGallery.length > 0 && (
                <div className="flex gap-2">
                  {profileGallery.map((gp) => (
                    <div
                      key={gp.id}
                      className="relative"
                      onMouseEnter={() => setProfileHoveredGallery(gp.id)}
                      onMouseLeave={() => setProfileHoveredGallery(null)}
                    >
                      <img
                        src={gp.photoUrl}
                        alt={gp.caption || 'Gallery'}
                        className="w-14 h-14 rounded-lg object-cover cursor-pointer"
                      />
                      {profileHoveredGallery === gp.id && (
                        <div className="fixed inset-0 z-[60] flex items-center justify-center pointer-events-none">
                          <div className="bg-white rounded-xl shadow-2xl p-2 max-w-xs pointer-events-auto">
                            <img src={gp.photoUrl} alt={gp.caption || 'Gallery'} className="w-64 h-64 object-cover rounded-lg" />
                            {gp.caption && (
                              <p className="text-xs text-slate-600 mt-1.5 px-1 text-center">{gp.caption}</p>
                            )}
                          </div>
                        </div>
                      )}
                      {gp.caption && (
                        <p className="text-[9px] text-gray-400 text-center mt-0.5 w-14 truncate">{gp.caption}</p>
                      )}
                    </div>
                  ))}
                </div>
              )}

              {/* Extra details */}
              {(detail.birth_date || detail.birth_year || detail.death_date || detail.death_year ||
                detail.born_city || detail.born_country || detail.died_city || detail.died_country || detail.notes) && (
                <div className="rounded-xl border border-gray-100 divide-y divide-gray-50 overflow-hidden text-sm">
                  {(detail.birth_date || detail.birth_year) && (
                    <div className="flex items-center gap-3 px-4 py-2.5">
                      <span className="text-green-500 shrink-0">●</span>
                      <span className="text-xs text-gray-400 w-12 shrink-0">{t('treeForm.born')}</span>
                      <span className="text-gray-800">
                        {detail.birth_date ? fmtDate(detail.birth_date) : detail.birth_year}
                      </span>
                    </div>
                  )}
                  {(detail.born_city || detail.born_country) && (
                    <div className="flex items-center gap-3 px-4 py-2.5">
                      <span className="text-xs shrink-0">📍</span>
                      <span className="text-xs text-gray-400 w-12 shrink-0">{t('treeForm.bornIn')}</span>
                      <span className="text-gray-800">{[detail.born_city, detail.born_country].filter(Boolean).join(', ')}</span>
                    </div>
                  )}
                  {(detail.is_deceased || detail.death_date || detail.death_year) && (
                    <div className="flex items-center gap-3 px-4 py-2.5">
                      <span className="text-gray-400 text-xs shrink-0">✝</span>
                      <span className="text-xs text-gray-400 w-12 shrink-0">{t('treeForm.died')}</span>
                      <span className="text-gray-800">
                        {detail.death_date ? fmtDate(detail.death_date) : detail.death_year ?? t('treeForm.unknown')}
                      </span>
                    </div>
                  )}
                  {(detail.died_city || detail.died_country) && (
                    <div className="flex items-center gap-3 px-4 py-2.5">
                      <span className="text-xs shrink-0">📍</span>
                      <span className="text-xs text-gray-400 w-12 shrink-0">{t('treeForm.buried')}</span>
                      <span className="text-gray-800">{[detail.died_city, detail.died_country].filter(Boolean).join(', ')}</span>
                    </div>
                  )}
                  {detail.notes && (
                    <div className="flex items-start gap-3 px-4 py-2.5">
                      <span className="text-xs shrink-0 mt-0.5">📝</span>
                      <span className="text-xs text-gray-400 w-12 shrink-0 mt-0.5">{t('treeForm.notesLabel')}</span>
                      <span className="text-gray-800 text-xs whitespace-pre-wrap">{detail.notes}</span>
                    </div>
                  )}
                </div>
              )}

              {/* Relationships */}
              <div className="rounded-xl border border-gray-100 overflow-hidden">
                <div className="px-4 py-2.5 bg-gray-50 border-b border-gray-100">
                  <span className="text-xs font-semibold text-gray-500 uppercase tracking-wider">{t('treeForm.relationships')}</span>
                </div>
                {hasRelatives ? (
                  <div className="divide-y divide-gray-50 p-1 space-y-1">
                    <RelGroup ids={detail.parents}  label={t('treeForm.parents')} />
                    <RelGroup ids={detail.spouses}  label={t('treeForm.spousesPartners')} showUnionDates />
                    <RelGroup ids={detail.children} label={t('treeForm.children')} />
                    <RelGroup ids={detail.siblings} label={t('treeForm.siblings')} />
                  </div>
                ) : (
                  <p className="px-4 py-6 text-center text-sm text-gray-400">{t('treeForm.noRelationshipsYet')}</p>
                )}
              </div>

            </div>
          )}
        </div>
      </div>
    </div>
  );
}

// ── Union dates sub-section (with local state for year fields) ───────────

function UnionDatesSection({
  fg, treeId, familyGroupId, savingDates, setSavingDates,
}: {
  fg: import('@features/tree/types').ApiFamilyGroup | undefined;
  treeId: string;
  familyGroupId: string;
  savingDates: boolean;
  setSavingDates: (v: boolean) => void;
}) {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const [startDate, setStartDate] = useState(fg?.unionDate ?? '');
  const [startYear, setStartYear] = useState(fg?.unionDateYear != null ? String(fg.unionDateYear) : '');
  const [endDate, setEndDate]     = useState(fg?.unionEndDate ?? '');
  const [endYear, setEndYear]     = useState(fg?.unionEndDateYear != null ? String(fg.unionEndDateYear) : '');

  React.useEffect(() => { setStartDate(fg?.unionDate ?? ''); }, [fg?.unionDate]);
  React.useEffect(() => { setStartYear(fg?.unionDateYear != null ? String(fg.unionDateYear) : ''); }, [fg?.unionDateYear]);
  React.useEffect(() => { setEndDate(fg?.unionEndDate ?? ''); }, [fg?.unionEndDate]);
  React.useEffect(() => { setEndYear(fg?.unionEndDateYear != null ? String(fg.unionEndDateYear) : ''); }, [fg?.unionEndDateYear]);

  async function saveField(field: string, value: string | number | null) {
    setSavingDates(true);
    try {
      await patch(`/trees/${treeId}/family-groups/${familyGroupId}`, { [field]: value });
      queryClient.invalidateQueries({ queryKey: queryKeys.trees.detail(treeId) });
    } catch { /* swallow */ }
    finally { setSavingDates(false); }
  }

  const ut = fg?.unionType ?? 'UNKNOWN';
  const unionDateLabelsMap: Record<string, [string, string]> = {
    MARRIAGE:     [t('treeForm.marriedDate'),      t('treeForm.marriedUntil')],
    PARTNERSHIP:  [t('treeForm.partnershipDate'),  t('treeForm.partnershipUntil')],
    COHABITATION: [t('treeForm.cohabitationDate'), t('treeForm.cohabitationUntil')],
    UNKNOWN:      [t('treeForm.unionDate'),        t('treeForm.unionUntil')],
  };
  const [startLabel, endLabel] = unionDateLabelsMap[ut] ?? unionDateLabelsMap.UNKNOWN;
  const startDateYear = startDate ? new Date(startDate + 'T00:00:00').getFullYear() : null;
  const startYearNum = startYear ? parseInt(startYear, 10) : null;
  const startMismatch = startDateYear != null && startYearNum != null && !isNaN(startYearNum) && startDateYear !== startYearNum;
  const endDateYear = endDate ? new Date(endDate + 'T00:00:00').getFullYear() : null;
  const endYearNum = endYear ? parseInt(endYear, 10) : null;
  const endMismatch = endDateYear != null && endYearNum != null && !isNaN(endYearNum) && endDateYear !== endYearNum;

  const inputCls = "w-full h-8 px-2 text-xs border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-brand-500 disabled:opacity-50";

  return (
    <div className="pt-1 border-t border-slate-100 space-y-2">
      <div className="grid grid-cols-2 gap-2">
        <div>
          <label className="text-xs font-medium text-slate-500 mb-1 block">{startLabel}</label>
          <input
            type="date"
            value={startDate}
            disabled={savingDates}
            onChange={(e) => setStartDate(e.target.value)}
            onBlur={() => saveField('union_date', startDate || null)}
            className={inputCls}
          />
        </div>
        <div>
          <label className="text-xs font-medium text-slate-500 mb-1 block">{t('treeForm.yearOnly')}</label>
          <input
            type="number"
            min={1}
            max={9999}
            placeholder="e.g. 1990"
            value={startYear}
            disabled={savingDates}
            onChange={(e) => setStartYear(e.target.value)}
            onBlur={() => saveField('union_date_year', startYear ? parseInt(startYear, 10) : null)}
            onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); saveField('union_date_year', startYear ? parseInt(startYear, 10) : null); (e.target as HTMLInputElement).blur(); } }}
            className={inputCls}
          />
        </div>
      </div>
      {startMismatch && (
        <p className="text-[10px] text-red-600 bg-red-50 border border-red-200 rounded-lg px-2 py-1">
          {startLabel} year ({startDateYear}) doesn't match "Year only" ({startYearNum}).
        </p>
      )}
      <div className="grid grid-cols-2 gap-2">
        <div>
          <label className="text-xs font-medium text-slate-500 mb-1 block">{endLabel}</label>
          <input
            type="date"
            value={endDate}
            disabled={savingDates}
            onChange={(e) => setEndDate(e.target.value)}
            onBlur={() => saveField('union_end_date', endDate || null)}
            className={inputCls}
          />
        </div>
        <div>
          <label className="text-xs font-medium text-slate-500 mb-1 block">{t('treeForm.yearOnly')}</label>
          <input
            type="number"
            min={1}
            max={9999}
            placeholder="e.g. 2005"
            value={endYear}
            disabled={savingDates}
            onChange={(e) => setEndYear(e.target.value)}
            onBlur={() => saveField('union_end_date_year', endYear ? parseInt(endYear, 10) : null)}
            onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); saveField('union_end_date_year', endYear ? parseInt(endYear, 10) : null); (e.target as HTMLInputElement).blur(); } }}
            className={inputCls}
          />
        </div>
      </div>
      {endMismatch && (
        <p className="text-[10px] text-red-600 bg-red-50 border border-red-200 rounded-lg px-2 py-1">
          {endLabel} year ({endDateYear}) doesn't match "Year only" ({endYearNum}).
        </p>
      )}
    </div>
  );
}

// ── Edge selection panel (right drawer) ──────────────────────────────────

const EDGE_UNION_LABEL: Record<string, string> = {
  MARRIAGE: 'Marriage', PARTNERSHIP: 'Partnership',
  COHABITATION: 'Cohabitation', UNKNOWN: 'Union',
};
const EDGE_PARENTAGE_LABEL: Record<string, string> = {
  BIOLOGICAL: 'Biological', ADOPTIVE: 'Adoptive',
  STEP: 'Step', FOSTER: 'Foster', UNKNOWN: 'Unknown',
};

interface EdgeSelectionPanelProps {
  edge: SelectedEdge | null;
  graph: ApiTreeGraph | null | undefined;
  treeId: string;
  token: string | null;
  canWrite: boolean;
  onClose: () => void;
  onDeleted: () => void;
}

const UNION_DATE_LABELS: Record<string, [string, string]> = {
  MARRIAGE:     ['Married Date',      'Married Until'],
  PARTNERSHIP:  ['Partnership Date',  'Partnership Until'],
  COHABITATION: ['Cohabitation Date', 'Cohabitation Until'],
  UNKNOWN:      ['Union Date',        'Union Until'],
};

function EdgeSelectionPanel({ edge, graph, treeId, token, canWrite, onClose, onDeleted }: EdgeSelectionPanelProps) {
  const { t } = useTranslation();
  const [confirmDelete, setConfirmDelete] = React.useState(false);
  const [deleting,      setDeleting]      = React.useState(false);
  const [deleteError,   setDeleteError]   = React.useState('');
  const [togglingDivorce, setTogglingDivorce] = React.useState(false);
  const [savingParentage, setSavingParentage] = React.useState(false);
  const [savingUnionType, setSavingUnionType] = React.useState(false);
  const [savingDates, setSavingDates] = React.useState(false);
  const queryClient = useQueryClient();

  if (!edge) return null;

  const isUnion      = edge.kind === 'union';
  const familyGroupId = isUnion ? edge.target : edge.source;
  const personId      = isUnion ? edge.source : edge.target;

  const resolveName = (pid: string) => {
    const p = graph?.persons.find(pp => pp.id === pid);
    return p ? [p.displayGivenName, p.displaySurname].filter(Boolean).join(' ') || '(unnamed)' : '(unknown)';
  };

  const personName  = resolveName(personId);
  const fg          = graph?.familyGroups.find(f => f.id === familyGroupId);
  const parentNames = (fg?.parentIds ?? []).map(resolveName);

  const edgeUnionLabelMap: Record<string, string> = { MARRIAGE: t('treeForm.marriageLabel'), PARTNERSHIP: t('treeForm.partnershipLabel'), COHABITATION: t('treeForm.cohabitation'), UNKNOWN: t('treeForm.union') };
  const edgeParentageLabelMap: Record<string, string> = { BIOLOGICAL: t('treeForm.biologicalLabel'), ADOPTIVE: t('treeForm.adopted'), STEP: t('treeForm.stepLabel'), FOSTER: t('treeForm.fosterLabel'), UNKNOWN: t('treeForm.unknown') };
  const kindLabel = isUnion
    ? (edgeUnionLabelMap[edge.unionType ?? 'UNKNOWN'] ?? t('treeForm.union'))
    : `${edgeParentageLabelMap[edge.parentageType ?? 'BIOLOGICAL'] ?? t('treeForm.biologicalLabel')} ${t('treeForm.parentChild')}`;
  const subLabel  = `${kindLabel} ${t('treeForm.link')}`;

  async function handleDelete() {
    setDeleting(true);
    setDeleteError('');
    try {
      await del(`/trees/${treeId}/family-groups/${familyGroupId}/members/${personId}`);
      onDeleted();
    } catch (err) {
      setDeleteError(apiErrorMessage(err, 'Failed to remove'));
      setDeleting(false);
    }
  }

  const onlyParent = isUnion && (fg?.parentIds ?? []).length <= 1;

  return (
    <div className="absolute top-0 right-0 h-full w-72 bg-white border-l border-slate-200 shadow-xl z-20 flex flex-col">
      <div className="flex items-center justify-between px-4 py-3 border-b border-slate-200">
        <div className="min-w-0">
          <span className="text-sm font-semibold text-slate-700">{t('treeForm.relationshipTitle')}</span>
          <p className="text-xs text-slate-400 mt-0.5 truncate">{subLabel}</p>
        </div>
        <button onClick={onClose} className="ml-2 w-7 h-7 flex-shrink-0 flex items-center justify-center rounded-lg hover:bg-slate-100 text-slate-400">✕</button>
      </div>

      <div className="flex-1 overflow-y-auto p-4">
        <div className="space-y-3">
          <div className="rounded-lg bg-slate-50 border border-slate-200 p-3 space-y-1.5 text-sm">
            <div className="flex items-center gap-2 text-slate-700">
              <span>{isUnion ? '👤' : '👶'}</span>
              <span className="font-medium">{personName}</span>
            </div>
            {parentNames.length > 0 && (
              <div className="flex items-start gap-2 text-xs text-slate-500">
                <span className="mt-0.5">{isUnion ? '🔗' : '👨‍👩'}</span>
                <span>{isUnion ? t('treeForm.familyWith', { names: parentNames.join(' & ') }) : t('treeForm.childOf', { names: parentNames.join(' & ') })}</span>
              </div>
            )}
          </div>

          {canWrite && !isUnion && (
            <div className="pt-1 border-t border-slate-100">
              <label className="text-xs font-medium text-slate-500 mb-1.5 block">{t('treeForm.parentageType')}</label>
              <select
                value={edge.parentageType ?? 'BIOLOGICAL'}
                disabled={savingParentage}
                onChange={async (e) => {
                  setSavingParentage(true);
                  try {
                    await patch(`/trees/${treeId}/family-groups/${familyGroupId}/members/${personId}`, {
                      parentage_type: e.target.value,
                    });
                    queryClient.invalidateQueries({ queryKey: queryKeys.trees.detail(treeId) });
                  } catch { /* swallow */ }
                  finally { setSavingParentage(false); }
                }}
                className="w-full h-8 px-2 text-sm border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-brand-500 disabled:opacity-50"
              >
                <option value="BIOLOGICAL">{t('treeForm.biologicalLabel')}</option>
                <option value="ADOPTIVE">{t('treeForm.adopted')}</option>
                <option value="STEP">{t('treeForm.stepLabel')}</option>
                <option value="FOSTER">{t('treeForm.fosterLabel')}</option>
                <option value="UNKNOWN">{t('treeForm.unknown')}</option>
              </select>
            </div>
          )}

          {canWrite && isUnion && (
            <div className="pt-1 border-t border-slate-100">
              <label className="text-xs font-medium text-slate-500 mb-1.5 block">{t('treeForm.unionType')}</label>
              <select
                value={fg?.unionType ?? 'MARRIAGE'}
                disabled={savingUnionType}
                onChange={async (e) => {
                  setSavingUnionType(true);
                  try {
                    await patch(`/trees/${treeId}/family-groups/${familyGroupId}`, {
                      union_type: e.target.value,
                    });
                    queryClient.invalidateQueries({ queryKey: queryKeys.trees.detail(treeId) });
                  } catch { /* swallow */ }
                  finally { setSavingUnionType(false); }
                }}
                className="w-full h-8 px-2 text-sm border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-brand-500 disabled:opacity-50"
              >
                <option value="MARRIAGE">{t('treeForm.marriageLabel')}</option>
                <option value="PARTNERSHIP">{t('treeForm.partnershipLabel')}</option>
                <option value="COHABITATION">{t('treeForm.cohabitation')}</option>
                <option value="UNKNOWN">{t('treeForm.unknown')}</option>
              </select>
            </div>
          )}

          {canWrite && isUnion && (
            <UnionDatesSection
              fg={fg}
              treeId={treeId}
              familyGroupId={familyGroupId}
              savingDates={savingDates}
              setSavingDates={setSavingDates}
            />
          )}

          {canWrite && isUnion && (
            <div className="pt-1 border-t border-slate-100">
              <button
                disabled={togglingDivorce}
                onClick={async () => {
                  setTogglingDivorce(true);
                  try {
                    await patch(`/trees/${treeId}/family-groups/${familyGroupId}`, {
                      is_divorced: !fg?.isDivorced,
                    });
                    queryClient.invalidateQueries({ queryKey: queryKeys.trees.detail(treeId) });
                  } catch { /* swallow */ }
                  finally { setTogglingDivorce(false); }
                }}
                className={`flex items-center gap-2 w-full px-3 py-2 text-sm rounded-lg border transition-colors ${
                  fg?.isDivorced
                    ? 'text-amber-700 bg-amber-50 border-amber-200 hover:bg-amber-100'
                    : 'text-slate-600 border-slate-200 hover:bg-slate-50'
                } disabled:opacity-50`}
              >
                {togglingDivorce ? '…' : fg?.isDivorced ? t('treeForm.undoDivorced') : t('treeForm.markAsDivorced')}
              </button>
            </div>
          )}

          {canWrite && (
            <>
              <div className="pt-1 border-t border-slate-100" />
              {!confirmDelete ? (
                <button
                  onClick={() => { setDeleteError(''); setConfirmDelete(true); }}
                  className="flex items-center gap-2 w-full px-3 py-2 text-sm text-red-500 rounded-lg hover:bg-red-50 border border-red-100"
                >
                  {t('treeForm.removeRelationship')}
                </button>
              ) : (
                <div className="rounded-lg border border-red-200 bg-red-50 p-3 space-y-2">
                  <p className="text-xs text-red-700 font-medium">
                    {isUnion
                      ? t('treeForm.removeFromUnion', { name: personName })
                      : t('treeForm.removeFromFamily', { name: personName })}
                  </p>
                  {onlyParent && (
                    <p className="text-xs text-red-500">{t('treeForm.lastParentWarning')}</p>
                  )}
                  {!isUnion && (
                    <p className="text-xs text-slate-500">The person stays in the tree; only the parent–child link is removed.</p>
                  )}
                  {deleteError && <p className="text-xs text-red-600">{deleteError}</p>}
                  <div className="flex gap-2">
                    <button
                      onClick={() => { setConfirmDelete(false); setDeleteError(''); }}
                      disabled={deleting}
                      className="flex-1 h-7 text-xs border border-slate-300 bg-white rounded-lg hover:bg-slate-50 disabled:opacity-50"
                    >Cancel</button>
                    <button
                      onClick={handleDelete}
                      disabled={deleting}
                      className="flex-1 h-7 text-xs bg-red-600 text-white rounded-lg hover:bg-red-700 disabled:opacity-50"
                    >{deleting ? 'Removing…' : 'Remove'}</button>
                  </div>
                </div>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
}

// ── Selection panel (right drawer) ────────────────────────────────────────

interface SelectionPanelProps {
  personId: string | null;
  personName: string;
  treeId: string;
  token: string | null;
  canWrite: boolean;
  onClose: () => void;
  onOpenProfile: () => void;
  onAddParent: () => void;
  onAddBothParents: () => void;
  onAddChild: () => void;
  onAddSpouse: () => void;
  onSetFocus: () => void;
  onDeleted: () => void;
  onEdit: () => void;
}

function SelectionPanel({
  personId, personName, treeId, token, canWrite,
  onClose, onOpenProfile, onAddParent, onAddBothParents, onAddChild, onAddSpouse, onSetFocus, onDeleted, onEdit,
}: SelectionPanelProps) {
  const { t } = useTranslation();
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [deleting,      setDeleting]      = useState(false);
  const [deleteError,   setDeleteError]   = useState('');

  if (!personId) return null;

  async function handleDelete() {
    setDeleting(true);
    setDeleteError('');
    try {
      await del(`/trees/${treeId}/persons/${personId}`);
      onDeleted();
    } catch (err) {
      setDeleteError(apiErrorMessage(err, 'Failed to delete'));
      setDeleting(false);
    }
  }

  return (
    <div className="absolute top-0 right-0 h-full w-72 bg-white border-l border-slate-200 shadow-xl z-20 flex flex-col">
      <div className="flex items-center justify-between px-4 py-3 border-b border-slate-200">
        <div className="min-w-0">
          <span className="text-sm font-semibold text-slate-700">{t('treeForm.person')}</span>
          {personName && (
            <p className="text-xs text-slate-400 mt-0.5 truncate">{personName}</p>
          )}
        </div>
        <button
          onClick={onClose}
          className="ml-2 w-7 h-7 flex-shrink-0 flex items-center justify-center rounded-lg hover:bg-slate-100 text-slate-400"
        >
          ✕
        </button>
      </div>

      <div className="flex-1 overflow-y-auto p-4">
        <div className="space-y-2">
          <button
            onClick={onOpenProfile}
            className="flex items-center gap-2 w-full px-3 py-2 text-sm text-slate-700 rounded-lg hover:bg-slate-50 border border-slate-200"
          >
            👤 {t('treeForm.openProfile')}
          </button>
          {canWrite && (
            <button onClick={onEdit}
              className="flex items-center gap-2 w-full px-3 py-2 text-sm text-slate-700 rounded-lg hover:bg-slate-50 border border-slate-200">
              ✏️ {t('treeForm.edit')}
            </button>
          )}
          {canWrite && (
            <button onClick={onAddParent}
              className="flex items-center gap-2 w-full px-3 py-2 text-sm text-slate-700 rounded-lg hover:bg-slate-50 border border-slate-200">
              ➕ {t('treeForm.addParent')}
            </button>
          )}
          {canWrite && (
            <button onClick={onAddBothParents}
              className="flex items-center gap-2 w-full px-3 py-2 text-sm text-slate-700 rounded-lg hover:bg-slate-50 border border-slate-200">
              👨‍👩 {t('treeForm.addFatherMother')}
            </button>
          )}
          {canWrite && (
            <button onClick={onAddChild}
              className="flex items-center gap-2 w-full px-3 py-2 text-sm text-slate-700 rounded-lg hover:bg-slate-50 border border-slate-200">
              ➕ {t('treeForm.addChild')}
            </button>
          )}
          {canWrite && (
            <button onClick={onAddSpouse}
              className="flex items-center gap-2 w-full px-3 py-2 text-sm text-slate-700 rounded-lg hover:bg-slate-50 border border-slate-200">
              ➕ {t('treeForm.addSpouse')}
            </button>
          )}
          <button onClick={onSetFocus}
            className="flex items-center gap-2 w-full px-3 py-2 text-sm text-slate-700 rounded-lg hover:bg-slate-50 border border-slate-200">
            🎯 {t('treeForm.setAsFocus')}
          </button>

          {/* Divider + delete — write only */}
          {canWrite && (
            <>
              <div className="pt-2 border-t border-slate-100" />
              {!confirmDelete ? (
                <button
                  onClick={() => { setDeleteError(''); setConfirmDelete(true); }}
                  className="flex items-center gap-2 w-full px-3 py-2 text-sm text-red-500 rounded-lg hover:bg-red-50 border border-red-100"
                >
                  🗑 {t('treeForm.deletePerson')}
                </button>
              ) : (
                <div className="rounded-lg border border-red-200 bg-red-50 p-3 space-y-2">
                  <p className="text-xs text-red-700 font-medium">
                    {t('treeForm.confirmDelete')}
                  </p>
                  {deleteError && <p className="text-xs text-red-600">{deleteError}</p>}
                  <div className="flex gap-2">
                    <button
                      onClick={() => { setConfirmDelete(false); setDeleteError(''); }}
                      disabled={deleting}
                      className="flex-1 h-7 text-xs border border-slate-300 bg-white rounded-lg hover:bg-slate-50 disabled:opacity-50"
                    >
                      {t('treeForm.cancel')}
                    </button>
                    <button
                      onClick={handleDelete}
                      disabled={deleting}
                      className="flex-1 h-7 text-xs bg-red-600 text-white rounded-lg hover:bg-red-700 disabled:opacity-50"
                    >
                      {deleting ? t('treeForm.deleting') : t('common.delete')}
                    </button>
                  </div>
                </div>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
}

// ── Members modal ─────────────────────────────────────────────────────────

interface Member {
  id: string;
  user_id: string;
  role: string;
  joined_at: string | null;
  email: string;
  display_name: string;
}

const ROLE_COLOR: Record<string, string> = {
  OWNER:  'bg-brand-100 text-brand-700',
  ADMIN:  'bg-purple-100 text-purple-700',
  EDITOR: 'bg-green-100 text-green-700',
  VIEWER: 'bg-gray-100 text-gray-500',
};

function MembersModal({
  treeId, token, currentUserId, onClose,
}: {
  treeId: string;
  token: string | null;
  currentUserId: string;
  onClose: () => void;
}) {
  const { t } = useTranslation();
  const [members,  setMembers]  = useState<Member[]>([]);
  const [loading,  setLoading]  = useState(true);
  const [error,    setError]    = useState('');
  const [removing, setRemoving] = useState<string | null>(null);

  useEffect(() => {
    get<Member[]>(`/trees/${treeId}/members`)
      .then(setMembers)
      .catch(() => setError(t('treePage.failedLoadMembers')))
      .finally(() => setLoading(false));
  }, [treeId]);

  const myRole = members.find((m) => m.user_id === currentUserId)?.role ?? '';
  const canRemove = myRole === 'OWNER' || myRole === 'ADMIN';

  async function handleRemove(member: Member) {
    setRemoving(member.user_id);
    try {
      await del(`/trees/${treeId}/members/${member.user_id}`);
      setMembers((prev) => prev.filter((m) => m.user_id !== member.user_id));
    } catch (err) {
      setError(apiErrorMessage(err, t('treePage.failedRemoveMember')));
    } finally {
      setRemoving(null);
    }
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4"
      onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}
    >
      <div className="bg-white rounded-2xl shadow-xl w-full max-w-md">
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-100">
          <h2 className="text-base font-semibold text-slate-900">{t('treePage.members')}</h2>
          <button onClick={onClose} className="w-7 h-7 flex items-center justify-center rounded-lg hover:bg-slate-100 text-slate-400">✕</button>
        </div>

        <div className="p-4 max-h-96 overflow-y-auto">
          {loading && (
            <div className="flex justify-center py-8">
              <div className="w-6 h-6 border-2 border-brand-500 border-t-transparent rounded-full animate-spin" />
            </div>
          )}
          {error && <p className="text-sm text-red-600 px-2">{error}</p>}
          {!loading && members.map((m) => (
            <div key={m.user_id} className="flex items-center gap-3 px-2 py-2.5 rounded-lg hover:bg-slate-50">
              <div className="w-8 h-8 rounded-full bg-slate-100 flex items-center justify-center text-sm font-semibold text-slate-500 flex-shrink-0">
                {(m.display_name[0] ?? '?').toUpperCase()}
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium text-slate-800 truncate">{m.display_name}</p>
                <p className="text-xs text-slate-400 truncate">{m.email}</p>
              </div>
              <span className={`text-xs font-medium px-2 py-0.5 rounded-full flex-shrink-0 ${ROLE_COLOR[m.role] ?? ROLE_COLOR.VIEWER}`}>
                {t('roles.' + m.role)}
              </span>
              {canRemove && m.user_id !== currentUserId && m.role !== 'OWNER' && (
                <button
                  onClick={() => handleRemove(m)}
                  disabled={removing === m.user_id}
                  className="ml-1 w-6 h-6 flex items-center justify-center rounded text-slate-300 hover:text-red-500 hover:bg-red-50 disabled:opacity-40 transition-colors flex-shrink-0"
                  title={t('treePage.removeMember')}
                >
                  ✕
                </button>
              )}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

// ── Top bar ────────────────────────────────────────────────────────────────

function TreeTopBar({
  treeName,
  treeDescription,
  personCount,
  graph,
  token,
  canWrite,
  onAddPerson,
  onMembers,
  onLayouts,
  onExportCsv,
  onExportPdf,
  onTheme,
  onShowActivity,
}: {
  treeName: string;
  treeDescription?: string | null;
  personCount: number;
  graph: import('@features/tree/types').ApiTreeGraph | null;
  token: string | null;
  canWrite: boolean;
  onAddPerson: () => void;
  onMembers: () => void;
  onLayouts: () => void;
  onExportCsv: () => void;
  onExportPdf: () => Promise<void>;
  onTheme: () => void;
  onShowActivity: () => void;
}) {
  const { t } = useTranslation();
  const [exportOpen,    setExportOpen]    = React.useState(false);
  const [moreOpen,      setMoreOpen]      = React.useState(false);
  const [exportingPdf,  setExportingPdf]  = React.useState(false);
  const [exportingZip,  setExportingZip]  = React.useState(false);
  const exportMenuRef = React.useRef<HTMLDivElement>(null);
  const moreMenuRef   = React.useRef<HTMLDivElement>(null);

  // Close export dropdown when clicking outside
  React.useEffect(() => {
    if (!exportOpen) return;
    function onMouseDown(e: MouseEvent) {
      if (exportMenuRef.current && !exportMenuRef.current.contains(e.target as Node)) {
        setExportOpen(false);
      }
    }
    document.addEventListener('mousedown', onMouseDown);
    return () => document.removeEventListener('mousedown', onMouseDown);
  }, [exportOpen]);

  // Close mobile "more" menu when clicking outside
  React.useEffect(() => {
    if (!moreOpen) return;
    function onMouseDown(e: MouseEvent) {
      if (moreMenuRef.current && !moreMenuRef.current.contains(e.target as Node)) {
        setMoreOpen(false);
      }
    }
    document.addEventListener('mousedown', onMouseDown);
    return () => document.removeEventListener('mousedown', onMouseDown);
  }, [moreOpen]);

  const [exportPdfError, setExportPdfError] = React.useState('');

  async function handleExportPdf() {
    if (exportingPdf) return;
    setExportingPdf(true);
    setExportOpen(false);
    setExportPdfError('');
    try {
      await onExportPdf();
    } catch (err) {
      console.error('PDF export failed:', err);
      setExportPdfError(t('treePage.pdfFailed'));
    } finally {
      setExportingPdf(false);
    }
  }

  function handleExportFrt() {
    if (!graph) return;
    setExportOpen(false);
    const payload = {
      frt_version: '1.0',
      exported_at: new Date().toISOString(),
      tree_name: treeName,
      tree_description: treeDescription ?? null,
      persons: graph.persons.map((p) => ({
        id: p.id,
        display_given_name: p.displayGivenName,
        display_surname: p.displaySurname,
        sex: p.sex,
        is_living: p.isLiving,
        is_deceased: p.isDeceased,
        ...(p.photoUrl ? { photo_url: p.photoUrl } : {}),
        ...(p.birthDate ? { birth_date: p.birthDate } : {}),
        ...(p.deathDate ? { death_date: p.deathDate } : {}),
        ...(p.birthYear != null ? { birth_year: p.birthYear } : {}),
        ...(p.deathYear != null ? { death_year: p.deathYear } : {}),
        ...(p.bornCity ? { born_city: p.bornCity } : {}),
        ...(p.bornCountry ? { born_country: p.bornCountry } : {}),
        ...(p.diedCity ? { died_city: p.diedCity } : {}),
        ...(p.diedCountry ? { died_country: p.diedCountry } : {}),
        ...(p.notes ? { notes: p.notes } : {}),
      })),
      family_groups: graph.familyGroups.map((fg) => ({
        id: fg.id,
        union_type: fg.unionType,
        ...(fg.customLabel ? { custom_label: fg.customLabel } : {}),
        ...(fg.isDivorced ? { is_divorced: true } : {}),
        ...(fg.unionDate ? { union_date: fg.unionDate } : {}),
        ...(fg.unionDateYear != null ? { union_date_year: fg.unionDateYear } : {}),
        ...(fg.unionEndDate ? { union_end_date: fg.unionEndDate } : {}),
        ...(fg.unionEndDateYear != null ? { union_end_date_year: fg.unionEndDateYear } : {}),
        parent_ids: fg.parentIds,
        children: fg.children,
      })),
    };
    const blob = new Blob([JSON.stringify(payload, null, 2)], { type: 'application/json' });
    const url  = URL.createObjectURL(blob);
    const a    = document.createElement('a');
    a.href     = url;
    a.download = `${treeName.replace(/\s+/g, '_')}.frt`;
    a.click();
    URL.revokeObjectURL(url);
    post(`/trees/${graph.treeId}/export-log`).catch(() => {});
  }

  async function handleExportZip() {
    if (!graph || exportingZip) return;
    setExportOpen(false);
    setExportingZip(true);
    try {
      const res = await apiClient.get(`/trees/${graph.treeId}/export-zip`, { responseType: 'blob' });
      const blob = res.data as Blob;
      const url  = URL.createObjectURL(blob);
      const a    = document.createElement('a');
      a.href     = url;
      a.download = `${treeName.replace(/\s+/g, '_')}.zip`;
      a.click();
      URL.revokeObjectURL(url);
      post(`/trees/${graph.treeId}/export-log`).catch(() => {});
    } catch {
      // silently ignore
    } finally {
      setExportingZip(false);
    }
  }

  function handleExportCsv() {
    setExportOpen(false);
    onExportCsv();
  }

  const anyExporting = exportingPdf || exportingZip;

  return (
    <div className="absolute top-0 left-0 right-0 h-12 bg-white/90 backdrop-blur border-b border-slate-200 flex items-center px-3 md:px-4 gap-2 md:gap-3 z-30">
      <Link to="/dashboard" className="text-slate-400 hover:text-slate-600 transition-colors text-sm shrink-0">
        {t('treePage.dashboard')}
      </Link>
      <div className="w-px h-5 bg-slate-200 shrink-0" />
      <span className="font-semibold text-slate-800 text-sm truncate min-w-0">{treeName}</span>
      <span className="text-xs text-slate-400 shrink-0 hidden sm:inline">{personCount} {t('treePage.people')}</span>

      <div className="ml-auto flex items-center gap-1.5 md:gap-2">

        {/* ── Export dropdown (hidden on mobile, shown md+) ── */}
        <div className="relative hidden md:block" ref={exportMenuRef}>
          <button
            onClick={() => setExportOpen((o) => !o)}
            disabled={!graph || anyExporting}
            title={t('treePage.exportTreeData')}
            className="px-3 py-1.5 text-xs font-medium text-slate-600 rounded-lg hover:bg-slate-100 transition-colors disabled:opacity-40 flex items-center gap-1.5"
          >
            {anyExporting ? (
              <span className="w-3 h-3 border border-slate-400 border-t-transparent rounded-full animate-spin" />
            ) : (
              <svg width="11" height="11" viewBox="0 0 11 11" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round">
                <path d="M5.5 1v6M2.5 5l3 3 3-3" />
                <path d="M1 9.5h9" />
              </svg>
            )}
            {t('treePage.export')}
            <svg width="10" height="10" viewBox="0 0 10 10" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" className={`transition-transform ${exportOpen ? 'rotate-180' : ''}`}>
              <path d="M2 3.5l3 3 3-3" />
            </svg>
          </button>

          {exportPdfError && (
            <div className="absolute right-0 top-full mt-1.5 bg-red-50 border border-red-200 text-red-700 text-xs rounded-lg px-3 py-2 z-50 whitespace-nowrap">
              {exportPdfError}
            </div>
          )}

          {exportOpen && (
            <div className="absolute right-0 top-full mt-1.5 w-52 bg-white rounded-xl border border-slate-200 shadow-lg z-50 overflow-hidden">
              <div className="px-3 pt-2.5 pb-1.5 text-[10px] font-semibold text-slate-400 uppercase tracking-widest border-b border-slate-100">
                {t('treePage.export')}
              </div>
              <div className="py-1">
                {/* PDF */}
                <button
                  onClick={handleExportPdf}
                  className="w-full flex items-center gap-2.5 px-3 py-2 text-xs text-slate-700 hover:bg-slate-50 transition-colors text-left"
                >
                  <svg width="14" height="14" viewBox="0 0 14 14" fill="none" stroke="currentColor" strokeWidth="1.5" className="text-red-400 shrink-0">
                    <path d="M2 2a1 1 0 011-1h5l3 3v8a1 1 0 01-1 1H3a1 1 0 01-1-1V2z" />
                    <path d="M8 1v3h3" />
                    <path d="M4 8h6M4 10h4" strokeLinecap="round" />
                  </svg>
                  {t('treePage.exportAsPdf')}
                </button>

                {/* CSV */}
                <button
                  onClick={handleExportCsv}
                  disabled={!graph}
                  className="w-full flex items-center gap-2.5 px-3 py-2 text-xs text-slate-700 hover:bg-slate-50 transition-colors text-left disabled:opacity-40"
                >
                  <svg width="14" height="14" viewBox="0 0 14 14" fill="none" stroke="currentColor" strokeWidth="1.5" className="text-green-500 shrink-0">
                    <rect x="1" y="1" width="12" height="12" rx="1.5" />
                    <path d="M1 4.5h12M4.5 4.5v8.5M1 7.5h12M1 10.5h12" strokeLinecap="round" />
                  </svg>
                  {t('treePage.exportAsCsv')}
                </button>

                {/* FRT */}
                <button
                  onClick={handleExportFrt}
                  disabled={!graph}
                  className="w-full flex items-center gap-2.5 px-3 py-2 text-xs text-slate-700 hover:bg-slate-50 transition-colors text-left disabled:opacity-40"
                >
                  <svg width="14" height="14" viewBox="0 0 14 14" fill="none" stroke="currentColor" strokeWidth="1.5" className="text-brand-400 shrink-0">
                    <path d="M2 2a1 1 0 011-1h5l3 3v8a1 1 0 01-1 1H3a1 1 0 01-1-1V2z" />
                    <path d="M8 1v3h3" />
                    <path d="M4 7h4M4 9.5h2.5" strokeLinecap="round" />
                  </svg>
                  {t('treePage.exportAsFrt')}
                </button>

                {/* ZIP */}
                <button
                  onClick={handleExportZip}
                  disabled={!graph || exportingZip}
                  className="w-full flex items-center gap-2.5 px-3 py-2 text-xs text-slate-700 hover:bg-slate-50 transition-colors text-left disabled:opacity-40"
                >
                  {exportingZip ? (
                    <span className="w-3.5 h-3.5 border border-slate-400 border-t-transparent rounded-full animate-spin shrink-0" />
                  ) : (
                    <svg width="14" height="14" viewBox="0 0 14 14" fill="none" stroke="currentColor" strokeWidth="1.5" className="text-amber-500 shrink-0">
                      <rect x="1" y="1" width="12" height="12" rx="1.5" />
                      <path d="M5.5 1v4M5.5 5h3M5.5 5v4" strokeLinecap="round" />
                      <path d="M4 10h6" strokeLinecap="round" />
                    </svg>
                  )}
                  {exportingZip ? t('treePage.exporting') : t('treePage.exportZipPhotos')}
                </button>
              </div>
            </div>
          )}
        </div>

        <div className="w-px h-4 bg-slate-200 hidden md:block" />

        <button
          onClick={onLayouts}
          title={t('treePage.saveLayout')}
          className="hidden md:inline-flex px-3 py-1.5 text-xs font-medium text-slate-600 rounded-lg hover:bg-slate-100 transition-colors"
        >
          {t('treePage.layouts')}
        </button>
        <button
          onClick={onTheme}
          title={t('treePage.customizeTheme')}
          className="hidden md:inline-flex px-3 py-1.5 text-xs font-medium text-slate-600 rounded-lg hover:bg-slate-100 transition-colors"
        >
          {`🎨 ${t('treePage.theme')}`}
        </button>
        <button
          onClick={onMembers}
          className="hidden md:inline-flex px-3 py-1.5 text-xs font-medium text-slate-600 rounded-lg hover:bg-slate-100 transition-colors"
        >
          {t('treePage.members')}
        </button>

        {/* ── Mobile "⋮" overflow menu ── */}
        <div className="relative md:hidden" ref={moreMenuRef}>
          <button
            onClick={() => setMoreOpen((o) => !o)}
            className="p-2 text-slate-600 rounded-lg hover:bg-slate-100 transition-colors"
            aria-label={t('treePage.moreOptions')}
          >
            <svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor">
              <circle cx="8" cy="3" r="1.4"/><circle cx="8" cy="8" r="1.4"/><circle cx="8" cy="13" r="1.4"/>
            </svg>
          </button>
          {moreOpen && (
            <div className="absolute right-0 top-full mt-1 w-44 bg-white rounded-xl border border-slate-200 shadow-lg z-50 overflow-hidden">
              <div className="py-1">
                <button onClick={() => { setMoreOpen(false); onLayouts(); }}
                  className="w-full text-left px-4 py-2.5 text-sm text-slate-700 hover:bg-slate-50">
                  {t('treePage.layouts')}
                </button>
                <button onClick={() => { setMoreOpen(false); onTheme(); }}
                  className="w-full text-left px-4 py-2.5 text-sm text-slate-700 hover:bg-slate-50">
                  {`🎨 ${t('treePage.theme')}`}
                </button>
                <button onClick={() => { setMoreOpen(false); onMembers(); }}
                  className="w-full text-left px-4 py-2.5 text-sm text-slate-700 hover:bg-slate-50">
                  {t('treePage.members')}
                </button>
                <div className="border-t border-slate-100 my-1" />
                <button onClick={() => { setMoreOpen(false); onExportCsv(); }}
                  disabled={!graph}
                  className="w-full text-left px-4 py-2.5 text-sm text-slate-700 hover:bg-slate-50 disabled:opacity-40">
                  {t('treePage.exportAsCsv')}
                </button>
                <button onClick={() => { setMoreOpen(false); handleExportPdf(); }}
                  disabled={exportingPdf}
                  className="w-full text-left px-4 py-2.5 text-sm text-slate-700 hover:bg-slate-50 disabled:opacity-40">
                  {exportingPdf ? t('treePage.exporting') : t('treePage.exportPdf')}
                </button>
              </div>
            </div>
          )}
        </div>

        {canWrite && (
          <button
            onClick={onAddPerson}
            className="px-2.5 md:px-3 py-1.5 bg-brand-500 text-white text-xs font-medium rounded-lg hover:bg-brand-600 transition-colors"
          >
            <span className="hidden sm:inline">{t('treePage.addPerson')}</span>
            <span className="sm:hidden">+</span>
          </button>
        )}
      </div>
    </div>
  );
}

// ── Page ───────────────────────────────────────────────────────────────────

// ── Saved layouts ──────────────────────────────────────────────────────────

interface SavedLayout {
  id: string;
  name: string;
  savedAt: string;
  positions: Record<string, { x: number; y: number }>;
}

function layoutsKey(treeId: string) { return `fr:layouts:${treeId}`; }

function loadLayouts(treeId: string): SavedLayout[] {
  try { return JSON.parse(localStorage.getItem(layoutsKey(treeId)) ?? '[]'); }
  catch { return []; }
}

function saveLayouts(treeId: string, layouts: SavedLayout[]) {
  localStorage.setItem(layoutsKey(treeId), JSON.stringify(layouts));
}

// ── CSV export ─────────────────────────────────────────────────────────────

function exportTreeCsv(graph: import('@features/tree/types').ApiTreeGraph, treeName: string) {
  const personMap = new Map(graph.persons.map((p) => [p.id, p]));
  const personParents = new Map<string, [string, string]>();
  for (const fg of graph.familyGroups) {
    for (const childId of Object.keys(fg.children)) {
      personParents.set(childId, [fg.parentIds[0] ?? '', fg.parentIds[1] ?? '']);
    }
  }

  const escape = (v: string) => `"${v.replace(/"/g, '""')}"`;

  const header = [
    'ID', 'First Name', 'Last Name', 'Sex', 'Status',
    'Parent 1 ID', 'Parent 1 First Name', 'Parent 1 Last Name',
    'Parent 2 ID', 'Parent 2 First Name', 'Parent 2 Last Name',
  ].map(escape).join(',');

  const rows = graph.persons.map((p) => {
    const [p1id, p2id] = personParents.get(p.id) ?? ['', ''];
    const p1 = personMap.get(p1id);
    const p2 = personMap.get(p2id);
    const status = p.isDeceased ? 'Deceased' : p.isLiving ? 'Living' : 'Unknown';
    return [
      p.id,
      p.displayGivenName ?? '',
      p.displaySurname ?? '',
      p.sex,
      status,
      p1id,
      p1?.displayGivenName ?? '',
      p1?.displaySurname ?? '',
      p2id,
      p2?.displayGivenName ?? '',
      p2?.displaySurname ?? '',
    ].map((v) => escape(String(v))).join(',');
  });

  const csv = [header, ...rows].join('\n');
  const blob = new Blob(['﻿' + csv], { type: 'text/csv;charset=utf-8;' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `${treeName.replace(/\s+/g, '_')}.csv`;
  a.click();
  URL.revokeObjectURL(url);
}

// ── Page ───────────────────────────────────────────────────────────────────

export default function FamilyTreePage() {
  const { treeId } = useParams<{ treeId: string }>();

  const canvasRef = React.useRef<TreeCanvasHandle>(null);
  const [showLayouts,     setShowLayouts]     = useState(false);
  const [showCanvasTheme, setShowCanvasTheme] = useState(false);

  const [panelPersonId,     setPanelPersonId]     = useState<string | null>(null);
  const [showAddPerson,     setShowAddPerson]     = useState(false);
  const [relationMode,      setRelationMode]      = useState<RelationMode | null>(null);
  const [showMembers,       setShowMembers]       = useState(false);
  const [unionChildFgId,    setUnionChildFgId]    = useState<string | null>(null);
  const [showEdit,          setShowEdit]          = useState(false);
  const [showProfile,       setShowProfile]       = useState(false);
  const [showActivity,      setShowActivity]      = useState(false);
  const [searchOpen,        setSearchOpen]        = useState(false);
  const [searchQuery,       setSearchQuery]       = useState('');
  const searchInputRef = React.useRef<HTMLInputElement>(null);

  const setTreeId        = useCanvasStore((s) => s.setTreeId);
  const resetCanvas      = useCanvasStore((s) => s.reset);
  const setFocusPerson   = useCanvasStore((s) => s.setFocusPersonId);
  const bumpLayoutReset  = useCanvasStore((s) => s.bumpLayoutReset);
  const selectedEdge     = useCanvasStore((s) => s.selectedEdge);
  const accessToken      = useAuthStore((s) => s.accessToken);

  // Close the person panel when an edge is selected, and vice-versa
  useEffect(() => {
    if (selectedEdge !== null) setPanelPersonId(null);
  }, [selectedEdge]);

  useEffect(() => {
    if (treeId) setTreeId(treeId);
    return () => resetCanvas();
  }, [treeId, setTreeId, resetCanvas]);

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.ctrlKey && e.code === 'Space') {
        e.preventDefault();
        setSearchOpen((o) => {
          if (!o) setTimeout(() => searchInputRef.current?.focus(), 30);
          else setSearchQuery('');
          return !o;
        });
      }
      if (e.key === 'Escape') {
        setSearchOpen(false);
        setSearchQuery('');
      }
    }
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, []);

  const { data: graph, isLoading, refetch } = useQuery({
    queryKey: queryKeys.trees.detail(treeId ?? ''),
    queryFn:  () => fetchTreeGraph(treeId ?? ''),
    enabled:  !!treeId && !!accessToken,
    staleTime: 5 * 60_000,
  });

  const handlePersonSelect = useCallback((personId: string) => {
    setPanelPersonId(personId);
    useCanvasStore.getState().setSelectedEdge(null);
  }, []);

  const handlePanelClose = useCallback(() => {
    setPanelPersonId(null);
    useCanvasStore.getState().setSelectedPersonId(null);
  }, []);

  const handleAdded = useCallback(async () => {
    const result = await refetch();
    if (result.data) {
      const { expandedNodeIds, setExpandedNodeIds } = useCanvasStore.getState();
      const next = new Set(expandedNodeIds);
      for (const p of result.data.persons) next.add(p.id);
      setExpandedNodeIds(next);
    }
  }, [refetch]);

  const panelPersonName = useMemo(() => {
    if (!panelPersonId || !graph) return '';
    const p = graph.persons.find((p) => p.id === panelPersonId);
    return p ? `${p.displayGivenName} ${p.displaySurname}`.trim() : '';
  }, [panelPersonId, graph]);

  function closeRelationModal() {
    setRelationMode(null);
  }

  function handleRelationAdded() {
    closeRelationModal();
    handleAdded();
  }

  function handleSetFocus() {
    if (panelPersonId) setFocusPerson(panelPersonId);
    handlePanelClose();
  }

  const treeName        = (graph as any)?.treeName ?? 'Family Tree';
  const treeDescription = (graph as any)?.treeDescription ?? null;
  const personCount     = graph?.persons.length ?? 0;

  const canWrite        = (graph as any)?.userRole !== 'VIEWER';

  return (
    <div className="fixed inset-0 flex flex-col">
      <SEO
        title={treeName}
        description={treeDescription ?? `Explore the ${treeName} family tree — ${personCount} people across multiple generations.`}
        noIndex
      />
      <TreeTopBar
        treeName={treeName}
        treeDescription={treeDescription}
        personCount={personCount}
        graph={graph ?? null}
        token={accessToken}
        canWrite={canWrite}
        onAddPerson={() => setShowAddPerson(true)}
        onMembers={() => setShowMembers(true)}
        onLayouts={() => setShowLayouts(true)}
        onExportCsv={() => graph && exportTreeCsv(graph, treeName)}
        onExportPdf={() => canvasRef.current?.exportPdf() ?? Promise.resolve()}
        onTheme={() => setShowCanvasTheme(true)}
        onShowActivity={() => setShowActivity(true)}
      />

      <div className="flex-1 relative mt-12">
        <TreeCanvas
          key={treeId}
          ref={canvasRef}
          graph={graph ?? null}
          isLoading={isLoading}
          onPersonSelect={handlePersonSelect}
          onFamilyGroupSelect={(fgId) => {
            if (!canWrite) return;
            setPanelPersonId(null);
            setUnionChildFgId(fgId);
          }}
        />

        {searchOpen && (() => {
          const query = searchQuery.toLowerCase().trim();
          const results = (graph?.persons ?? []).filter((p) => {
            const name = `${p.displayGivenName ?? ''} ${p.displaySurname ?? ''}`.toLowerCase();
            return !query || name.includes(query);
          }).slice(0, 10);
          return (
            <div className="absolute bottom-8 left-1/2 -translate-x-1/2 z-40 w-[calc(100vw-2rem)] max-w-xs sm:max-w-sm">
              <div className="bg-white rounded-2xl shadow-2xl ring-1 ring-black/10 overflow-hidden">
                <div className="flex items-center gap-2 px-3 py-2.5 border-b border-gray-100">
                  <svg className="w-4 h-4 text-gray-400 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                      d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
                  </svg>
                  <input
                    ref={searchInputRef}
                    type="text"
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    placeholder="Search people…"
                    className="flex-1 text-sm bg-transparent outline-none placeholder-gray-400 text-gray-900"
                    onKeyDown={(e) => {
                      if (e.key === 'Enter' && results.length > 0) {
                        canvasRef.current?.scrollToNode(results[0].id);
                        setSearchOpen(false);
                        setSearchQuery('');
                      }
                    }}
                  />
                  <span className="text-[10px] text-gray-300 font-mono shrink-0">Esc</span>
                </div>
                {results.length > 0 ? (
                  <ul className="max-h-60 overflow-y-auto py-1">
                    {results.map((p) => {
                      const name = [p.displayGivenName, p.displaySurname].filter(Boolean).join(' ') || '(unnamed)';
                      return (
                        <li key={p.id}>
                          <button
                            className="w-full text-left px-4 py-2 text-sm text-gray-800 hover:bg-brand-50 hover:text-brand-700 flex items-center gap-3"
                            onMouseDown={(e) => {
                              e.preventDefault();
                              canvasRef.current?.scrollToNode(p.id);
                              setSearchOpen(false);
                              setSearchQuery('');
                            }}
                          >
                            {p.photoUrl ? (
                              <img src={p.photoUrl} alt="" className="w-7 h-7 rounded-full object-cover shrink-0" />
                            ) : (
                              <span className="w-7 h-7 rounded-full bg-gray-100 flex items-center justify-center shrink-0 text-xs text-gray-400">
                                {(p.displayGivenName?.[0] ?? p.displaySurname?.[0] ?? '?').toUpperCase()}
                              </span>
                            )}
                            {name}
                          </button>
                        </li>
                      );
                    })}
                  </ul>
                ) : (
                  <p className="px-4 py-3 text-sm text-gray-400">No people found.</p>
                )}
              </div>
              <p className="text-center text-[10px] text-white/70 mt-1.5">Ctrl+Space to close</p>
            </div>
          );
        })()}

        <SelectionPanel
          key={panelPersonId ?? '__empty__'}
          personId={panelPersonId}
          personName={panelPersonName}
          treeId={treeId ?? ''}
          token={accessToken}
          canWrite={canWrite}
          onClose={handlePanelClose}
          onAddParent={() => setRelationMode('parent')}
          onAddBothParents={() => setRelationMode('bothParents')}
          onAddChild={()  => setRelationMode('child')}
          onAddSpouse={() => setRelationMode('spouse')}
          onSetFocus={handleSetFocus}
          onDeleted={() => { handlePanelClose(); handleAdded(); }}
          onOpenProfile={() => setShowProfile(true)}
          onEdit={() => setShowEdit(true)}
        />

        <EdgeSelectionPanel
          key={selectedEdge?.id ?? '__no-edge__'}
          edge={selectedEdge}
          graph={graph}
          treeId={treeId ?? ''}
          token={accessToken}
          canWrite={canWrite}
          onClose={() => useCanvasStore.getState().setSelectedEdge(null)}
          onDeleted={() => {
            useCanvasStore.getState().setSelectedEdge(null);
            handleAdded();
          }}
        />
      </div>

      {canWrite && showAddPerson && (
        <AddPersonModal
          treeId={treeId ?? ''}
          token={accessToken}
          onClose={() => setShowAddPerson(false)}
          onAdded={handleAdded}
        />
      )}

      {canWrite && relationMode && panelPersonId && (() => {
        const alreadyHasParents = new Set(
          (graph?.familyGroups ?? []).flatMap((g) => Object.keys(g.children))
        );

        if (relationMode === 'bothParents') {
          const existingParents = (graph?.familyGroups ?? [])
            .filter((fg) => Object.keys(fg.children).includes(panelPersonId))
            .flatMap((fg) => fg.parentIds);
          const excludeIds = new Set([panelPersonId, ...existingParents]);
          const candidates = (graph?.persons ?? [])
            .filter((p) => !excludeIds.has(p.id))
            .map((p) => ({ ...p, hasParents: alreadyHasParents.has(p.id) }));
          return (
            <AddBothParentsModal
              anchorPersonId={panelPersonId}
              anchorName={panelPersonName}
              anchorHasParents={alreadyHasParents.has(panelPersonId)}
              treeId={treeId ?? ''}
              token={accessToken}
              candidates={candidates}
              familyGroups={graph?.familyGroups ?? []}
              onClose={closeRelationModal}
              onAdded={handleRelationAdded}
            />
          );
        }

        let excludeIds: Set<string>;
        if (relationMode === 'parent') {
          const existingParents = (graph?.familyGroups ?? [])
            .filter((fg) => Object.keys(fg.children).includes(panelPersonId))
            .flatMap((fg) => fg.parentIds);
          excludeIds = new Set([panelPersonId, ...existingParents]);
        } else if (relationMode === 'child') {
          const existingChildren = (graph?.familyGroups ?? [])
            .filter((fg) => fg.parentIds.includes(panelPersonId))
            .flatMap((fg) => Object.keys(fg.children));
          excludeIds = new Set([panelPersonId, ...existingChildren]);
        } else {
          const existingSpouses = (graph?.familyGroups ?? [])
            .filter((fg) => fg.parentIds.includes(panelPersonId))
            .flatMap((fg) => fg.parentIds.filter((id) => id !== panelPersonId));
          excludeIds = new Set([panelPersonId, ...existingSpouses]);
        }
        const candidates = (graph?.persons ?? [])
          .filter((p) => !excludeIds.has(p.id))
          .map((p) => ({ ...p, hasParents: alreadyHasParents.has(p.id) }));
        return (
          <AddRelationModal
            mode={relationMode}
            anchorPersonId={panelPersonId}
            anchorName={panelPersonName}
            treeId={treeId ?? ''}
            token={accessToken}
            candidates={candidates}
            onClose={closeRelationModal}
            onAdded={handleRelationAdded}
          />
        );
      })()}

      {canWrite && showEdit && panelPersonId && (() => {
        const p = graph?.persons.find((x) => x.id === panelPersonId);
        if (!p) return null;
        const initial: EditPersonFields = {
          givenName:       p.displayGivenName,
          surname:         p.displaySurname,
          sex:             p.sex,
          status:          p.isLiving ? 'living' : p.isDeceased ? 'deceased' : 'unknown',
          birthDate:       p.birthDate ?? '',
          deathDate:       p.deathDate ?? '',
          birthYear:       p.birthYear != null ? String(p.birthYear) : '',
          deathYear:       p.deathYear != null ? String(p.deathYear) : '',
          bornCity:        p.bornCity ?? '',
          bornCountry:     p.bornCountry ?? '',
          diedCity:        p.diedCity ?? '',
          diedCountry:     p.diedCountry ?? '',
          notes:           p.notes ?? '',
        };
        return (
          <EditPersonModal
            personId={panelPersonId}
            initial={initial}
            initialPhotoUrl={p.photoUrl}
            treeId={treeId ?? ''}
            token={accessToken}
            onClose={() => setShowEdit(false)}
            onSaved={() => { setShowEdit(false); handleAdded(); }}
            onRefresh={handleAdded}
          />
        );
      })()}

      {showProfile && panelPersonId && (
        <PersonProfileModal
          initialPersonId={panelPersonId}
          treeId={treeId ?? ''}
          token={accessToken}
          graph={graph ?? null}
          onClose={() => setShowProfile(false)}
        />
      )}

      {showMembers && (
        <MembersModal
          treeId={treeId ?? ''}
          token={accessToken}
          currentUserId={useAuthStore.getState().user?.id ?? ''}
          onClose={() => setShowMembers(false)}
        />
      )}

      {showCanvasTheme && (
        <CanvasThemeModal onClose={() => setShowCanvasTheme(false)} />
      )}

      {showLayouts && treeId && (
        <LayoutsModal
          treeId={treeId}
          onGetPositions={() => canvasRef.current?.getPositions() ?? {}}
          onLoadPositions={(p) => canvasRef.current?.loadPositions(p)}
          onClose={() => setShowLayouts(false)}
        />
      )}

      {(() => {
        if (!unionChildFgId || !graph) return null;
        const fg = graph.familyGroups.find((f) => f.id === unionChildFgId);
        if (!fg) return null;
        const [p1Id, p2Id] = fg.parentIds;
        const personName = (id: string) => {
          const p = graph.persons.find((p) => p.id === id);
          return p ? `${p.displayGivenName} ${p.displaySurname}`.trim() : 'Unknown';
        };
        // Exclude parents and existing children from the candidate list
        const excludeIds = new Set([
          p1Id,
          ...(p2Id ? [p2Id] : []),
          ...Object.keys(fg.children),
        ]);
        // Track which persons are already children in any family group
        const alreadyHasParents = new Set(
          graph.familyGroups.flatMap((g) => Object.keys(g.children))
        );
        const candidates = graph.persons
          .filter((p) => !excludeIds.has(p.id))
          .map((p) => ({ ...p, hasParents: alreadyHasParents.has(p.id) }));
        return (
          <AddChildToUnionModal
            fgId={unionChildFgId}
            parent1Id={p1Id}
            parent2Id={p2Id ?? null}
            parent1Name={personName(p1Id)}
            parent2Name={p2Id ? personName(p2Id) : ''}
            treeId={treeId ?? ''}
            token={accessToken}
            candidates={candidates}
            onClose={() => setUnionChildFgId(null)}
            onAdded={() => { setUnionChildFgId(null); handleAdded(); }}
            onRemoved={() => { setUnionChildFgId(null); handleAdded(); }}
          />
        );
      })()}
    </div>
  );
}

// ── Layouts Modal ──────────────────────────────────────────────────────────

function LayoutsModal({
  treeId,
  onGetPositions,
  onLoadPositions,
  onClose,
}: {
  treeId: string;
  onGetPositions: () => Record<string, { x: number; y: number }>;
  onLoadPositions: ((p: Record<string, { x: number; y: number }>) => void) | undefined;
  onClose: () => void;
}) {
  const [layouts, setLayouts] = useState<SavedLayout[]>(() => loadLayouts(treeId));
  const [saveName, setSaveName] = useState('');
  const [saving, setSaving] = useState(false);

  function handleSave(e: React.FormEvent) {
    e.preventDefault();
    const name = saveName.trim();
    if (!name) return;
    setSaving(true);
    const positions = onGetPositions();
    const newLayout: SavedLayout = {
      id: crypto.randomUUID(),
      name,
      savedAt: new Date().toISOString(),
      positions,
    };
    const updated = [newLayout, ...layouts];
    saveLayouts(treeId, updated);
    setLayouts(updated);
    setSaveName('');
    setSaving(false);
  }

  function handleLoad(layout: SavedLayout) {
    onLoadPositions?.(layout.positions);
    onClose();
  }

  function handleDelete(id: string) {
    const updated = layouts.filter((l) => l.id !== id);
    saveLayouts(treeId, updated);
    setLayouts(updated);
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4"
      onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}
    >
      <div className="bg-white rounded-2xl shadow-xl w-full max-w-md p-6 max-h-[80vh] flex flex-col">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold text-slate-900">Saved layouts</h2>
          <button onClick={onClose} className="text-slate-400 hover:text-slate-600 text-xl leading-none">×</button>
        </div>

        {/* Save current */}
        <form onSubmit={handleSave} className="flex gap-2 mb-5">
          <input
            type="text"
            value={saveName}
            onChange={(e) => setSaveName(e.target.value)}
            placeholder="Layout name…"
            maxLength={60}
            className="flex-1 h-9 px-3 text-sm border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-brand-500"
          />
          <button
            type="submit"
            disabled={saving || !saveName.trim()}
            className="h-9 px-4 bg-brand-500 text-white text-sm font-medium rounded-lg hover:bg-brand-600 disabled:opacity-50 transition-colors whitespace-nowrap"
          >
            Save current
          </button>
        </form>

        {/* Saved list */}
        <div className="flex-1 overflow-y-auto min-h-0">
          {layouts.length === 0 ? (
            <p className="text-sm text-slate-400 text-center py-8">
              No layouts saved yet. Arrange the canvas and save it with a name.
            </p>
          ) : (
            <div className="space-y-2">
              {layouts.map((l) => (
                <div key={l.id} className="flex items-center gap-3 px-3 py-2.5 rounded-lg border border-slate-200 hover:bg-slate-50">
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium text-slate-800 truncate">{l.name}</p>
                    <p className="text-xs text-slate-400">
                      {new Date(l.savedAt).toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' })}
                      {' · '}{Object.keys(l.positions).length} nodes
                    </p>
                  </div>
                  <button
                    onClick={() => handleLoad(l)}
                    className="px-2.5 py-1 text-xs font-medium text-brand-600 bg-white border border-brand-200 rounded-lg hover:bg-brand-50 transition-colors whitespace-nowrap"
                  >
                    Load
                  </button>
                  <button
                    onClick={() => handleDelete(l.id)}
                    className="px-2.5 py-1 text-xs font-medium text-red-500 bg-white border border-red-200 rounded-lg hover:bg-red-50 transition-colors"
                  >
                    Delete
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

// ── Canvas Theme Modal ─────────────────────────────────────────────────────

function CanvasColorField({
  label, field, value,
}: { label: string; field: keyof CanvasTheme; value: string }) {
  const updateField = useThemeStore((s) => s.updateField);
  return (
    <div className="flex items-center justify-between py-2 border-b border-slate-100 last:border-0">
      <label className="text-sm text-slate-700">{label}</label>
      <div className="flex items-center gap-2">
        <div className="w-5 h-5 rounded border border-slate-300" style={{ background: value }} />
        <input
          type="color"
          value={value}
          onChange={(e) => updateField(field, e.target.value)}
          className="w-7 h-7 rounded cursor-pointer border-0 p-0 bg-transparent"
          title={value}
        />
        <span className="text-xs text-slate-400 font-mono w-14">{value}</span>
      </div>
    </div>
  );
}

function CanvasThemeModal({ onClose }: { onClose: () => void }) {
  const { theme, setPreset, updateField, reset } = useThemeStore();

  return (
    <div
      className="fixed inset-0 z-50 flex items-start justify-end bg-black/20 p-4"
      onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}
    >
      <div
        className="bg-white rounded-2xl shadow-2xl w-[calc(100vw-2rem)] max-w-xs sm:w-80 max-h-[calc(100vh-5rem)] flex flex-col border border-slate-200 mt-14"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between px-4 py-3 border-b border-slate-100">
          <h2 className="text-sm font-semibold text-slate-900">Tree canvas theme</h2>
          <button onClick={onClose} className="text-slate-400 hover:text-slate-600 text-lg leading-none">×</button>
        </div>

        <div className="flex-1 overflow-y-auto p-4 space-y-4">
          {/* Presets */}
          <div>
            <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-2">Presets</p>
            <div className="grid grid-cols-3 gap-1.5">
              {THEME_PRESETS.map((p) => (
                <button
                  key={p.preset}
                  onClick={() => setPreset(p.preset)}
                  className={`flex flex-col items-center gap-1 p-2 rounded-lg border-2 text-xs font-medium transition-colors ${
                    theme.preset === p.preset
                      ? 'border-brand-500 bg-brand-50 text-brand-700'
                      : 'border-slate-200 hover:border-slate-300 text-slate-600'
                  }`}
                >
                  <span className="flex gap-0.5">
                    <span className="w-3 h-3 rounded-sm" style={{ background: p.canvasBg, border: `1px solid ${p.canvasDot}` }} />
                    <span className="w-3 h-3 rounded-sm" style={{ background: p.nodeBg, border: `1px solid ${p.nodeBorder}` }} />
                    <span className="w-3 h-3 rounded-sm" style={{ background: p.edgeColor }} />
                  </span>
                  {PRESET_LABEL[p.preset]}
                </button>
              ))}
              {theme.preset === 'custom' && (
                <span className="flex flex-col items-center gap-1 p-2 rounded-lg border-2 border-brand-500 bg-brand-50 text-xs font-medium text-brand-700">
                  Custom
                </span>
              )}
            </div>
          </div>

          {/* Background */}
          <div>
            <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-1">Background</p>
            <div className="rounded-lg border border-slate-200 px-3">
              <CanvasColorField label="Canvas fill" field="canvasBg"  value={theme.canvasBg} />
              <CanvasColorField label="Grid dots"   field="canvasDot" value={theme.canvasDot} />
            </div>
          </div>

          {/* Box */}
          <div>
            <p className="text-xs font-semibond text-slate-500 uppercase tracking-wider mb-1">Box (person card)</p>
            <div className="rounded-lg border border-slate-200 px-3">
              <CanvasColorField label="Background" field="nodeBg"      value={theme.nodeBg} />
              <CanvasColorField label="Border"     field="nodeBorder"  value={theme.nodeBorder} />
              <CanvasColorField label="Hover"      field="nodeHoverBg" value={theme.nodeHoverBg} />
            </div>
          </div>

          {/* Foreground */}
          <div>
            <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-1">Foreground (text)</p>
            <div className="rounded-lg border border-slate-200 px-3">
              <CanvasColorField label="Name text" field="nodeText"    value={theme.nodeText} />
              <CanvasColorField label="Sub text"  field="nodeSubtext" value={theme.nodeSubtext} />
            </div>
          </div>

          {/* Lines */}
          <div>
            <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-1">Lines</p>
            <div className="rounded-lg border border-slate-200 px-3">
              <CanvasColorField label="Line color"      field="edgeColor"     value={theme.edgeColor} />
              <CanvasColorField label="Highlight color" field="edgeHighlight" value={theme.edgeHighlight} />
              <div className="flex items-center justify-between py-2">
                <label className="text-sm text-slate-700">Thickness</label>
                <div className="flex items-center gap-2">
                  <input
                    type="range" min={0.5} max={4} step={0.25}
                    value={theme.edgeWidth}
                    onChange={(e) => updateField('edgeWidth', parseFloat(e.target.value))}
                    className="w-24 accent-brand-500"
                  />
                  <span className="text-xs font-mono text-slate-500 w-9 text-right">
                    {theme.edgeWidth}px
                  </span>
                </div>
              </div>
            </div>
          </div>

          <button
            onClick={reset}
            className="w-full py-2 text-xs text-slate-500 border border-slate-200 rounded-lg hover:bg-slate-50 transition-colors"
          >
            Reset to Classic
          </button>
        </div>
      </div>
    </div>
  );
}
