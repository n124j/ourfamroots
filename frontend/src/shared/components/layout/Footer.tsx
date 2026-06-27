import React from 'react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';

export function Footer() {
  const { t } = useTranslation();
  return (
    <footer className="border-t border-gray-200 bg-white mt-auto shrink-0">
      <div className="max-w-5xl mx-auto px-6 py-5">
        <div className="flex flex-col sm:flex-row items-center justify-between gap-3">

          {/* Nav links */}
          <nav className="flex items-center gap-1 flex-wrap justify-center">
            <Link to="/help"    className="px-3 py-1.5 text-sm text-gray-500 hover:text-brand-600 rounded-lg hover:bg-gray-50 transition-colors">{t('footer.help')}</Link>
            <span className="text-gray-300 select-none">·</span>
            <Link to="/contact" className="px-3 py-1.5 text-sm text-gray-500 hover:text-brand-600 rounded-lg hover:bg-gray-50 transition-colors">{t('footer.contact')}</Link>
            <span className="text-gray-300 select-none">·</span>
            <Link to="/terms"   className="px-3 py-1.5 text-sm text-gray-500 hover:text-brand-600 rounded-lg hover:bg-gray-50 transition-colors">{t('footer.terms')}</Link>
            <span className="text-gray-300 select-none">·</span>
            <Link to="/privacy" className="px-3 py-1.5 text-sm text-gray-500 hover:text-brand-600 rounded-lg hover:bg-gray-50 transition-colors">{t('footer.privacy')}</Link>
          </nav>

          {/* Copyright */}
          <p className="text-xs text-gray-400 shrink-0">
            {t('footer.copyright', { year: new Date().getFullYear() })}
          </p>

        </div>
      </div>
    </footer>
  );
}
