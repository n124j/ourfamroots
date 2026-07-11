/**
 * AdminPage — user management dashboard.
 * Visible to ADMIN role only.
 */
import React, { useCallback, useEffect, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useAuthStore } from '@store/auth.store';
import { SEO } from '@shared/components/SEO';
import { UserAvatar } from '@shared/components/UserAvatar';

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? '/api/v1';
const PAGE_SIZE = 25;

// ── Types ──────────────────────────────────────────────────────────────────────

interface AdminUser {
  id: string;
  email: string;
  given_name: string | null;
  family_name: string | null;
  avatar_url: string | null;
  app_role: 'SUPER_ADMIN' | 'ADMIN' | 'STANDARD' | 'AUDITOR';
  email_verified: boolean;
  is_active: boolean;
  last_login_at: string | null;
  created_at: string;
}

interface UsersResponse {
  total: number;
  items: AdminUser[];
  page: number;
  page_size: number;
  total_pages: number;
}

const ROLE_OPTIONS = ['ADMIN', 'STANDARD', 'AUDITOR'] as const;

const ROLE_BADGE: Record<string, string> = {
  SUPER_ADMIN: 'bg-red-100 text-red-700',
  ADMIN:       'bg-purple-100 text-purple-700',
  STANDARD:    'bg-blue-100 text-blue-700',
  AUDITOR:     'bg-amber-100 text-amber-700',
};

// ── Permission Group types ──────────────────────────────────────────────────────

interface PermissionGroup {
  id: string;
  name: string;
  description: string | null;
  permission_level: 'VISIBLE' | 'READ' | 'READ_WRITE';
  is_global: boolean;
  tree_count: number;
  member_count: number;
  created_by: string | null;
  created_at: string;
  updated_at: string;
}

interface GroupTree {
  id: string;
  tree_id: string;
  tree_name: string;
  added_by: string | null;
  added_at: string;
}

interface GroupMember {
  id: string;
  user_id: string;
  user_email: string;
  user_display_name: string;
  added_by: string | null;
  added_at: string;
}

interface TenantTree { id: string; name: string; }

const LEVEL_LABEL_KEY: Record<string, string> = {
  VISIBLE:    'adminPage.visible',
  READ:       'adminPage.read',
  READ_WRITE: 'adminPage.readWrite',
};

const LEVEL_BADGE: Record<string, string> = {
  VISIBLE:    'bg-gray-100 text-gray-700',
  READ:       'bg-blue-100 text-blue-700',
  READ_WRITE: 'bg-green-100 text-green-700',
};

// ── Subscription types ────────────────────────────────────────────────────────

interface Subscription {
  id: string;
  name: string;
  tier: 'FREE' | 'PREMIUM_INDIVIDUAL' | 'PREMIUM_TEAM';
  expires_at: string | null;
  is_expired: boolean;
  filter_count: number;
  member_count: number;
  created_by: string | null;
  created_at: string;
  updated_at: string;
}

const EXPIRING_SOON_MS = 24 * 60 * 60 * 1000;

function formatExpiry(iso: string): string {
  return new Date(iso).toLocaleString(undefined, {
    year: 'numeric', month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit',
  });
}

