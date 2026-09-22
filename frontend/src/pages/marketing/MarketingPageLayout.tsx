import React from 'react';
import { Link } from 'react-router-dom';

const DEMO_SHARE_TOKEN = import.meta.env.VITE_DEMO_TREE_SHARE_TOKEN as string | undefined;

interface MarketingPageLayoutProps {
  eyebrow: string;
  heading: string;
  subheading: string;
  demoLabel: string;
  children: React.ReactNode;
}

/** Shared header/hero/footer chrome for standalone acquisition pages like
 * /family-tree-maker and /fan-chart-generator — public, crawlable routes
 * that showcase one real product capability and funnel into signup. */
export function MarketingPageLayout({ eyebrow, heading, subheading, demoLabel, children }: MarketingPageLayoutProps) {
  return (
    <div className="min-h-screen bg-surface-muted">
      <div className="flex items-center justify-between px-4 md:px-8 py-4 bg-white border-b border-gray-200">
        <Link to="/" className="flex items-center gap-2 text-brand-600 hover:text-brand-700">
          <span className="text-2xl">🌳</span>
          <span className="font-semibold text-gray-900">OurFamRoots</span>
        </Link>
        <Link
          to="/register"
          className="text-sm font-medium px-4 py-2 bg-brand-500 text-white rounded-lg hover:bg-brand-600 transition-colors"
        >
          Sign up free
        </Link>
      </div>

      <div className="max-w-3xl mx-auto px-4 md:px-8 py-16 text-center">
        <p className="text-sm font-semibold text-brand-600 uppercase tracking-wide mb-3">{eyebrow}</p>
        <h1 className="text-3xl md:text-4xl font-bold text-gray-900 mb-4">{heading}</h1>
        <p className="text-lg text-gray-600 mb-8">{subheading}</p>
        <div className="flex flex-col sm:flex-row gap-3 justify-center">
          <Link
            to="/register"
            className="px-6 py-3 bg-brand-500 text-white font-medium rounded-lg hover:bg-brand-600 transition-colors"
          >
            Start building free
          </Link>
          {DEMO_SHARE_TOKEN && (
            <Link
              to={`/shared/${DEMO_SHARE_TOKEN}`}
              className="px-6 py-3 border border-gray-300 text-gray-700 font-medium rounded-lg hover:bg-gray-50 transition-colors"
            >
              {demoLabel}
            </Link>
          )}
        </div>
      </div>

      <div className="max-w-3xl mx-auto px-4 md:px-8 pb-20">
        {children}
      </div>

      <div className="border-t border-gray-200 py-6">
        <nav className="max-w-3xl mx-auto px-4 md:px-8 flex flex-wrap gap-x-4 gap-y-1 justify-center text-sm text-gray-500">
          <Link to="/help" className="hover:text-gray-700">Help</Link>
          <span>·</span>
          <Link to="/contact" className="hover:text-gray-700">Contact</Link>
          <span>·</span>
          <Link to="/terms" className="hover:text-gray-700">Terms &amp; Conditions</Link>
          <span>·</span>
          <Link to="/privacy" className="hover:text-gray-700">Privacy Policy</Link>
        </nav>
      </div>
    </div>
  );
}
