import type { ViewPlugin } from '../registry';
import { HeritagePersonNode } from './HeritagePersonNode';

const plugin: ViewPlugin = {
  id: 'heritage',
  label: 'Heritage',
  description: 'Vintage parchment style with serif text',
  category: 'builtin',
  PersonNodeComponent: HeritagePersonNode as any,
  orthogonalEdges: true,
  hideFamilyGroupNode: true,
  layoutOverrides: {
    mode: 'compact',
    personNodeHeight: 150,
    nodeVGap: 70,
    nodeHGap: 36,
  },
};

export default plugin;
