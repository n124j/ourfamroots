import React, { useState, useEffect, useRef } from 'react';
import { useTranslation } from 'react-i18next';
import { useNameSearch, useRelationship } from '../useSearch';
import type { PersonHit, RelationshipPath, PathStep } from '../types';

interface Tree { id: string; name: string; }

interface Props {
  trees: Tree[];
}

export function RelationshipSearch({ trees }: Props) {
  const { t } = useTranslation();
  const [treeId, setTreeId]   = useState('');
  const [person1, setPerson1] = useState<PersonHit | null>(null);
  const [person2, setPerson2] = useState<PersonHit | null>(null);

  const enabled = !!(treeId && person1 && person2);
  const { data, isFetching } = useRelationship(
    treeId,
    person1?.person_id ?? '',
    person2?.person_id ?? '',
    enabled,
  );

  function handleTreeChange(id: string) {
    setTreeId(id);
    setPerson1(null);
    setPerson2(null);
  }

  return (
    <div className="space-y-6">
      {/* Tree selector */}
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1.5">{t('relationshipSearch.familyTree')}</label>
        <select
          value={treeId}
          onChange={(e) => handleTreeChange(e.target.value)}
          className="w-full rounded-lg border border-gray-300 bg-white px-3 py-2.5 text-sm shadow-sm
                     text-gray-700 focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
        >
          <option value="">{t('relationshipSearch.selectTree')}</option>
          {trees.map((t) => <option key={t.id} value={t.id}>{t.name}</option>)}
        </select>
      </div>

      {/* Person pickers */}
      <div className="grid grid-cols-1 sm:grid-cols-[1fr_auto_1fr] gap-4 items-end">
        <PersonPicker
          label={t('relationshipSearch.person1')}
          treeId={treeId}
          value={person1}
          onChange={setPerson1}
          placeholder={t('relationshipSearch.searchFirst')}
          excludeId={person2?.person_id}
        />
        <button
          type="button"
          onClick={() => { setPerson1(person2); setPerson2(person1); }}
          disabled={!person1 && !person2}
          className="mb-0.5 h-9 w-9 flex items-center justify-center rounded-full border border-gray-300
                     bg-white text-gray-500 shadow-sm transition-colors
                     hover:bg-indigo-50 hover:text-indigo-600 hover:border-indigo-300
                     disabled:opacity-30 disabled:cursor-not-allowed disabled:hover:bg-white disabled:hover:text-gray-500 disabled:hover:border-gray-300"
          title={t('relationshipSearch.swap')}
        >
          <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M7 16l-4-4m0 0l4-4m-4 4h18M17 8l4 4m0 0l-4 4m4-4H3" />
          </svg>
        </button>
        <PersonPicker
          label={t('relationshipSearch.person2')}
          treeId={treeId}
          value={person2}
          onChange={setPerson2}
          placeholder={t('relationshipSearch.searchSecond')}
          excludeId={person1?.person_id}
        />
      </div>

      {/* Divider with "vs" */}
      {(person1 || person2) && (
        <div className="flex items-center gap-3 -mt-2">
          <div className="flex-1 h-px bg-gray-200" />
          <span className="text-xs text-gray-400 font-medium">{t('relationshipSearch.vs')}</span>
          <div className="flex-1 h-px bg-gray-200" />
        </div>
      )}

      {/* Result */}
      {enabled && (
        isFetching
          ? <Spinner />
          : data
            ? <RelationshipResult
                rel={data.relationship}
                name1={personName(person1!)}
                name2={personName(person2!)}
              />
            : null
      )}
    </div>
  );
}

// ── Person picker ──────────────────────────────────────────────────────────────

