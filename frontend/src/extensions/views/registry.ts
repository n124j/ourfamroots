/**
 * View Plugin Registry — auto-discovers view extensions.
 *
 * HOW TO ADD A NEW VIEW:
 *   1. Create a folder under  src/extensions/views/<your-view>/
 *   2. Export a default object satisfying the ViewPlugin interface from index.ts
 *   3. That's it — the registry auto-discovers it via import.meta.glob
 *
 * No core files need to change. The dropdown, node rendering, and canvas
 * all read from this registry at runtime.
 */

import type { ComponentType } from 'react';
import type { NodeProps } from 'reactflow';
import type {
  ApiTreeGraph,
  PersonNodeData,
  FamilyGroupNodeData,
  LayoutMode,
} from '@features/tree/types';
import type { CanvasTheme } from '@store/theme.store';

// ── Plugin interface ────────────────────────────────────────────────────

export interface ViewPlugin {
  /** Unique identifier (used in store state) */
  id: string;
  /** Display label in dropdown */
  label: string;
  /** Short description shown below the label */
  description: string;
  /** 'builtin' shows in View Styles dropdown, 'extension' shows in Extensions dropdown */
  category?: 'builtin' | 'extension';

  /**
   * If provided, replaces the entire React Flow canvas with this component.
   * Used for fundamentally different views like Timeline.
   */
  CanvasComponent?: ComponentType<{ graph: ApiTreeGraph }>;

  /**
   * If provided, replaces the default PersonNode rendering.
   * Receives the standard NodeProps + the active theme.
   */
  PersonNodeComponent?: ComponentType<
    NodeProps<PersonNodeData> & { theme: CanvasTheme }
  >;

  /**
   * If provided, replaces the default FamilyGroupNode rendering.
   */
  FamilyGroupNodeComponent?: ComponentType<
    NodeProps<FamilyGroupNodeData> & { theme: CanvasTheme }
  >;

  /** Use orthogonal (right-angle) edge routing instead of bezier/straight */
  orthogonalEdges?: boolean;

  /** Hide the family-group union dot/circle */
  hideFamilyGroupNode?: boolean;

  /** Layout overrides applied when this view is active */
  layoutOverrides?: {
    mode?: LayoutMode;
    personNodeHeight?: number;
    nodeVGap?: number;
    nodeHGap?: number;
  };
}

// ── Auto-discovery ──────────────────────────────────────────────────────

const pluginModules = import.meta.glob<{ default: ViewPlugin }>(
  './**/index.ts',
  { eager: true },
);

const _plugins: ViewPlugin[] = [];

for (const [path, mod] of Object.entries(pluginModules)) {
  if (mod.default?.id) {
    _plugins.push(mod.default);
  } else {
    console.warn(`[ViewRegistry] Skipping ${path}: no default export with id`);
  }
}

_plugins.sort((a, b) => a.label.localeCompare(b.label));

/** All registered view plugins (sorted alphabetically). */
export const viewPlugins: readonly ViewPlugin[] = _plugins;

/** Built-in view styles (Default, Heritage, etc.) */
export const builtinViews: readonly ViewPlugin[] = _plugins.filter(
  (p) => p.category === 'builtin',
);

/** Third-party / extension views (Timeline, Grid Cards, etc.) */
export const extensionViews: readonly ViewPlugin[] = _plugins.filter(
  (p) => p.category === 'extension',
);

/** Quick lookup by plugin id. */
export const viewPluginMap = new Map<string, ViewPlugin>(
  _plugins.map((p) => [p.id, p]),
);

/** Get a plugin by id, or undefined. */
export function getViewPlugin(id: string): ViewPlugin | undefined {
  return viewPluginMap.get(id);
}
