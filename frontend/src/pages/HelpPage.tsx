import React from 'react';
import { Link } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { SEO } from '@shared/components/SEO';

export default function HelpPage() {
  return (
    <div className="flex flex-col" style={{ height: '100vh', overflow: 'hidden' }}>
      <SEO
        title="Help — Getting Started"
        description="Step-by-step guide to getting started with OurFamRoots. Learn how to build your family tree, add members, collaborate, and more."
        canonical="/help"
        keywords="help, getting started, tutorial, family tree guide, how to use ourfamroots"
      />

      {/* ── Header bar ── */}
      <header className="h-12 bg-white border-b border-gray-200 flex items-center px-4 gap-3 shrink-0 z-10 shadow-sm">
        {/* Brand */}
        <Link
          to="/"
          className="flex items-center gap-2 font-bold text-gray-900 hover:text-brand-600 transition-colors"
        >
          <img src="/favicon.svg" alt="OurFamRoots" className="w-6 h-6" />
          <span className="hidden sm:inline">OurFamRoots</span>
        </Link>

        <span className="text-gray-300 select-none">|</span>

        <span className="text-sm font-semibold text-gray-700">
          Help — Getting Started Guide
        </span>

        {/* Right side */}
        <div className="ml-auto flex items-center gap-4">
          <a
            href="/getting-started.html"
            target="_blank"
            rel="noopener noreferrer"
            className="hidden sm:inline text-xs text-brand-600 hover:text-brand-700 hover:underline"
          >
            Open fullscreen ↗
          </a>
          <Link
            to="/login"
            className="text-sm font-medium text-brand-600 hover:text-brand-700 transition-colors"
          >
            Sign in →
          </Link>
        </div>
      </header>

      {/* ── Slideshow iframe ── */}
      <iframe
        src="/getting-started.html"
        title="OurFamRoots Getting Started Guide"
        className="flex-1 w-full border-0"
        style={{ display: 'block' }}
      />
    </div>
  );
}
