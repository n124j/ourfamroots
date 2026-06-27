import React, { useEffect, useRef, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { useAuthStore } from '@store/auth.store';
import { SEO } from '@shared/components/SEO';
import { UserAvatar } from '@shared/components/UserAvatar';

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? '/api/v1';

interface TreeSummary {
  id: string;
  name: string;
  description: string | null;
  cover_emoji: string | null;
  cover_image_url: string | null;
  role: string;
  person_count: number;
  member_count: number;
  link_sharing: string;
  share_token: string | null;
  is_pinned: boolean;
  is_searchable: boolean;
}

const TREE_COVER_PRESETS = ['🌳','🌲','🌴','🌿','🌸','🏡','📜','⛩️','🎋','🧬','🗺️','📖'];
const DEFAULT_COVER = '🌳';

const DASHBOARD_PAGE_KEY = 'ourfamroots_dashboard_page';

function getStoredPage(): number {
  const raw = sessionStorage.getItem(DASHBOARD_PAGE_KEY);
  const n = raw ? parseInt(raw, 10) : 1;
  return Number.isFinite(n) && n > 0 ? n : 1;
}

const ROLE_BADGE: Record<string, string> = {
  OWNER:  'bg-brand-100 text-brand-700',
  ADMIN:  'bg-purple-100 text-purple-700',
  EDITOR: 'bg-green-100  text-green-700',
  VIEWER: 'bg-gray-100   text-gray-600',
};

// ── Share types ────────────────────────────────────────────────────────────

interface TreeMember {
  id: string;
  user_id: string;
  role: string;
  email: string;
  display_name: string;
  joined_at: string | null;
}

interface PendingInvitation {
  id: string;
  invitee_email: string;
  role: string;
  status: string;
  expires_at: string;
}

interface TenantUser {
  id: string;
  email: string;
  display_name: string;
}

const MEMBER_ROLE_BADGE: Record<string, string> = {
  OWNER:  'bg-brand-100 text-brand-700',
  ADMIN:  'bg-purple-100 text-purple-700',
  EDITOR: 'bg-green-100 text-green-700',
  VIEWER: 'bg-gray-100 text-gray-600',
};

// ── Tree card ──────────────────────────────────────────────────────────────

interface TreeCardProps {
  tree: TreeSummary;
  onEdit: (tree: TreeSummary) => void;
  onDelete: (tree: TreeSummary) => void;
  onShare: (tree: TreeSummary) => void;
  onTogglePin: (tree: TreeSummary) => void;
}

const PinIcon = ({ filled }: { filled: boolean }) => (
  <svg width="14" height="14" viewBox="0 0 16 16" fill={filled ? 'currentColor' : 'none'} stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round">
    <path d="M5.5 1.5h5l-.5 4.5 2 2v1.5h-4v4l-.5 1-.5-1v-4h-4V8l2-2z" />
  </svg>
);

function TreeCard({ tree, onEdit, onDelete, onShare, onTogglePin }: TreeCardProps) {
  const { t } = useTranslation();
  const [menuOpen, setMenuOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);

  const canEdit = tree.role === 'OWNER' || tree.role === 'ADMIN';

  useEffect(() => {
    if (!menuOpen) return;
    function handle(e: MouseEvent) {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setMenuOpen(false);
      }
    }
    document.addEventListener('mousedown', handle);
    return () => document.removeEventListener('mousedown', handle);
  }, [menuOpen]);

  return (
    <div className="relative rounded-xl border hover:border-brand-300 hover:shadow-sm transition-all group"
      style={{ background: 'var(--portal-card-bg)', borderColor: 'var(--portal-border)' }}>
      <button
        onClick={(e) => { e.preventDefault(); e.stopPropagation(); onTogglePin(tree); }}
        title={tree.is_pinned ? 'Unpin from top' : 'Pin to top'}
        style={!tree.is_pinned ? { background: 'var(--portal-card-bg)', borderColor: 'var(--portal-border)' } : undefined}
        className={`absolute -top-2.5 left-1/2 -translate-x-1/2 z-10 w-7 h-7 flex items-center justify-center rounded-full border shadow-sm transition-colors ${
          tree.is_pinned
            ? 'text-brand-600 bg-brand-50 border-brand-200 hover:bg-brand-100'
            : 'text-gray-300 hover:text-gray-500 hover:bg-gray-100 sm:opacity-0 sm:group-hover:opacity-100 focus:opacity-100'
        }`}
      >
        <PinIcon filled={tree.is_pinned} />
      </button>
      <Link to={`/trees/${tree.id}`} className="block p-6">
        <div className="flex items-start justify-between mb-4">
          {tree.cover_image_url ? (
            <img
              src={tree.cover_image_url}
              alt=""
              className="w-12 h-12 rounded-xl object-cover flex-shrink-0"
            />
          ) : (
            <div className="text-3xl">{tree.cover_emoji || DEFAULT_COVER}</div>
          )}
          <div className="flex items-center gap-1.5">
            {tree.is_searchable && (
              <span
                className="w-6 h-6 flex items-center justify-center rounded-full bg-amber-50 border border-amber-200 text-amber-600"
                title="Public &middot; Searchable by other users"
              >
                <svg width="14" height="14" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round">
                  <circle cx="8" cy="8" r="5.5" />
                  <ellipse cx="8" cy="8" rx="2.2" ry="5.5" />
                  <line x1="2.5" y1="6" x2="13.5" y2="6" />
                  <line x1="2.5" y1="10" x2="13.5" y2="10" />
                </svg>
              </span>
            )}
            <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${ROLE_BADGE[tree.role] ?? ROLE_BADGE.VIEWER}`}>
              {tree.role.charAt(0) + tree.role.slice(1).toLowerCase()}
            </span>
          </div>
        </div>

        <h2 className="font-semibold group-hover:text-brand-600 transition-colors truncate" style={{ color: 'var(--portal-text-primary)' }}>
          {tree.name}
        </h2>
        {tree.description && (
          <p className="text-sm text-gray-500 mt-1 line-clamp-2">{tree.description}</p>
        )}

        <div className="flex gap-4 mt-4 pt-4 border-t border-gray-100 text-xs text-gray-500">
          <span><span className="font-semibold text-gray-700">{tree.person_count}</span> {t('common.people')}</span>
          <span><span className="font-semibold text-gray-700">{tree.member_count}</span> {tree.member_count === 1 ? t('common.member') : t('common.members')}</span>
        </div>
      </Link>

      {/* Actions menu — OWNER or ADMIN */}
      {canEdit && (
        <div className="absolute bottom-3 right-3" ref={menuRef}>
          <button
            onClick={(e) => { e.preventDefault(); setMenuOpen((v) => !v); }}
            className="w-7 h-7 flex items-center justify-center rounded-lg text-gray-400 hover:text-gray-700 hover:bg-gray-100 transition-colors sm:opacity-0 sm:group-hover:opacity-100 focus:opacity-100"
            title="Tree options"
          >
            ⋯
          </button>
          {menuOpen && (
            <div className="absolute right-0 bottom-full mb-1 z-20 w-44 rounded-xl border shadow-lg py-1"
              style={{ background: 'var(--portal-card-bg)', borderColor: 'var(--portal-border)' }}>
              <button
                onClick={(e) => { e.preventDefault(); setMenuOpen(false); onShare(tree); }}
                className="w-full text-left px-4 py-2 text-sm text-gray-700 hover:bg-gray-50 transition-colors"
              >
                {t('dashboard.shareTree')}
              </button>
              <button
                onClick={(e) => { e.preventDefault(); setMenuOpen(false); onEdit(tree); }}
                className="w-full text-left px-4 py-2 text-sm text-gray-700 hover:bg-gray-50 transition-colors"
              >
                {t('dashboard.editTree')}
              </button>
              {tree.role === 'OWNER' && (
                <button
                  onClick={(e) => { e.preventDefault(); setMenuOpen(false); onDelete(tree); }}
                  className="w-full text-left px-4 py-2 text-sm text-red-600 hover:bg-red-50 transition-colors"
                >
                  {t('dashboard.deleteTree')}
                </button>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ── Page ───────────────────────────────────────────────────────────────────

export default function DashboardPage() {
  const { t } = useTranslation();
  const accessToken = useAuthStore((s) => s.accessToken);
  const user        = useAuthStore((s) => s.user);
  const navigate    = useNavigate();

  const [trees,   setTrees]   = useState<TreeSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error,   setError]   = useState('');
  const [page,    setPage]    = useState(getStoredPage);
  const [search,  setSearch]  = useState('');

  function goToPage(p: number) {
    setPage(p);
    sessionStorage.setItem(DASHBOARD_PAGE_KEY, String(p));
  }

  function handleSearchChange(value: string) {
    setSearch(value);
    goToPage(1);
  }

  const PAGE_SIZE   = 16;
  const query = search.trim().toLowerCase();
  const matchingTrees = query
    ? trees.filter((t) =>
        t.name.toLowerCase().includes(query) ||
        (t.description ?? '').toLowerCase().includes(query)
      )
    : trees;
  const sortedTrees  = [...matchingTrees].sort((a, b) => Number(b.is_pinned) - Number(a.is_pinned));
  const totalPages  = Math.max(1, Math.ceil(sortedTrees.length / PAGE_SIZE));
  const visibleTrees = sortedTrees.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE);

  // Import .frt
  const importInputRef             = useRef<HTMLInputElement>(null);
  const [importing, setImporting]  = useState(false);
  const [importError, setImportError] = useState('');

  async function handleImportFile(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    setImporting(true);
    setImportError('');
    try {
      let tree_id: string;

      if (file.name.endsWith('.zip')) {
        // ZIP import — send as multipart/form-data
        const form = new FormData();
        form.append('file', file);
        const res = await fetch(`${API_BASE}/trees/import-zip`, {
          method: 'POST',
          headers: accessToken ? { Authorization: `Bearer ${accessToken}` } : {},
          credentials: 'include',
          body: form,
        });
        if (!res.ok) {
          const err = await res.json().catch(() => ({}));
          throw new Error((err as any).detail ?? 'Import failed');
        }
        ({ tree_id } = await res.json());
      } else {
        // Plain .frt import — send as JSON
        const text = await file.text();
        const data = JSON.parse(text);
        if (!data.frt_version || !data.tree_name) throw new Error('Invalid .frt file format');
        const res = await fetch(`${API_BASE}/trees/import`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', ...(accessToken ? { Authorization: `Bearer ${accessToken}` } : {}) },
          credentials: 'include',
          body: JSON.stringify(data),
        });
        if (!res.ok) {
          const err = await res.json().catch(() => ({}));
          throw new Error((err as any).detail ?? 'Import failed');
        }
        ({ tree_id } = await res.json());
      }

      navigate(`/trees/${tree_id}`);
    } catch (err) {
      setImportError((err as Error).message);
    } finally {
      setImporting(false);
      if (importInputRef.current) importInputRef.current.value = '';
    }
  }

  // Create tree modal
  const [modalOpen,   setModalOpen]   = useState(false);
  const [newName,     setNewName]     = useState('');
  const [newDesc,     setNewDesc]     = useState('');
  const [creating,    setCreating]    = useState(false);
  const [createError, setCreateError] = useState('');

  // Edit tree modal
  const [editTarget,        setEditTarget]        = useState<TreeSummary | null>(null);
  const [editName,          setEditName]          = useState('');
  const [editDesc,          setEditDesc]          = useState('');
  const [editCoverEmoji,    setEditCoverEmoji]    = useState('');
  const [editCoverImageUrl, setEditCoverImageUrl] = useState<string | null>(null);
  const [editing,           setEditing]           = useState(false);
  const [editError,         setEditError]         = useState('');
  const [uploadingPhoto,    setUploadingPhoto]    = useState(false);
  const [photoError,        setPhotoError]        = useState('');
  const photoInputRef = useRef<HTMLInputElement>(null);

  function openEdit(tree: TreeSummary) {
    setEditTarget(tree);
    setEditName(tree.name);
    setEditDesc(tree.description ?? '');
    setEditCoverEmoji(tree.cover_emoji || DEFAULT_COVER);
    setEditCoverImageUrl(tree.cover_image_url);
    setEditError('');
    setPhotoError('');
  }

  async function handleTreePhotoChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file || !editTarget) return;
    setUploadingPhoto(true);
    setPhotoError('');
    try {
      const form = new FormData();
      form.append('file', file);
      const res = await fetch(`${API_BASE}/trees/${editTarget.id}/photo`, {
        method: 'POST',
        headers: accessToken ? { Authorization: `Bearer ${accessToken}` } : {},
        credentials: 'include',
        body: form,
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error((err as any).detail ?? 'Upload failed');
      }
      const { cover_image_url } = await res.json();
      setEditCoverImageUrl(cover_image_url);
      setTrees((prev) => prev.map((t) => t.id === editTarget.id ? { ...t, cover_image_url } : t));
    } catch (err) {
      setPhotoError((err as Error).message);
    } finally {
      setUploadingPhoto(false);
      if (photoInputRef.current) photoInputRef.current.value = '';
    }
  }

  async function handleRemoveTreePhoto() {
    if (!editTarget) return;
    setUploadingPhoto(true);
    setPhotoError('');
    try {
      await fetch(`${API_BASE}/trees/${editTarget.id}/photo`, {
        method: 'DELETE',
        headers: accessToken ? { Authorization: `Bearer ${accessToken}` } : {},
        credentials: 'include',
      });
      setEditCoverImageUrl(null);
      setTrees((prev) => prev.map((t) => t.id === editTarget.id ? { ...t, cover_image_url: null } : t));
    } catch {
      setPhotoError('Failed to remove photo');
    } finally {
      setUploadingPhoto(false);
    }
  }

  async function handleEditSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!editTarget) return;
    setEditing(true);
    setEditError('');
    try {
      const res = await fetch(`${API_BASE}/trees/${editTarget.id}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json', ...(accessToken ? { Authorization: `Bearer ${accessToken}` } : {}) },
        credentials: 'include',
        body: JSON.stringify({ name: editName.trim(), description: editDesc.trim() || null, cover_emoji: editCoverEmoji || null }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error((err as any).detail ?? 'Failed to update tree');
      }
      const updated = await res.json();
      setTrees((prev) => prev.map((t) => t.id === editTarget.id
        ? { ...t, name: updated.name, description: updated.description, cover_emoji: updated.cover_emoji, cover_image_url: updated.cover_image_url ?? t.cover_image_url }
        : t
      ));
      setEditTarget(null);
    } catch (err) {
      setEditError((err as Error).message);
    } finally {
      setEditing(false);
    }
  }

  // Share tree modal
  const [shareTarget, setShareTarget] = useState<TreeSummary | null>(null);

  // Delete tree confirmation
  const [deleteTarget, setDeleteTarget] = useState<TreeSummary | null>(null);
  const [deleting,     setDeleting]     = useState(false);
  const [deleteError,  setDeleteError]  = useState('');

  useEffect(() => {
    if (!accessToken) return;
    fetch(`${API_BASE}/trees`, {
      headers: { Authorization: `Bearer ${accessToken}` },
      credentials: 'include',
    })
      .then((r) => {
        if (!r.ok) throw new Error('Failed to load trees');
        return r.json();
      })
      .then((data) => {
        setTrees(data);
        // Clamp the restored page in case the tree count has shrunk since last visit
        const tp = Math.max(1, Math.ceil(data.length / PAGE_SIZE));
        setPage((p) => Math.min(Math.max(p, 1), tp));
      })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [accessToken]);

  function openModal() {
    setNewName('');
    setNewDesc('');
    setCreateError('');
    setModalOpen(true);
  }

  async function handleCreateTree(e: React.FormEvent) {
    e.preventDefault();
    if (!newName.trim()) return;
    setCreating(true);
    setCreateError('');
    try {
      const res = await fetch(`${API_BASE}/trees`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${accessToken}` },
        credentials: 'include',
        body: JSON.stringify({ name: newName.trim(), description: newDesc.trim() || null }),
      });
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error((data as any).detail ?? 'Failed to create tree');
      }
      const tree: TreeSummary = await res.json();
      setTrees((prev) => [tree, ...prev]);
      goToPage(1);
      setModalOpen(false);
    } catch (err: any) {
      setCreateError(err.message);
    } finally {
      setCreating(false);
    }
  }

  async function handleTogglePin(tree: TreeSummary) {
    const pinning = !tree.is_pinned;
    setTrees((prev) => prev.map((t) => t.id === tree.id ? { ...t, is_pinned: pinning } : t));
    try {
      const res = await fetch(`${API_BASE}/trees/${tree.id}/pin`, {
        method: pinning ? 'POST' : 'DELETE',
        headers: accessToken ? { Authorization: `Bearer ${accessToken}` } : {},
        credentials: 'include',
      });
      if (!res.ok) throw new Error('Failed to update pin');
    } catch {
      setTrees((prev) => prev.map((t) => t.id === tree.id ? { ...t, is_pinned: !pinning } : t));
    }
  }

  async function handleDeleteTree() {
    if (!deleteTarget) return;
    setDeleting(true);
    setDeleteError('');
    try {
      const res = await fetch(`${API_BASE}/trees/${deleteTarget.id}`, {
        method: 'DELETE',
        headers: { Authorization: `Bearer ${accessToken}` },
        credentials: 'include',
      });
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error((data as any).detail ?? 'Failed to delete tree');
      }
      setTrees((prev) => prev.filter((t) => t.id !== deleteTarget.id));
      setDeleteTarget(null);
    } catch (err: any) {
      setDeleteError(err.message);
    } finally {
      setDeleting(false);
    }
  }

  return (
    <div className="p-4 md:p-8 max-w-7xl mx-auto">
      <SEO
        title="Dashboard"
        description="Manage your family trees, collaborate with members, and explore your ancestry on OurFamRoots."
        noIndex
      />
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-6 md:mb-8">
        <div className="flex items-center gap-3">
          <UserAvatar
            avatarUrl={user?.avatarUrl}
            displayName={user?.displayName}
            email={user?.email}
            size="md"
          />
          <div>
            <h1 className="text-xl md:text-2xl font-bold" style={{ color: 'var(--portal-text-primary)' }}>
              {t('dashboard.welcomeBack')}{user?.displayName ? `, ${user.displayName.split(' ')[0]}` : ''}
            </h1>
            <p className="text-sm mt-0.5" style={{ color: 'var(--portal-text-muted)' }}>{t('dashboard.yourFamilyTrees')}</p>
          </div>
        </div>
        <div className="flex items-center gap-2 flex-wrap">
          {importError && <p className="text-xs text-red-600 w-full">{importError}</p>}
          <input
            ref={importInputRef}
            type="file"
            accept=".frt,.zip"
            className="hidden"
            onChange={handleImportFile}
          />
          <button
            onClick={() => { setImportError(''); importInputRef.current?.click(); }}
            disabled={importing}
            title="Import a .frt backup or a .zip with photos"
            className="px-3 py-2 border border-gray-300 text-gray-700 text-sm font-medium rounded-lg hover:bg-gray-50 transition-colors disabled:opacity-50"
          >
            {importing ? t('dashboard.importing') : t('dashboard.import')}
          </button>
          <button
            className="px-3 py-2 bg-brand-500 text-white text-sm font-medium rounded-lg hover:bg-brand-600 transition-colors"
            onClick={openModal}
          >
            {t('dashboard.newTree')}
          </button>
        </div>
      </div>

      {!loading && !error && trees.length > 0 && (
        <div className="relative mb-5 max-w-sm">
          <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5"
            className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400 pointer-events-none">
            <circle cx="7" cy="7" r="5.5" />
            <line x1="11" y1="11" x2="15" y2="15" strokeLinecap="round" />
          </svg>
          <input
            type="text"
            value={search}
            onChange={(e) => handleSearchChange(e.target.value)}
            placeholder={t('dashboard.searchTrees')}
            aria-label="Search trees"
            className="w-full h-10 pl-9 pr-8 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-brand-500"
          />
          {search && (
            <button
              onClick={() => handleSearchChange('')}
              title="Clear search"
              className="absolute right-2.5 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600 leading-none"
            >
              ×
            </button>
          )}
        </div>
      )}

      {loading && (
        <div className="flex justify-center py-16">
          <div className="w-7 h-7 border-2 border-brand-500 border-t-transparent rounded-full animate-spin" />
        </div>
      )}

      {error && (
        <div className="px-4 py-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700">
          {error}
        </div>
      )}

      {!loading && !error && trees.length === 0 && (
        <div className="text-center py-20 text-gray-400">
          <div className="text-5xl mb-4">🌳</div>
          <p className="text-lg font-medium text-gray-600">{t('dashboard.noTreesYet')}</p>
          <p className="text-sm mt-1">{t('dashboard.createFirstTree')}</p>
        </div>
      )}

      {!loading && !error && trees.length > 0 && sortedTrees.length === 0 && (
        <div className="text-center py-20 text-gray-400">
          <div className="text-5xl mb-4">🔍</div>
          <p className="text-lg font-medium text-gray-600">{t('dashboard.noTreesMatch', { query: search.trim() })}</p>
          <p className="text-sm mt-1">{t('dashboard.tryDifferent')}</p>
        </div>
      )}

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-5">
        {visibleTrees.map((tree) => (
          <TreeCard key={tree.id} tree={tree} onEdit={openEdit} onDelete={setDeleteTarget} onShare={setShareTarget} onTogglePin={handleTogglePin} />
        ))}
      </div>

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-between mt-6 pt-5 border-t border-gray-100">
          <p className="text-sm text-gray-500">
            Showing {(page - 1) * PAGE_SIZE + 1}–{Math.min(page * PAGE_SIZE, sortedTrees.length)} of {sortedTrees.length} trees
          </p>
          <div className="flex items-center gap-1">
            <button
              onClick={() => goToPage(page - 1)}
              disabled={page === 1}
              className="px-3 py-1.5 text-sm font-medium text-gray-600 rounded-lg hover:bg-gray-100 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
            >
              ← Prev
            </button>
            {Array.from({ length: totalPages }, (_, i) => i + 1).map((p) => (
              <button
                key={p}
                onClick={() => goToPage(p)}
                className={[
                  'w-8 h-8 text-sm font-medium rounded-lg transition-colors',
                  p === page
                    ? 'bg-brand-500 text-white'
                    : 'text-gray-600 hover:bg-gray-100',
                ].join(' ')}
              >
                {p}
              </button>
            ))}
            <button
              onClick={() => goToPage(page + 1)}
              disabled={page === totalPages}
              className="px-3 py-1.5 text-sm font-medium text-gray-600 rounded-lg hover:bg-gray-100 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
            >
              Next →
            </button>
          </div>
        </div>
      )}

      {/* Create tree modal */}
      {modalOpen && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4"
          onClick={(e) => { if (e.target === e.currentTarget) setModalOpen(false); }}
        >
          <div className="bg-white rounded-2xl shadow-xl w-full max-w-md p-4 md:p-6 mx-4 md:mx-0">
            <h2 className="text-lg font-semibold text-gray-900 mb-4">{t('dashboard.newFamilyTree')}</h2>
            <form onSubmit={handleCreateTree} className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  {t('dashboard.name')} <span className="text-red-500">*</span>
                </label>
                <input
                  autoFocus
                  type="text"
                  value={newName}
                  onChange={(e) => setNewName(e.target.value)}
                  placeholder={t('dashboard.namePlaceholder')}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
                  required
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">{t('dashboard.descriptionLabel')}</label>
                <textarea
                  value={newDesc}
                  onChange={(e) => setNewDesc(e.target.value)}
                  placeholder={t('dashboard.descriptionPlaceholder')}
                  rows={3}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-brand-500 resize-none"
                />
              </div>
              {createError && <p className="text-sm text-red-600">{createError}</p>}
              <div className="flex justify-end gap-3 pt-2">
                <button type="button" onClick={() => setModalOpen(false)}
                  className="px-4 py-2 text-sm text-gray-600 hover:text-gray-900 transition-colors">
                  {t('common.cancel')}
                </button>
                <button type="submit" disabled={creating || !newName.trim()}
                  className="px-4 py-2 bg-brand-500 text-white text-sm font-medium rounded-lg hover:bg-brand-600 disabled:opacity-50 transition-colors">
                  {creating ? t('dashboard.creating') : t('dashboard.createTree')}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Edit tree modal */}
      {editTarget && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4"
          onClick={(e) => { if (e.target === e.currentTarget && !editing) setEditTarget(null); }}
        >
          <div className="bg-white rounded-2xl shadow-xl w-full max-w-sm p-6">
            <h2 className="text-lg font-semibold text-gray-900 mb-4">{t('dashboard.editTreeTitle')}</h2>
            <form onSubmit={handleEditSubmit} className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">{t('dashboard.name')}</label>
                <input
                  autoFocus
                  type="text"
                  value={editName}
                  onChange={(e) => setEditName(e.target.value)}
                  maxLength={255}
                  required
                  className="w-full h-10 px-3 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-brand-500"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1"
                  dangerouslySetInnerHTML={{ __html: t('dashboard.descriptionOptional') }} />
                <textarea
                  value={editDesc}
                  onChange={(e) => setEditDesc(e.target.value)}
                  maxLength={1000}
                  rows={3}
                  className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-brand-500 resize-none"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">{t('dashboard.coverPhoto')}</label>
                <input
                  ref={photoInputRef}
                  type="file"
                  accept="image/jpeg,image/png,image/webp,image/gif"
                  className="hidden"
                  onChange={handleTreePhotoChange}
                />
                {editCoverImageUrl ? (
                  <div className="flex items-center gap-3">
                    <img
                      src={editCoverImageUrl}
                      alt="Tree cover"
                      className="w-16 h-16 rounded-xl object-cover border border-gray-200"
                    />
                    <div className="flex flex-col gap-1">
                      <button
                        type="button"
                        onClick={() => photoInputRef.current?.click()}
                        disabled={uploadingPhoto}
                        className="text-sm text-brand-600 hover:text-brand-700 font-medium disabled:opacity-50"
                      >
                        {uploadingPhoto ? t('dashboard.uploading') : t('dashboard.changePhoto')}
                      </button>
                      <button
                        type="button"
                        onClick={handleRemoveTreePhoto}
                        disabled={uploadingPhoto}
                        className="text-sm text-red-500 hover:text-red-600 disabled:opacity-50"
                      >
                        {t('dashboard.removePhoto')}
                      </button>
                    </div>
                  </div>
                ) : (
                  <button
                    type="button"
                    onClick={() => photoInputRef.current?.click()}
                    disabled={uploadingPhoto}
                    className="w-full py-3 border-2 border-dashed border-gray-300 rounded-xl text-sm text-gray-500 hover:border-brand-400 hover:text-brand-600 transition-colors disabled:opacity-50"
                  >
                    {uploadingPhoto ? t('dashboard.uploading') : t('dashboard.uploadPhoto')}
                  </button>
                )}
                {photoError && <p className="text-xs text-red-600 mt-1">{photoError}</p>}
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  {t('dashboard.coverIcon')} <span className="text-gray-400 font-normal">{t('dashboard.coverIconHint')}</span>
                </label>
                <div className="flex flex-wrap gap-2">
                  {TREE_COVER_PRESETS.map((emoji) => (
                    <button
                      key={emoji}
                      type="button"
                      onClick={() => setEditCoverEmoji(emoji)}
                      className={`w-10 h-10 text-xl rounded-lg border-2 transition-colors ${
                        editCoverEmoji === emoji
                          ? 'border-brand-500 bg-brand-50'
                          : 'border-gray-200 hover:border-gray-300 bg-white'
                      }`}
                    >
                      {emoji}
                    </button>
                  ))}
                </div>
              </div>
              {editError && <p className="text-sm text-red-600">{editError}</p>}
              <div className="flex justify-end gap-3 pt-1">
                <button type="button" onClick={() => setEditTarget(null)} disabled={editing}
                  className="px-4 py-2 text-sm text-gray-600 hover:text-gray-900 disabled:opacity-50 transition-colors">
                  {t('common.cancel')}
                </button>
                <button type="submit" disabled={editing || !editName.trim()}
                  className="px-4 py-2 bg-brand-500 text-white text-sm font-medium rounded-lg hover:bg-brand-600 disabled:opacity-50 transition-colors">
                  {editing ? t('dashboard.saving') : t('dashboard.saveChanges')}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Share tree modal */}
      {shareTarget && (
        <ShareTreeModal
          tree={shareTarget}
          token={accessToken}
          currentUserId={user?.id ?? ''}
          onClose={() => {
            setShareTarget(null);
            // Refresh trees so member_count stays in sync
            fetch(`${API_BASE}/trees`, {
              headers: { Authorization: `Bearer ${accessToken}` },
              credentials: 'include',
            }).then((r) => r.json()).then(setTrees).catch(() => {});
          }}
        />
      )}

      {/* Delete tree confirmation */}
      {deleteTarget && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4"
          onClick={(e) => { if (e.target === e.currentTarget && !deleting) setDeleteTarget(null); }}
        >
          <div className="bg-white rounded-2xl shadow-xl w-full max-w-sm p-6">
            <h2 className="text-lg font-semibold text-gray-900 mb-1">{t('dashboard.deleteTreeTitle')}</h2>
            <p className="text-sm text-gray-500 mb-4">
              {t('dashboard.deleteTreeDesc', { name: deleteTarget.name })}
            </p>
            {deleteError && <p className="text-sm text-red-600 mb-3">{deleteError}</p>}
            <div className="flex gap-3 justify-end">
              <button onClick={() => setDeleteTarget(null)} disabled={deleting}
                className="px-4 py-2 text-sm text-gray-600 hover:text-gray-900 disabled:opacity-50 transition-colors">
                {t('common.cancel')}
              </button>
              <button onClick={handleDeleteTree} disabled={deleting}
                className="px-4 py-2 bg-red-600 text-white text-sm font-medium rounded-lg hover:bg-red-700 disabled:opacity-50 transition-colors">
                {deleting ? t('dashboard.deleting') : t('dashboard.deleteTree')}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

// ── Share Tree Modal ───────────────────────────────────────────────────────

function ShareTreeModal({
  tree,
  token,
  currentUserId,
  onClose,
}: {
  tree: TreeSummary;
  token: string | null;
  currentUserId: string;
  onClose: () => void;
}) {
  const { t } = useTranslation();
  const appRole    = useAuthStore((s) => s.user?.appRole);
  const isStandard = appRole === 'STANDARD';

  const [linkSharing,    setLinkSharing]    = useState(tree.link_sharing ?? 'RESTRICTED');
  const [savingSharing,  setSavingSharing]  = useState(false);
  const [linkCopied,     setLinkCopied]     = useState(false);

  const [isSearchable,     setIsSearchable]     = useState(tree.is_searchable ?? false);
  const [savingSearchable, setSavingSearchable] = useState(false);

  const [members,     setMembers]     = useState<TreeMember[]>([]);
  const [invitations, setInvitations] = useState<PendingInvitation[]>([]);
  const [tenantUsers, setTenantUsers] = useState<TenantUser[]>([]);
  const [loading,     setLoading]     = useState(true);
  const [error,       setError]       = useState('');

  const [inviteMode,   setInviteMode]   = useState<'user' | 'email'>(isStandard ? 'email' : 'user');
  const [selectedUser, setSelectedUser] = useState('');
  const [emailInput,   setEmailInput]   = useState('');
  const [inviteRole,   setInviteRole]   = useState('VIEWER');
  const [inviting,     setInviting]     = useState(false);
  const [inviteError,  setInviteError]  = useState('');

  // Pending requests (access + merge) — visible to owner
  const [accessRequests, setAccessRequests] = useState<any[]>([]);
  const [mergeRequests,  setMergeRequests]  = useState<any[]>([]);

  const authHeader: Record<string, string> = token ? { Authorization: `Bearer ${token}` } : {};

  async function fetchAll() {
    setLoading(true);
    try {
      const [mRes, iRes, uRes] = await Promise.all([
        fetch(`${API_BASE}/trees/${tree.id}/members`,      { headers: authHeader, credentials: 'include' }),
        fetch(`${API_BASE}/trees/${tree.id}/invitations`,  { headers: authHeader, credentials: 'include' }),
        fetch(`${API_BASE}/trees/${tree.id}/tenant-users`, { headers: authHeader, credentials: 'include' }),
      ]);
      if (mRes.ok) setMembers(await mRes.json());
      if (iRes.ok) {
        const all: PendingInvitation[] = await iRes.json();
        setInvitations(all.filter((i) => i.status === 'PENDING'));
      }
      if (uRes.ok) setTenantUsers(await uRes.json());

      // Fetch pending requests for owners
      if (tree.role === 'OWNER') {
        const [arRes, mrRes] = await Promise.all([
          fetch(`${API_BASE}/trees/${tree.id}/access-requests?status=PENDING`, { headers: authHeader, credentials: 'include' }),
          fetch(`${API_BASE}/trees/${tree.id}/merge-requests?status=PENDING`,  { headers: authHeader, credentials: 'include' }),
        ]);
        if (arRes.ok) setAccessRequests(await arRes.json());
        if (mrRes.ok) setMergeRequests(await mrRes.json());
      }
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { fetchAll(); }, []);

  async function handleInvite(e: React.FormEvent) {
    e.preventDefault();
    setInviting(true);
    setInviteError('');
    try {
      if (inviteMode === 'user') {
        const res = await fetch(`${API_BASE}/trees/${tree.id}/members`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', ...authHeader },
          credentials: 'include',
          body: JSON.stringify({ user_id: selectedUser, role: inviteRole }),
        });
        if (!res.ok) {
          const err = await res.json().catch(() => ({}));
          throw new Error((err as any).detail ?? 'Failed to add member');
        }
        setSelectedUser('');
      } else {
        const email = emailInput.trim();
        if (!email) return;
        const res = await fetch(`${API_BASE}/trees/${tree.id}/invitations`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', ...authHeader },
          credentials: 'include',
          body: JSON.stringify({ email, role: inviteRole }),
        });
        if (!res.ok) {
          const err = await res.json().catch(() => ({}));
          throw new Error((err as any).detail ?? 'Failed to send invite');
        }
        setEmailInput('');
      }
      fetchAll();
    } catch (e) {
      setInviteError((e as Error).message);
    } finally {
      setInviting(false);
    }
  }

  async function handleRevoke(invitationId: string) {
    await fetch(`${API_BASE}/trees/${tree.id}/invitations/${invitationId}`, {
      method: 'DELETE', headers: authHeader, credentials: 'include',
    });
    fetchAll();
  }

  async function handleRemoveMember(userId: string) {
    await fetch(`${API_BASE}/trees/${tree.id}/members/${userId}`, {
      method: 'DELETE', headers: authHeader, credentials: 'include',
    });
    fetchAll();
  }

  async function handleLinkSharingChange(value: 'RESTRICTED' | 'ANYONE') {
    setSavingSharing(true);
    try {
      const res = await fetch(`${API_BASE}/trees/${tree.id}/link-sharing`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json', ...authHeader },
        credentials: 'include',
        body: JSON.stringify({ link_sharing: value }),
      });
      if (res.ok) setLinkSharing(value);
    } finally {
      setSavingSharing(false);
    }
  }

  async function handleSearchableChange(value: boolean) {
    setSavingSearchable(true);
    try {
      const res = await fetch(`${API_BASE}/trees/${tree.id}/searchable`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json', ...authHeader },
        credentials: 'include',
        body: JSON.stringify({ is_searchable: value }),
      });
      if (res.ok) setIsSearchable(value);
    } finally {
      setSavingSearchable(false);
    }
  }

  function copyShareLink() {
    const url = `${window.location.origin}/shared/${tree.share_token}`;
    navigator.clipboard.writeText(url).then(() => {
      setLinkCopied(true);
      setTimeout(() => setLinkCopied(false), 2000);
    }).catch(() => {});
  }

  const canManage = tree.role === 'OWNER' || tree.role === 'ADMIN';

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4"
      onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}
    >
      <div className="bg-white rounded-2xl shadow-xl w-full max-w-xl flex flex-col mx-4 md:mx-0 max-h-[90vh] md:max-h-[85vh]">

        {/* Header */}
        <div className="flex items-center justify-between px-6 pt-5 pb-4 border-b border-gray-100">
          <h2 className="text-lg font-semibold text-gray-900">{t('dashboard.shareTitle', { name: tree.name })}</h2>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600 text-xl leading-none">×</button>
        </div>

        {error && (
          <div className="mx-6 mt-4 px-3 py-2 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700">{error}</div>
        )}

        {loading ? (
          <div className="flex justify-center py-10">
            <div className="w-7 h-7 border-2 border-brand-500 border-t-transparent rounded-full animate-spin" />
          </div>
        ) : (
          <div className="flex-1 overflow-y-auto min-h-0">

            {/* Add people — OWNER or ADMIN only */}
            {canManage && (
              <div className="px-6 py-4 border-b border-gray-100">
                {/* Mode toggle — hidden for Standard users who can only invite by email */}
                {!isStandard && (
                  <div className="flex gap-1 p-1 bg-gray-100 rounded-lg w-fit mb-3">
                    {(['user', 'email'] as const).map((m) => (
                      <button
                        key={m}
                        type="button"
                        onClick={() => { setInviteMode(m); setSelectedUser(''); setEmailInput(''); }}
                        className={`px-3 py-1 text-xs font-medium rounded-md transition-colors ${
                          inviteMode === m ? 'bg-white shadow text-gray-800' : 'text-gray-500 hover:text-gray-700'
                        }`}
                      >
                        {m === 'user' ? t('dashboard.selectUser') : t('dashboard.emailAddress')}
                      </button>
                    ))}
                  </div>
                )}

                <form onSubmit={handleInvite}>
                  <div className="flex gap-2">
                    <div className="flex-1">
                      {inviteMode === 'user' ? (
                        <select
                          value={selectedUser}
                          onChange={(e) => setSelectedUser(e.target.value)}
                          required
                          className="w-full h-10 px-3 text-sm border border-gray-300 rounded-lg bg-white focus:outline-none focus:ring-2 focus:ring-brand-500"
                        >
                          <option value="">
                            {tenantUsers.length === 0 ? t('dashboard.allUsersAreMembers') : t('dashboard.selectPerson')}
                          </option>
                          {tenantUsers.map((u) => (
                            <option key={u.id} value={u.id}>{u.display_name} ({u.email})</option>
                          ))}
                        </select>
                      ) : (
                        <input
                          type="email"
                          value={emailInput}
                          onChange={(e) => setEmailInput(e.target.value)}
                          placeholder={t('dashboard.addByEmail')}
                          required
                          className="w-full h-10 px-3 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-brand-500"
                        />
                      )}
                    </div>
                    <select
                      value={inviteRole}
                      onChange={(e) => setInviteRole(e.target.value)}
                      className="h-10 px-2 text-sm border border-gray-300 rounded-lg bg-white focus:outline-none focus:ring-2 focus:ring-brand-500"
                    >
                      <option value="VIEWER">{t('roles.VIEWER')}</option>
                      <option value="EDITOR">{t('roles.EDITOR')}</option>
                      <option value="ADMIN">{t('roles.ADMIN')}</option>
                    </select>
                    <button
                      type="submit"
                      disabled={inviting || (inviteMode === 'user' ? !selectedUser : !emailInput.trim())}
                      className="h-10 px-4 bg-brand-500 text-white text-sm font-medium rounded-lg hover:bg-brand-600 disabled:opacity-50 transition-colors whitespace-nowrap"
                    >
                      {inviting ? '…' : t('common.share')}
                    </button>
                  </div>
                  {inviteError && <p className="text-xs text-red-600 mt-1.5">{inviteError}</p>}
                </form>
              </div>
            )}

            {/* People with access — members + pending invitations */}
            <div className="px-6 py-4">
              <p className="text-sm font-medium text-gray-700 mb-3">
                {t('dashboard.peopleWithAccess')}
              </p>
              <div className="space-y-0.5">
                {members.map((m) => (
                  <div key={m.id} className="flex items-center justify-between py-2 rounded-lg">
                    <div className="flex items-center gap-3 min-w-0">
                      <div className="w-8 h-8 rounded-full bg-brand-100 flex items-center justify-center text-xs font-semibold text-brand-700 shrink-0">
                        {(m.display_name || m.email).charAt(0).toUpperCase()}
                      </div>
                      <div className="min-w-0">
                        <div className="text-sm font-medium text-gray-900 truncate">{m.display_name}</div>
                        <div className="text-xs text-gray-500 truncate">{m.email}</div>
                      </div>
                    </div>
                    <div className="flex items-center gap-2 shrink-0 ml-2">
                      <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${MEMBER_ROLE_BADGE[m.role] ?? MEMBER_ROLE_BADGE['VIEWER']}`}>
                        {m.role.charAt(0) + m.role.slice(1).toLowerCase()}
                      </span>
                      {canManage && m.role !== 'OWNER' && m.user_id !== currentUserId
                        && !(tree.role === 'ADMIN' && m.role === 'ADMIN') && (
                        <button
                          onClick={() => handleRemoveMember(m.user_id)}
                          title={t('dashboard.removeFromTree')}
                          className="text-sm text-gray-300 hover:text-red-500 transition-colors leading-none"
                        >
                          ×
                        </button>
                      )}
                    </div>
                  </div>
                ))}

                {invitations.map((inv) => (
                  <div key={inv.id} className="flex items-center justify-between py-2 rounded-lg">
                    <div className="flex items-center gap-3 min-w-0">
                      <div className="w-8 h-8 rounded-full bg-amber-100 flex items-center justify-center text-xs font-semibold text-amber-700 shrink-0">
                        {inv.invitee_email.charAt(0).toUpperCase()}
                      </div>
                      <div className="min-w-0">
                        <div className="text-sm text-gray-800 truncate">{inv.invitee_email}</div>
                        <div className="text-xs text-amber-600">{t('dashboard.invitationPending')}</div>
                      </div>
                    </div>
                    <div className="flex items-center gap-2 shrink-0 ml-2">
                      <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${MEMBER_ROLE_BADGE[inv.role] ?? MEMBER_ROLE_BADGE['VIEWER']}`}>
                        {inv.role.charAt(0) + inv.role.slice(1).toLowerCase()}
                      </span>
                      {canManage && (
                        <button
                          onClick={() => handleRevoke(inv.id)}
                          title={t('dashboard.revokeInvitation')}
                          className="text-sm text-gray-300 hover:text-red-500 transition-colors leading-none"
                        >
                          ×
                        </button>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </div>

          </div>
        )}

        {/* Searchable — visible to all users */}
        <div className="px-6 py-4 border-t border-gray-100">
          <label className="flex items-center gap-3 cursor-pointer">
            <input
              type="checkbox"
              checked={isSearchable}
              onChange={(e) => canManage && handleSearchableChange(e.target.checked)}
              disabled={!canManage || savingSearchable}
              className="w-4 h-4 rounded border-gray-300 text-brand-500 focus:ring-brand-500 disabled:opacity-50"
            />
            <div className="min-w-0">
              <p className="text-sm font-medium text-gray-900">{t('dashboard.searchable')}</p>
              <p className="text-xs text-gray-500">
                {t('dashboard.searchableDesc')}
              </p>
            </div>
          </label>
        </div>

        {/* General access — visible to all users */}
        <div className="px-6 py-4 border-t border-gray-100">
          <p className="text-sm font-medium text-gray-700 mb-3">{t('dashboard.generalAccess')}</p>
          <div className="flex items-center justify-between gap-3">
            <div className="flex items-center gap-3 min-w-0">
              <div className="w-8 h-8 rounded-full bg-gray-100 flex items-center justify-center shrink-0">
                {linkSharing === 'ANYONE' ? (
                  <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round">
                    <circle cx="8" cy="8" r="6.5" />
                    <ellipse cx="8" cy="8" rx="3" ry="6.5" />
                    <line x1="1.5" y1="6" x2="14.5" y2="6" />
                    <line x1="1.5" y1="10" x2="14.5" y2="10" />
                  </svg>
                ) : (
                  <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round">
                    <rect x="3" y="7" width="10" height="7" rx="1.5" />
                    <path d="M5 7V5a3 3 0 0 1 6 0v2" />
                  </svg>
                )}
              </div>
              <div className="min-w-0">
                {canManage ? (
                  <select
                    value={linkSharing}
                    onChange={(e) => handleLinkSharingChange(e.target.value as 'RESTRICTED' | 'ANYONE')}
                    disabled={savingSharing}
                    className="text-sm font-medium text-gray-900 bg-transparent border-none outline-none cursor-pointer pr-1 disabled:opacity-60"
                  >
                    <option value="RESTRICTED">{t('dashboard.restricted')}</option>
                    <option value="ANYONE">{t('dashboard.anyoneWithLink')}</option>
                  </select>
                ) : (
                  <p className="text-sm font-medium text-gray-900">
                    {linkSharing === 'ANYONE' ? t('dashboard.anyoneWithLink') : t('dashboard.restricted')}
                  </p>
                )}
                <p className="text-xs text-gray-500">
                  {linkSharing === 'ANYONE'
                    ? t('dashboard.anyoneCanView')
                    : t('dashboard.onlyInvited')}
                </p>
              </div>
            </div>
            {tree.share_token && (
              <button
                onClick={copyShareLink}
                className={`shrink-0 text-xs font-medium px-3 py-1.5 rounded-lg transition-colors whitespace-nowrap border ${
                  linkCopied
                    ? 'text-green-700 bg-green-50 border-green-300'
                    : 'text-brand-600 hover:text-brand-700 border-brand-200 hover:border-brand-300'
                }`}
              >
                {linkCopied ? t('common.copied') : t('common.copyLink')}
              </button>
            )}
          </div>
        </div>

        {/* Pending Requests — visible to owner only */}
        {tree.role === 'OWNER' && (accessRequests.length > 0 || mergeRequests.length > 0) && (
          <div className="px-6 py-4 border-t border-gray-100">
            <p className="text-sm font-medium text-gray-700 mb-3">
              {t('dashboard.pendingRequests')}
              <span className="ml-1.5 text-xs font-normal text-gray-400">
                ({accessRequests.length + mergeRequests.length})
              </span>
            </p>

            <div className="space-y-2 max-h-48 overflow-y-auto">
              {/* Access requests */}
              {accessRequests.map((ar: any) => (
                <div key={ar.id} className="flex items-center justify-between gap-3 p-3 bg-gray-50 rounded-lg">
                  <div className="min-w-0 flex-1">
                    <p className="text-sm font-medium text-gray-900 truncate">{ar.requester_name}</p>
                    <p className="text-xs text-gray-500">
                      {t('dashboard.wantsAccess', { role: ar.requested_role })}
                      {ar.message && <> &middot; "{ar.message}"</>}
                    </p>
                  </div>
                  <div className="flex gap-1.5 shrink-0">
                    <button
                      onClick={async () => {
                        await fetch(`${API_BASE}/trees/${tree.id}/access-requests/${ar.id}`, {
                          method: 'PATCH',
                          headers: { 'Content-Type': 'application/json', ...authHeader },
                          credentials: 'include',
                          body: JSON.stringify({ action: 'approve' }),
                        });
                        setAccessRequests((prev) => prev.filter((r: any) => r.id !== ar.id));
                      }}
                      className="px-2.5 py-1 text-xs font-medium bg-brand-500 text-white rounded-md hover:bg-brand-600 transition-colors"
                    >
                      {t('common.approve')}
                    </button>
                    <button
                      onClick={async () => {
                        await fetch(`${API_BASE}/trees/${tree.id}/access-requests/${ar.id}`, {
                          method: 'PATCH',
                          headers: { 'Content-Type': 'application/json', ...authHeader },
                          credentials: 'include',
                          body: JSON.stringify({ action: 'deny' }),
                        });
                        setAccessRequests((prev) => prev.filter((r: any) => r.id !== ar.id));
                      }}
                      className="px-2.5 py-1 text-xs font-medium bg-gray-200 text-gray-700 rounded-md hover:bg-gray-300 transition-colors"
                    >
                      {t('common.deny')}
                    </button>
                  </div>
                </div>
              ))}

              {/* Merge requests */}
              {mergeRequests.map((mr: any) => (
                <div key={mr.id} className="flex items-center justify-between gap-3 p-3 bg-amber-50 rounded-lg border border-amber-100">
                  <div className="min-w-0 flex-1">
                    <p className="text-sm font-medium text-gray-900 truncate">
                      {t('dashboard.mergeFrom', { name: mr.source_tree_name })}
                    </p>
                    <p className="text-xs text-gray-500">
                      {t('dashboard.by')} {mr.requester_name}
                      {mr.target_pivot_name && mr.source_pivot_name && (
                        <> &middot; {t('dashboard.pivot')}: {mr.source_pivot_name} = {mr.target_pivot_name}</>
                      )}
                    </p>
                    {mr.message && <p className="text-xs text-gray-400 mt-0.5 truncate">"{mr.message}"</p>}
                  </div>
                  <div className="flex gap-1.5 shrink-0">
                    <button
                      onClick={async () => {
                        await fetch(`${API_BASE}/trees/${tree.id}/merge-requests/${mr.id}`, {
                          method: 'PATCH',
                          headers: { 'Content-Type': 'application/json', ...authHeader },
                          credentials: 'include',
                          body: JSON.stringify({ action: 'approve' }),
                        });
                        setMergeRequests((prev) => prev.filter((r: any) => r.id !== mr.id));
                      }}
                      className="px-2.5 py-1 text-xs font-medium bg-brand-500 text-white rounded-md hover:bg-brand-600 transition-colors"
                    >
                      Approve
                    </button>
                    <button
                      onClick={async () => {
                        await fetch(`${API_BASE}/trees/${tree.id}/merge-requests/${mr.id}`, {
                          method: 'PATCH',
                          headers: { 'Content-Type': 'application/json', ...authHeader },
                          credentials: 'include',
                          body: JSON.stringify({ action: 'deny' }),
                        });
                        setMergeRequests((prev) => prev.filter((r: any) => r.id !== mr.id));
                      }}
                      className="px-2.5 py-1 text-xs font-medium bg-gray-200 text-gray-700 rounded-md hover:bg-gray-300 transition-colors"
                    >
                      Deny
                    </button>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Footer */}
        <div className="flex justify-end px-6 py-4 border-t border-gray-100">
          <button
            onClick={onClose}
            className="px-5 py-2 bg-brand-500 text-white text-sm font-medium rounded-lg hover:bg-brand-600 transition-colors"
          >
            {t('common.done')}
          </button>
        </div>

      </div>
    </div>
  );
}