function PersonPicker({
  label, treeId, value, onChange, placeholder, excludeId,
}: {
  label: string;
  treeId: string;
  value: PersonHit | null;
  onChange: (p: PersonHit | null) => void;
  placeholder: string;
  excludeId?: string;
}) {
  const { t } = useTranslation();
  const [query, setQuery]         = useState('');
  const [open, setOpen]           = useState(false);
  const [debounced, setDebounced] = useState('');
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const t = setTimeout(() => setDebounced(query), 300);
    return () => clearTimeout(t);
  }, [query]);

  const { data, isFetching } = useNameSearch(debounced, {}, treeId || undefined);

  const hits = data?.hits.filter((h) => h.person_id !== excludeId).slice(0, 6) ?? [];

  useEffect(() => {
    function onMouseDown(e: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    document.addEventListener('mousedown', onMouseDown);
    return () => document.removeEventListener('mousedown', onMouseDown);
  }, []);

  if (value) {
    return (
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1.5">{label}</label>
        <div className="flex items-center gap-2 px-3 py-2.5 rounded-lg border border-indigo-300 bg-indigo-50">
          <div className="h-7 w-7 rounded-full bg-indigo-200 flex items-center justify-center text-xs font-bold text-indigo-700 flex-shrink-0">
            {(value.given_name?.[0] ?? value.surname?.[0] ?? '?').toUpperCase()}
          </div>
          <p className="flex-1 text-sm font-medium text-gray-900 truncate min-w-0">
            {personName(value)}
          </p>
          <button
            onClick={() => onChange(null)}
            className="text-gray-400 hover:text-gray-700 flex-shrink-0 leading-none"
            title="Clear"
          >
            ✕
          </button>
        </div>
      </div>
    );
  }

  return (
    <div ref={containerRef}>
      <label className="block text-sm font-medium text-gray-700 mb-1.5">{label}</label>
      <div className="relative">
        <input
          type="search"
          value={query}
          onChange={(e) => { setQuery(e.target.value); setOpen(true); }}
          onFocus={() => debounced.length >= 2 && setOpen(true)}
          placeholder={treeId ? placeholder : t('relationshipSearch.selectTreeFirst')}
          disabled={!treeId}
          autoComplete="off"
          className="w-full rounded-lg border border-gray-300 bg-white py-2.5 pl-3 pr-3 text-sm
                     shadow-sm placeholder-gray-400 focus:border-indigo-500 focus:outline-none
                     focus:ring-1 focus:ring-indigo-500 disabled:bg-gray-50 disabled:text-gray-400"
        />
        {open && debounced.length >= 2 && (
          <div className="absolute z-50 mt-1 w-full rounded-lg border border-gray-200 bg-white py-1 shadow-lg">
            {isFetching ? (
              <p className="px-4 py-3 text-sm text-gray-400">{t('relationshipSearch.searching')}</p>
            ) : hits.length === 0 ? (
              <p className="px-4 py-3 text-sm text-gray-400">{t('relationshipSearch.noResults')}</p>
            ) : (
              hits.map((hit) => (
                <button
                  key={hit.person_id}
                  className="flex w-full items-center gap-3 px-4 py-2 text-left hover:bg-gray-50 transition-colors"
                  onMouseDown={() => { onChange(hit); setQuery(''); setOpen(false); }}
                >
                  <div className="h-7 w-7 rounded-full bg-indigo-100 flex items-center justify-center text-xs font-semibold text-indigo-700 flex-shrink-0">
                    {(hit.given_name?.[0] ?? hit.surname?.[0] ?? '?').toUpperCase()}
                  </div>
                  <span className="text-sm text-gray-900">{personName(hit)}</span>
                </button>
              ))
            )}
          </div>
        )}
      </div>
    </div>
  );
}

// ── Result ─────────────────────────────────────────────────────────────────────

