# Family Tree Visualization — Architecture

## Library Comparison

### D3.js

| Criterion | Score | Notes |
|---|---|---|
| React integration | ⚠️ Poor | Imperative DOM mutations conflict with React's virtual DOM |
| Custom nodes | ✅ Excellent | Full SVG/Canvas control |
| Built-in zoom/pan | ✅ | d3-zoom, but wired manually |
| Drag & drop | ⚠️ Manual | d3-drag, significant boilerplate |
| Large graph perf | ✅ | Canvas renderer possible |
| Layout algorithms | ✅ | dagre-d3, cola, elk |
| TypeScript DX | ⚠️ | Types exist but loose |
| Mobile (touch) | ⚠️ Manual | Touch events on d3-zoom work but fragile |
| Learning curve | ❌ High | |

**Verdict:** Maximum flexibility but requires building an entire React binding layer. Wrong tool when React is the framework.

---

### Cytoscape.js

| Criterion | Score | Notes |
|---|---|---|
| React integration | ⚠️ | `react-cytoscapejs` wrapper, not truly React-native |
| Custom nodes | ⚠️ | Canvas-only; HTML overlays are a hack |
| Built-in zoom/pan | ✅ | First-class |
| Drag & drop | ✅ | First-class |
| Large graph perf | ✅ Excellent | Canvas renderer, WebGL via Cytoscape GL |
| Layout algorithms | ✅ Excellent | Cola, dagre, elk, breadthfirst, concentric |
| TypeScript DX | ✅ | Official types |
| Mobile (touch) | ✅ | First-class |
| Learning curve | Medium | |

**Verdict:** Best performance ceiling for 10,000+ nodes, but HTML-in-canvas custom nodes are painful. Not idiomatic React.

---

### React Flow (v11 — `reactflow`)

| Criterion | Score | Notes |
|---|---|---|
| React integration | ✅ Excellent | Nodes are React components — full ecosystem |
| Custom nodes | ✅ Excellent | Arbitrary JSX inside every node |
| Built-in zoom/pan | ✅ | Zero config |
| Drag & drop | ✅ | Zero config, with callbacks |
| Large graph perf | ✅ | Viewport culling; nodes outside viewport not rendered |
| Layout algorithms | ✅ | dagre, elk via adapters |
| TypeScript DX | ✅ Excellent | First-class TS, generic node/edge data |
| Mobile (touch) | ✅ | Built-in touch handling |
| Learning curve | ✅ Low | |

**Verdict:** Best fit for this stack. React-native, zero infrastructure overhead, nodes are plain React components.

---

## Recommendation: **React Flow + dagre**

React Flow wins on every criterion that matters for OurFamRoots:

1. **Nodes are React** — `PersonNode` uses the full design system (Avatar, Badge, Tailwind). No canvas hacks.
2. **Zoom / pan / drag** — built-in, battle-tested, works on mobile.
3. **Viewport culling** — unlimited generations without performance collapse. Only visible nodes render.
4. **dagre layout** — proven for hierarchical graphs, supports TB/LR, gap control, and the bipartite person↔family-group graph.
5. **TypeScript** — generic `Node<Data>` and `Edge<Data>` types align perfectly with our domain entities.

Cytoscape is the right choice only if node count exceeds ~5,000 AND custom node styling is unimportant. For a genealogy SaaS with rich person cards, React Flow is correct.

---

## Graph Model

The backend uses a **bipartite graph**: `PersonNode` ↔ `FamilyGroupNode`. The canvas mirrors this exactly.

```
[PersonNode]──parent-member──▶[FamilyGroupNode]──child-member──▶[PersonNode]
[PersonNode]──parent-member──▶[FamilyGroupNode]
```

This naturally handles:
- **Multiple spouses**: one person appears as parent-member in multiple FamilyGroupNodes
- **Adoption**: child-member edge carries `parentage_type = ADOPTIVE` → rendered as dashed line
- **Step relations**: `parentage_type = STEP` → dotted line
- **Childless couples**: FamilyGroupNode with two parents, zero children

---

## Rendering Strategy

```
API Response (persons + family_groups)
        │
        ▼
  useTreeTransform()          ← converts domain data to ReactFlow nodes/edges
        │
        ▼
  useTreeLayout()             ← applies chosen layout algorithm
        │
        ▼
  useExpandCollapse()         ← hides/shows subtrees
        │
        ▼
  <ReactFlow>                 ← renders with zoom/pan/drag
        │
   ┌────┴────┐
   │         │
PersonNode  FamilyGroupNode   ← custom React components
   │         │
ParentChildEdge  UnionEdge   ← custom SVG path edges
```

---

## Layout Algorithms

| `LayoutMode` | Algorithm | Use Case |
| --- | --- | --- |
| `generation` | dagre `rankdir: TB` | Oldest generation at top; each subsequent generation one rank lower. Simple, fast, ignores marriage coupling. |
| `vertical` | `familyTreeLayout` (custom bottom-up) | Multi-marriage-aware; spouses placed adjacent, children centred below their family group. Default for deep genealogies. |
| `horizontal` | dagre `rankdir: LR` | Left-to-right flow; useful on wide displays or small trees. |
| `ancestor` | Custom BFS upward from focus | Shows all ancestors of the focus person going up. |
| `descendant` | Custom BFS downward from focus | Shows all descendants of the focus person going down. |
| `ancestor-family` | `familyTreeLayout` (ancestor subgraph) | Ancestors with their spouses kept adjacent. |
| `descendant-family` | `familyTreeLayout` (descendant subgraph) | Descendants with their spouses kept adjacent. |
| `fan` | Custom polar coordinates (180°) | Classic semicircular genealogy wheel up to 4 generations. |
| `ancestry-fan` | Single custom `AncestryFanNode` | Full 360° ancestry fan rendered inside a single React Flow node. |
| `pedigree` | `pedigreeChartLayout` (horizontal binary tree) | Focus person on the left, ancestors expanding right. |
| `compact` | `familyTreeLayout` (tighter spacing) | Traditional family-tree layout with reduced gaps. Spouses adjacent, children centred below. |

