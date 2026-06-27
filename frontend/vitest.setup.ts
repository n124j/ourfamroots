import '@testing-library/jest-dom';
import { vi } from 'vitest';

// Expose jest as an alias for vi so existing test files using
// jest.fn(), jest.spyOn(), jest.clearAllMocks() etc. work without changes.
// Note: jest.requireActual() is not supported — use vi.importActual() instead.
(globalThis as any).jest = vi;

// jsdom does not implement URL.createObjectURL; mock it globally.
global.URL.createObjectURL = vi.fn(() => 'blob:mock-url');
global.URL.revokeObjectURL = vi.fn();