function RelationshipResult({
  rel, name1, name2,
}: {
  rel: RelationshipPath;
  name1: string;
  name2: string;
}) {
  const { t } = useTranslation();
  if (!rel.found) {
    return (
      <div className="rounded-xl border border-dashed border-gray-300 py-12 text-center">
        <div className="text-3xl mb-3">🔍</div>
        <p className="font-medium text-gray-700">{t('relationshipSearch.noConnection')}</p>
        <p className="text-sm text-gray-400 mt-1">
          {t('relationshipSearch.notConnected', { name1, name2 })}
        </p>
      </div>
    );
  }

  const rawLabel = rel.relationship_label;
  const lineage = inferLineage(rel.path, rel.edge_labels ?? []);
  const label = rawLabel
    ? translateRelLabel(rawLabel, t, lineage)
    : `${rel.distance} ${rel.distance === 1 ? t('relationshipSearch.step') : t('relationshipSearch.steps')} ${t('relationshipSearch.apart')}`;

  return (
    <div className="rounded-xl border border-gray-200 bg-white shadow-sm overflow-hidden">
      {/* Header */}
      <div className="bg-indigo-50 border-b border-indigo-100 px-5 py-4">
        <p className="text-xs font-semibold text-indigo-500 uppercase tracking-wider">
          {t('relationshipSearch.relationship')}
        </p>
        <p className="text-xl font-bold text-gray-900 mt-1">{label}</p>
        <p className="text-sm text-gray-500 mt-0.5">
          {name1} → {name2} · {rel.distance} {rel.distance === 1 ? t('relationshipSearch.step') : t('relationshipSearch.steps')}
        </p>
      </div>

      {/* Connection path (horizontal chain) */}
      {rel.path.length > 0 && (
        <div className="px-5 py-5 border-b border-gray-100">
          <p className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-4">
            {t('relationshipSearch.connectionPath')}
          </p>
          <div className="flex flex-wrap items-center gap-2">
            {rel.path.map((step, i) => (
              <React.Fragment key={step.person_id}>
                <div className="flex items-center gap-2 bg-gray-50 border border-gray-200 rounded-lg px-3 py-1.5">
                  <div className="h-6 w-6 rounded-full bg-indigo-100 flex items-center justify-center text-xs font-bold text-indigo-700 flex-shrink-0">
                    {step.name[0]?.toUpperCase() ?? '?'}
                  </div>
                  <span className="text-sm text-gray-800 font-medium whitespace-nowrap">
                    {step.name}
                  </span>
                </div>
                {i < rel.path.length - 1 && (
                  <svg className="h-4 w-4 text-gray-400 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                  </svg>
                )}
              </React.Fragment>
            ))}
          </div>
        </div>
      )}

      {/* Tree structure view */}
      {rel.path.length > 0 && (
        <div className="px-5 py-6">
          <p className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-5">
            {t('relationshipSearch.familyTreeStructure')}
          </p>
          <RelationshipTreeView path={rel.path} edgeLabels={rel.edge_labels ?? []} />
        </div>
      )}
    </div>
  );
}

// ── Tree structure visualization ───────────────────────────────────────────────

const EDGE_STYLE_BASE: Record<string, { color: string; icon: string; labelKey: string }> = {
  parent:  { color: '#6366f1', icon: '↑', labelKey: 'relationshipSearch.parentOf' },
  child:   { color: '#10b981', icon: '↓', labelKey: 'relationshipSearch.childOf'  },
  spouse:  { color: '#8b5cf6', icon: '♦', labelKey: 'relationshipSearch.spouse'    },
  sibling: { color: '#f59e0b', icon: '↔', labelKey: 'relationshipSearch.sibling'   },
  relative:{ color: '#9ca3af', icon: '→', labelKey: 'relationshipSearch.relative'  },
};

function PersonBubble({
  step,
  highlight,
}: {
  step: PathStep;
  highlight?: 'start' | 'end' | 'ancestor' | 'none';
}) {
  const { t } = useTranslation();
  const styles = {
    start:    { wrap: 'bg-indigo-50 border-indigo-300',   avatar: 'bg-indigo-200 text-indigo-800',   text: 'text-indigo-800'  },
    end:      { wrap: 'bg-emerald-50 border-emerald-300', avatar: 'bg-emerald-200 text-emerald-800', text: 'text-emerald-800' },
    ancestor: { wrap: 'bg-amber-50 border-amber-300',     avatar: 'bg-amber-200 text-amber-800',     text: 'text-amber-800'   },
    none:     { wrap: 'bg-white border-gray-200',         avatar: 'bg-gray-100 text-gray-700',       text: 'text-gray-800'    },
  };
  const s = styles[highlight ?? 'none'];

  return (
    <div className={`flex items-center gap-2 px-3 py-2 rounded-lg border shadow-sm ${s.wrap}`}>
      <div className={`h-7 w-7 rounded-full flex items-center justify-center text-xs font-bold flex-shrink-0 ${s.avatar}`}>
        {step.name[0]?.toUpperCase() ?? '?'}
      </div>
      <span className={`text-sm font-medium whitespace-nowrap ${s.text}`}>{step.name}</span>
      {highlight === 'ancestor' && (
        <span className="text-[10px] font-semibold text-amber-600 bg-amber-100 border border-amber-200 px-1.5 py-0.5 rounded ml-1">
          {t('relationshipSearch.commonAncestor')}
        </span>
      )}
    </div>
  );
}

