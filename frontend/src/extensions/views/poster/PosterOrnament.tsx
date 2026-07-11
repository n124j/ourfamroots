/**
 * PosterOrnament — a simple mirrored flourish/scroll used under the poster title.
 */

import React from 'react';

export function PosterOrnament({ width = 260, color = '#4a4038' }: { width?: number; color?: string }) {
  const h = width * 0.14;
  return (
    <svg width={width} height={h} viewBox={`0 0 ${width} ${h}`} fill="none">
      <path
        d={`M2 ${h / 2} C ${width * 0.22} ${h * 0.1}, ${width * 0.32} ${h * 0.9}, ${width * 0.5} ${h / 2}`}
        stroke={color} strokeWidth={1.4} fill="none"
      />
      <path
        d={`M${width - 2} ${h / 2} C ${width * 0.78} ${h * 0.1}, ${width * 0.68} ${h * 0.9}, ${width * 0.5} ${h / 2}`}
        stroke={color} strokeWidth={1.4} fill="none"
      />
      <circle cx={width / 2} cy={h / 2} r={3} fill={color} />
    </svg>
  );
}
