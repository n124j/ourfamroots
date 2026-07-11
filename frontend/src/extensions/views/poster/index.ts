import type { ViewPlugin } from '../registry';
import { PosterPedigreeView } from './PosterPedigreeView';

const plugin: ViewPlugin = {
  id: 'poster',
  label: 'Family Tree Poster',
  description: 'Decorative printable ancestor poster',
  category: 'extension',
  CanvasComponent: PosterPedigreeView,
};

export default plugin;