/** Converts an ISO datetime to the "YYYY-MM-DDTHH:mm" value a <input type="datetime-local"> expects, in local time. */
function toDatetimeLocalValue(iso: string): string {
  const d = new Date(iso);
  const pad = (n: number) => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

interface SubscriptionFilter {
  id: string;
  filter_key: string;
  added_by: string | null;
  added_at: string;
}

interface SubscriptionMember {
  id: string;
  user_id: string;
  user_email: string;
  user_display_name: string;
  added_by: string | null;
  added_at: string;
}

interface AvailableFilter { key: string; label: string; }

const TIER_LABEL: Record<string, string> = {
  FREE: 'Free',
  PREMIUM_INDIVIDUAL: 'Premium — Individual',
  PREMIUM_TEAM: 'Premium — Team',
};

const TIER_BADGE: Record<string, string> = {
  FREE: 'bg-gray-100 text-gray-700',
  PREMIUM_INDIVIDUAL: 'bg-blue-100 text-blue-700',
  PREMIUM_TEAM: 'bg-purple-100 text-purple-700',
};

const LEVEL_DESC_KEY: Record<string, string> = {
  VISIBLE:    'adminPage.visibleDesc',
  READ:       'adminPage.readDesc',
  READ_WRITE: 'adminPage.readWriteDesc',
};

// ── Helpers ────────────────────────────────────────────────────────────────────

function displayName(u: AdminUser) {
  return [u.given_name, u.family_name].filter(Boolean).join(' ') || u.email;
}

function formatDate(iso: string | null) {
  if (!iso) return '—';
  return new Date(iso).toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric' });
}

function formatDateTime(iso: string | null) {
  if (!iso) return '—';
  return new Date(iso).toLocaleString(undefined, {
    year: 'numeric', month: 'short', day: 'numeric',
    hour: '2-digit', minute: '2-digit',
  });
}

// ── Create user modal ──────────────────────────────────────────────────────────

function CreateUserModal({
  token,
  onClose,
  onCreated,
}: {
  token: string | null;
  onClose: () => void;
  onCreated: () => void;
}) {
  const { t } = useTranslation();
  const [email,      setEmail]      = useState('');
  const [givenName,  setGivenName]  = useState('');
  const [familyName, setFamilyName] = useState('');
  const [role,       setRole]       = useState<'ADMIN' | 'STANDARD' | 'AUDITOR'>('STANDARD');
  const [saving,     setSaving]     = useState(false);
  const [error,      setError]      = useState('');

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    setError('');
    try {
      const res = await fetch(`${API_BASE}/admin/users`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...(token ? { Authorization: `Bearer ${token}` } : {}) },
        credentials: 'include',
        body: JSON.stringify({ email: email.trim(), given_name: givenName.trim(), family_name: familyName.trim(), app_role: role }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error((err as any).detail ?? 'Failed to create user');
      }
      await res.json();
      onCreated();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4"
      onClick={(e) => { if (e.target === e.currentTarget && !saving) onClose(); }}>
      <div className="bg-white rounded-2xl shadow-xl w-full max-w-sm p-6">
        <h2 className="text-lg font-semibold text-gray-900 mb-1">{t('adminPage.createUser')}</h2>
        <p className="text-xs text-gray-500 mb-4">{t('adminPage.activationEmail')}</p>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-xs font-medium text-gray-600 mb-1">{t('adminPage.email')} <span className="text-red-500">*</span></label>
            <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} required autoFocus
              className="w-full h-9 px-3 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-brand-500"
              placeholder="user@example.com" />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-medium text-gray-600 mb-1">{t('adminPage.firstName')} <span className="text-red-500">*</span></label>
              <input type="text" value={givenName} onChange={(e) => setGivenName(e.target.value)} required maxLength={100}
                className="w-full h-9 px-3 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-brand-500" />
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-600 mb-1">{t('adminPage.lastName')}</label>
              <input type="text" value={familyName} onChange={(e) => setFamilyName(e.target.value)} maxLength={100}
                className="w-full h-9 px-3 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-brand-500" />
            </div>
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-600 mb-1">{t('adminPage.role')}</label>
            <select value={role} onChange={(e) => setRole(e.target.value as typeof role)}
              className="w-full h-9 px-3 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-brand-500 bg-white">
              {ROLE_OPTIONS.map((r) => <option key={r} value={r}>{t('roles.' + r)}</option>)}
            </select>
          </div>
          {error && <p className="text-sm text-red-600">{error}</p>}
          <div className="flex justify-end gap-3 pt-1">
            <button type="button" onClick={onClose} disabled={saving}
              className="px-4 py-2 text-sm text-gray-600 hover:text-gray-900 disabled:opacity-50">
              {t('adminPage.cancel')}
            </button>
            <button type="submit" disabled={saving || !email.trim() || !givenName.trim()}
              className="px-4 py-2 bg-brand-500 text-white text-sm font-medium rounded-lg hover:bg-brand-600 disabled:opacity-50">
              {saving ? t('adminPage.creating') : t('adminPage.createUser')}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

// ── Edit modal ─────────────────────────────────────────────────────────────────

function EditUserModal({
  user,
  token,
  isSelf,
  onClose,
  onSaved,
}: {
  user: AdminUser;
  token: string | null;
  isSelf: boolean;
  onClose: () => void;
  onSaved: (updated: AdminUser) => void;
}) {
  const { t } = useTranslation();
  const [givenName,  setGivenName]  = useState(user.given_name ?? '');
  const [familyName, setFamilyName] = useState(user.family_name ?? '');
  const [role,       setRole]       = useState(user.app_role);
  const [active,     setActive]     = useState(user.is_active);
  const [verified,   setVerified]   = useState(user.email_verified);
  const [saving,     setSaving]     = useState(false);
  const [error,      setError]      = useState('');

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    setError('');
    try {
      const res = await fetch(`${API_BASE}/admin/users/${user.id}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json', ...(token ? { Authorization: `Bearer ${token}` } : {}) },
        credentials: 'include',
        body: JSON.stringify({
          given_name:    givenName.trim() || null,
          family_name:   familyName.trim() || null,
          app_role:      role,
          is_active:     active,
          email_verified: verified,
        }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error((err as any).detail ?? 'Failed to save');
      }
      onSaved(await res.json());
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4"
      onClick={(e) => { if (e.target === e.currentTarget && !saving) onClose(); }}>
      <div className="bg-white rounded-2xl shadow-xl w-full max-w-sm p-6">
        <h2 className="text-lg font-semibold text-gray-900 mb-4">{t('common.edit')}</h2>
        {isSelf && (
          <p className="text-xs text-amber-700 bg-amber-50 border border-amber-200 rounded-lg px-3 py-2 mb-3">
            Role, active status, and verification cannot be changed on your own account.
          </p>
        )}
        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-medium text-gray-600 mb-1">{t('adminPage.firstName')}</label>
              <input type="text" value={givenName} onChange={(e) => setGivenName(e.target.value)} maxLength={100}
                className="w-full h-9 px-3 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-brand-500" />
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-600 mb-1">{t('adminPage.lastName')}</label>
              <input type="text" value={familyName} onChange={(e) => setFamilyName(e.target.value)} maxLength={100}
                className="w-full h-9 px-3 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-brand-500" />
            </div>
          </div>
          <div>
            <label className={`block text-xs font-medium mb-1 ${isSelf ? 'text-gray-400' : 'text-gray-600'}`}>{t('adminPage.role')}</label>
            <select
              value={role}
              onChange={(e) => setRole(e.target.value as typeof role)}
              disabled={isSelf}
              title={isSelf ? 'You cannot change your own role' : undefined}
              className={`w-full h-9 px-3 text-sm border rounded-lg bg-white focus:outline-none focus:ring-2 focus:ring-brand-500 ${
                isSelf ? 'border-gray-200 text-gray-400 cursor-not-allowed bg-gray-50' : 'border-gray-300'
              }`}
            >
              {ROLE_OPTIONS.map((r) => <option key={r} value={r}>{t('roles.' + r)}</option>)}
            </select>
          </div>
          <label className={`flex items-center gap-3 ${isSelf ? 'cursor-not-allowed opacity-50' : 'cursor-pointer'}`}>
            <input
              type="checkbox"
              checked={active}
              onChange={(e) => setActive(e.target.checked)}
              disabled={isSelf}
              title={isSelf ? 'You cannot deactivate your own account' : undefined}
              className="w-4 h-4 accent-brand-500 disabled:cursor-not-allowed"
            />
            <span className={`text-sm ${isSelf ? 'text-gray-400' : 'text-gray-700'}`}>{t('adminPage.accountActive')}</span>
          </label>
          <label className={`flex items-center gap-3 ${isSelf ? 'cursor-not-allowed opacity-50' : 'cursor-pointer'}`}>
            <input
              type="checkbox"
              checked={verified}
              onChange={(e) => setVerified(e.target.checked)}
              disabled={isSelf}
              title={isSelf ? 'You cannot change your own verification status' : undefined}
              className="w-4 h-4 accent-brand-500 disabled:cursor-not-allowed"
            />
            <span className={`text-sm ${isSelf ? 'text-gray-400' : 'text-gray-700'}`}>{t('adminPage.emailVerified')}</span>
          </label>
          {error && <p className="text-sm text-red-600">{error}</p>}
          <div className="flex justify-end gap-3 pt-1">
            <button type="button" onClick={onClose} disabled={saving}
              className="px-4 py-2 text-sm text-gray-600 hover:text-gray-900 disabled:opacity-50">
              {t('adminPage.cancel')}
            </button>
            <button type="submit" disabled={saving}
              className="px-4 py-2 bg-brand-500 text-white text-sm font-medium rounded-lg hover:bg-brand-600 disabled:opacity-50">
              {saving ? t('adminPage.saving') : t('common.save')}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

// ── Merge Trees — step 2 sub-component ───────────────────────────────────────

interface MergePersonOption {
  id: string;
  display_given_name: string;
  display_surname: string;
  photo_url: string | null;
  birth_year: number | null;
  sex: string;
}

interface Step2Props {
  selectedTreeIds: string[];
  allTrees: TenantTree[];
  persons: Record<string, MergePersonOption[]>;
  loadingPersons: Record<string, boolean>;
  pivots: Record<string, string>;
  setPivots: React.Dispatch<React.SetStateAction<Record<string, string>>>;
  mergeIdentical: boolean;
  setMergeIdentical: (v: boolean) => void;
  mergeError: string;
  merging: boolean;
  allPivotsSelected: boolean;
  onBack: () => void;
  onMerge: () => void;
  // Auto-merge
  autoMerging: boolean;
  showProgressBar: boolean;
  autoProgress: number;
  autoProgressLabel: string;
  onAutoMerge: () => void;
}

function Step2MergePanel({
  selectedTreeIds, allTrees, persons, loadingPersons,
  pivots, setPivots,
  mergeIdentical, setMergeIdentical,
  mergeError, merging, allPivotsSelected,
  onBack, onMerge,
  autoMerging, showProgressBar, autoProgress, autoProgressLabel, onAutoMerge,
}: Step2Props) {
  // Compute which persons would be auto-merged (live preview)
  const identicalMatches = React.useMemo(() => {
    if (!mergeIdentical) return [];

    // name|sex key → [{ treeId, person }]
    const nameGroups: Record<string, { treeId: string; person: MergePersonOption }[]> = {};

    for (const tid of selectedTreeIds) {
      const pivotId = pivots[tid];
      for (const p of (persons[tid] ?? [])) {
        if (p.id === pivotId) continue;
        const given   = (p.display_given_name || '').trim().toLowerCase();
        const surname = (p.display_surname || '').trim().toLowerCase();
        if (!given && !surname) continue;
        const key = `${given}|${surname}`;
        if (!nameGroups[key]) nameGroups[key] = [];
        nameGroups[key].push({ treeId: tid, person: p });
      }
    }

    // Keep only groups that span multiple trees
    return Object.values(nameGroups).filter(entries => {
      const trees = new Set(entries.map(e => e.treeId));
      return trees.size > 1;
    });
  }, [mergeIdentical, selectedTreeIds, pivots, persons]);

  const personsLoaded = selectedTreeIds.every(tid => persons[tid] !== undefined);

  return (
    <div className="space-y-5">
      <p className="text-sm text-gray-600">
        For each tree, select the <span className="font-medium">same real person</span> who connects the trees.
        All pivot people will be merged into one person in the new tree.
      </p>

      {selectedTreeIds.map(tid => {
        const tree   = allTrees.find(t => t.id === tid);
        const pList  = persons[tid] ?? [];
        const loading = loadingPersons[tid];
        return (
          <div key={tid} className="border border-gray-200 rounded-lg p-4">
            <p className="text-sm font-medium text-gray-800 mb-2">{tree?.name ?? tid}</p>
            {loading ? (
              <div className="flex justify-center py-3">
                <div className="w-5 h-5 border-2 border-brand-500 border-t-transparent rounded-full animate-spin" />
              </div>
            ) : pList.length === 0 ? (
              <p className="text-xs text-gray-400">No people in this tree.</p>
            ) : (
              <select
                value={pivots[tid] ?? ''}
                onChange={e => setPivots(prev => ({ ...prev, [tid]: e.target.value }))}
                className="w-full h-9 px-3 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-brand-500"
              >
                <option value="">— select pivot person —</option>
                {pList.map(p => (
                  <option key={p.id} value={p.id}>
                    {[p.display_given_name, p.display_surname].filter(Boolean).join(' ') || '(unnamed)'}
                    {p.birth_year ? ` (${p.birth_year})` : ''}
                  </option>
                ))}
              </select>
            )}
          </div>
        );
      })}

      {/* ── Merge identical checkbox ── */}
      <div className="border border-gray-200 rounded-lg p-4 space-y-3">
        <label className="flex items-start gap-3 cursor-pointer">
          <input
            type="checkbox"
            checked={mergeIdentical}
            onChange={e => setMergeIdentical(e.target.checked)}
            className="mt-0.5 rounded border-gray-300 text-brand-500 focus:ring-brand-500"
          />
          <div>
            <span className="text-sm font-medium text-gray-800">Merge identical members</span>
            <p className="text-xs text-gray-500 mt-0.5">
              Members with the same name (and compatible birth year / sex) across both trees
              are collapsed into a single person in the merged tree.
            </p>
          </div>
        </label>

        {/* Live preview of what would be merged */}
        {mergeIdentical && personsLoaded && (
          identicalMatches.length > 0 ? (
            <div className="bg-amber-50 border border-amber-200 rounded-lg px-3 py-2.5">
              <p className="text-xs font-medium text-amber-700 mb-1.5">
                {identicalMatches.length} member{identicalMatches.length !== 1 ? 's' : ''} will be auto-merged:
              </p>
              <ul className="space-y-0.5">
                {identicalMatches.slice(0, 6).map((group, i) => {
                  const name = [group[0].person.display_given_name, group[0].person.display_surname]
                    .filter(Boolean).join(' ') || '(unnamed)';
                  const by   = group[0].person.birth_year;
                  return (
                    <li key={i} className="text-xs text-amber-800 flex items-center gap-1">
                      <span className="text-amber-400">•</span>
                      {name}{by ? ` (${by})` : ''}
                      <span className="text-amber-500 ml-1">
                        — found in {group.length} trees
                      </span>
                    </li>
                  );
                })}
                {identicalMatches.length > 6 && (
                  <li className="text-xs text-amber-600">
                    … and {identicalMatches.length - 6} more
                  </li>
                )}
              </ul>
            </div>
          ) : (
            <p className="text-xs text-gray-400">
              No members with identical names found across the selected trees.
            </p>
          )
        )}
      </div>

      {mergeError && (
        <p className="text-sm text-red-600 bg-red-50 border border-red-200 rounded-lg px-3 py-2">{mergeError}</p>
      )}

      {/* Auto-merge progress bar (shown only if operation takes >1.5 s) */}
      {showProgressBar && (
        <div className="space-y-1">
          <div className="flex justify-between text-xs text-gray-500">
            <span>{autoProgressLabel}</span>
            <span>{autoProgress}%</span>
          </div>
          <div className="w-full bg-gray-200 rounded-full h-2 overflow-hidden">
            <div
              className="bg-brand-500 h-2 rounded-full transition-all duration-500"
              style={{ width: `${autoProgress}%` }}
            />
          </div>
        </div>
      )}

      <div className="flex gap-3">
        <button
          onClick={onBack}
          disabled={merging || autoMerging}
          className="px-4 py-2 border border-gray-300 text-gray-700 text-sm font-medium rounded-lg hover:bg-gray-50 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
        >
          Back
        </button>
        <button
          onClick={onMerge}
          disabled={!allPivotsSelected || merging || autoMerging}
          className="px-4 py-2 bg-brand-500 text-white text-sm font-medium rounded-lg hover:bg-brand-600 disabled:opacity-40 disabled:cursor-not-allowed transition-colors flex items-center gap-2"
        >
          {merging && <span className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin inline-block" />}
          {merging ? 'Merging…' : 'Create merged tree'}
        </button>
        <button
          onClick={onAutoMerge}
          disabled={merging || autoMerging}
          title="Automatically find common members across all selected trees and create a merged tree"
          className="px-4 py-2 border border-brand-400 text-brand-600 text-sm font-medium rounded-lg hover:bg-brand-50 disabled:opacity-40 disabled:cursor-not-allowed transition-colors flex items-center gap-2"
        >
          {autoMerging && <span className="w-4 h-4 border-2 border-brand-500 border-t-transparent rounded-full animate-spin inline-block" />}
          {autoMerging ? 'Auto-merging…' : 'Auto'}
        </button>
      </div>
    </div>
  );
}

// ── Merge Trees panel ─────────────────────────────────────────────────────────

function MergeTreesPanel({ token }: { token: string | null }) {
  const { t } = useTranslation();
  const authHeader: Record<string, string> = token ? { Authorization: `Bearer ${token}` } : {};

  // All trees in tenant
  const [allTrees, setAllTrees] = useState<TenantTree[]>([]);
  const [loadingTrees, setLoadingTrees] = useState(true);

  // Wizard state
  const [step, setStep] = useState<1 | 2 | 3>(1);
  const [newName, setNewName] = useState('');
  const [newDesc, setNewDesc] = useState('');
  const [selectedTreeIds, setSelectedTreeIds] = useState<string[]>([]);

  // Per-tree person lists
  const [persons, setPersons] = useState<Record<string, MergePersonOption[]>>({});
  const [loadingPersons, setLoadingPersons] = useState<Record<string, boolean>>({});

  // Pivot selections: tree_id → person_id
  const [pivots, setPivots] = useState<Record<string, string>>({});

  // Identical-merge option
  const [mergeIdentical, setMergeIdentical] = useState(false);

  // Submit state
  const [merging, setMerging] = useState(false);
  const [mergeError, setMergeError] = useState('');
  const [result, setResult] = useState<{ tree_id: string; tree_name: string; person_count: number } | null>(null);

  // Auto-merge state
  const [autoMerging, setAutoMerging] = useState(false);
  const [autoProgress, setAutoProgress] = useState(0);
  const [autoProgressLabel, setAutoProgressLabel] = useState('');
  const [showProgressBar, setShowProgressBar] = useState(false);

  useEffect(() => {
    fetch(`${API_BASE}/admin/trees`, { headers: authHeader, credentials: 'include' })
      .then(r => r.ok ? r.json() : [])
      .then(data => setAllTrees(data))
      .finally(() => setLoadingTrees(false));
  }, []);

  function toggleTree(id: string) {
    setSelectedTreeIds(prev =>
      prev.includes(id) ? prev.filter(t => t !== id) : [...prev, id]
    );
    setPivots(prev => { const n = { ...prev }; delete n[id]; return n; });
  }

  async function goToStep2() {
    if (!newName.trim() || selectedTreeIds.length < 2) return;
    setStep(2);
    const missing = selectedTreeIds.filter(tid => !persons[tid]);
    setLoadingPersons(prev => Object.fromEntries(missing.map(tid => [tid, true])));
    await Promise.all(missing.map(async (tid) => {
      try {
        const r = await fetch(`${API_BASE}/admin/trees/${tid}/persons`, { headers: authHeader, credentials: 'include' });
        const data = r.ok ? await r.json() : [];
        setPersons(prev => ({ ...prev, [tid]: data }));
      } finally {
        setLoadingPersons(prev => ({ ...prev, [tid]: false }));
      }
    }));
  }

  async function handleMerge() {
    setMerging(true);
    setMergeError('');
    try {
      const sources = selectedTreeIds.map(tid => ({ tree_id: tid, pivot_person_id: pivots[tid] }));
      const res = await fetch(`${API_BASE}/trees/merge`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...authHeader },
        credentials: 'include',
        body: JSON.stringify({
          new_tree_name: newName.trim(),
          new_tree_description: newDesc.trim() || null,
          sources,
          merge_identical: mergeIdentical,
        }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error((err as any).detail ?? 'Merge failed');
      }
      setResult(await res.json());
      setStep(3);
    } catch (e) {
      setMergeError((e as Error).message);
    } finally {
      setMerging(false);
    }
  }

  async function handleAutoMerge() {
    if (selectedTreeIds.length < 2) return;
    setAutoMerging(true);
    setAutoProgress(0);
    setAutoProgressLabel('');
    setShowProgressBar(false);
    setMergeError('');

    // Show progress bar only if request takes longer than 1.5 s
    const showBarTimer = setTimeout(() => {
      setShowProgressBar(true);
      setAutoProgress(10);
      setAutoProgressLabel('Finding common members…');
    }, 1500);

    // Simulated progress stages
    const stage1 = setTimeout(() => { setAutoProgress(35); setAutoProgressLabel('Comparing trees…'); }, 2500);
    const stage2 = setTimeout(() => { setAutoProgress(60); setAutoProgressLabel('Building merged tree…'); }, 4000);
    const stage3 = setTimeout(() => { setAutoProgress(82); setAutoProgressLabel('Linking relationships…'); }, 5500);
    const stage4 = setTimeout(() => { setAutoProgress(92); setAutoProgressLabel('Finalising…'); }, 7000);

    try {
      const res = await fetch(`${API_BASE}/trees/merge/auto`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...authHeader },
        credentials: 'include',
        body: JSON.stringify({
          new_tree_name: newName.trim(),
          new_tree_description: newDesc.trim() || null,
          tree_ids: selectedTreeIds,
        }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error((err as any).detail ?? 'Auto-merge failed');
      }
      setAutoProgress(100);
      setAutoProgressLabel('Done!');
      await new Promise(r => setTimeout(r, 400));
      setResult(await res.json());
      setStep(3);
    } catch (e) {
      setMergeError((e as Error).message);
    } finally {
      clearTimeout(showBarTimer);
      clearTimeout(stage1);
      clearTimeout(stage2);
      clearTimeout(stage3);
      clearTimeout(stage4);
      setAutoMerging(false);
      setShowProgressBar(false);
      setAutoProgress(0);
    }
  }

  function reset() {
    setStep(1); setNewName(''); setNewDesc(''); setSelectedTreeIds([]);
    setPersons({}); setPivots({}); setMergeError(''); setResult(null);
    setMergeIdentical(false);
    setAutoMerging(false); setAutoProgress(0); setAutoProgressLabel(''); setShowProgressBar(false);
  }

  const allPivotsSelected = selectedTreeIds.length >= 2 && selectedTreeIds.every(tid => !!pivots[tid]);

  if (loadingTrees) return (
    <div className="flex justify-center py-16">
      <div className="w-7 h-7 border-2 border-brand-500 border-t-transparent rounded-full animate-spin" />
    </div>
  );

  if (step === 3 && result) return (
    <div className="max-w-lg mx-auto py-12 text-center">
      <div className="w-16 h-16 bg-green-100 rounded-full flex items-center justify-center mx-auto mb-4">
        <svg className="w-8 h-8 text-green-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
        </svg>
      </div>
      <h2 className="text-lg font-semibold text-gray-900 mb-1">{t('adminPage.mergeComplete')}</h2>
      <p className="text-sm text-gray-500 mb-1">
        <span className="font-medium text-gray-700">{result.tree_name}</span> was created with {result.person_count} people.
      </p>
      <div className="mt-6 flex gap-3 justify-center">
        <a
          href={`/trees/${result.tree_id}`}
          className="px-4 py-2 bg-brand-500 text-white text-sm font-medium rounded-lg hover:bg-brand-600 transition-colors"
        >
          {t('adminPage.openMergedTree')}
        </a>
        <button onClick={reset} className="px-4 py-2 border border-gray-300 text-gray-700 text-sm font-medium rounded-lg hover:bg-gray-50 transition-colors">
          {t('adminPage.mergeAnother')}
        </button>
      </div>
    </div>
  );

  return (
    <div className="max-w-2xl">
      {/* Step indicator */}
      <div className="flex items-center gap-2 mb-6 text-sm">
        {([t('adminPage.step1Label'), t('adminPage.step2Label'), t('adminPage.step3Label')]).map((label, i) => (
          <React.Fragment key={i}>
            {i > 0 && <span className="text-gray-300">›</span>}
            <span className={step === i + 1 ? 'text-brand-600 font-medium' : 'text-gray-400'}>{label}</span>
          </React.Fragment>
        ))}
      </div>

      {/* Step 1 */}
      {step === 1 && (
        <div className="space-y-5">
          <div>
            <label className="block text-xs font-medium text-gray-600 mb-1">
              {t('adminPage.newTreeName')} <span className="text-red-500">*</span>
            </label>
            <input
              type="text"
              value={newName}
              onChange={e => setNewName(e.target.value)}
              placeholder={t('adminPage.newTreePlaceholder')}
              className="w-full h-9 px-3 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-brand-500"
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-600 mb-1">{t('adminPage.descriptionOptional')}</label>
            <textarea
              value={newDesc}
              onChange={e => setNewDesc(e.target.value)}
              rows={2}
              placeholder={t('adminPage.descMergedPlaceholder')}
              className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-brand-500 resize-none"
            />
          </div>

          <div>
            <p className="text-xs font-medium text-gray-600 mb-2">
              {t('adminPage.selectTreesToMerge')} <span className="text-red-500">*</span>
              <span className="text-gray-400 font-normal ml-1">{t('adminPage.minimum2')}</span>
            </p>
            {allTrees.length === 0 ? (
              <p className="text-sm text-gray-400">{t('adminPage.noTreesFound')}</p>
            ) : (
              <div className="border border-gray-200 rounded-lg divide-y divide-gray-100 max-h-64 overflow-y-auto">
                {allTrees.map(tree => (
                  <label key={tree.id} className="flex items-center gap-3 px-4 py-2.5 hover:bg-gray-50 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={selectedTreeIds.includes(tree.id)}
                      onChange={() => toggleTree(tree.id)}
                      className="rounded border-gray-300 text-brand-500"
                    />
                    <span className="text-sm text-gray-800">{tree.name}</span>
                  </label>
                ))}
              </div>
            )}
          </div>

          <button
            onClick={goToStep2}
            disabled={!newName.trim() || selectedTreeIds.length < 2}
            className="px-4 py-2 bg-brand-500 text-white text-sm font-medium rounded-lg hover:bg-brand-600 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
          >
            Next: choose pivot people
          </button>
        </div>
      )}

      {/* Step 2 */}
      {step === 2 && (
        <Step2MergePanel
          selectedTreeIds={selectedTreeIds}
          allTrees={allTrees}
          persons={persons}
          loadingPersons={loadingPersons}
          pivots={pivots}
          setPivots={setPivots}
          mergeIdentical={mergeIdentical}
          setMergeIdentical={setMergeIdentical}
          mergeError={mergeError}
          merging={merging}
          allPivotsSelected={allPivotsSelected}
          onBack={() => setStep(1)}
          onMerge={handleMerge}
          autoMerging={autoMerging}
          showProgressBar={showProgressBar}
          autoProgress={autoProgress}
          autoProgressLabel={autoProgressLabel}
          onAutoMerge={handleAutoMerge}
        />
      )}
    </div>
  );
}

// ── Broadcast email panel (Super Admin only) ─────────────────────────────────

interface Recipient {
  id: string;
  email: string;
  given_name: string | null;
  family_name: string | null;
  app_role: string;
  broadcast_unsubscribed: boolean;
}

interface BroadcastHistoryEntry {
  id: string;
  sender_display_name: string;
  subject: string;
  body: string;
  category: string;
  recipient_count: number;
  sent_count: number;
  failed_count: number;
  recipient_emails: string[];
  created_at: string;
}

const CATEGORY_OPTIONS = [
  { value: 'notice',  label: 'Notice',  color: 'bg-indigo-100 text-indigo-700' },
  { value: 'alert',   label: 'Alert',   color: 'bg-red-100 text-red-700' },
  { value: 'event',   label: 'Event',   color: 'bg-green-100 text-green-700' },
  { value: 'update',  label: 'Update',  color: 'bg-amber-100 text-amber-700' },
] as const;

function BroadcastPanel({ token }: { token: string | null }) {
  const { t } = useTranslation();
  const [subject,    setSubject]    = useState('');
  const [body,       setBody]       = useState('');
  const [category,   setCategory]   = useState<string>('notice');
  const [sendToAll,  setSendToAll]  = useState(true);
  const [sending,    setSending]    = useState(false);
  const [feedback,   setFeedback]   = useState<{ type: 'success' | 'error'; text: string } | null>(null);

  // History
  const [history,         setHistory]         = useState<BroadcastHistoryEntry[]>([]);
  const [historyLoading,  setHistoryLoading]  = useState(true);
  const [historyPage,     setHistoryPage]     = useState(1);
  const [historyTotal,    setHistoryTotal]    = useState(0);
  const [expandedId,      setExpandedId]      = useState<string | null>(null);
  const [deletingId,      setDeletingId]      = useState<string | null>(null);

  // Recipient list
  const [recipients,       setRecipients]       = useState<Recipient[]>([]);
  const [recipientSearch,  setRecipientSearch]  = useState('');
  const [loadingRecipients, setLoadingRecipients] = useState(false);
  const [selectedIds,      setSelectedIds]      = useState<Set<string>>(new Set());

  const searchRef = useRef<ReturnType<typeof setTimeout>>();

  // Load recipients when switching to selective mode
  useEffect(() => {
    if (sendToAll || !token) return;
    loadRecipients('');
  }, [sendToAll, token]);

  // Debounced search
  useEffect(() => {
    if (sendToAll) return;
    clearTimeout(searchRef.current);
    searchRef.current = setTimeout(() => loadRecipients(recipientSearch), 350);
    return () => clearTimeout(searchRef.current);
  }, [recipientSearch]);

  async function loadRecipients(search: string) {
    if (!token) return;
    setLoadingRecipients(true);
    try {
      const params = search ? `?search=${encodeURIComponent(search)}` : '';
      const res = await fetch(`${API_BASE}/broadcast/recipients${params}`, {
        headers: { Authorization: `Bearer ${token}` },
        credentials: 'include',
      });
      if (res.ok) {
        const data = await res.json();
        setRecipients(data.items);
      }
    } catch { /* ignore */ }
    finally { setLoadingRecipients(false); }
  }

  function toggleRecipient(id: string) {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  function selectAll() {
    setSelectedIds(new Set(recipients.map((r) => r.id)));
  }

  function deselectAll() {
    setSelectedIds(new Set());
  }

  async function handleSend() {
    if (!token || !subject.trim() || !body.trim()) return;
    if (!sendToAll && selectedIds.size === 0) {
      setFeedback({ type: 'error', text: 'Please select at least one recipient.' });
      return;
    }

    setSending(true);
    setFeedback(null);
    try {
      const res = await fetch(`${API_BASE}/broadcast/send`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`,
        },
        credentials: 'include',
        body: JSON.stringify({
          subject: subject.trim(),
          body: body.trim(),
          category,
          recipient_ids: sendToAll ? [] : Array.from(selectedIds),
        }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error((err as any).detail ?? 'Failed to send');
      }
      const data = await res.json();
      const failedMsg = data.failed_count > 0 ? ` (${data.failed_count} failed)` : '';
      setFeedback({ type: 'success', text: `Sent to ${data.sent_count} recipient${data.sent_count !== 1 ? 's' : ''}${failedMsg}.` });
      setSubject('');
      setBody('');
      loadHistory();
    } catch (err) {
      setFeedback({ type: 'error', text: (err as Error).message });
    } finally {
      setSending(false);
    }
  }

  function recipientName(r: Recipient) {
    return [r.given_name, r.family_name].filter(Boolean).join(' ') || r.email;
  }

  const loadHistory = useCallback(async () => {
    if (!token) return;
    setHistoryLoading(true);
    try {
      const res = await fetch(`${API_BASE}/broadcast/history?page=${historyPage}&page_size=10`, {
        headers: { Authorization: `Bearer ${token}` },
        credentials: 'include',
      });
      if (res.ok) {
        const data = await res.json();
        setHistory(data.items);
        setHistoryTotal(data.total);
      }
    } catch { /* ignore */ }
    finally { setHistoryLoading(false); }
  }, [token, historyPage]);

  useEffect(() => { loadHistory(); }, [loadHistory]);

  async function handleDeleteLog(id: string) {
    if (!token) return;
    setDeletingId(id);
    try {
      await fetch(`${API_BASE}/broadcast/history/${id}`, {
        method: 'DELETE',
        headers: { Authorization: `Bearer ${token}` },
        credentials: 'include',
      });
      setHistory((prev) => prev.filter((h) => h.id !== id));
      setHistoryTotal((t) => Math.max(0, t - 1));
    } catch { /* ignore */ }
    finally { setDeletingId(null); }
  }

  return (
    <div className="max-w-3xl">
      <div className="rounded-xl border p-6" style={{ background: 'var(--portal-card-bg)', borderColor: 'var(--portal-card-border)' }}>
        <h2 className="text-lg font-semibold mb-1" style={{ color: 'var(--portal-text-primary)' }}>
          {t('adminPage.broadcastEmail')}
        </h2>
        <p className="text-sm mb-6" style={{ color: 'var(--portal-text-muted)' }}>
          Compose and send an email to all users or selected recipients.
        </p>

        {/* Category */}
        <label className="block text-sm font-medium mb-1.5" style={{ color: 'var(--portal-text-primary)' }}>
          Category
        </label>
        <div className="flex gap-2 mb-5">
          {CATEGORY_OPTIONS.map((c) => (
            <button
              key={c.value}
              type="button"
              onClick={() => setCategory(c.value)}
              className={`px-3 py-1.5 text-xs font-semibold rounded-full border-2 transition-colors ${
                category === c.value
                  ? `${c.color} border-current`
                  : 'bg-gray-50 text-gray-400 border-transparent hover:bg-gray-100'
              }`}
            >
              {c.label}
            </button>
          ))}
        </div>

        {/* Subject */}
        <label className="block text-sm font-medium mb-1.5" style={{ color: 'var(--portal-text-primary)' }}>
          {t('adminPage.broadcastSubject')}
        </label>
        <input
          type="text"
          value={subject}
          onChange={(e) => setSubject(e.target.value)}
          placeholder="e.g. Scheduled maintenance on Saturday"
          maxLength={200}
          className="w-full h-10 px-3 text-sm border rounded-lg focus:outline-none focus:ring-2 focus:ring-brand-500 mb-4"
          style={{ background: 'var(--portal-card-bg)', color: 'var(--portal-text-primary)', borderColor: 'var(--portal-card-border)' }}
        />

        {/* Body */}
        <label className="block text-sm font-medium mb-1.5" style={{ color: 'var(--portal-text-primary)' }}>
          {t('adminPage.broadcastBody')}
        </label>
        <textarea
          rows={6}
          value={body}
          onChange={(e) => setBody(e.target.value)}
          placeholder="Write your message here…"
          maxLength={10000}
          className="w-full px-3 py-2 text-sm border rounded-lg focus:outline-none focus:ring-2 focus:ring-brand-500 resize-y mb-1"
          style={{ background: 'var(--portal-card-bg)', color: 'var(--portal-text-primary)', borderColor: 'var(--portal-card-border)' }}
        />
        <p className="text-xs mb-5" style={{ color: 'var(--portal-text-muted)' }}>
          Plain text. Line breaks will be preserved in the email.
        </p>

        {/* Recipients toggle */}
        <label className="block text-sm font-medium mb-2" style={{ color: 'var(--portal-text-primary)' }}>
          Recipients
        </label>
        <div className="flex gap-3 mb-4">
          <button
            type="button"
            onClick={() => setSendToAll(true)}
            className={`px-4 py-2 text-sm font-medium rounded-lg border transition-colors ${
              sendToAll
                ? 'bg-brand-50 text-brand-700 border-brand-300'
                : 'bg-white text-gray-500 border-gray-300 hover:bg-gray-50'
            }`}
          >
            All users
          </button>
          <button
            type="button"
            onClick={() => setSendToAll(false)}
            className={`px-4 py-2 text-sm font-medium rounded-lg border transition-colors ${
              !sendToAll
                ? 'bg-brand-50 text-brand-700 border-brand-300'
                : 'bg-white text-gray-500 border-gray-300 hover:bg-gray-50'
            }`}
          >
            Select recipients
          </button>
        </div>

        {/* Selective recipients list */}
        {!sendToAll && (
          <div className="border rounded-lg mb-5" style={{ borderColor: 'var(--portal-card-border)' }}>
            {/* Search + select/deselect all */}
            <div className="flex items-center gap-2 p-3 border-b" style={{ borderColor: 'var(--portal-card-border)' }}>
              <input
                type="text"
                value={recipientSearch}
                onChange={(e) => setRecipientSearch(e.target.value)}
                placeholder="Search users…"
                className="flex-1 h-8 px-3 text-sm border rounded-md focus:outline-none focus:ring-2 focus:ring-brand-500"
                style={{ background: 'var(--portal-card-bg)', color: 'var(--portal-text-primary)', borderColor: 'var(--portal-card-border)' }}
              />
              <button type="button" onClick={selectAll}
                className="text-xs text-brand-600 hover:text-brand-700 font-medium whitespace-nowrap">
                Select all
              </button>
              <button type="button" onClick={deselectAll}
                className="text-xs text-gray-500 hover:text-gray-700 font-medium whitespace-nowrap">
                Clear
              </button>
            </div>

            {/* User list */}
            <div className="max-h-56 overflow-y-auto">
              {loadingRecipients ? (
                <div className="flex justify-center py-6">
                  <div className="w-5 h-5 border-2 border-brand-500 border-t-transparent rounded-full animate-spin" />
                </div>
              ) : recipients.length === 0 ? (
                <p className="text-sm text-center py-6" style={{ color: 'var(--portal-text-muted)' }}>
                  No users found
                </p>
              ) : (
                recipients.map((r) => (
                  <label
                    key={r.id}
                    className="flex items-center gap-3 px-3 py-2 hover:bg-gray-50 cursor-pointer transition-colors"
                  >
                    <input
                      type="checkbox"
                      checked={selectedIds.has(r.id)}
                      onChange={() => toggleRecipient(r.id)}
                      disabled={r.broadcast_unsubscribed}
                      className="h-4 w-4 rounded border-gray-300 text-brand-600 focus:ring-brand-500 disabled:opacity-40"
                    />
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-medium truncate" style={{ color: r.broadcast_unsubscribed ? 'var(--portal-text-muted)' : 'var(--portal-text-primary)' }}>
                        {recipientName(r)}
                      </p>
                      <p className="text-xs truncate" style={{ color: 'var(--portal-text-muted)' }}>
                        {r.email}
                      </p>
                    </div>
                    {r.broadcast_unsubscribed && (
                      <span className="text-[10px] font-semibold px-1.5 py-0.5 rounded bg-gray-100 text-gray-500">
                        Unsubscribed
                      </span>
                    )}
                    <span className={`text-[10px] font-semibold px-1.5 py-0.5 rounded ${ROLE_BADGE[r.app_role] ?? 'bg-gray-100 text-gray-600'}`}>
                      {r.app_role}
                    </span>
                  </label>
                ))
              )}
            </div>

            {/* Selected count */}
            <div className="px-3 py-2 border-t text-xs" style={{ borderColor: 'var(--portal-card-border)', color: 'var(--portal-text-muted)' }}>
              {selectedIds.size} of {recipients.length} selected
            </div>
          </div>
        )}

        {/* Send */}
        <div className="flex items-center gap-3">
          <button
            onClick={handleSend}
            disabled={sending || !subject.trim() || !body.trim()}
            className="px-5 py-2 bg-brand-500 text-white text-sm font-medium rounded-lg hover:bg-brand-600 disabled:opacity-50 transition-colors"
          >
            {sending ? t('adminPage.sending') : t('adminPage.sendBroadcast')}
          </button>
          {feedback && (
            <span className={`text-sm font-medium ${feedback.type === 'success' ? 'text-green-600' : 'text-red-500'}`}>
              {feedback.text}
            </span>
          )}
        </div>
      </div>

      {/* ── Broadcast History ── */}
      <div className="rounded-xl border p-6 mt-6" style={{ background: 'var(--portal-card-bg)', borderColor: 'var(--portal-card-border)' }}>
        <h2 className="text-lg font-semibold mb-4" style={{ color: 'var(--portal-text-primary)' }}>
          {t('adminPage.broadcastHistory')}
        </h2>

        {historyLoading ? (
          <div className="flex justify-center py-8">
            <div className="w-5 h-5 border-2 border-brand-500 border-t-transparent rounded-full animate-spin" />
          </div>
        ) : history.length === 0 ? (
          <p className="text-sm py-6 text-center" style={{ color: 'var(--portal-text-muted)' }}>
            {t('adminPage.noBroadcasts')}
          </p>
        ) : (
          <>
            <div className="space-y-3">
              {history.map((h) => {
                const catColor = CATEGORY_OPTIONS.find((c) => c.value === h.category)?.color ?? 'bg-gray-100 text-gray-600';
                const isExpanded = expandedId === h.id;
                return (
                  <div
                    key={h.id}
                    className="border rounded-lg overflow-hidden"
                    style={{ borderColor: 'var(--portal-card-border)' }}
                  >
                    {/* Summary row */}
                    <button
                      type="button"
                      onClick={() => setExpandedId(isExpanded ? null : h.id)}
                      className="w-full flex items-center gap-3 px-4 py-3 text-left hover:bg-gray-50 transition-colors"
                    >
                      <span className={`text-[10px] font-semibold px-1.5 py-0.5 rounded uppercase ${catColor}`}>
                        {h.category}
                      </span>
                      <span className="flex-1 text-sm font-medium truncate" style={{ color: 'var(--portal-text-primary)' }}>
                        {h.subject}
                      </span>
                      <span className="text-xs whitespace-nowrap" style={{ color: 'var(--portal-text-muted)' }}>
                        {h.sent_count} sent{h.failed_count > 0 ? `, ${h.failed_count} failed` : ''}
                      </span>
                      <span className="text-xs whitespace-nowrap" style={{ color: 'var(--portal-text-muted)' }}>
                        {new Date(h.created_at).toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric', hour: '2-digit', minute: '2-digit' })}
                      </span>
                      <svg className={`w-4 h-4 text-gray-400 transition-transform ${isExpanded ? 'rotate-180' : ''}`} fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                      </svg>
                    </button>

                    {/* Expanded details */}
                    {isExpanded && (
                      <div className="px-4 pb-4 border-t" style={{ borderColor: 'var(--portal-card-border)' }}>
                        <div className="mt-3 text-sm whitespace-pre-line" style={{ color: 'var(--portal-text-primary)' }}>
                          {h.body}
                        </div>
                        <div className="mt-3">
                          <p className="text-xs font-medium mb-1" style={{ color: 'var(--portal-text-muted)' }}>
                            Recipients ({h.recipient_count}):
                          </p>
                          <div className="flex flex-wrap gap-1">
                            {h.recipient_emails.map((email) => (
                              <span key={email} className="text-[11px] px-2 py-0.5 rounded-full bg-gray-100 text-gray-600">
                                {email}
                              </span>
                            ))}
                          </div>
                        </div>
                        <div className="mt-3 flex items-center justify-between">
                          <span className="text-xs" style={{ color: 'var(--portal-text-muted)' }}>
                            Sent by {h.sender_display_name}
                          </span>
                          <button
                            onClick={() => handleDeleteLog(h.id)}
                            disabled={deletingId === h.id}
                            className="text-xs text-red-500 hover:text-red-700 font-medium disabled:opacity-50"
                          >
                            {deletingId === h.id ? 'Deleting…' : 'Delete'}
                          </button>
                        </div>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>

            {/* Pagination */}
            {historyTotal > 10 && (
              <div className="flex items-center justify-center gap-2 mt-4">
                <button
                  onClick={() => setHistoryPage((p) => Math.max(1, p - 1))}
                  disabled={historyPage <= 1}
                  className="px-3 py-1 text-xs border rounded disabled:opacity-40"
                  style={{ borderColor: 'var(--portal-card-border)', color: 'var(--portal-text-primary)' }}
                >
                  Previous
                </button>
                <span className="text-xs" style={{ color: 'var(--portal-text-muted)' }}>
                  {t('adminPage.pageOf', { page: historyPage, total: Math.ceil(historyTotal / 10) })}
                </span>
                <button
                  onClick={() => setHistoryPage((p) => p + 1)}
                  disabled={historyPage >= Math.ceil(historyTotal / 10)}
                  className="px-3 py-1 text-xs border rounded disabled:opacity-40"
                  style={{ borderColor: 'var(--portal-card-border)', color: 'var(--portal-text-primary)' }}
                >
                  Next
                </button>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}

// ── Maintenance mode panel (Super Admin only) ────────────────────────────────

function MaintenancePanel({ token }: { token: string | null }) {
  const { t } = useTranslation();
  const [loading, setLoading]       = useState(true);
  const [saving, setSaving]         = useState(false);
  const [enabled, setEnabled]       = useState(false);
  const [message, setMessage]       = useState('');
  const [feedback, setFeedback]     = useState('');

  useEffect(() => {
    if (!token) return;
    (async () => {
      try {
        const res = await fetch(`${API_BASE}/site-settings/maintenance`, {
          headers: { Authorization: `Bearer ${token}` },
          credentials: 'include',
        });
        if (res.ok) {
          const data = await res.json();
          setEnabled(data.maintenance_mode);
          setMessage(data.maintenance_message);
        }
      } catch { /* ignore */ }
      finally { setLoading(false); }
    })();
  }, [token]);

  async function handleSave() {
    if (!token) return;
    setSaving(true);
    setFeedback('');
    try {
      const res = await fetch(`${API_BASE}/site-settings/maintenance`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`,
        },
        credentials: 'include',
        body: JSON.stringify({
          maintenance_mode: enabled,
          maintenance_message: message || undefined,
        }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error((err as any).detail ?? 'Failed to update');
      }
      const data = await res.json();
      setEnabled(data.maintenance_mode);
      setMessage(data.maintenance_message);
      setFeedback(data.maintenance_mode ? 'Site is now Under Construction' : 'Site is now Live');
    } catch (err) {
      setFeedback((err as Error).message);
    } finally {
      setSaving(false);
    }
  }

  if (loading) {
    return (
      <div className="flex justify-center py-12">
        <div className="w-6 h-6 border-2 border-brand-500 border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  return (
    <div className="max-w-2xl">
      <div className="rounded-xl border p-6" style={{ background: 'var(--portal-card-bg)', borderColor: 'var(--portal-card-border)' }}>
        <h2 className="text-lg font-semibold mb-1" style={{ color: 'var(--portal-text-primary)' }}>
          {t('adminPage.maintenanceMode')}
        </h2>
        <p className="text-sm mb-6" style={{ color: 'var(--portal-text-muted)' }}>
          {t('adminPage.maintenanceModeDesc')}
        </p>

        {/* Toggle */}
        <div className="flex items-center gap-3 mb-6">
          <button
            type="button"
            role="switch"
            aria-checked={enabled}
            onClick={() => setEnabled(!enabled)}
            className={`relative inline-flex h-6 w-11 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors ${
              enabled ? 'bg-amber-500' : 'bg-gray-300'
            }`}
          >
            <span
              className={`pointer-events-none inline-block h-5 w-5 rounded-full bg-white shadow ring-0 transition-transform ${
                enabled ? 'translate-x-5' : 'translate-x-0'
              }`}
            />
          </button>
          <span className="text-sm font-medium" style={{ color: 'var(--portal-text-primary)' }}>
            {enabled ? (
              <span className="text-amber-600 font-semibold">{t('adminPage.enabled')}</span>
            ) : (
              <span className="text-green-600 font-semibold">{t('adminPage.disabled')}</span>
            )}
          </span>
        </div>

        {/* Message */}
        <div className="flex items-center justify-between mb-1.5">
          <label className="block text-sm font-medium" style={{ color: 'var(--portal-text-primary)' }}>
            {t('adminPage.motd')}
          </label>
          <button
            type="button"
            onClick={() => setMessage('We are currently performing scheduled maintenance. Please check back soon!')}
            className="text-xs px-2 py-1 rounded border border-gray-300 hover:bg-gray-100 transition-colors"
            style={{ color: 'var(--portal-text-muted)' }}
          >
            Reset to default
          </button>
        </div>
        <textarea
          rows={4}
          value={message}
          onChange={(e) => setMessage(e.target.value)}
          placeholder="We are currently performing scheduled maintenance. Please check back soon!"
          maxLength={2000}
          className="w-full px-3 py-2 text-sm border rounded-lg focus:outline-none focus:ring-2 focus:ring-brand-500 resize-y"
          style={{ background: 'var(--portal-card-bg)', color: 'var(--portal-text-primary)', borderColor: 'var(--portal-card-border)' }}
        />
        <p className="text-xs mt-1 mb-4" style={{ color: 'var(--portal-text-muted)' }}>
          This message is shown to all visitors when maintenance mode is enabled.
        </p>

        {/* Save */}
        <div className="flex items-center gap-3">
          <button
            onClick={handleSave}
            disabled={saving}
            className="px-5 py-2 bg-brand-500 text-white text-sm font-medium rounded-lg hover:bg-brand-600 disabled:opacity-50 transition-colors"
          >
            {saving ? t('adminPage.saving') : t('adminPage.saveSettings')}
          </button>
          {feedback && (
            <span className="text-sm font-medium" style={{ color: feedback.includes('Failed') ? '#ef4444' : '#22c55e' }}>
              {feedback}
            </span>
          )}
        </div>
      </div>
    </div>
  );
}

// ── Global Trees panel (Super Admin only) ────────────────────────────────────

function GlobalTreesPanel({ token }: { token: string | null }) {
  const { t } = useTranslation();
  const authHeader: Record<string, string> = token ? { Authorization: `Bearer ${token}` } : {};

  const [allTrees, setAllTrees] = useState<TenantTree[]>([]);
  const [groups, setGroups] = useState<PermissionGroup[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const [selectedTreeIds, setSelectedTreeIds] = useState<string[]>([]);
  const [selectedGroupId, setSelectedGroupId] = useState('');
  const [submitting, setSubmitting] = useState(false);

  const [groupTrees, setGroupTrees] = useState<Record<string, GroupTree[]>>({});
  const [loadingGroupTrees, setLoadingGroupTrees] = useState<Record<string, boolean>>({});
  const [togglingId, setTogglingId] = useState<string | null>(null);

  const fetchAll = React.useCallback(async () => {
    if (!token) return;
    setLoading(true);
    setError('');
    try {
      const [treesRes, groupsRes] = await Promise.all([
        fetch(`${API_BASE}/admin/trees`, { headers: authHeader, credentials: 'include' }),
        fetch(`${API_BASE}/admin/permission-groups`, { headers: authHeader, credentials: 'include' }),
      ]);
      if (treesRes.ok) setAllTrees(await treesRes.json());
      if (groupsRes.ok) setGroups(await groupsRes.json());
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  }, [token]);

  useEffect(() => { fetchAll(); }, [fetchAll]);

  const globalGroups = groups.filter((g) => g.is_global);

  const fetchGroupTrees = useCallback(async (groupId: string) => {
    setLoadingGroupTrees((prev) => ({ ...prev, [groupId]: true }));
    try {
      const res = await fetch(`${API_BASE}/admin/permission-groups/${groupId}/trees`, { headers: authHeader, credentials: 'include' });
      if (res.ok) {
        const data = await res.json();
        setGroupTrees((prev) => ({ ...prev, [groupId]: data }));
      }
    } finally {
      setLoadingGroupTrees((prev) => ({ ...prev, [groupId]: false }));
    }
  }, [token]);

  useEffect(() => {
    globalGroups.forEach((g) => {
      if (groupTrees[g.id] === undefined && !loadingGroupTrees[g.id]) fetchGroupTrees(g.id);
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [groups]);

  function toggleTree(id: string) {
    setSelectedTreeIds((prev) => (prev.includes(id) ? prev.filter((tid) => tid !== id) : [...prev, id]));
  }

  async function handleMakeGlobal() {
    if (!selectedGroupId || selectedTreeIds.length === 0) return;
    setSubmitting(true);
    setError('');
    try {
      const existingTreeIds = new Set((groupTrees[selectedGroupId] ?? []).map((gt) => gt.tree_id));
      const toAdd = selectedTreeIds.filter((id) => !existingTreeIds.has(id));
      for (const treeId of toAdd) {
        const res = await fetch(`${API_BASE}/admin/permission-groups/${selectedGroupId}/trees`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', ...authHeader },
          credentials: 'include',
          body: JSON.stringify({ tree_id: treeId }),
        });
        if (!res.ok) {
          const err = await res.json().catch(() => ({}));
          throw new Error((err as any).detail ?? 'Failed to attach tree to group');
        }
      }
      const res = await fetch(`${API_BASE}/admin/permission-groups/${selectedGroupId}/global`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json', ...authHeader },
        credentials: 'include',
        body: JSON.stringify({ is_global: true }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error((err as any).detail ?? 'Failed to make group global');
      }
      setSelectedTreeIds([]);
      setSelectedGroupId('');
      setGroupTrees((prev) => { const n = { ...prev }; delete n[selectedGroupId]; return n; });
      await fetchAll();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setSubmitting(false);
    }
  }

  async function handleUnGlobalize(groupId: string) {
    setTogglingId(groupId);
    try {
      await fetch(`${API_BASE}/admin/permission-groups/${groupId}/global`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json', ...authHeader },
        credentials: 'include',
        body: JSON.stringify({ is_global: false }),
      });
      await fetchAll();
    } finally {
      setTogglingId(null);
    }
  }

  async function handleRemoveTreeFromGroup(groupId: string, treeId: string) {
    await fetch(`${API_BASE}/admin/permission-groups/${groupId}/trees/${treeId}`, {
      method: 'DELETE', headers: authHeader, credentials: 'include',
    });
    fetchGroupTrees(groupId);
  }

  if (loading) return (
    <div className="flex justify-center py-16">
      <div className="w-7 h-7 border-2 border-brand-500 border-t-transparent rounded-full animate-spin" />
    </div>
  );

  return (
    <div className="max-w-2xl">
      <p className="text-sm text-gray-500 mb-4">{t('adminPage.globalTreesDesc')}</p>

      {error && (
        <div className="mb-4 px-4 py-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700">{error}</div>
      )}

      {/* Make trees global */}
      <div className="rounded-xl border p-5 mb-6" style={{ background: 'var(--portal-card-bg)', borderColor: 'var(--portal-border)' }}>
        <p className="text-xs font-medium text-gray-600 mb-2">
          {t('adminPage.selectTreesGlobal')} <span className="text-red-500">*</span>
        </p>
        {allTrees.length === 0 ? (
          <p className="text-sm text-gray-400">{t('adminPage.noTreesFound')}</p>
        ) : (
          <div className="border border-gray-200 rounded-lg divide-y divide-gray-100 max-h-56 overflow-y-auto mb-4">
            {allTrees.map((tree) => (
              <label key={tree.id} className="flex items-center gap-3 px-4 py-2.5 hover:bg-gray-50 cursor-pointer">
                <input
                  type="checkbox"
                  checked={selectedTreeIds.includes(tree.id)}
                  onChange={() => toggleTree(tree.id)}
                  className="rounded border-gray-300 text-brand-500"
                />
                <span className="text-sm text-gray-800">{tree.name}</span>
              </label>
            ))}
          </div>
        )}

        <p className="text-xs font-medium text-gray-600 mb-1">
          {t('adminPage.selectPermissionGroup')} <span className="text-red-500">*</span>
        </p>
        <select
          value={selectedGroupId}
          onChange={(e) => setSelectedGroupId(e.target.value)}
          className="w-full h-9 px-3 text-sm border border-gray-300 rounded-lg bg-white focus:outline-none focus:ring-2 focus:ring-brand-500 mb-4"
        >
          <option value="">{t('adminPage.selectGroup')}</option>
          {groups.map((g) => (
            <option key={g.id} value={g.id}>
              {g.name} — {t(LEVEL_LABEL_KEY[g.permission_level])}{g.is_global ? ` (${t('adminPage.alreadyGlobal')})` : ''}
            </option>
          ))}
        </select>

        <button
          onClick={handleMakeGlobal}
          disabled={submitting || !selectedGroupId || selectedTreeIds.length === 0}
          className="px-4 py-2 bg-brand-500 text-white text-sm font-medium rounded-lg hover:bg-brand-600 disabled:opacity-40 disabled:cursor-not-allowed transition-colors flex items-center gap-2"
        >
          {submitting && <span className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin inline-block" />}
          {submitting ? t('adminPage.saving') : t('adminPage.makeGlobal')}
        </button>
      </div>

      {/* Currently-global groups */}
      <h3 className="text-sm font-semibold text-gray-700 mb-2">{t('adminPage.globalGroupsHeading')}</h3>
      {globalGroups.length === 0 ? (
        <p className="text-sm text-gray-400 text-center py-6 border border-dashed border-gray-200 rounded-lg">
          {t('adminPage.noGlobalGroups')}
        </p>
      ) : (
        <div className="space-y-3">
          {globalGroups.map((g) => (
            <div key={g.id} className="rounded-xl border p-4" style={{ background: 'var(--portal-card-bg)', borderColor: 'var(--portal-border)' }}>
              <div className="flex items-center justify-between mb-2">
                <div className="flex items-center gap-2">
                  <span className="text-sm font-medium text-gray-900">{g.name}</span>
                  <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${LEVEL_BADGE[g.permission_level]}`}>
                    {t(LEVEL_LABEL_KEY[g.permission_level])}
                  </span>
                </div>
                <button
                  onClick={() => handleUnGlobalize(g.id)}
                  disabled={togglingId === g.id}
                  className="px-2.5 py-1 text-xs font-medium text-red-600 bg-white border border-red-200 rounded-lg hover:bg-red-50 disabled:opacity-50 transition-colors"
                >
                  {togglingId === g.id ? '…' : t('adminPage.unGlobalize')}
                </button>
              </div>
              {loadingGroupTrees[g.id] ? (
                <div className="flex justify-center py-2">
                  <div className="w-4 h-4 border-2 border-brand-500 border-t-transparent rounded-full animate-spin" />
                </div>
              ) : (groupTrees[g.id]?.length ?? 0) === 0 ? (
                <p className="text-xs text-gray-400">{t('adminPage.noTreesFound')}</p>
              ) : (
                <div className="flex flex-wrap gap-1.5">
                  {(groupTrees[g.id] ?? []).map((gt) => (
                    <span key={gt.id} className="inline-flex items-center gap-1.5 pl-2.5 pr-1.5 py-1 rounded-full bg-gray-100 text-xs text-gray-700">
                      {gt.tree_name}
                      <button
                        onClick={() => handleRemoveTreeFromGroup(g.id, gt.tree_id)}
                        className="text-gray-400 hover:text-red-600 leading-none"
                        title={t('common.remove')}
                      >
                        ×
                      </button>
                    </span>
                  ))}
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// ── Page ───────────────────────────────────────────────────────────────────────

export default function AdminPage() {
  const { t } = useTranslation();
  const accessToken  = useAuthStore((s) => s.accessToken);
  const currentUser  = useAuthStore((s) => s.user);
  const isSuperAdmin = currentUser?.appRole === 'SUPER_ADMIN';
  const [activeTab, setActiveTab] = useState<'users' | 'permissions' | 'merge' | 'global' | 'subscriptions' | 'broadcast' | 'site'>('users');

  const [data,     setData]     = useState<UsersResponse | null>(null);
  const [loading,  setLoading]  = useState(false);
  const [error,    setError]    = useState('');

  const [page,     setPage]     = useState(1);
  const [search,   setSearch]   = useState('');
  const [debouncedSearch, setDebounced] = useState('');
  const [roleFilter,  setRoleFilter]  = useState('');
  const [verifiedFilter, setVerifiedFilter] = useState('');
  const [sort,     setSort]     = useState('created_at_desc');

  const [createOpen,      setCreateOpen]      = useState(false);
  const [editTarget,      setEditTarget]      = useState<AdminUser | null>(null);
  const [confirmDeactivate, setConfirmDeactivate] = useState<AdminUser | null>(null);
  const [confirmPurge,    setConfirmPurge]    = useState<AdminUser | null>(null);
  const [actionLoading,   setActionLoading]   = useState<string | null>(null);

  const debounceRef = useRef<ReturnType<typeof setTimeout>>();
  useEffect(() => {
    clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => { setDebounced(search); setPage(1); }, 350);
    return () => clearTimeout(debounceRef.current);
  }, [search]);

  const fetchUsers = useCallback(async () => {
    if (!accessToken) return;
    setLoading(true);
    setError('');
    try {
      const params = new URLSearchParams({
        page: String(page), page_size: String(PAGE_SIZE), sort,
        ...(debouncedSearch ? { search: debouncedSearch } : {}),
        ...(roleFilter ? { app_role: roleFilter } : {}),
        ...(verifiedFilter !== '' ? { verified: verifiedFilter } : {}),
      });
      const res = await fetch(`${API_BASE}/admin/users?${params}`, {
        headers: { Authorization: `Bearer ${accessToken}` },
        credentials: 'include',
      });
      if (!res.ok) throw new Error('Failed to load users');
      setData(await res.json());
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  }, [accessToken, page, debouncedSearch, roleFilter, verifiedFilter, sort]);

  useEffect(() => { fetchUsers(); }, [fetchUsers]);

  async function handleVerify(user: AdminUser) {
    setActionLoading(user.id + '_verify');
    try {
      const res = await fetch(`${API_BASE}/admin/users/${user.id}/verify`, {
        method: 'POST',
        headers: accessToken ? { Authorization: `Bearer ${accessToken}` } : {},
        credentials: 'include',
      });
      if (!res.ok) throw new Error('Verification failed');
      const updated: AdminUser = await res.json();
      setData((d) => d ? { ...d, items: d.items.map((u) => u.id === updated.id ? updated : u) } : d);
    } finally {
      setActionLoading(null);
    }
  }

  async function handleDeactivate(user: AdminUser) {
    setActionLoading(user.id + '_del');
    try {
      await fetch(`${API_BASE}/admin/users/${user.id}`, {
        method: 'DELETE',
        headers: accessToken ? { Authorization: `Bearer ${accessToken}` } : {},
        credentials: 'include',
      });
      setData((d) => d ? { ...d, items: d.items.map((u) => u.id === user.id ? { ...u, is_active: false } : u) } : d);
    } finally {
      setActionLoading(null);
      setConfirmDeactivate(null);
    }
  }

  async function handlePurge(user: AdminUser) {
    setActionLoading(user.id + '_purge');
    try {
      const res = await fetch(`${API_BASE}/admin/users/${user.id}/purge`, {
        method: 'DELETE',
        headers: accessToken ? { Authorization: `Bearer ${accessToken}` } : {},
        credentials: 'include',
      });
      if (!res.ok) throw new Error('Failed to permanently delete user');
      setData((d) => d ? { ...d, items: d.items.filter((u) => u.id !== user.id), total: d.total - 1 } : d);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setActionLoading(null);
      setConfirmPurge(null);
    }
  }

  function handleSaved(updated: AdminUser) {
    setData((d) => d ? { ...d, items: d.items.map((u) => u.id === updated.id ? updated : u) } : d);
    setEditTarget(null);
  }

  return (
    <div className="p-4 md:p-6 max-w-7xl mx-auto">
      <SEO
        title="Admin Dashboard"
        description="Manage users, roles, and permission groups for your OurFamRoots organisation."
        noIndex
      />
      {/* Header */}
      <div className="mb-4 md:mb-6">
        <h1 className="text-xl font-bold" style={{ color: 'var(--portal-text-primary)' }}>{t('adminPage.title')}</h1>
        <p className="text-sm mt-0.5" style={{ color: 'var(--portal-text-muted)' }}>{t('adminPage.subtitle')}</p>
      </div>

      {/* Tab bar */}
      <div className="flex gap-1 border-b border-gray-200 mb-6">
        {([
          ['users', t('adminPage.tabs.users')],
          ['permissions', t('adminPage.tabs.permissions')],
          ['merge', t('adminPage.tabs.merge')],
          ...(isSuperAdmin ? [
            ['global', t('adminPage.tabs.global')] as const,
            ['subscriptions', 'Subscriptions'] as const,
            ['broadcast', t('adminPage.tabs.broadcast')] as const,
            ['site', t('adminPage.tabs.site')] as const,
          ] : []),
        ] as const).map(([key, label]) => (
          <button
            key={key}
            onClick={() => setActiveTab(key as typeof activeTab)}
            className={`px-4 py-2 text-sm font-medium rounded-t-lg border-b-2 transition-colors ${
              activeTab === key
                ? 'border-brand-500 text-brand-600'
                : 'border-transparent text-gray-500 hover:text-gray-700'
            }`}
          >
            {label}
          </button>
        ))}
      </div>

      {activeTab === 'permissions' && <PermissionGroupsPanel token={accessToken} />}
      {activeTab === 'merge' && <MergeTreesPanel token={accessToken} />}
      {activeTab === 'global' && isSuperAdmin && <GlobalTreesPanel token={accessToken} />}
      {activeTab === 'subscriptions' && isSuperAdmin && <SubscriptionsPanel token={accessToken} />}
      {activeTab === 'broadcast' && isSuperAdmin && <BroadcastPanel token={accessToken} />}
      {activeTab === 'site' && isSuperAdmin && <MaintenancePanel token={accessToken} />}
      {activeTab === 'users' && (<>

      {/* Users tab header actions */}
      <div className="flex items-center justify-between mb-4">
        <span />
        <button
          onClick={() => setCreateOpen(true)}
          className="px-4 py-2 bg-brand-500 text-white text-sm font-medium rounded-lg hover:bg-brand-600 transition-colors"
        >
          + {t('adminPage.createUser')}
        </button>
      </div>

      {/* Filters */}
      <div className="flex flex-wrap gap-3 mb-4">
        <div className="relative flex-1 min-w-48">
          <svg className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400"
            fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
              d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
          </svg>
          <input type="text" value={search} onChange={(e) => setSearch(e.target.value)}
            placeholder={t('adminPage.search')}
            className="w-full h-9 pl-9 pr-3 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-brand-500"
          style={{ background: 'var(--portal-card-bg)', color: 'var(--portal-text-primary)' }} />
        </div>
        <select value={roleFilter} onChange={(e) => { setRoleFilter(e.target.value); setPage(1); }}
          className="h-9 px-3 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-brand-500"
          style={{ background: 'var(--portal-card-bg)', color: 'var(--portal-text-primary)' }}>
          <option value="">{t('adminPage.allRoles')}</option>
          <option value="SUPER_ADMIN">{t('roles.SUPER_ADMIN')}</option>
          <option value="ADMIN">{t('roles.ADMIN')}</option>
          <option value="STANDARD">{t('roles.STANDARD')}</option>
          <option value="AUDITOR">{t('roles.AUDITOR')}</option>
        </select>
        <select value={verifiedFilter} onChange={(e) => { setVerifiedFilter(e.target.value); setPage(1); }}
          className="h-9 px-3 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-brand-500"
          style={{ background: 'var(--portal-card-bg)', color: 'var(--portal-text-primary)' }}>
          <option value="">{t('adminPage.status')}</option>
          <option value="false">{t('adminPage.unverified')}</option>
          <option value="true">{t('adminPage.verified')}</option>
        </select>
        <select value={sort} onChange={(e) => { setSort(e.target.value); setPage(1); }}
          className="h-9 px-3 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-brand-500"
          style={{ background: 'var(--portal-card-bg)', color: 'var(--portal-text-primary)' }}>
          <option value="created_at_desc">{t('adminPage.newestFirst')}</option>
          <option value="created_at_asc">{t('adminPage.oldestFirst')}</option>
          <option value="name_asc">{t('adminPage.nameAZ')}</option>
          <option value="email_asc">{t('adminPage.emailAZ')}</option>
          <option value="last_login_desc">{t('adminPage.lastActive')}</option>
        </select>
      </div>

      {data && (
        <p className="text-xs text-gray-500 mb-3">
          {debouncedSearch || roleFilter || verifiedFilter
            ? t('adminPage.usersMatching', { count: data.total })
            : t('adminPage.usersTotal', { count: data.total })}
          {' · '}{t('adminPage.pageOf', { page: data.page, total: data.total_pages })}
        </p>
      )}

      {error && (
        <div className="mb-4 px-4 py-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700">{error}</div>
      )}

      {/* Table */}
      <div className="rounded-xl border overflow-hidden" style={{ background: 'var(--portal-card-bg)', borderColor: 'var(--portal-border)' }}>
        {loading && !data ? (
          <div className="flex justify-center py-16">
            <div className="w-7 h-7 border-2 border-brand-500 border-t-transparent rounded-full animate-spin" />
          </div>
        ) : data?.items.length === 0 ? (
          <div className="text-center py-16 text-sm" style={{ color: 'var(--portal-text-muted)' }}>{t('adminPage.noUsersFound')}</div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b" style={{ background: 'var(--portal-main-bg)', borderColor: 'var(--portal-border)' }}>
                  <th className="text-left px-4 py-3 text-xs font-semibold uppercase tracking-wider" style={{ color: 'var(--portal-text-muted)' }}>{t('adminPage.name')}</th>
                  <th className="text-left px-4 py-3 text-xs font-semibold uppercase tracking-wider" style={{ color: 'var(--portal-text-muted)' }}>{t('adminPage.role')}</th>
                  <th className="text-left px-4 py-3 text-xs font-semibold uppercase tracking-wider" style={{ color: 'var(--portal-text-muted)' }}>{t('adminPage.status')}</th>
                  <th className="text-left px-4 py-3 text-xs font-semibold uppercase tracking-wider" style={{ color: 'var(--portal-text-muted)' }}>{t('adminPage.lastLogin')}</th>
                  <th className="text-left px-4 py-3 text-xs font-semibold uppercase tracking-wider" style={{ color: 'var(--portal-text-muted)' }}>{t('adminPage.joined')}</th>
                  <th className="text-right px-4 py-3 text-xs font-semibold uppercase tracking-wider" style={{ color: 'var(--portal-text-muted)' }}>{t('adminPage.actions')}</th>
                </tr>
              </thead>
              <tbody className={`divide-y divide-gray-50 ${loading ? 'opacity-50' : ''}`}>
                {data?.items.map((user) => (
                  <tr key={user.id} className="hover:bg-gray-50 transition-colors">
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-3">
                        <UserAvatar
                          avatarUrl={user.avatar_url}
                          displayName={displayName(user)}
                          email={user.email}
                          size="sm"
                        />
                        <div className="min-w-0">
                          <div className="font-medium text-gray-900 truncate">{displayName(user)}</div>
                          <div className="text-xs text-gray-500 truncate">{user.email}</div>
                        </div>
                      </div>
                    </td>
                    <td className="px-4 py-3">
                      <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${ROLE_BADGE[user.app_role]}`}>
                        {t('roles.' + user.app_role)}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex flex-col gap-0.5">
                        <span className={`inline-flex items-center gap-1 text-xs font-medium ${user.email_verified ? 'text-green-700' : 'text-amber-700'}`}>
                          <span className={`w-1.5 h-1.5 rounded-full ${user.email_verified ? 'bg-green-500' : 'bg-amber-400'}`} />
                          {user.email_verified ? t('adminPage.verified') : t('adminPage.unverified')}
                        </span>
                        {!user.is_active && (
                          <span className="inline-flex items-center gap-1 text-xs font-medium text-red-600">
                            <span className="w-1.5 h-1.5 rounded-full bg-red-500" />
                            {t('adminPage.inactive')}
                          </span>
                        )}
                      </div>
                    </td>
                    <td className="px-4 py-3 text-xs text-gray-500">{formatDateTime(user.last_login_at)}</td>
                    <td className="px-4 py-3 text-xs text-gray-500">{formatDate(user.created_at)}</td>
                    <td className="px-4 py-3">
                      <div className="flex items-center justify-end gap-1">
                        {!user.email_verified && (
                          <button
                            onClick={() => handleVerify(user)}
                            disabled={actionLoading === user.id + '_verify'}
                            title="Verify email"
                            className="px-2.5 py-1 text-xs font-medium text-green-700 bg-green-50 border border-green-200 rounded-lg hover:bg-green-100 disabled:opacity-50 transition-colors"
                          >
                            {actionLoading === user.id + '_verify' ? '…' : t('adminPage.verify')}
                          </button>
                        )}
                        <button
                          onClick={() => setEditTarget(user)}
                          title="Edit user"
                          className="px-2.5 py-1 text-xs font-medium text-gray-600 bg-white border border-gray-200 rounded-lg hover:bg-gray-50 transition-colors"
                        >
                          {t('common.edit')}
                        </button>
                        {user.is_active && (
                          <button
                            onClick={() => { if (user.id !== currentUser?.id) setConfirmDeactivate(user); }}
                            disabled={actionLoading === user.id + '_del' || user.id === currentUser?.id}
                            title={user.id === currentUser?.id ? 'Cannot deactivate your own account' : t('adminPage.deactivate')}
                            className="px-2.5 py-1 text-xs font-medium text-red-600 bg-white border border-red-200 rounded-lg hover:bg-red-50 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                          >
                            {t('adminPage.deactivate')}
                          </button>
                        )}
                        {isSuperAdmin && !user.is_active && user.id !== currentUser?.id && (
                          <button
                            onClick={() => setConfirmPurge(user)}
                            disabled={actionLoading === user.id + '_purge'}
                            title={t('adminPage.deleteForever')}
                            className="px-2.5 py-1 text-xs font-medium text-white bg-red-600 border border-red-600 rounded-lg hover:bg-red-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                          >
                            {actionLoading === user.id + '_purge' ? t('adminPage.deletingUser') : t('adminPage.deleteForever')}
                          </button>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Pagination */}
      {data && data.total_pages > 1 && (
        <div className="flex items-center justify-between mt-4">
          <button onClick={() => setPage((p) => Math.max(1, p - 1))} disabled={page === 1 || loading}
            className="h-8 px-3 text-sm border border-gray-300 rounded-lg disabled:opacity-40 hover:bg-gray-50">
            ← Previous
          </button>
          <span className="text-sm text-gray-500">{t('adminPage.pageOf', { page, total: data.total_pages })}</span>
          <button onClick={() => setPage((p) => Math.min(data.total_pages, p + 1))} disabled={page === data.total_pages || loading}
            className="h-8 px-3 text-sm border border-gray-300 rounded-lg disabled:opacity-40 hover:bg-gray-50">
            Next →
          </button>
        </div>
      )}

      {/* Create user modal */}
      {createOpen && (
        <CreateUserModal
          token={accessToken}
          onClose={() => setCreateOpen(false)}
          onCreated={() => {
            setCreateOpen(false);
            fetchUsers();
          }}
        />
      )}

      {/* Edit modal */}
      {editTarget && (
        <EditUserModal
          user={editTarget}
          token={accessToken}
          isSelf={editTarget.id === currentUser?.id}
          onClose={() => setEditTarget(null)}
          onSaved={handleSaved}
        />
      )}

      {/* Deactivate confirmation */}
      {confirmDeactivate && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4"
          onClick={(e) => { if (e.target === e.currentTarget) setConfirmDeactivate(null); }}>
          <div className="bg-white rounded-2xl shadow-xl w-full max-w-sm p-6">
            <h2 className="text-lg font-semibold text-gray-900 mb-1">{t('adminPage.deactivate')}?</h2>
            <p className="text-sm text-gray-500 mb-4">
              <span className="font-medium text-gray-800">{displayName(confirmDeactivate)}</span> will
              lose access immediately. You can re-activate them via Edit.
            </p>
            <div className="flex justify-end gap-3">
              <button onClick={() => setConfirmDeactivate(null)}
                className="px-4 py-2 text-sm text-gray-600 hover:text-gray-900 transition-colors">
                {t('adminPage.cancel')}
              </button>
              <button onClick={() => handleDeactivate(confirmDeactivate)}
                disabled={actionLoading === confirmDeactivate.id + '_del'}
                className="px-4 py-2 bg-red-600 text-white text-sm font-medium rounded-lg hover:bg-red-700 disabled:opacity-50">
                {actionLoading === confirmDeactivate.id + '_del' ? t('adminPage.saving') : t('adminPage.deactivate')}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Permanent delete confirmation */}
      {confirmPurge && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4"
          onClick={(e) => { if (e.target === e.currentTarget) setConfirmPurge(null); }}>
          <div className="bg-white rounded-2xl shadow-xl w-full max-w-sm p-6">
            <h2 className="text-lg font-semibold text-gray-900 mb-1">{t('adminPage.deleteForever')}?</h2>
            <p className="text-sm text-gray-500 mb-4">
              <span className="font-medium text-gray-800">{displayName(confirmPurge)}</span> {t('adminPage.deleteForeverWarning')}
            </p>
            <div className="flex justify-end gap-3">
              <button onClick={() => setConfirmPurge(null)}
                className="px-4 py-2 text-sm text-gray-600 hover:text-gray-900 transition-colors">
                {t('adminPage.cancel')}
              </button>
              <button onClick={() => handlePurge(confirmPurge)}
                disabled={actionLoading === confirmPurge.id + '_purge'}
                className="px-4 py-2 bg-red-600 text-white text-sm font-medium rounded-lg hover:bg-red-700 disabled:opacity-50">
                {actionLoading === confirmPurge.id + '_purge' ? t('adminPage.deletingUser') : t('adminPage.deleteForever')}
              </button>
            </div>
          </div>
        </div>
      )}
      </>)}
    </div>
  );
}

// ── Permission Groups Panel ────────────────────────────────────────────────────

function PermissionGroupsPanel({ token }: { token: string | null }) {
  const { t } = useTranslation();
  const [groups, setGroups]           = useState<PermissionGroup[]>([]);
  const [loading, setLoading]         = useState(false);
  const [createOpen, setCreateOpen]   = useState(false);
  const [editTarget, setEditTarget]   = useState<PermissionGroup | null>(null);
  const [membersTarget, setMembersTarget] = useState<PermissionGroup | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<PermissionGroup | null>(null);
  const [error, setError]             = useState('');

  const authHeader: Record<string, string> = token ? { Authorization: `Bearer ${token}` } : {};

  const fetchGroups = React.useCallback(async () => {
    if (!token) return;
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE}/admin/permission-groups`, { headers: authHeader, credentials: 'include' });
      if (!res.ok) throw new Error('Failed to load permission groups');
      setGroups(await res.json());
    } catch (e) { setError((e as Error).message); }
    finally { setLoading(false); }
  }, [token]);

  useEffect(() => { fetchGroups(); }, [fetchGroups]);

  async function handleDelete(g: PermissionGroup) {
    await fetch(`${API_BASE}/admin/permission-groups/${g.id}`, {
      method: 'DELETE', headers: authHeader, credentials: 'include',
    });
    setDeleteTarget(null);
    fetchGroups();
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <p className="text-sm text-gray-500">
          {t('adminPage.permGroupsDesc')}
        </p>
        <button
          onClick={() => setCreateOpen(true)}
          className="px-4 py-2 bg-brand-500 text-white text-sm font-medium rounded-lg hover:bg-brand-600 transition-colors"
        >
          + {t('adminPage.createGroup')}
        </button>
      </div>

      {error && (
        <div className="mb-4 px-4 py-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700">{error}</div>
      )}

      <div className="rounded-xl border overflow-hidden" style={{ background: 'var(--portal-card-bg)', borderColor: 'var(--portal-border)' }}>
        {loading ? (
          <div className="flex justify-center py-16">
            <div className="w-7 h-7 border-2 border-brand-500 border-t-transparent rounded-full animate-spin" />
          </div>
        ) : groups.length === 0 ? (
          <div className="text-center py-16 text-sm" style={{ color: 'var(--portal-text-muted)' }}>
            {t('adminPage.noGroups')}
          </div>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b" style={{ background: 'var(--portal-main-bg)', borderColor: 'var(--portal-border)' }}>
                <th className="text-left px-4 py-3 text-xs font-semibold uppercase tracking-wider" style={{ color: 'var(--portal-text-muted)' }}>Group</th>
                <th className="text-left px-4 py-3 text-xs font-semibold uppercase tracking-wider" style={{ color: 'var(--portal-text-muted)' }}>Level</th>
                <th className="text-left px-4 py-3 text-xs font-semibold uppercase tracking-wider" style={{ color: 'var(--portal-text-muted)' }}>Access</th>
                <th className="text-right px-4 py-3 text-xs font-semibold uppercase tracking-wider" style={{ color: 'var(--portal-text-muted)' }}>Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-50">
              {groups.map((g) => (
                <tr key={g.id} className="hover:bg-gray-50 transition-colors">
                  <td className="px-4 py-3">
                    <div className="font-medium text-gray-900">{g.name}</div>
                    {g.description && <div className="text-xs text-gray-500 mt-0.5">{g.description}</div>}
                    <div className="text-xs text-gray-400 mt-0.5">{t(LEVEL_DESC_KEY[g.permission_level])}</div>
                  </td>
                  <td className="px-4 py-3">
                    <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${LEVEL_BADGE[g.permission_level]}`}>
                      {t(LEVEL_LABEL_KEY[g.permission_level])}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-sm text-gray-600">
                    <span>{g.tree_count} {g.tree_count === 1 ? 'tree' : 'trees'}</span>
                    <span className="mx-1 text-gray-300">·</span>
                    <span>{g.member_count} {g.member_count === 1 ? 'member' : 'members'}</span>
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex items-center justify-end gap-1">
                      <button
                        onClick={() => setMembersTarget(g)}
                        className="px-2.5 py-1 text-xs font-medium text-brand-600 bg-white border border-brand-200 rounded-lg hover:bg-brand-50 transition-colors"
                      >
                        Manage
                      </button>
                      <button
                        onClick={() => setEditTarget(g)}
                        className="px-2.5 py-1 text-xs font-medium text-gray-600 bg-white border border-gray-200 rounded-lg hover:bg-gray-50 transition-colors"
                      >
                        Edit
                      </button>
                      <button
                        onClick={() => setDeleteTarget(g)}
                        className="px-2.5 py-1 text-xs font-medium text-red-600 bg-white border border-red-200 rounded-lg hover:bg-red-50 transition-colors"
                      >
                        Delete
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {/* Create / Edit modal */}
      {(createOpen || editTarget) && (
        <GroupFormModal
          token={token}
          initial={editTarget}
          onClose={() => { setCreateOpen(false); setEditTarget(null); }}
          onSaved={() => { setCreateOpen(false); setEditTarget(null); fetchGroups(); }}
        />
      )}

      {/* Detail modal */}
      {membersTarget && (
        <GroupDetailModal
          group={membersTarget}
          token={token}
          onClose={() => { setMembersTarget(null); fetchGroups(); }}
        />
      )}

      {/* Delete confirmation */}
      {deleteTarget && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4"
          onClick={(e) => { if (e.target === e.currentTarget) setDeleteTarget(null); }}>
          <div className="bg-white rounded-2xl shadow-xl w-full max-w-sm p-6">
            <h2 className="text-lg font-semibold text-gray-900 mb-1">{t('common.delete')}?</h2>
            <p className="text-sm text-gray-500 mb-4">
              <span className="font-medium text-gray-800">{deleteTarget.name}</span> will be permanently removed.
              All {deleteTarget.member_count} member{deleteTarget.member_count !== 1 ? 's' : ''} will lose access to its{' '}
              {deleteTarget.tree_count} tree{deleteTarget.tree_count !== 1 ? 's' : ''}.
            </p>
            <div className="flex justify-end gap-3">
              <button onClick={() => setDeleteTarget(null)}
                className="px-4 py-2 text-sm text-gray-600 hover:text-gray-900">{t('adminPage.cancel')}</button>
              <button onClick={() => handleDelete(deleteTarget)}
                className="px-4 py-2 bg-red-600 text-white text-sm font-medium rounded-lg hover:bg-red-700">
                {t('common.delete')}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

// ── Group Form Modal (Create / Edit) ───────────────────────────────────────────

function GroupFormModal({
  token, initial, onClose, onSaved,
}: {
  token: string | null;
  initial: PermissionGroup | null;
  onClose: () => void;
  onSaved: () => void;
}) {
  const { t } = useTranslation();
  const [name,  setName]  = useState(initial?.name ?? '');
  const [desc,  setDesc]  = useState(initial?.description ?? '');
  const [level, setLevel] = useState<'VISIBLE'|'READ'|'READ_WRITE'>(initial?.permission_level ?? 'READ');
  const [saving, setSaving] = useState(false);
  const [error,  setError]  = useState('');
  const authHeader: Record<string, string> = token ? { Authorization: `Bearer ${token}` } : {};

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true); setError('');
    try {
      const url = initial
        ? `${API_BASE}/admin/permission-groups/${initial.id}`
        : `${API_BASE}/admin/permission-groups`;
      const res = await fetch(url, {
        method: initial ? 'PATCH' : 'POST',
        headers: { 'Content-Type': 'application/json', ...authHeader },
        credentials: 'include',
        body: JSON.stringify({ name: name.trim(), description: desc.trim() || null, permission_level: level }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error((err as any).detail ?? 'Failed to save');
      }
      onSaved();
    } catch (e) { setError((e as Error).message); }
    finally { setSaving(false); }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4"
      onClick={(e) => { if (e.target === e.currentTarget && !saving) onClose(); }}>
      <div className="bg-white rounded-2xl shadow-xl w-full max-w-sm p-6">
        <h2 className="text-lg font-semibold text-gray-900 mb-4">
          {initial ? t('common.edit') : t('adminPage.createGroup')}
        </h2>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-xs font-medium text-gray-600 mb-1">
              {t('adminPage.groupName')} <span className="text-red-500">*</span>
            </label>
            <input
              type="text" value={name} onChange={(e) => setName(e.target.value)}
              required maxLength={100} autoFocus
              placeholder="e.g. Viewers, Family Editors…"
              className="w-full h-9 px-3 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-brand-500"
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-600 mb-1">{t('adminPage.description')}</label>
            <textarea
              value={desc} onChange={(e) => setDesc(e.target.value)}
              rows={2} maxLength={500} placeholder="Optional description…"
              className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-brand-500 resize-none"
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-600 mb-2">{t('adminPage.permissionLevel')}</label>
            <div className="space-y-2">
              {(['VISIBLE','READ','READ_WRITE'] as const).map((lvl) => (
                <label key={lvl} className={`flex items-start gap-3 p-3 rounded-lg border-2 cursor-pointer transition-colors ${
                  level === lvl ? 'border-brand-500 bg-brand-50' : 'border-gray-200 hover:border-gray-300'
                }`}>
                  <input type="radio" name="level" value={lvl} checked={level === lvl}
                    onChange={() => setLevel(lvl)} className="mt-0.5 accent-brand-500" />
                  <div>
                    <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${LEVEL_BADGE[lvl]}`}>
                      {t(LEVEL_LABEL_KEY[lvl])}
                    </span>
                    <p className="text-xs text-gray-500 mt-1">{t(LEVEL_DESC_KEY[lvl])}</p>
                  </div>
                </label>
              ))}
            </div>
          </div>
          {error && <p className="text-sm text-red-600">{error}</p>}
          <div className="flex justify-end gap-3 pt-1">
            <button type="button" onClick={onClose} disabled={saving}
              className="px-4 py-2 text-sm text-gray-600 hover:text-gray-900 disabled:opacity-50">
              {t('adminPage.cancel')}
            </button>
            <button type="submit" disabled={saving || !name.trim()}
              className="px-4 py-2 bg-brand-500 text-white text-sm font-medium rounded-lg hover:bg-brand-600 disabled:opacity-50">
              {saving ? t('adminPage.saving') : initial ? t('common.save') : t('adminPage.createGroup')}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

// ── Group Detail Modal (Trees + Members) ───────────────────────────────────────

function GroupDetailModal({
  group, token, onClose,
}: { group: PermissionGroup; token: string | null; onClose: () => void; }) {
  const { t } = useTranslation();
  const [groupTrees,   setGroupTrees]   = useState<GroupTree[]>([]);
  const [groupMembers, setGroupMembers] = useState<GroupMember[]>([]);
  const [availTrees,   setAvailTrees]   = useState<TenantTree[]>([]);
  const [availUsers,   setAvailUsers]   = useState<{ id: string; email: string; display: string }[]>([]);
  const [loading, setLoading] = useState(true);
  const [addTreeOpen,   setAddTreeOpen]   = useState(false);
  const [addMemberOpen, setAddMemberOpen] = useState(false);
  const [selTree,   setSelTree]   = useState('');
  const [selUser,   setSelUser]   = useState('');
  const [saving,    setSaving]    = useState(false);
  const [error,     setError]     = useState('');
  const authHeader: Record<string, string> = token ? { Authorization: `Bearer ${token}` } : {};

  async function fetchAll() {
    setLoading(true);
    const [tRes, mRes, atRes, auRes] = await Promise.all([
      fetch(`${API_BASE}/admin/permission-groups/${group.id}/trees`, { headers: authHeader, credentials: 'include' }),
      fetch(`${API_BASE}/admin/permission-groups/${group.id}/members`, { headers: authHeader, credentials: 'include' }),
      fetch(`${API_BASE}/admin/trees`, { headers: authHeader, credentials: 'include' }),
      fetch(`${API_BASE}/admin/users?page_size=200`, { headers: authHeader, credentials: 'include' }),
    ]);
    if (tRes.ok) setGroupTrees(await tRes.json());
    if (mRes.ok) setGroupMembers(await mRes.json());
    if (atRes.ok) setAvailTrees(await atRes.json());
    if (auRes.ok) {
      const d = await auRes.json();
      setAvailUsers((d.items ?? []).map((u: any) => ({
        id: u.id, email: u.email,
        display: [u.given_name, u.family_name].filter(Boolean).join(' ') || u.email,
      })));
    }
    setLoading(false);
  }

  useEffect(() => { fetchAll(); }, []);

  async function handleAddTree(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true); setError('');
    try {
      const res = await fetch(`${API_BASE}/admin/permission-groups/${group.id}/trees`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...authHeader },
        credentials: 'include',
        body: JSON.stringify({ tree_id: selTree }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error((err as any).detail ?? 'Failed to add tree');
      }
      setAddTreeOpen(false); setSelTree('');
      fetchAll();
    } catch (e) { setError((e as Error).message); }
    finally { setSaving(false); }
  }

  async function handleRemoveTree(entryId: string) {
    const entry = groupTrees.find(gt => gt.id === entryId);
    if (!entry) return;
    await fetch(`${API_BASE}/admin/permission-groups/${group.id}/trees/${entry.tree_id}`, {
      method: 'DELETE', headers: authHeader, credentials: 'include',
    });
    fetchAll();
  }

  async function handleAddMember(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true); setError('');
    try {
      const res = await fetch(`${API_BASE}/admin/permission-groups/${group.id}/members`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...authHeader },
        credentials: 'include',
        body: JSON.stringify({ user_id: selUser }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error((err as any).detail ?? 'Failed to add member');
      }
      setAddMemberOpen(false); setSelUser('');
      fetchAll();
    } catch (e) { setError((e as Error).message); }
    finally { setSaving(false); }
  }

  async function handleRemoveMember(memberId: string) {
    await fetch(`${API_BASE}/admin/permission-groups/${group.id}/members/${memberId}`, {
      method: 'DELETE', headers: authHeader, credentials: 'include',
    });
    fetchAll();
  }

  const groupTreeIds   = new Set(groupTrees.map(gt => gt.tree_id));
  const groupMemberIds = new Set(groupMembers.map(m => m.user_id));
  const treesToAdd     = availTrees.filter(tr => !groupTreeIds.has(tr.id));
  const usersToAdd     = availUsers.filter(u => !groupMemberIds.has(u.id));

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4"
      onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}>
      <div className="bg-white rounded-2xl shadow-xl w-full max-w-2xl max-h-[85vh] flex flex-col">
        {/* Header */}
        <div className="flex items-start justify-between px-6 pt-6 pb-4 border-b border-gray-100">
          <div>
            <h2 className="text-lg font-semibold text-gray-900">{group.name}</h2>
            <div className="flex items-center gap-2 mt-1">
              <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${LEVEL_BADGE[group.permission_level]}`}>
                {t(LEVEL_LABEL_KEY[group.permission_level])}
              </span>
              <span className="text-xs text-gray-400">{t(LEVEL_DESC_KEY[group.permission_level])}</span>
            </div>
          </div>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600 text-xl leading-none mt-1">×</button>
        </div>

        {loading ? (
          <div className="flex justify-center py-12">
            <div className="w-7 h-7 border-2 border-brand-500 border-t-transparent rounded-full animate-spin" />
          </div>
        ) : (
          <div className="flex-1 overflow-y-auto min-h-0 px-6 py-4 space-y-6">
            {error && (
              <div className="px-3 py-2 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700">{error}</div>
            )}

            {/* ── Trees section ── */}
            <section>
              <div className="flex items-center justify-between mb-2">
                <h3 className="text-sm font-semibold text-gray-700">{t('adminPage.trees')} ({groupTrees.length})</h3>
                {treesToAdd.length > 0 && !addTreeOpen && (
                  <button onClick={() => { setAddTreeOpen(true); setAddMemberOpen(false); setError(''); }}
                    className="text-xs text-brand-600 font-medium hover:text-brand-700">+ {t('adminPage.addTree')}</button>
                )}
              </div>

              {addTreeOpen && (
                <form onSubmit={handleAddTree} className="flex gap-2 mb-3">
                  <select value={selTree} onChange={(e) => setSelTree(e.target.value)} required
                    className="flex-1 h-9 px-2 text-sm border border-gray-300 rounded-lg bg-white focus:outline-none focus:ring-2 focus:ring-brand-500">
                    <option value="">{t('adminPage.selectTree')}</option>
                    {treesToAdd.map(tr => <option key={tr.id} value={tr.id}>{tr.name}</option>)}
                  </select>
                  <button type="button" onClick={() => { setAddTreeOpen(false); setSelTree(''); setError(''); }}
                    className="px-3 text-sm text-gray-500 hover:text-gray-700">{t('adminPage.cancel')}</button>
                  <button type="submit" disabled={saving || !selTree}
                    className="px-3 py-1.5 bg-brand-500 text-white text-sm font-medium rounded-lg hover:bg-brand-600 disabled:opacity-50">
                    {saving ? '…' : 'Add'}
                  </button>
                </form>
              )}

              {groupTrees.length === 0 ? (
                <p className="text-sm text-gray-400 text-center py-3 border border-dashed border-gray-200 rounded-lg">
                  No trees yet. Add trees for members to access.
                </p>
              ) : (
                <div className="divide-y divide-gray-100 border border-gray-100 rounded-lg overflow-hidden">
                  {groupTrees.map(gt => (
                    <div key={gt.id} className="flex items-center justify-between px-3 py-2 hover:bg-gray-50">
                      <span className="text-sm font-medium text-gray-800">{gt.tree_name}</span>
                      <button onClick={() => handleRemoveTree(gt.id)}
                        className="text-xs text-red-500 hover:text-red-700">{t('common.remove')}</button>
                    </div>
                  ))}
                </div>
              )}
            </section>

            {/* ── Members section ── */}
            <section>
              <div className="flex items-center justify-between mb-2">
                <h3 className="text-sm font-semibold text-gray-700">{t('adminPage.membersLabel')} ({groupMembers.length})</h3>
                {usersToAdd.length > 0 && !addMemberOpen && (
                  <button onClick={() => { setAddMemberOpen(true); setAddTreeOpen(false); setError(''); }}
                    className="text-xs text-brand-600 font-medium hover:text-brand-700">+ {t('adminPage.addMember')}</button>
                )}
              </div>

              {addMemberOpen && (
                <form onSubmit={handleAddMember} className="flex gap-2 mb-3">
                  <select value={selUser} onChange={(e) => setSelUser(e.target.value)} required
                    className="flex-1 h-9 px-2 text-sm border border-gray-300 rounded-lg bg-white focus:outline-none focus:ring-2 focus:ring-brand-500">
                    <option value="">Select user…</option>
                    {usersToAdd.map(u => <option key={u.id} value={u.id}>{u.display} ({u.email})</option>)}
                  </select>
                  <button type="button" onClick={() => { setAddMemberOpen(false); setSelUser(''); setError(''); }}
                    className="px-3 text-sm text-gray-500 hover:text-gray-700">{t('adminPage.cancel')}</button>
                  <button type="submit" disabled={saving || !selUser}
                    className="px-3 py-1.5 bg-brand-500 text-white text-sm font-medium rounded-lg hover:bg-brand-600 disabled:opacity-50">
                    {saving ? '…' : 'Add'}
                  </button>
                </form>
              )}

              {groupMembers.length === 0 ? (
                <p className="text-sm text-gray-400 text-center py-3 border border-dashed border-gray-200 rounded-lg">
                  No members yet. Add users to grant them access to all group trees.
                </p>
              ) : (
                <div className="divide-y divide-gray-100 border border-gray-100 rounded-lg overflow-hidden">
                  {groupMembers.map(m => (
                    <div key={m.id} className="flex items-center justify-between px-3 py-2 hover:bg-gray-50">
                      <div>
                        <div className="text-sm font-medium text-gray-800">{m.user_display_name}</div>
                        <div className="text-xs text-gray-500">{m.user_email}</div>
                      </div>
                      <button onClick={() => handleRemoveMember(m.id)}
                        className="text-xs text-red-500 hover:text-red-700">{t('common.remove')}</button>
                    </div>
                  ))}
                </div>
              )}
            </section>
          </div>
        )}
      </div>
    </div>
  );
}

// ── Subscriptions Panel (Super Admin only) ──────────────────────────────────────

function SubscriptionsPanel({ token }: { token: string | null }) {
  const [subs, setSubs]               = useState<Subscription[]>([]);
  const [loading, setLoading]         = useState(false);
  const [createOpen, setCreateOpen]   = useState(false);
  const [editTarget, setEditTarget]   = useState<Subscription | null>(null);
  const [manageTarget, setManageTarget] = useState<Subscription | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<Subscription | null>(null);
  const [error, setError]             = useState('');

  const authHeader: Record<string, string> = token ? { Authorization: `Bearer ${token}` } : {};

  const fetchSubs = React.useCallback(async () => {
    if (!token) return;
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE}/admin/subscriptions`, { headers: authHeader, credentials: 'include' });
      if (!res.ok) throw new Error('Failed to load subscriptions');
      setSubs(await res.json());
    } catch (e) { setError((e as Error).message); }
    finally { setLoading(false); }
  }, [token]);

  useEffect(() => { fetchSubs(); }, [fetchSubs]);

  async function handleDelete(s: Subscription) {
    await fetch(`${API_BASE}/admin/subscriptions/${s.id}`, {
      method: 'DELETE', headers: authHeader, credentials: 'include',
    });
    setDeleteTarget(null);
    fetchSubs();
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <p className="text-sm text-gray-500">
          Manage Free and Premium subscriptions — each grants its members access to a set of tree filters.
        </p>
        <button
          onClick={() => setCreateOpen(true)}
          className="px-4 py-2 bg-brand-500 text-white text-sm font-medium rounded-lg hover:bg-brand-600 transition-colors"
        >
          + Create subscription
        </button>
      </div>

      {error && (
        <div className="mb-4 px-4 py-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700">{error}</div>
      )}

      <div className="rounded-xl border overflow-hidden" style={{ background: 'var(--portal-card-bg)', borderColor: 'var(--portal-border)' }}>
        {loading ? (
          <div className="flex justify-center py-16">
            <div className="w-7 h-7 border-2 border-brand-500 border-t-transparent rounded-full animate-spin" />
          </div>
        ) : subs.length === 0 ? (
          <div className="text-center py-16 text-sm" style={{ color: 'var(--portal-text-muted)' }}>
            No subscriptions yet.
          </div>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b" style={{ background: 'var(--portal-main-bg)', borderColor: 'var(--portal-border)' }}>
                <th className="text-left px-4 py-3 text-xs font-semibold uppercase tracking-wider" style={{ color: 'var(--portal-text-muted)' }}>Name</th>
                <th className="text-left px-4 py-3 text-xs font-semibold uppercase tracking-wider" style={{ color: 'var(--portal-text-muted)' }}>Tier</th>
                <th className="text-left px-4 py-3 text-xs font-semibold uppercase tracking-wider" style={{ color: 'var(--portal-text-muted)' }}>Entitlements</th>
                <th className="text-left px-4 py-3 text-xs font-semibold uppercase tracking-wider" style={{ color: 'var(--portal-text-muted)' }}>Expires</th>
                <th className="text-right px-4 py-3 text-xs font-semibold uppercase tracking-wider" style={{ color: 'var(--portal-text-muted)' }}>Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-50">
              {subs.map((s) => (
                <tr key={s.id} className="hover:bg-gray-50 transition-colors">
                  <td className="px-4 py-3">
                    <div className="font-medium text-gray-900">{s.name}</div>
                  </td>
                  <td className="px-4 py-3">
                    <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${TIER_BADGE[s.tier]}`}>
                      {TIER_LABEL[s.tier]}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-sm text-gray-600">
                    <span>{s.filter_count} {s.filter_count === 1 ? 'filter' : 'filters'}</span>
                    <span className="mx-1 text-gray-300">·</span>
                    <span>{s.member_count} {s.member_count === 1 ? 'member' : 'members'}</span>
                  </td>
                  <td className="px-4 py-3 text-sm">
                    {!s.expires_at ? (
                      <span className="text-gray-400">—</span>
                    ) : (
                      <div>
                        <div className="text-gray-600">{formatExpiry(s.expires_at)}</div>
                        {s.is_expired ? (
                          <span className="inline-flex items-center px-1.5 py-0.5 mt-0.5 rounded text-[11px] font-medium bg-red-100 text-red-700">
                            Expired
                          </span>
                        ) : new Date(s.expires_at).getTime() - Date.now() < EXPIRING_SOON_MS ? (
                          <span className="inline-flex items-center px-1.5 py-0.5 mt-0.5 rounded text-[11px] font-medium bg-amber-100 text-amber-700">
                            Expiring soon
                          </span>
                        ) : null}
                      </div>
                    )}
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex items-center justify-end gap-1">
                      <button
                        onClick={() => setManageTarget(s)}
                        className="px-2.5 py-1 text-xs font-medium text-brand-600 bg-white border border-brand-200 rounded-lg hover:bg-brand-50 transition-colors"
                      >
                        Manage
                      </button>
                      <button
                        onClick={() => setEditTarget(s)}
                        className="px-2.5 py-1 text-xs font-medium text-gray-600 bg-white border border-gray-200 rounded-lg hover:bg-gray-50 transition-colors"
                      >
                        Edit
                      </button>
                      <button
                        onClick={() => setDeleteTarget(s)}
                        className="px-2.5 py-1 text-xs font-medium text-red-600 bg-white border border-red-200 rounded-lg hover:bg-red-50 transition-colors"
                      >
                        Delete
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {(createOpen || editTarget) && (
        <SubscriptionFormModal
          token={token}
          initial={editTarget}
          onClose={() => { setCreateOpen(false); setEditTarget(null); }}
          onSaved={() => { setCreateOpen(false); setEditTarget(null); fetchSubs(); }}
        />
      )}

      {manageTarget && (
        <SubscriptionDetailModal
          subscription={manageTarget}
          token={token}
          onClose={() => { setManageTarget(null); fetchSubs(); }}
        />
      )}

      {deleteTarget && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4"
          onClick={(e) => { if (e.target === e.currentTarget) setDeleteTarget(null); }}>
          <div className="bg-white rounded-2xl shadow-xl w-full max-w-sm p-6">
            <h2 className="text-lg font-semibold text-gray-900 mb-1">Delete subscription?</h2>
            <p className="text-sm text-gray-500 mb-4">
              <span className="font-medium text-gray-800">{deleteTarget.name}</span> will be permanently removed.
              All {deleteTarget.member_count} member{deleteTarget.member_count !== 1 ? 's' : ''} will lose access to its{' '}
              {deleteTarget.filter_count} filter{deleteTarget.filter_count !== 1 ? 's' : ''}.
            </p>
            <div className="flex justify-end gap-3">
              <button onClick={() => setDeleteTarget(null)}
                className="px-4 py-2 text-sm text-gray-600 hover:text-gray-900">Cancel</button>
              <button onClick={() => handleDelete(deleteTarget)}
                className="px-4 py-2 bg-red-600 text-white text-sm font-medium rounded-lg hover:bg-red-700">
                Delete
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

// ── Subscription Form Modal (Create / Edit) ─────────────────────────────────────

function SubscriptionFormModal({
  token, initial, onClose, onSaved,
}: {
  token: string | null;
  initial: Subscription | null;
  onClose: () => void;
  onSaved: () => void;
}) {
  const [name, setName]   = useState(initial?.name ?? '');
  const [tier, setTier]   = useState<'FREE' | 'PREMIUM_INDIVIDUAL' | 'PREMIUM_TEAM'>(initial?.tier ?? 'FREE');
  const [saving, setSaving] = useState(false);
  const [error, setError]   = useState('');

  const [hasExpiry, setHasExpiry] = useState(!!initial?.expires_at);
  const [expiryMode, setExpiryMode] = useState<'date' | 'duration'>('date');
  const [expiryDateTime, setExpiryDateTime] = useState(
    initial?.expires_at ? toDatetimeLocalValue(initial.expires_at) : '',
  );
  const [durationValue, setDurationValue] = useState(24);
  const [durationUnit, setDurationUnit] = useState<'Hours' | 'Days'>('Hours');

  const authHeader: Record<string, string> = token ? { Authorization: `Bearer ${token}` } : {};

  function computeExpiresAt(): string | null {
    if (!hasExpiry) return null;
    if (expiryMode === 'date') {
      return expiryDateTime ? new Date(expiryDateTime).toISOString() : null;
    }
    const ms = durationValue * (durationUnit === 'Hours' ? 3_600_000 : 86_400_000);
    return new Date(Date.now() + ms).toISOString();
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true); setError('');
    try {
      const url = initial
        ? `${API_BASE}/admin/subscriptions/${initial.id}`
        : `${API_BASE}/admin/subscriptions`;
      const res = await fetch(url, {
        method: initial ? 'PATCH' : 'POST',
        headers: { 'Content-Type': 'application/json', ...authHeader },
        credentials: 'include',
        body: JSON.stringify({ name: name.trim(), tier, expires_at: computeExpiresAt() }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error((err as any).detail ?? 'Failed to save');
      }
      onSaved();
    } catch (e) { setError((e as Error).message); }
    finally { setSaving(false); }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4"
      onClick={(e) => { if (e.target === e.currentTarget && !saving) onClose(); }}>
      <div className="bg-white rounded-2xl shadow-xl w-full max-w-sm p-6">
        <h2 className="text-lg font-semibold text-gray-900 mb-4">
          {initial ? 'Edit subscription' : 'Create subscription'}
        </h2>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-xs font-medium text-gray-600 mb-1">
              Name <span className="text-red-500">*</span>
            </label>
            <input
              type="text" value={name} onChange={(e) => setName(e.target.value)}
              required maxLength={100} autoFocus
              placeholder="e.g. Premium Family Plan…"
              className="w-full h-9 px-3 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-brand-500"
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-600 mb-2">Tier</label>
            <div className="space-y-2">
              {(['FREE', 'PREMIUM_INDIVIDUAL', 'PREMIUM_TEAM'] as const).map((tr) => (
                <label key={tr} className={`flex items-start gap-3 p-3 rounded-lg border-2 cursor-pointer transition-colors ${
                  tier === tr ? 'border-brand-500 bg-brand-50' : 'border-gray-200 hover:border-gray-300'
                }`}>
                  <input type="radio" name="tier" value={tr} checked={tier === tr}
                    onChange={() => setTier(tr)} className="mt-0.5 accent-brand-500" />
                  <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${TIER_BADGE[tr]}`}>
                    {TIER_LABEL[tr]}
                  </span>
                </label>
              ))}
            </div>
          </div>
          <div>
            <label className="flex items-center gap-2 text-xs font-medium text-gray-600 mb-2">
              <input type="checkbox" checked={hasExpiry} onChange={(e) => setHasExpiry(e.target.checked)}
                className="accent-brand-500" />
              This subscription expires (promotional / time-limited)
            </label>
            {hasExpiry && (
              <div className="pl-6 space-y-2">
                <div className="flex gap-4">
                  <label className="flex items-center gap-1.5 text-xs text-gray-600">
                    <input type="radio" name="expiryMode" checked={expiryMode === 'date'}
                      onChange={() => setExpiryMode('date')} className="accent-brand-500" />
                    On a specific date
                  </label>
                  <label className="flex items-center gap-1.5 text-xs text-gray-600">
                    <input type="radio" name="expiryMode" checked={expiryMode === 'duration'}
                      onChange={() => setExpiryMode('duration')} className="accent-brand-500" />
                    In…
                  </label>
                </div>
                {expiryMode === 'date' ? (
                  <input
                    type="datetime-local" value={expiryDateTime}
                    onChange={(e) => setExpiryDateTime(e.target.value)}
                    required={hasExpiry}
                    className="w-full h-9 px-3 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-brand-500"
                  />
                ) : (
                  <div className="flex gap-2">
                    <input
                      type="number" min={1} value={durationValue}
                      onChange={(e) => setDurationValue(Math.max(1, Number(e.target.value)))}
                      className="w-24 h-9 px-3 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-brand-500"
                    />
                    <select value={durationUnit} onChange={(e) => setDurationUnit(e.target.value as 'Hours' | 'Days')}
                      className="h-9 px-2 text-sm border border-gray-300 rounded-lg bg-white focus:outline-none focus:ring-2 focus:ring-brand-500">
                      <option value="Hours">Hours</option>
                      <option value="Days">Days</option>
                    </select>
                  </div>
                )}
              </div>
            )}
          </div>
          {error && <p className="text-sm text-red-600">{error}</p>}
          <div className="flex justify-end gap-3 pt-1">
            <button type="button" onClick={onClose} disabled={saving}
              className="px-4 py-2 text-sm text-gray-600 hover:text-gray-900 disabled:opacity-50">
              Cancel
            </button>
            <button
              type="submit"
              disabled={saving || !name.trim() || (hasExpiry && expiryMode === 'date' && !expiryDateTime)}
              className="px-4 py-2 bg-brand-500 text-white text-sm font-medium rounded-lg hover:bg-brand-600 disabled:opacity-50">
              {saving ? 'Saving…' : initial ? 'Save' : 'Create subscription'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

// ── Subscription Detail Modal (Filters + Members) ───────────────────────────────

function SubscriptionDetailModal({
  subscription, token, onClose,
}: { subscription: Subscription; token: string | null; onClose: () => void; }) {
  const [subFilters, setSubFilters]     = useState<SubscriptionFilter[]>([]);
  const [subMembers, setSubMembers]     = useState<SubscriptionMember[]>([]);
  const [availFilters, setAvailFilters] = useState<AvailableFilter[]>([]);
  const [availUsers, setAvailUsers]     = useState<{ id: string; email: string; display: string }[]>([]);
  const [loading, setLoading] = useState(true);
  const [addFilterOpen, setAddFilterOpen] = useState(false);
  const [addMemberOpen, setAddMemberOpen] = useState(false);
  const [selFilter, setSelFilter] = useState('');
  const [selUser, setSelUser]     = useState('');
  const [saving, setSaving]       = useState(false);
  const [error, setError]         = useState('');
  const authHeader: Record<string, string> = token ? { Authorization: `Bearer ${token}` } : {};

  async function fetchAll() {
    setLoading(true);
    const [fRes, mRes, afRes, auRes] = await Promise.all([
      fetch(`${API_BASE}/admin/subscriptions/${subscription.id}/filters`, { headers: authHeader, credentials: 'include' }),
      fetch(`${API_BASE}/admin/subscriptions/${subscription.id}/members`, { headers: authHeader, credentials: 'include' }),
      fetch(`${API_BASE}/admin/subscriptions/available-filters`, { headers: authHeader, credentials: 'include' }),
      fetch(`${API_BASE}/admin/users?page_size=200`, { headers: authHeader, credentials: 'include' }),
    ]);
    if (fRes.ok) setSubFilters(await fRes.json());
    if (mRes.ok) setSubMembers(await mRes.json());
    if (afRes.ok) setAvailFilters(await afRes.json());
    if (auRes.ok) {
      const d = await auRes.json();
      setAvailUsers((d.items ?? []).map((u: any) => ({
        id: u.id, email: u.email,
        display: [u.given_name, u.family_name].filter(Boolean).join(' ') || u.email,
      })));
    }
    setLoading(false);
  }

  useEffect(() => { fetchAll(); }, []);

  async function handleAddFilter(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true); setError('');
    try {
      const res = await fetch(`${API_BASE}/admin/subscriptions/${subscription.id}/filters`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...authHeader },
        credentials: 'include',
        body: JSON.stringify({ filter_key: selFilter }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error((err as any).detail ?? 'Failed to add filter');
      }
      setAddFilterOpen(false); setSelFilter('');
      fetchAll();
    } catch (e) { setError((e as Error).message); }
    finally { setSaving(false); }
  }

  async function handleRemoveFilter(entry: SubscriptionFilter) {
    await fetch(`${API_BASE}/admin/subscriptions/${subscription.id}/filters/${entry.filter_key}`, {
      method: 'DELETE', headers: authHeader, credentials: 'include',
    });
    fetchAll();
  }

  async function handleAddMember(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true); setError('');
    try {
      const res = await fetch(`${API_BASE}/admin/subscriptions/${subscription.id}/members`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...authHeader },
        credentials: 'include',
        body: JSON.stringify({ user_id: selUser }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error((err as any).detail ?? 'Failed to add member');
      }
      setAddMemberOpen(false); setSelUser('');
      fetchAll();
    } catch (e) { setError((e as Error).message); }
    finally { setSaving(false); }
  }

  async function handleRemoveMember(memberId: string) {
    await fetch(`${API_BASE}/admin/subscriptions/${subscription.id}/members/${memberId}`, {
      method: 'DELETE', headers: authHeader, credentials: 'include',
    });
    fetchAll();
  }

  const subFilterKeys = new Set(subFilters.map((f) => f.filter_key));
  const subMemberIds  = new Set(subMembers.map((m) => m.user_id));
  const filtersToAdd  = availFilters.filter((f) => !subFilterKeys.has(f.key));
  const usersToAdd     = availUsers.filter((u) => !subMemberIds.has(u.id));

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4"
      onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}>
      <div className="bg-white rounded-2xl shadow-xl w-full max-w-2xl max-h-[85vh] flex flex-col">
        <div className="flex items-start justify-between px-6 pt-6 pb-4 border-b border-gray-100">
          <div>
            <h2 className="text-lg font-semibold text-gray-900">{subscription.name}</h2>
            <div className="flex items-center gap-2 mt-1">
              <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${TIER_BADGE[subscription.tier]}`}>
                {TIER_LABEL[subscription.tier]}
              </span>
              {subscription.expires_at && (
                <span className={`text-xs ${subscription.is_expired ? 'text-red-600 font-medium' : 'text-gray-500'}`}>
                  {subscription.is_expired ? 'Expired ' : 'Expires '}
                  {formatExpiry(subscription.expires_at)}
                </span>
              )}
            </div>
          </div>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600 text-xl leading-none mt-1">×</button>
        </div>

        {loading ? (
          <div className="flex justify-center py-12">
            <div className="w-7 h-7 border-2 border-brand-500 border-t-transparent rounded-full animate-spin" />
          </div>
        ) : (
          <div className="flex-1 overflow-y-auto min-h-0 px-6 py-4 space-y-6">
            {error && (
              <div className="px-3 py-2 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700">{error}</div>
            )}

            {/* ── Filters section ── */}
            <section>
              <div className="flex items-center justify-between mb-2">
                <h3 className="text-sm font-semibold text-gray-700">Filters ({subFilters.length})</h3>
                {filtersToAdd.length > 0 && !addFilterOpen && (
                  <button onClick={() => { setAddFilterOpen(true); setAddMemberOpen(false); setError(''); }}
                    className="text-xs text-brand-600 font-medium hover:text-brand-700">+ Add filter</button>
                )}
              </div>

              {addFilterOpen && (
                <form onSubmit={handleAddFilter} className="flex gap-2 mb-3">
                  <select value={selFilter} onChange={(e) => setSelFilter(e.target.value)} required
                    className="flex-1 h-9 px-2 text-sm border border-gray-300 rounded-lg bg-white focus:outline-none focus:ring-2 focus:ring-brand-500">
                    <option value="">Select filter…</option>
                    {filtersToAdd.map((f) => <option key={f.key} value={f.key}>{f.label}</option>)}
                  </select>
                  <button type="button" onClick={() => { setAddFilterOpen(false); setSelFilter(''); setError(''); }}
                    className="px-3 text-sm text-gray-500 hover:text-gray-700">Cancel</button>
                  <button type="submit" disabled={saving || !selFilter}
                    className="px-3 py-1.5 bg-brand-500 text-white text-sm font-medium rounded-lg hover:bg-brand-600 disabled:opacity-50">
                    {saving ? '…' : 'Add'}
                  </button>
                </form>
              )}

              {subFilters.length === 0 ? (
                <p className="text-sm text-gray-400 text-center py-3 border border-dashed border-gray-200 rounded-lg">
                  No filters yet. Add filters for members to unlock.
                </p>
              ) : (
                <div className="divide-y divide-gray-100 border border-gray-100 rounded-lg overflow-hidden">
                  {subFilters.map((f) => (
                    <div key={f.id} className="flex items-center justify-between px-3 py-2 hover:bg-gray-50">
                      <span className="text-sm font-medium text-gray-800">
                        {availFilters.find((af) => af.key === f.filter_key)?.label ?? f.filter_key}
                      </span>
                      <button onClick={() => handleRemoveFilter(f)}
                        className="text-xs text-red-500 hover:text-red-700">Remove</button>
                    </div>
                  ))}
                </div>
              )}
            </section>

            {/* ── Members section ── */}
            <section>
              <div className="flex items-center justify-between mb-2">
                <h3 className="text-sm font-semibold text-gray-700">Members ({subMembers.length})</h3>
                {usersToAdd.length > 0 && !addMemberOpen && (
                  <button onClick={() => { setAddMemberOpen(true); setAddFilterOpen(false); setError(''); }}
                    className="text-xs text-brand-600 font-medium hover:text-brand-700">+ Add member</button>
                )}
              </div>

              {addMemberOpen && (
                <form onSubmit={handleAddMember} className="flex gap-2 mb-3">
                  <select value={selUser} onChange={(e) => setSelUser(e.target.value)} required
                    className="flex-1 h-9 px-2 text-sm border border-gray-300 rounded-lg bg-white focus:outline-none focus:ring-2 focus:ring-brand-500">
                    <option value="">Select user…</option>
                    {usersToAdd.map((u) => <option key={u.id} value={u.id}>{u.display} ({u.email})</option>)}
                  </select>
                  <button type="button" onClick={() => { setAddMemberOpen(false); setSelUser(''); setError(''); }}
                    className="px-3 text-sm text-gray-500 hover:text-gray-700">Cancel</button>
                  <button type="submit" disabled={saving || !selUser}
                    className="px-3 py-1.5 bg-brand-500 text-white text-sm font-medium rounded-lg hover:bg-brand-600 disabled:opacity-50">
                    {saving ? '…' : 'Add'}
                  </button>
                </form>
              )}

              {subMembers.length === 0 ? (
                <p className="text-sm text-gray-400 text-center py-3 border border-dashed border-gray-200 rounded-lg">
                  No members yet. Add users to grant them these filters.
                </p>
              ) : (
                <div className="divide-y divide-gray-100 border border-gray-100 rounded-lg overflow-hidden">
                  {subMembers.map((m) => (
                    <div key={m.id} className="flex items-center justify-between px-3 py-2 hover:bg-gray-50">
                      <div>
                        <div className="text-sm font-medium text-gray-800">{m.user_display_name}</div>
                        <div className="text-xs text-gray-500">{m.user_email}</div>
                      </div>
                      <button onClick={() => handleRemoveMember(m.id)}
                        className="text-xs text-red-500 hover:text-red-700">Remove</button>
                    </div>
                  ))}
                </div>
              )}
            </section>
          </div>
        )}
      </div>
    </div>
  );
}
