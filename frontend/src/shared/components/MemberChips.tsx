/**
 * MemberChips — shows a handful of member names inline (as small pills) with
 * a "+N" overflow chip when there are more than fit. Used anywhere an admin
 * table previously just showed a bare count (namespaces, permission groups,
 * user groups, subscriptions).
 */
import React from 'react';

export function MemberChips({
  names,
  total,
  emptyLabel = 'None',
}: {
  names: string[];
  total: number;
  emptyLabel?: string;
}) {
  if (total === 0) {
    return <span className="text-xs text-gray-400">{emptyLabel}</span>;
  }

  const remaining = total - names.length;

  return (
    <div className="flex flex-wrap items-center gap-1">
      {names.map((name, i) => (
        <span
          key={i}
          className="inline-flex items-center px-2 py-0.5 rounded-full bg-gray-100 text-gray-700 text-xs whitespace-nowrap"
        >
          {name}
        </span>
      ))}
      {remaining > 0 && (
        <span className="inline-flex items-center px-2 py-0.5 rounded-full bg-gray-200 text-gray-600 text-xs font-medium">
          +{remaining}
        </span>
      )}
    </div>
  );
}
