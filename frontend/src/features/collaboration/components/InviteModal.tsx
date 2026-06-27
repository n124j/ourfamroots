/**
 * InviteModal — form to invite a new member by email.
 *
 * Fields: email, role, optional message.
 * On submit: POST /trees/{id}/invitations → show success state with invite link.
 */

import React, { memo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { queryKeys } from '@queries/keys';
import { useAuthStore } from '@store/auth.store';

type TreeRole = 'ADMIN' | 'EDITOR' | 'VIEWER';

async function sendInvitation(
  treeId: string,
  data: { email: string; role: TreeRole; message?: string }
) {
  const res = await fetch(`/api/v1/trees/${treeId}/invitations`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${useAuthStore.getState().accessToken}`,
    },
    body: JSON.stringify(data),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail ?? 'Failed to send invitation');
  }
  return res.json();
}

// ── Component ──────────────────────────────────────────────────────────────

interface InviteModalProps {
  treeId: string;
  onClose: () => void;
}

export const InviteModal = memo(({ treeId, onClose }: InviteModalProps) => {
  const { t } = useTranslation();
  const queryClient = useQueryClient();

  const ROLE_DESCRIPTIONS: Record<TreeRole, string> = {
    ADMIN:  t('inviteModal.adminDesc'),
    EDITOR: t('inviteModal.editorDesc'),
    VIEWER: t('inviteModal.viewerDesc'),
  };
  const [email, setEmail]     = useState('');
  const [role, setRole]       = useState<TreeRole>('EDITOR');
  const [message, setMessage] = useState('');
  const [success, setSuccess] = useState(false);

  const mutation = useMutation({
    mutationFn: () => sendInvitation(treeId, { email, role, message: message || undefined }),
    onSuccess: () => {
      setSuccess(true);
      queryClient.invalidateQueries({ queryKey: queryKeys.trees.invitations(treeId) });
    },
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!email) return;
    mutation.mutate();
  };

  return (
    /* Backdrop */
    <div
      className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4"
      onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}
    >
      <div className="bg-white rounded-2xl shadow-xl w-full max-w-md">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-slate-200">
          <h2 className="text-base font-semibold text-slate-800">{t('inviteModal.title')}</h2>
          <button
            onClick={onClose}
            className="w-7 h-7 flex items-center justify-center rounded-lg hover:bg-slate-100 text-slate-400"
          >
            ✕
          </button>
        </div>

        {/* Body */}
        <div className="px-6 py-5">
          {success ? (
            /* Success state */
            <div className="text-center py-4">
              <div className="text-3xl mb-3">✉️</div>
              <p className="font-medium text-slate-800">{t('inviteModal.sent')}</p>
              <p className="text-sm text-slate-500 mt-1">
                {t('inviteModal.sentDesc')} <strong>{email}</strong>.
                {' '}{t('inviteModal.expiresIn72')}
              </p>
              <button
                onClick={onClose}
                className="mt-4 px-4 py-2 bg-brand-500 text-white text-sm font-medium rounded-lg hover:bg-brand-600"
              >
                {t('common.done')}
              </button>
            </div>
          ) : (
            <form onSubmit={handleSubmit} className="space-y-4">
              {/* Email */}
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1.5">
                  {t('auth.email')}
                </label>
                <input
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder={t('inviteModal.emailPlaceholder')}
                  required
                  className="w-full h-10 px-3 text-sm border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-brand-500 focus:border-transparent"
                />
              </div>

              {/* Role */}
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1.5">
                  Role
                </label>
                <div className="space-y-2">
                  {(['ADMIN', 'EDITOR', 'VIEWER'] as TreeRole[]).map((r) => (
                    <label
                      key={r}
                      className={[
                        'flex items-start gap-3 p-3 rounded-lg border cursor-pointer transition-colors',
                        role === r
                          ? 'border-brand-500 bg-brand-50'
                          : 'border-slate-200 hover:border-slate-300',
                      ].join(' ')}
                    >
                      <input
                        type="radio"
                        name="role"
                        value={r}
                        checked={role === r}
                        onChange={() => setRole(r)}
                        className="mt-0.5 accent-brand-500"
                      />
                      <div>
                        <div className="text-sm font-medium text-slate-800">{t(`roles.${r}`)}</div>
                        <div className="text-xs text-slate-500 mt-0.5">{ROLE_DESCRIPTIONS[r]}</div>
                      </div>
                    </label>
                  ))}
                </div>
              </div>

              {/* Optional message */}
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1.5">
                  Personal message{' '}
                  <span className="text-slate-400 font-normal">(optional)</span>
                </label>
                <textarea
                  value={message}
                  onChange={(e) => setMessage(e.target.value)}
                  placeholder="I'd love to share our family history with you…"
                  rows={3}
                  maxLength={500}
                  className="w-full px-3 py-2 text-sm border border-slate-300 rounded-lg resize-none focus:outline-none focus:ring-2 focus:ring-brand-500 focus:border-transparent"
                />
              </div>

              {/* Error */}
              {mutation.isError && (
                <div className="px-3 py-2 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700">
                  {(mutation.error as Error).message}
                </div>
              )}

              {/* Submit */}
              <div className="flex gap-3 pt-1">
                <button
                  type="button"
                  onClick={onClose}
                  className="flex-1 h-10 text-sm font-medium text-slate-600 border border-slate-300 rounded-lg hover:bg-slate-50"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={mutation.isPending || !email}
                  className="flex-1 h-10 text-sm font-medium text-white bg-brand-500 rounded-lg hover:bg-brand-600 disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {mutation.isPending ? 'Sending…' : 'Send invitation'}
                </button>
              </div>
            </form>
          )}
        </div>
      </div>
    </div>
  );
});
InviteModal.displayName = 'InviteModal';
