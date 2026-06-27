/**
 * Jest global test setup.
 * Runs after the test framework is installed but before each test file.
 */
import '@testing-library/jest-dom';

// Mock IntersectionObserver (not available in jsdom)
global.IntersectionObserver = class IntersectionObserver {
  constructor(cb: IntersectionObserverCallback) {}
  observe()    { return null; }
  unobserve()  { return null; }
  disconnect() { return null; }
} as any;

// Mock ResizeObserver
global.ResizeObserver = class ResizeObserver {
  constructor(cb: ResizeObserverCallback) {}
  observe()    { return null; }
  unobserve()  { return null; }
  disconnect() { return null; }
} as any;

// Mock matchMedia
Object.defineProperty(window, 'matchMedia', {
  writable: true,
  value: jest.fn().mockImplementation((query) => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: jest.fn(),
    removeListener: jest.fn(),
    addEventListener: jest.fn(),
    removeEventListener: jest.fn(),
    dispatchEvent: jest.fn(),
  })),
});

// Mock scrollTo
window.scrollTo = jest.fn();

// Silence console.error for known React warnings in tests
const originalConsoleError = console.error;
beforeEach(() => {
  jest.spyOn(console, 'error').mockImplementation((...args) => {
    const msg = args[0]?.toString() ?? '';
    // Allow legitimate errors through; suppress React act() warnings in tests
    if (msg.includes('Warning: An update to') || msg.includes('Warning: act(')) {
      return;
    }
    originalConsoleError(...args);
  });
});

afterEach(() => {
  jest.restoreAllMocks();
});
