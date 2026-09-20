import React, { useState } from 'react';
import { post } from '@api/client';
import { useAiTreeImportJob } from './useAiTreeImportJob';
import type { ExtractedFamilyGroup, ExtractedPerson } from './types';

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

  if (finalizeResult) {
    return (
      <div>
        <p>Tree "{finalizeResult.tree_name}" created.</p>
        <a href={`/trees/${finalizeResult.tree_id}`}>Open tree</a>
        <button onClick={reset}>Import another screenshot</button>
      </div>
    );
  }

  if (status === 'idle') {
    return (
      <div>
        <input
          type="file"
          accept="image/jpeg,image/png,image/webp"
          onChange={(e) => e.target.files?.[0] && uploadScreenshot(e.target.files[0])}
        />
      </div>
    );
  }

  if (status === 'uploading' || status === 'processing') {
    return <p>{status === 'uploading' ? 'Uploading screenshot…' : 'Extracting family tree…'}</p>;
  }

  if (status === 'error') {
    return (
      <div>
        <p>{errorMessage}</p>
        <button onClick={reset}>Try again</button>
      </div>
    );
  }

  return (
    <div>
      <label>
        Tree name
        <input value={treeName} onChange={(e) => setTreeName(e.target.value)} />
      </label>

      <h3>People ({persons.length})</h3>
      {persons.map((p) => (
        <div key={p.id}>
          {photoUrls[p.id] && <img src={photoUrls[p.id]} alt="" width={48} height={48} />}
          <input
            value={p.display_given_name}
            onChange={(e) => updatePerson(p.id, { display_given_name: e.target.value })}
          />
          <input
            value={p.display_surname}
            onChange={(e) => updatePerson(p.id, { display_surname: e.target.value })}
          />
          <select value={p.sex} onChange={(e) => updatePerson(p.id, { sex: e.target.value as ExtractedPerson['sex'] })}>
            <option value="MALE">Male</option>
            <option value="FEMALE">Female</option>
            <option value="OTHER">Other</option>
            <option value="UNKNOWN">Unknown</option>
          </select>
          <button onClick={() => removePerson(p.id)}>Remove</button>
        </div>
      ))}

      <h3>Family groups ({familyGroups.length})</h3>
      {familyGroups.map((fg) => (
        <div key={fg.id}>
          {fg.parent_ids.map((id) => personLabel(id, persons)).join(' & ')} → {Object.keys(fg.children).map((id) => personLabel(id, persons)).join(', ') || '(no children)'}
        </div>
      ))}

      <button onClick={handleFinalize} disabled={finalizing}>
        {finalizing ? 'Creating…' : 'Create Tree'}
      </button>
    </div>
  );
}
