/**
 * RelationshipEdge — Person-to-Person edge for a non-family-group
 * relationship (Godparent/Guardian/Mentor/Custom).
 *
 * Unlike UnionEdge/ParentChildEdge, this is a pure visual overlay: its
 * source/target ids are never fed into the layout algorithm (see
 * TreeCanvas.tsx's `edges` useMemo, which merges these in *after* layout
 * has already positioned every node). One fixed violet dashed style is
 * used for all relationship types — the label text carries the
 * distinction, not the stroke.
 */

import React, { memo } from 'react';
import { BaseEdge, EdgeLabelRenderer, getBezierPath, type EdgeProps } from 'reactflow';
import type { RelationshipEdgeData } from '../../types';

// Exported for RelationshipEdge.style.test.ts — a single fixed style is used
// for every relationship type (label text carries the distinction instead).
export const STROKE_COLOR = '#8b5cf6';
export const DASH_ARRAY = '4 3';

export function relationshipEdgeStrokeWidth(selected: boolean): number {
  return selected ? 3 : 1.5;
}

function RelationshipEdgeComponent({
  id,
  sourceX,
  sourceY,
  targetX,
  targetY,
  sourcePosition,
  targetPosition,
  data,
  markerEnd,
  selected,
}: EdgeProps<RelationshipEdgeData>) {
  const label = data?.label;

  const [path, labelX, labelY] = getBezierPath({
    sourceX,
    sourceY,
    sourcePosition,
    targetX,
    targetY,
    targetPosition,
    curvature: 0.25,
  });

  return (
    <>
      <BaseEdge
        id={id}
        path={path}
        markerEnd={markerEnd}
        style={{
          stroke: STROKE_COLOR,
          strokeWidth: relationshipEdgeStrokeWidth(!!selected),
          strokeDasharray: DASH_ARRAY,
          filter: selected ? 'drop-shadow(0 0 4px #8b5cf6aa)' : undefined,
        }}
      />

      {label && (
        <EdgeLabelRenderer>
          <div
            className="absolute pointer-events-none"
            style={{ transform: `translate(-50%, -50%) translate(${labelX}px,${labelY}px)` }}
          >
            <span
              className="px-1 py-0.5 text-[9px] font-medium rounded border shadow-sm"
              style={{ background: '#f5f3ff', borderColor: STROKE_COLOR, color: STROKE_COLOR }}
            >
              {label}
            </span>
          </div>
        </EdgeLabelRenderer>
      )}
    </>
  );
}

export const RelationshipEdge = memo(RelationshipEdgeComponent);
RelationshipEdge.displayName = 'RelationshipEdge';
export default RelationshipEdge;
