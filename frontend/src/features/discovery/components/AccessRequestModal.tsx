import React, { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useAuthStore } from '@store/auth.store';

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? '/api/v1';

export function AccessRequestModal({
  treeId,
  treeName,
  onClose,
  onSuccess,
}: {
  treeId: string;
  treeName: string;
  onClose: () => void;
  onSuccess: () => void;
}) {
  const { t } = useTranslation();
  const accessToken = useAuthStore((s) => s.accessToken);
  const [role, setRole] = useState<'EDITOR' | 'ADMIN'>('EDITOR');
  const [message, setMessage] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    setError('');
    try {
      const res = await fetch(`${API_BASE}/discover/trees/${treeId}/access-requests`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${accessToken}` },
        credentials: 'include',
        body: JSON.stringify({ requested_role: role, message: message.trim() || null }),
      });
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error((data as any).detail ?? 'Failed to submit request');
      }
      setSuccess(true);
      onSuccess();
    } catch (err: any) {
      setError(err.message);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4" onClick={onClose}>
      <div className="bg-white rounded-2xl shadow-xl w-full max-w-md" onClick={(e) => e.stopPropagation()}>
        <div className="px-6 pt-5 pb-2">
          <h2 className="text-lg font-semibold text-gray-900">{t('accessRequest.title')}</h2>
          <p className="text-sm text-gray-500 mt-1">
            {t('accessRequest.requestElevated')} <span className="font-medium">{treeName}</span>
          </p>
        </div>

        {success ? (
          <div className="px-6 py-6 text-center">
            <div className="w-12 h-12 bg-green-50 rounded-full flex items-center justify-center mx-auto mb-3">
              <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#16a34a" strokeWidth="2" strokeLinecap="round">
                <polyline points="20 6 9 17 4 12" />
              </svg>
            </div>
            <p className="text-sm font-medium text-gray-900">{t('accessRequest.sent')}</p>
            <p className="text-xs text-gray-500 mt-1">{t('accessRequest.sentDesc')}</p>
          </div>
        ) : (
          <form onSubmit={handleSubmit} className="px-6 pb-2">
            <div className="mb-4">
              <label className="block text-sm font-medium text-gray-700 mb-2">{t('accessRequest.requestedRole')}</label>
              <div className="flex gap-3">
                {(['EDITOR', 'ADMIN'] as const).map((r) => (
                  <label key={r} className="flex items-center gap-2 cursor-pointer">
                    <input
                      type="radio"
                      name="role"
                      value={r}
                      checked={role === r}
                      onChange={() => setRole(r)}
                      className="text-brand-500 focus:ring-brand-500"
                    />
                    <span className="text-sm text-gray-700">{t(`roles.${r}`)}</span>
                  </label>
                ))}
              </div>
              <p className="text-xs text-gray-400 mt-1">
                {role === 'EDITOR' ? t('accessRequest.editorDesc') : t('accessRequest.adminDesc')}
              </p>
            </div>

            <div className="mb-4">
              <label className="block text-sm font-medium text-gray-700 mb-1">Message (optional)</label>
              <textarea
                value={message}
                onChange={(e) => setMessage(e.target.value)}
                maxLength={500}
                rows={3}
                placeholder="Explain why you'd like access..."
                className="w-full text-sm border border-gray-200 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-brand-500 resize-none"
              />
              <p className="text-xs text-gray-400 mt-1 text-right">{message.length}/500</p>
            </div>

            {error && <p className="text-xs text-red-600 mb-3">{error}</p>}
          </form>
        )}

        <div className="flex justify-end gap-2 px-6 py-4 border-t border-gray-100">
          <button onClick={onClose} className="px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50 rounded-lg transition-colors">
            {success ? 'Close' : 'Cancel'}
          </button>
          {!success && (
            <button
              onClick={(e) => { const form = (e.target as HTMLElement).closest('.bg-white')?.querySelector('form'); form?.requestSubmit(); }}
              disabled={submitting}
              className="px-4 py-2 text-sm font-medium text-white bg-brand-500 rounded-lg hover:bg-brand-600 disabled:opacity-50 transition-colors"
            >
              {submitting ? 'Sending...' : 'Send Request'}
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
