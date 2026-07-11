import type { ViewPlugin } from '../registry';
import { TextPedigreeView } from './TextPedigreeView';

const plugin: ViewPlugin = {
  id: 'text-pedigree',
  label: 'Text Pedigree',
  description: 'Compact text-only ancestor tree — saves space',
  category: 'extension',
  CanvasComponent: TextPedigreeView,
};

export default plugin;
