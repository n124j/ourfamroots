import React, { useState } from 'react';
import { post } from '@api/client';
import { useAiTreeImportJob } from './useAiTreeImportJob';
import type { ExtractedFamilyGroup, ExtractedPerson } from './types';

const ACCEPTED_TYPES = ['image/jpeg', 'image/png', 'image/webp'];

function personLabel(id: string, persons: ExtractedPerson[]): string {
  const p = persons.find((person) => person.id === id);
  if (!p) return id;
  const name = `${p.display_given_name} ${p.display_surname}`.trim();
  return name || id;
}

export function AiTreeImportPanel() {
  const { status, jobId, draft, photoUrls, errorMessage, uploadScreenshot, reset } = useAiTreeImportJob();
  const [persons, setPersons] = useState<ExtractedPerson[]>([]);
  const [familyGroups, setFamilyGroups] = useState<ExtractedFamilyGroup[]>([]);
  const [treeName, setTreeName] = useState('Imported Tree');
  const [finalizeResult, setFinalizeResult] = useState<{ tree_id: string; tree_name: string } | null>(null);
  const [finalizing, setFinalizing] = useState(false);
  const [isDraggingOver, setIsDraggingOver] = useState(false);
  const [dropError, setDropError] = useState<string | null>(null);

  React.useEffect(() => {
    if (status === 'ready' && draft) {
      setPersons(draft.persons);
      setFamilyGroups(draft.family_groups);
    }
  }, [status, draft]);

  function updatePerson(id: string, patch: Partial<ExtractedPerson>) {
    setPersons((prev) => prev.map((p) => (p.id === id ? { ...p, ...patch } : p)));
  }

  function removePerson(id: string) {
    setPersons((prev) => prev.filter((p) => p.id !== id));
  }

  async function handleFinalize() {
    if (!jobId) return;
    setFinalizing(true);
    try {
      const result = await post<{ tree_id: string; tree_name: string }>(
        `/admin/ai-tree-import/${jobId}/finalize`,
        { tree_name: treeName, persons, family_groups: familyGroups },
      );
      setFinalizeResult(result);
    } finally {
      setFinalizing(false);
    }
  }

  function pickFile(file: File) {
    if (!ACCEPTED_TYPES.includes(file.type)) {
      setDropError('Please use a JPEG, PNG, or WebP image.');
      return;
    }
    setDropError(null);
    uploadScreenshot(file);
  }

  if (finalizeResult) {
    return (
      <div className="max-w-lg">
        <p className="text-sm text-gray-700 mb-3">Tree "{finalizeResult.tree_name}" created.</p>
        <div className="flex items-center gap-4">
          <a href={`/trees/${finalizeResult.tree_id}`} className="text-sm text-brand-600 hover:underline">Open tree</a>
          <button onClick={reset} className="text-sm text-gray-600 hover:text-gray-900">Import another screenshot</button>
        </div>
      </div>
    );
  }

  if (status === 'idle') {
    return (
      <div className="max-w-lg">
        <label
          onDragOver={(e) => { e.preventDefault(); setIsDraggingOver(true); }}
          onDragLeave={() => setIsDraggingOver(false)}
          onDrop={(e) => {
            e.preventDefault();
            setIsDraggingOver(false);
            const file = e.dataTransfer.files?.[0];
            if (file) pickFile(file);
          }}
          className={`flex flex-col items-center justify-center gap-2 border-2 border-dashed rounded-lg px-6 py-10 text-center cursor-pointer transition-colors ${
            isDraggingOver ? 'border-brand-500 bg-brand-50' : 'border-gray-300 hover:border-gray-400'
          }`}
        >
          <span className="text-sm text-gray-600">Drag & drop a family-tree screenshot here, or click to browse</span>
          <span className="text-xs text-gray-400">JPEG, PNG, or WebP</span>
          <input
            type="file"
            accept="image/jpeg,image/png,image/webp"
            className="hidden"
            onChange={(e) => e.target.files?.[0] && pickFile(e.target.files[0])}
          />
        </label>
        {dropError && <p className="text-sm text-red-600 mt-2">{dropError}</p>}
      </div>
    );
  }

  if (status === 'uploading' || status === 'processing') {
    return <p className="text-sm text-gray-600">{status === 'uploading' ? 'Uploading screenshot…' : 'Extracting family tree…'}</p>;
  }

  if (status === 'error') {
    return (
      <div>
        <p className="text-sm text-red-600 mb-3">{errorMessage}</p>
        <button onClick={reset} className="px-4 py-2 bg-brand-500 text-white text-sm font-medium rounded-lg hover:bg-brand-600">
          Try again
        </button>
      </div>
    );
  }

  return (
    <div className="max-w-3xl space-y-6">
      <div>
        <label className="block text-xs font-medium text-gray-600 mb-1">Tree name</label>
        <input
          value={treeName}
          onChange={(e) => setTreeName(e.target.value)}
          placeholder="Name this tree before creating it"
          className="w-full max-w-sm h-9 px-3 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-brand-500"
        />
      </div>

      <div>
        <h3 className="text-sm font-semibold text-gray-900 mb-2">People ({persons.length})</h3>
        <div className="space-y-2">
          {persons.map((p) => (
            <div key={p.id} className="flex items-center gap-2">
              {photoUrls[p.id] && <img src={photoUrls[p.id]} alt="" width={48} height={48} className="rounded-full object-cover" />}
              <input
                value={p.display_given_name}
                onChange={(e) => updatePerson(p.id, { display_given_name: e.target.value })}
                className="h-9 px-3 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-brand-500"
              />
              <input
                value={p.display_surname}
                onChange={(e) => updatePerson(p.id, { display_surname: e.target.value })}
                className="h-9 px-3 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-brand-500"
              />
              <select
                value={p.sex}
                onChange={(e) => updatePerson(p.id, { sex: e.target.value as ExtractedPerson['sex'] })}
                className="h-9 px-3 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-brand-500 bg-white"
              >
                <option value="MALE">Male</option>
                <option value="FEMALE">Female</option>
                <option value="OTHER">Other</option>
                <option value="UNKNOWN">Unknown</option>
              </select>
              <button onClick={() => removePerson(p.id)} className="text-sm text-red-600 hover:text-red-800">Remove</button>
            </div>
          ))}
        </div>
      </div>

      <div>
        <h3 className="text-sm font-semibold text-gray-900 mb-2">Family groups ({familyGroups.length})</h3>
        <div className="space-y-1">
          {familyGroups.map((fg) => (
            <div key={fg.id} className="text-sm text-gray-700">
              {fg.parent_ids.map((id) => personLabel(id, persons)).join(' & ')} → {Object.keys(fg.children).map((id) => personLabel(id, persons)).join(', ') || '(no children)'}
            </div>
          ))}
        </div>
      </div>

      <button
        onClick={handleFinalize}
        disabled={finalizing}
        className="px-4 py-2 bg-brand-500 text-white text-sm font-medium rounded-lg hover:bg-brand-600 disabled:opacity-50"
      >
        {finalizing ? 'Creating…' : 'Create Tree'}
      </button>
    </div>
  );
}
