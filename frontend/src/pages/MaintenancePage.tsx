import React from 'react';
import { useTranslation } from 'react-i18next';
import { useMaintenanceStore } from '@store/maintenance.store';

export default function MaintenancePage() {
  const { t } = useTranslation();
  const message = useMaintenanceStore((s) => s.maintenanceMessage);

  return (
    <div className="fixed inset-0 flex items-center justify-center bg-gradient-to-br from-amber-50 to-orange-50">
      <div className="max-w-lg mx-auto px-6 text-center">
        {/* Icon */}
        <div className="mb-6">
          <div className="inline-flex items-center justify-center w-20 h-20 rounded-full bg-amber-100">
            <svg
              className="w-10 h-10 text-amber-600"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
              strokeWidth={1.5}
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d="M11.42 15.17L17.25 21A2.652 2.652 0 0021 17.25l-5.877-5.877M11.42 15.17l2.496-3.03c.317-.384.74-.626 1.208-.766M11.42 15.17l-4.655 5.653a2.548 2.548 0 11-3.586-3.586l6.837-5.63m5.108-.233c.55-.164 1.163-.188 1.743-.14a4.5 4.5 0 004.486-6.336l-3.276 3.277a3.004 3.004 0 01-2.25-2.25l3.276-3.276a4.5 4.5 0 00-6.336 4.486c.091 1.076-.071 2.264-.904 2.95l-.102.085m-1.745 1.437L5.909 7.5H4.5L2.25 3.75l1.5-1.5L7.5 4.5v1.409l4.26 4.26m-1.745 1.437l1.745-1.437m6.615 8.206L15.75 15.75M4.867 19.125h.008v.008h-.008v-.008z"
              />
            </svg>
          </div>
        </div>

        {/* Title */}
        <h1 className="text-3xl font-bold text-gray-900 mb-3">
          {t('maintenancePage.title')}
        </h1>

        {/* Customizable message */}
        <p className="text-lg text-gray-600 mb-8 leading-relaxed whitespace-pre-line">
          {message || t('maintenancePage.message')}
        </p>

        {/* Admin access + brand */}
        <div className="flex items-center justify-center gap-3 text-sm text-gray-400">
          <span className="font-semibold">{t('common.appName')}</span>
          <span>·</span>
          <a
            href="/admin/login"
            className="text-amber-600 hover:text-amber-700 font-medium transition-colors"
          >
            {t('maintenancePage.admin')}
          </a>
        </div>
      </div>
    </div>
  );
}
