import React, { useState, useEffect } from 'react';
import { useAuthStore } from '@store/auth.store';

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? '/api/v1';

interface TreeOption {
  id: string;
  name: string;
  role: string;
}

interface PersonOption {
  id: string;
  displayGivenName: string;
  displaySurname: string;
}

export function MergeRequestModal({
  treeId,
  treeName,
  targetPersons,
  onClose,
  onSuccess,
}: {
  treeId: string;
  treeName: string;
  targetPersons: PersonOption[];
  onClose: () => void;
  onSuccess: () => void;
}) {
  const accessToken = useAuthStore((s) => s.accessToken);

  const [step, setStep] = useState(1);
  const [myTrees, setMyTrees] = useState<TreeOption[]>([]);
  const [sourceTreeId, setSourceTreeId] = useState('');
  const [sourcePersons, setSourcePersons] = useState<PersonOption[]>([]);
  const [sourcePivotId, setSourcePivotId] = useState('');
  const [targetPivotId, setTargetPivotId] = useState('');
  const [newTreeName, setNewTreeName] = useState('');
  const [message, setMessage] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState(false);
  const [loadingPersons, setLoadingPersons] = useState(false);

  // Search state for person pickers
  const [sourceSearch, setSourceSearch] = useState('');
  const [targetSearch, setTargetSearch] = useState('');

  // Load user's trees (only ones they own)
  useEffect(() => {
    (async () => {
      try {
        const res = await fetch(`${API_BASE}/trees`, {
          headers: { Authorization: `Bearer ${accessToken}` },
          credentials: 'include',
        });
        if (res.ok) {
          const trees: TreeOption[] = await res.json();
          setMyTrees(trees.filter((t) => t.role === 'OWNER'));
        }
      } catch { /* ignore */ }
    })();
  }, [accessToken]);

  // Load source tree persons when source tree is selected
  useEffect(() => {
    if (!sourceTreeId) {
      setSourcePersons([]);
      return;
    }
    setLoadingPersons(true);
    (async () => {
      try {
        const res = await fetch(`${API_BASE}/trees/${sourceTreeId}/graph`, {
          headers: { Authorization: `Bearer ${accessToken}` },
          credentials: 'include',
        });
        if (res.ok) {
          const data = await res.json();
          setSourcePersons(
            (data.persons || []).map((p: any) => ({
              id: p.id,
              displayGivenName: p.displayGivenName || '',
              displaySurname: p.displaySurname || '',
            })),
          );
        }
      } catch { /* ignore */ }
      finally { setLoadingPersons(false); }
    })();
  }, [sourceTreeId, accessToken]);

  // Default tree name when both trees selected
  useEffect(() => {
    if (sourceTreeId && !newTreeName) {
      const source = myTrees.find((t) => t.id === sourceTreeId);
      if (source) {
        setNewTreeName(`${source.name} + ${treeName}`);
      }
    }
  }, [sourceTreeId, myTrees, treeName, newTreeName]);

  function personLabel(p: PersonOption): string {
    return [p.displayGivenName, p.displaySurname].filter(Boolean).join(' ') || '(unnamed)';
  }

  function filterPersons(persons: PersonOption[], search: string): PersonOption[] {
    if (!search.trim()) return persons;
    const q = search.toLowerCase();
    return persons.filter((p) =>
      personLabel(p).toLowerCase().includes(q),
    );
  }

  async function handleSubmit() {
    setSubmitting(true);
    setError('');
    try {
      const res = await fetch(`${API_BASE}/discover/trees/${treeId}/merge-requests`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${accessToken}` },
        credentials: 'include',
        body: JSON.stringify({
          source_tree_id: sourceTreeId,
          source_pivot_person_id: sourcePivotId,
          target_pivot_person_id: targetPivotId,
          new_tree_name: newTreeName.trim(),
          message: message.trim() || null,
        }),
      });
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error((data as any).detail ?? 'Failed to submit merge request');
      }
      setSuccess(true);
      onSuccess();
    } catch (err: any) {
      setError(err.message);
    } finally {
      setSubmitting(false);
    }
  }

  const canProceedStep1 = !!sourceTreeId;
  const canProceedStep2 = !!sourcePivotId && !!targetPivotId;
  const canSubmit = canProceedStep2 && newTreeName.trim().length > 0;

  return (
    <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4" onClick={onClose}>
      <div className="bg-white rounded-2xl shadow-xl w-full max-w-lg max-h-[90vh] overflow-y-auto" onClick={(e) => e.stopPropagation()}>
        <div className="px-6 pt-5 pb-2">
          <h2 className="text-lg font-semibold text-gray-900">Request Merge</h2>
          <p className="text-sm text-gray-500 mt-1">
            Propose merging your tree with <span className="font-medium">{treeName}</span>
          </p>
        </div>

        {success ? (
          <div className="px-6 py-6 text-center">
            <div className="w-12 h-12 bg-green-50 rounded-full flex items-center justify-center mx-auto mb-3">
              <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#16a34a" strokeWidth="2" strokeLinecap="round">
                <polyline points="20 6 9 17 4 12" />
              </svg>
            </div>
            <p className="text-sm font-medium text-gray-900">Merge request sent!</p>
            <p className="text-xs text-gray-500 mt-1">The tree owner will review your request.</p>
          </div>
        ) : (
          <div className="px-6 pb-2">
            {/* Step indicator */}
            <div className="flex items-center gap-2 mb-5">
              {[1, 2, 3].map((s) => (
                <div key={s} className="flex items-center gap-2 flex-1">
                  <div className={`w-6 h-6 rounded-full flex items-center justify-center text-xs font-medium ${
                    step >= s ? 'bg-brand-500 text-white' : 'bg-gray-100 text-gray-400'
                  }`}>
                    {s}
                  </div>
                  <span className={`text-xs ${step >= s ? 'text-gray-700' : 'text-gray-400'}`}>
                    {s === 1 ? 'Your tree' : s === 2 ? 'Pivot persons' : 'Details'}
                  </span>
                </div>
              ))}
            </div>

            {/* Step 1: Select source tree */}
            {step === 1 && (
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">Select your tree to merge</label>
                {myTrees.length === 0 ? (
                  <p className="text-sm text-gray-400 py-4">You don't own any trees yet.</p>
                ) : (
                  <div className="space-y-2 max-h-48 overflow-y-auto">
                    {myTrees.map((t) => (
                      <label
                        key={t.id}
                        className={`flex items-center gap-3 p-3 border rounded-lg cursor-pointer transition-colors ${
                          sourceTreeId === t.id ? 'border-brand-500 bg-brand-50' : 'border-gray-200 hover:border-gray-300'
                        }`}
                      >
                        <input
                          type="radio"
                          name="sourceTree"
                          value={t.id}
                          checked={sourceTreeId === t.id}
                          onChange={() => { setSourceTreeId(t.id); setSourcePivotId(''); }}
                          className="text-brand-500 focus:ring-brand-500"
                        />
                        <span className="text-sm text-gray-900">{t.name}</span>
                      </label>
                    ))}
                  </div>
                )}
              </div>
            )}

            {/* Step 2: Select pivot persons */}
            {step === 2 && (
              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Common person in your tree
                  </label>
                  <p className="text-xs text-gray-400 mb-2">
                    The person who exists in both trees (the merge point)
                  </p>
                  <input
                    type="text"
                    value={sourceSearch}
                    onChange={(e) => setSourceSearch(e.target.value)}
                    placeholder="Search..."
                    className="w-full text-sm border border-gray-200 rounded-lg px-3 py-2 mb-2 focus:outline-none focus:ring-2 focus:ring-brand-500"
                  />
                  {loadingPersons ? (
                    <p className="text-xs text-gray-400 py-2">Loading...</p>
                  ) : (
                    <div className="max-h-32 overflow-y-auto space-y-1">
                      {filterPersons(sourcePersons, sourceSearch).slice(0, 50).map((p) => (
                        <label
                          key={p.id}
                          className={`flex items-center gap-2 px-2 py-1.5 rounded cursor-pointer text-xs ${
                            sourcePivotId === p.id ? 'bg-brand-50 text-brand-700' : 'hover:bg-gray-50 text-gray-700'
                          }`}
                        >
                          <input
                            type="radio"
                            name="sourcePivot"
                            checked={sourcePivotId === p.id}
                            onChange={() => setSourcePivotId(p.id)}
                            className="text-brand-500 focus:ring-brand-500"
                          />
                          {personLabel(p)}
                        </label>
                      ))}
                    </div>
                  )}
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Same person in "{treeName}"
                  </label>
                  <input
                    type="text"
                    value={targetSearch}
                    onChange={(e) => setTargetSearch(e.target.value)}
                    placeholder="Search..."
                    className="w-full text-sm border border-gray-200 rounded-lg px-3 py-2 mb-2 focus:outline-none focus:ring-2 focus:ring-brand-500"
                  />
                  <div className="max-h-32 overflow-y-auto space-y-1">
                    {filterPersons(targetPersons, targetSearch).slice(0, 50).map((p) => (
                      <label
                        key={p.id}
                        className={`flex items-center gap-2 px-2 py-1.5 rounded cursor-pointer text-xs ${
                          targetPivotId === p.id ? 'bg-brand-50 text-brand-700' : 'hover:bg-gray-50 text-gray-700'
                        }`}
                      >
                        <input
                          type="radio"
                          name="targetPivot"
                          checked={targetPivotId === p.id}
                          onChange={() => setTargetPivotId(p.id)}
                          className="text-brand-500 focus:ring-brand-500"
                        />
                        {personLabel(p)}
                      </label>
                    ))}
                  </div>
                </div>
              </div>
            )}

            {/* Step 3: Details */}
            {step === 3 && (
              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Merged tree name</label>
                  <input
                    type="text"
                    value={newTreeName}
                    onChange={(e) => setNewTreeName(e.target.value)}
                    maxLength={255}
                    className="w-full text-sm border border-gray-200 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-brand-500"
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Message (optional)</label>
                  <textarea
                    value={message}
                    onChange={(e) => setMessage(e.target.value)}
                    maxLength={1000}
                    rows={3}
                    placeholder="Explain the connection between the trees..."
                    className="w-full text-sm border border-gray-200 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-brand-500 resize-none"
                  />
                </div>
              </div>
            )}

            {error && <p className="text-xs text-red-600 mt-3">{error}</p>}
          </div>
        )}

        <div className="flex justify-between px-6 py-4 border-t border-gray-100">
          <div>
            {!success && step > 1 && (
              <button
                onClick={() => setStep(step - 1)}
                className="px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50 rounded-lg transition-colors"
              >
                Back
              </button>
            )}
          </div>
          <div className="flex gap-2">
            <button onClick={onClose} className="px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50 rounded-lg transition-colors">
              {success ? 'Close' : 'Cancel'}
            </button>
            {!success && step < 3 && (
              <button
                onClick={() => setStep(step + 1)}
                disabled={step === 1 ? !canProceedStep1 : !canProceedStep2}
                className="px-4 py-2 text-sm font-medium text-white bg-brand-500 rounded-lg hover:bg-brand-600 disabled:opacity-50 transition-colors"
              >
                Next
              </button>
            )}
            {!success && step === 3 && (
              <button
                onClick={handleSubmit}
                disabled={!canSubmit || submitting}
                className="px-4 py-2 text-sm font-medium text-white bg-brand-500 rounded-lg hover:bg-brand-600 disabled:opacity-50 transition-colors"
              >
                {submitting ? 'Sending...' : 'Send Merge Request'}
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
