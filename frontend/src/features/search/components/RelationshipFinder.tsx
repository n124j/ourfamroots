/**
 * RelationshipFinder — panel that lets the user pick two people and
 * displays the shortest relationship path between them.
 */
import React, { useState } from 'react';
import { useRelationship } from '../useSearch';
import { SearchBar } from './SearchBar';
import type { PersonHit } from '../types';

interface Props {
  treeId: string;
  defaultPersonId?: string;    // pre-select one side (e.g. currently-viewed person)
  defaultPersonName?: string;
}

export function RelationshipFinder({ treeId, defaultPersonId, defaultPersonName }: Props) {
  const [person1, setPerson1] = useState<{ id: string; name: string } | null>(
    defaultPersonId && defaultPersonName
      ? { id: defaultPersonId, name: defaultPersonName }
      : null
  );
  const [person2, setPerson2] = useState<{ id: string; name: string } | null>(null);

  const { data, isFetching, isError } = useRelationship(
    treeId,
    person1?.id ?? '',
    person2?.id ?? '',
    !!person1 && !!person2,
  );

  return (
    <div className="space-y-4 rounded-xl border border-gray-200 bg-white p-4 shadow-sm">
      <h3 className="font-semibold text-gray-900">Relationship Finder</h3>

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
        {/* Person 1 */}
        <PersonSelector
          label="First person"
          selected={person1}
          treeId={treeId}
          onSelect={(h) => setPerson1({ id: h.person_id, name: formatName(h) })}
          onClear={() => setPerson1(null)}
        />

        {/* Person 2 */}
        <PersonSelector
          label="Second person"
          selected={person2}
          treeId={treeId}
          onSelect={(h) => setPerson2({ id: h.person_id, name: formatName(h) })}
          onClear={() => setPerson2(null)}
        />
      </div>

      {/* Result */}
      {isFetching && (
        <div className="flex items-center gap-2 text-sm text-gray-500">
          <span className="h-4 w-4 animate-spin rounded-full border-2 border-indigo-500 border-t-transparent" />
          Finding relationship…
        </div>
      )}

      {isError && (
        <p className="text-sm text-red-500">Could not compute relationship. Please try again.</p>
      )}

      {data && !isFetching && (
        <RelationshipResult data={data.relationship} />
      )}
    </div>
  );
}

// ── Person selector ────────────────────────────────────────────────────────────

function PersonSelector({
  label,
  selected,
  treeId,
  onSelect,
  onClear,
}: {
  label: string;
  selected: { id: string; name: string } | null;
  treeId: string;
  onSelect: (h: PersonHit) => void;
  onClear: () => void;
}) {
  return (
    <div>
      <p className="mb-1 text-xs font-medium text-gray-500 uppercase tracking-wide">{label}</p>
      {selected ? (
        <div className="flex items-center gap-2 rounded-lg border border-indigo-300 bg-indigo-50 px-3 py-2">
          <span className="flex-1 truncate text-sm font-medium text-indigo-800">
            {selected.name}
          </span>
          <button
            onClick={onClear}
            className="text-indigo-400 hover:text-indigo-600"
            aria-label="Clear"
          >
            ×
          </button>
        </div>
      ) : (
        <SearchBar
          treeId={treeId}
          placeholder={`Search ${label}…`}
          onSelect={onSelect}
        />
      )}
    </div>
  );
}

// ── Relationship result ────────────────────────────────────────────────────────

function RelationshipResult({ data }: { data: import('../types').RelationshipPath }) {
  if (!data.found) {
    return (
      <div className="rounded-lg bg-yellow-50 p-3 text-sm text-yellow-800">
        No relationship found within the search depth. They may be unrelated in this tree.
      </div>
    );
  }

  if (data.distance === 0) {
    return (
      <div className="rounded-lg bg-gray-50 p-3 text-sm text-gray-700">
        Same person.
      </div>
    );
  }

  return (
    <div className="space-y-3">
      {/* Label */}
      <div className="rounded-lg bg-green-50 px-4 py-3">
        <p className="text-sm font-medium text-green-900">
          {data.relationship_label ?? `${data.distance} hops apart`}
        </p>
        {data.alternative_label && (
          <p className="text-xs text-green-700 mt-0.5">
            Also known as: <span className="font-medium">{data.alternative_label}</span>
          </p>
        )}
        <p className="text-xs text-green-700 mt-0.5">
          {data.distance} connection{data.distance !== 1 ? 's' : ''} between them
        </p>
      </div>

      {/* Path chain */}
      <div>
        <p className="mb-2 text-xs font-medium text-gray-500 uppercase tracking-wide">Path</p>
        <ol className="relative border-l border-indigo-200 pl-5 space-y-2">
          {data.path.map((step, i) => (
            <li key={step.person_id} className="relative">
              <span className="absolute -left-[1.35rem] flex h-5 w-5 items-center justify-center rounded-full bg-indigo-100 text-xs font-bold text-indigo-600">
                {i + 1}
              </span>
              <span className="text-sm text-gray-800">{step.name || 'Unknown'}</span>
            </li>
          ))}
        </ol>
      </div>
    </div>
  );
}

// ── Helpers ────────────────────────────────────────────────────────────────────

function formatName(h: PersonHit): string {
  return [h.given_name, h.surname].filter(Boolean).join(' ') || 'Unknown';
}