---

## Canvas Controls — Reset Layout

The **Reset Layout (↺)** button calls `bumpLayoutReset()` in the canvas store, which increments `layoutResetKey`. The effect in `TreeCanvas` that watches this key recomputes the layout from the current graph and replaces `displayNodes` — it does **not** call `fitView`. This means node positions are reset to their algorithmic defaults while the viewport pan/zoom remains where the user left it.

Switching to a different layout mode (via any layout-mode button) still calls `fitView` after layout, so the whole tree centres in the viewport on mode change.

### Union Ordinal Labels

When a person has more than one union (e.g., two marriages), the edges are labelled with ordinals: **2nd Marriage**, **3rd Marriage**, etc. The first union carries no label. Labels appear only on the edge with the highest ordinal (i.e., the most recent marriage label is shown). The label text is derived from `unionOrdinal` on `UnionEdgeData` and can be overridden per family-group via `customLabel`.

---

## Performance Budget

| Nodes | Strategy |
|---|---|
| < 200 | Render all; no optimisation needed |
| 200–1,000 | Expand/collapse; viewport culling |
| 1,000–5,000 | Progressive loading per branch; simplified nodes at zoom < 0.3 |
| > 5,000 | Cytoscape GL (future v2 feature) |

---

## TreeCanvasHandle — Imperative API

`TreeCanvas` exposes a ref handle (`TreeCanvasHandle`) for parent components to call canvas operations imperatively:

| Method | Description |
|---|---|
| `getPositions()` | Returns a `Record<id, {x,y}>` snapshot of all current node positions |
| `loadPositions(positions)` | Restores a saved layout snapshot and fits the view |
| `scrollToNode(personId)` | Smooth fly-to animation centred on a single person node |
| `refitView()` | Fits all visible nodes into the viewport with a 500 ms animation |
| `exportPdf()` | Rasterises the canvas via `html-to-image` and downloads a PDF |

---

## Ctrl+Space Member Search

A floating search bar appears at the bottom-centre of the canvas when the user presses `Ctrl+Space`.

- **Trigger**: `keydown` listener on `window` checks `e.ctrlKey && e.code === 'Space'`
- **Dismiss**: second `Ctrl+Space` or `Escape`
- **Filter**: filters `graph.persons` by full name as the user types (up to 10 results)
- **Navigation**: clicking a result or pressing `Enter` calls `canvasRef.current.scrollToNode(personId)` and closes the bar
- Implemented in `FamilyTreePage.tsx`; no canvas-layer changes required

---

## Ctrl+Drag on Union Nodes (Ring Drag)

By default, `FamilyGroupNode` has `draggable: false` (set in `useTreeTransform.ts`) to prevent accidental drags when clicking to add children.

When the user holds `Ctrl`, a `keydown/keyup` listener (`ctrlHeld` state) flips every `family-group` node to `draggable: true` via `useMemo` on `reactFlowNodes`. The union node can then be dragged freely; **no companion nodes move with it** (the ring union moves alone). A banner hint is shown at the top of the canvas while Ctrl is held.

The existing Ctrl+drag behaviour for `PersonNode` (move with all visible descendants) is unchanged.

---

## Immediate Tree Updates after Add / Remove

When a child is created or removed via a Ring union, the following chain ensures the canvas updates immediately without a viewport jump:

1. `handleAdded` in `FamilyTreePage` calls `await refetch()` (React Query forced fetch)
2. After the fetch resolves, all person IDs in the new graph are added to `expandedNodeIds` via `useCanvasStore.getState().setExpandedNodeIds(next)` — this is what makes newly-created persons visible (they would otherwise be absent from the expand set)
3. `useTreeLayout` re-runs (`useMemo` on `graph` + `expandedNodeIds`) → new layout computed
4. The `useEffect` in `TreeCanvas` detects the changed layout key → `setDisplayNodes(layoutNodes)`
5. React Flow renders the new/removed node in-place; the viewport is not changed

---

## Instant Edit Reflection (Data-Patch)

When a person is edited (name, living/deceased status, photo), the layout positions do not change. The `useEffect` in `TreeCanvas` uses a key built from `node.id + position` only. If the key is unchanged, instead of skipping the update entirely, it now **patches only `node.data`** in the existing `displayNodes`:

```typescript
// Key unchanged → patch data in-place, preserve user's drag positions
const dataMap = new Map(layoutNodes.map((n) => [n.id, n.data]));
setDisplayNodes((curr) =>
  curr.map((dn) => {
    const newData = dataMap.get(dn.id);
    return newData ? { ...dn, data: newData } : dn;
  }),
);
```

This means edits are visible immediately without resetting manually-dragged node positions.

---

## Legend Theming

`ChartLegend` (the draggable statistics overlay) uses `useThemeStore` to derive all colours from the active canvas theme:

| Element | Theme token |
|---|---|
| Background | `nodeBg` |
| Border | `nodeBorder` |
| Title & drag-handle dots | `nodeSubtext` |
| Row labels and counts | `nodeText` |
| Dividers | `nodeBorder` |
| Male / Female / Living icons | Fixed semantic colours (blue / pink / green) |

The `LegendRow` component accepts a `textColor` prop so `ChartLegend` can pass `theme.nodeText` dynamically.
