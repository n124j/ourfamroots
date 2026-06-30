import type { ViewPlugin } from '../registry';
import { TimelineView } from '@features/tree/canvas/TimelineView';

const plugin: ViewPlugin = {
  id: 'timeline',
  label: 'Timeline',
  description: 'Horizontal timeline with year axis',
  category: 'extension',
  CanvasComponent: TimelineView,
};

export default plugin;
