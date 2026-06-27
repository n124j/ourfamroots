import React from 'react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';
import { SEO } from '@shared/components/SEO';

export default function NotFoundPage() {
  const { t } = useTranslation();
  return (
    <div className="min-h-screen flex items-center justify-center bg-surface-muted">
      <SEO title="Page Not Found" noIndex />
      <div className="text-center">
        <p className="text-6xl font-bold text-brand-500 mb-4">{t('notFoundPage.code')}</p>
        <h1 className="text-2xl font-bold text-gray-900 mb-2">{t('notFoundPage.title')}</h1>
        <Link to="/dashboard" className="text-brand-600 hover:underline">{t('notFoundPage.goToDashboard')}</Link>
      </div>
    </div>
  );
}
