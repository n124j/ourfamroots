/**
 * FamilyGroupNode — the junction node between parents and children.
 *
 * Rendered as a small circle with a union-type icon.
 * Parents connect INTO this node; children connect OUT of it.
 *
 *   [PersonNode] ──union-edge──▶ (◉) ──parent-child-edge──▶ [PersonNode]
 *   [PersonNode] ──union-edge──▶ (◉)
 */

import React, { memo } from 'react';
import { Handle, Position, type NodeProps } from 'reactflow';
import type { FamilyGroupNodeData } from '../../types';
import { FAMILY_NODE_SIZE } from '../../types';
import { useThemeStore } from '@store/theme.store';

const UNION_ICONS: Record<FamilyGroupNodeData['unionType'], string> = {
  MARRIAGE: '💍',
  PARTNERSHIP: '🤝',
  COHABITATION: '🏠',
  UNKNOWN: '○',
};

const UNION_COLORS: Record<FamilyGroupNodeData['unionType'], string> = {
  MARRIAGE: '#f59e0b',
  PARTNERSHIP: '#10b981',
  COHABITATION: '#6366f1',
  UNKNOWN: '#94a3b8',
};

const UNION_TOOLTIPS: Record<FamilyGroupNodeData['unionType'], string> = {
  MARRIAGE: 'Marriage',
  PARTNERSHIP: 'Partnership',
  COHABITATION: 'Cohabitation',
  UNKNOWN: 'Union',
};

function FamilyGroupNodeComponent({ data, selected }: NodeProps<FamilyGroupNodeData>) {
  const { unionType, showUnionIcon } = data;
  const color   = UNION_COLORS[unionType];
  const icon    = UNION_ICONS[unionType];
  const nodeBg  = useThemeStore((s) => s.theme.nodeBg);

  return (
    <>
      {/* Handles — parents connect in from left/right (LR) or top (TB) */}
      <Handle
        type="target"
        position={Position.Top}
        id="parent-top"
        className="!opacity-0 !pointer-events-none"
      />
      <Handle
        type="target"
        position={Position.Left}
        id="parent-left"
        className="!opacity-0 !pointer-events-none"
      />
      <Handle
        type="target"
        position={Position.Right}
        id="parent-right"
        className="!opacity-0 !pointer-events-none"
      />

      <div
        className="relative flex items-center justify-center rounded-full transition-all select-none group/fg"
        style={{
          width: FAMILY_NODE_SIZE,
          height: FAMILY_NODE_SIZE,
          background: nodeBg,
          border: `2px solid ${selected ? color : color + '99'}`,
          boxShadow: selected
            ? `0 0 0 4px ${color}33`
            : `0 1px 3px rgba(0,0,0,0.1)`,
          cursor: 'pointer',
        }}
        title={`${UNION_TOOLTIPS[unionType]} — click to add a child`}
      >
        {/* Normal icon */}
        <span
          className="transition-opacity group-hover/fg:opacity-0"
          style={{ position: 'absolute', display: 'flex', alignItems: 'center', justifyContent: 'center' }}
        >
          {showUnionIcon ? (
            <span className="text-[8px] leading-none">
              {unionType === 'UNKNOWN' ? (
                <span style={{ color, fontSize: 10 }}>○</span>
              ) : icon}
            </span>
          ) : (
            <div className="w-2 h-2 rounded-full" style={{ background: color }} />
          )}
        </span>

        {/* Hover: show + */}
        <span
          className="opacity-0 group-hover/fg:opacity-100 transition-opacity font-bold leading-none"
          style={{ fontSize: 14, color, position: 'absolute' }}
        >
          +
        </span>
      </div>

      {/* Children connect out from bottom */}
      <Handle
        type="source"
        position={Position.Bottom}
        className="!opacity-0 !pointer-events-none"
      />
    </>
  );
}

export const FamilyGroupNode = memo(FamilyGroupNodeComponent);
FamilyGroupNode.displayName = 'FamilyGroupNode';
export default FamilyGroupNode;
