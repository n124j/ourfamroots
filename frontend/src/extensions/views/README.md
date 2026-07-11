# View Extensions

Drop-in view plugins for the family tree canvas. Each subfolder is auto-discovered
at build time — no core files need to change.

## Adding a new view

1. Create a folder: `src/extensions/views/<your-view>/`
2. Create `index.ts` that default-exports a `ViewPlugin` object
3. Optionally add custom components in the same folder
4. Restart the dev server (Vite picks up new glob entries on restart)

### Minimal example (layout-only view)

```
src/extensions/views/my-view/
  index.ts
```

```typescript
// index.ts
import type { ViewPlugin } from '../registry';

const plugin: ViewPlugin = {
  id: 'my-view',
  label: 'My View',
  description: 'A custom tree layout',
  layoutOverrides: {
    mode: 'compact',
    nodeVGap: 120,
    nodeHGap: 50,
  },
};

export default plugin;
```

### Custom PersonNode renderer

```
src/extensions/views/my-view/
  index.ts
  MyPersonNode.tsx
```

```typescript
// index.ts
import type { ViewPlugin } from '../registry';
import { MyPersonNode } from './MyPersonNode';

const plugin: ViewPlugin = {
  id: 'my-view',
  label: 'My View',
  description: 'Custom card rendering',
  PersonNodeComponent: MyPersonNode as any,
  layoutOverrides: { personNodeHeight: 160 },
};

export default plugin;
```

### Full canvas replacement (e.g. chart/timeline)

```typescript
// index.ts
import type { ViewPlugin } from '../registry';
import { MyCanvas } from './MyCanvas';

const plugin: ViewPlugin = {
  id: 'my-chart',
  label: 'My Chart',
  description: 'Completely replaces the React Flow canvas',
  CanvasComponent: MyCanvas,
};

export default plugin;
```

## ViewPlugin interface

| Field | Type | Description |
|-------|------|-------------|
| `id` | `string` | Unique ID stored in state |
| `label` | `string` | Dropdown display name |
| `description` | `string` | Dropdown subtitle |
| `CanvasComponent` | `Component` | Replaces the entire React Flow canvas |
| `PersonNodeComponent` | `Component` | Replaces the person card rendering |
| `FamilyGroupNodeComponent` | `Component` | Replaces the union junction rendering |
| `orthogonalEdges` | `boolean` | Use right-angle edge routing |
| `hideFamilyGroupNode` | `boolean` | Make the union junction invisible/minimal |
| `layoutOverrides.mode` | `LayoutMode` | Force a specific layout algorithm |
| `layoutOverrides.personNodeHeight` | `number` | Override card height for spacing |
| `layoutOverrides.nodeVGap` | `number` | Vertical gap between generations |
| `layoutOverrides.nodeHGap` | `number` | Horizontal gap between siblings |

## Removing a view

Delete the folder. Restart the dev server.

## Current views

- `default/` — Standard modern tree (no overrides)
- `heritage/` — Vintage parchment style with serif text and sepia photos
- `timeline/` — Horizontal year-axis timeline with person bars
- `text-pedigree/` — Compact indented text ancestor tree (connector-line style)
- `poster/` — Decorative printable ancestor poster with a tree silhouette