function BranchConnector({ label }: { label: string }) {
  const { t } = useTranslation();
  const e = EDGE_STYLE_BASE[label] ?? EDGE_STYLE_BASE.relative;
  return (
    <div className="flex flex-col items-center" style={{ gap: 2 }}>
      <div className="w-px h-3 bg-gray-300" />
      <div className="flex items-center gap-1">
        <span style={{ color: e.color, fontSize: 13, lineHeight: 1 }}>{e.icon}</span>
        <span className="text-[10px] text-gray-400">{t(e.labelKey)}</span>
      </div>
      <div className="w-px h-3 bg-gray-300" />
    </div>
  );
}

function RelationshipTreeView({
  path,
  edgeLabels,
}: {
  path: PathStep[];
  edgeLabels: string[];
}) {
  const { t } = useTranslation();
  if (path.length === 0) return null;

  if (path.length === 1) {
    return (
      <div className="flex justify-center">
        <PersonBubble step={path[0]} highlight="start" />
      </div>
    );
  }

  // Compute generation offset: parent = −1, child = +1, spouse/sibling = 0
  const gens: number[] = [0];
  let g = 0;
  for (const lbl of edgeLabels) {
    if (lbl === 'parent') g--;
    else if (lbl === 'child') g++;
    gens.push(g);
  }

  const minGen  = Math.min(...gens);
  const pivotIdx = gens.indexOf(minGen);
  const hasAscent  = pivotIdx > 0;
  const hasDescent = pivotIdx < path.length - 1;

  // ── Direct spouse / sibling (2 people, same generation) ──────────────────
  if (path.length === 2 && minGen === 0) {
    const e = EDGE_STYLE_BASE[edgeLabels[0]] ?? EDGE_STYLE_BASE.relative;
    return (
      <div className="flex items-center justify-center gap-4">
        <PersonBubble step={path[0]} highlight="start" />
        <div className="flex flex-col items-center gap-0.5">
          <span className="text-[10px] text-gray-400">{t(e.labelKey)}</span>
          <span style={{ color: e.color, fontSize: 20 }}>{e.icon}</span>
        </div>
        <PersonBubble step={path[1]} highlight="end" />
      </div>
    );
  }

  // ── V-shape: path ascends to a common ancestor then descends ─────────────
  if (hasAscent && hasDescent) {
    const ancestor = path[pivotIdx];

    // Left branch: closest-to-ancestor first → person1 at bottom
    const leftBranch  = path.slice(0, pivotIdx).reverse();
    // Flip labels because we're now showing ancestor → person1 (going down)
    const leftLabels  = edgeLabels.slice(0, pivotIdx).reverse().map((l) =>
      l === 'parent' ? 'child' : l === 'child' ? 'parent' : l
    );

    // Right branch: ancestor → person2 (going down)
    const rightBranch = path.slice(pivotIdx + 1);
    const rightLabels = edgeLabels.slice(pivotIdx);

    return (
      <div className="flex flex-col items-center">
        {/* Common ancestor centered at top */}
        <PersonBubble step={ancestor} highlight="ancestor" />

        {/* Horizontal bar connecting to both branches */}
        <div className="flex w-full" style={{ maxWidth: 520 }}>
          <div className="flex-1 flex flex-col items-center">
            <div className="w-px h-4 bg-gray-300" />
            <div className="w-full h-px bg-gray-300" />
          </div>
          <div className="flex-1 flex flex-col items-center">
            <div className="w-px h-4 bg-gray-300" />
            <div className="w-full h-px bg-gray-300" />
          </div>
        </div>

        {/* Two columns: left = path to person1, right = path to person2 */}
        <div
          className="grid gap-6 w-full"
          style={{ gridTemplateColumns: '1fr 1fr', maxWidth: 520 }}
        >
          {/* Left branch (ancestor → person 1) */}
          <div className="flex flex-col items-center gap-0">
            {leftBranch.map((p, i) => (
              <React.Fragment key={p.person_id}>
                <BranchConnector label={leftLabels[i] ?? 'child'} />
                <PersonBubble
                  step={p}
                  highlight={i === leftBranch.length - 1 ? 'start' : 'none'}
                />
              </React.Fragment>
            ))}
          </div>

          {/* Right branch (ancestor → person 2) */}
          <div className="flex flex-col items-center gap-0">
            {rightBranch.map((p, i) => (
              <React.Fragment key={p.person_id}>
                <BranchConnector label={rightLabels[i] ?? 'child'} />
                <PersonBubble
                  step={p}
                  highlight={i === rightBranch.length - 1 ? 'end' : 'none'}
                />
              </React.Fragment>
            ))}
          </div>
        </div>
      </div>
    );
  }

  // ── Simple vertical chain (all ascending or all descending) ───────────────
  return (
    <div className="flex flex-col items-center gap-0">
      {path.map((p, i) => (
        <React.Fragment key={p.person_id}>
          <PersonBubble
            step={p}
            highlight={i === 0 ? 'start' : i === path.length - 1 ? 'end' : 'none'}
          />
          {i < edgeLabels.length && <BranchConnector label={edgeLabels[i]} />}
        </React.Fragment>
      ))}
    </div>
  );
}

