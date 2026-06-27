import type { Config } from 'jest';

const config: Config = {
  preset: 'ts-jest',
  testEnvironment: 'jsdom',
  roots: ['<rootDir>/src'],
  testMatch: ['**/__tests__/**/*.test.{ts,tsx}'],

  // Module resolution (mirrors tsconfig paths)
  moduleNameMapper: {
    '^@api/(.*)$':      '<rootDir>/src/api/$1',
    '^@store/(.*)$':    '<rootDir>/src/store/$1',
    '^@features/(.*)$': '<rootDir>/src/features/$1',
    '^@shared/(.*)$':   '<rootDir>/src/shared/$1',
    '^@queries/(.*)$':  '<rootDir>/src/queries/$1',
    '^@pages/(.*)$':    '<rootDir>/src/pages/$1',
    // CSS modules
    '\\.css$': '<rootDir>/src/__mocks__/styleMock.ts',
  },

  // Setup files
  setupFilesAfterFramework: ['<rootDir>/src/__tests__/setup.ts'],
  setupFilesAfterFramework: [],

  // Coverage
  collectCoverageFrom: [
    'src/**/*.{ts,tsx}',
    '!src/**/*.d.ts',
    '!src/main.tsx',
    '!src/**/__tests__/**',
    '!src/**/*.stories.{ts,tsx}',
  ],
  coverageThresholds: {
    global: {
      branches:   85,
      functions:  90,
      lines:      90,
      statements: 90,
    },
    // Per-file thresholds for critical paths
    './src/store/auth.store.ts': {
      branches: 90, functions: 95, lines: 95, statements: 95,
    },
    './src/features/media/useMediaUpload.ts': {
      branches: 85, functions: 90, lines: 90, statements: 90,
    },
  },
  coverageReporters: ['text', 'lcov', 'html'],
  coverageDirectory: 'coverage',

  // Transform
  transform: {
    '^.+\\.tsx?$': ['ts-jest', {
      tsconfig: {
        jsx: 'react-jsx',
        esModuleInterop: true,
      },
    }],
  },

  // Test timeout
  testTimeout: 10_000,

  // Global mocks
  globals: {
    'import.meta': {
      env: {
        VITE_API_BASE_URL: '/api/v1',
      },
    },
  },
};

export default config;