// ── Helpers ────────────────────────────────────────────────────────────────────

function personName(hit: PersonHit): string {
  return [hit.given_name, hit.surname].filter(Boolean).join(' ') || '?';
}

const LINEAGE_WORDS = new Set([
  'Uncle', 'Aunt', 'Nephew', 'Niece',
  'Great-uncle', 'Great-aunt', 'Great-nephew', 'Great-niece',
  'Grandfather', 'Grandmother', 'Grandson', 'Granddaughter',
]);

function inferLineage(
  path: PathStep[],
  edgeLabels: string[],
): 'paternal' | 'maternal' | null {
  if (path.length < 3) return null;

  const siblingIdx = edgeLabels.indexOf('sibling');
  if (siblingIdx !== -1) {
    const hasPrev = siblingIdx > 0 && (edgeLabels[siblingIdx - 1] === 'parent' || edgeLabels[siblingIdx - 1] === 'child');
    const hasNext = siblingIdx < edgeLabels.length - 1 && (edgeLabels[siblingIdx + 1] === 'parent' || edgeLabels[siblingIdx + 1] === 'child');
    let connectingPerson: PathStep | undefined;
    if (hasPrev && hasNext) {
      connectingPerson = path[siblingIdx] ?? path[siblingIdx + 1];
    } else if (hasPrev) {
      connectingPerson = path[siblingIdx];
    } else if (hasNext) {
      connectingPerson = path[siblingIdx + 1];
    }
    if (connectingPerson) {
      const sex = (connectingPerson.sex ?? '').toUpperCase();
      if (sex === 'MALE') return 'paternal';
      if (sex === 'FEMALE') return 'maternal';
    }
    return null;
  }

  if (path.length === 3 && edgeLabels.every((l) => l === 'parent' || l === 'child')) {
    const mid = path[1];
    if (!mid) return null;
    const sex = (mid.sex ?? '').toUpperCase();
    if (sex === 'MALE') return 'paternal';
    if (sex === 'FEMALE') return 'maternal';
  }

  return null;
}

function translateRelLabel(
  raw: string,
  t: (key: string, opts?: Record<string, string>) => string,
  lineage: 'paternal' | 'maternal' | null,
): string {
  const wk = (w: string) => {
    if (lineage && LINEAGE_WORDS.has(w)) {
      const suffixed = t(`relationshipSearch.words.${w}_${lineage}`, { defaultValue: '' });
      if (suffixed) return suffixed;
    }
    return t(`relationshipSearch.words.${w}`, { defaultValue: w });
  };
  const full = wk(raw);
  if (full !== raw) return full;
  const translated = raw
    .split(/( \/ | ↔ |\/)/)
    .map((part) => /^ \/ $|^ ↔ $|^\/$/.test(part) ? '/' : wk(part.trim()))
    .join('');
  return translated;
}

function Spinner() {
  return (
    <div className="flex justify-center py-10">
      <div className="w-6 h-6 border-2 border-indigo-500 border-t-transparent rounded-full animate-spin" />
    </div>
  );
}
