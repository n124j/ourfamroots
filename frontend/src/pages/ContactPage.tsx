import React, { useState } from 'react';
import { Link } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { SEO } from '@shared/components/SEO';
import { Footer } from '@shared/components/layout/Footer';

const API_BASE     = import.meta.env.VITE_API_BASE_URL ?? '/api/v1';
const CONTACT_EMAIL = 'support@ourfamroots.com';

const SUBJECTS = [
  'General Inquiry',
  'Technical Support',
  'Bug Report',
  'Feature Request',
  'Account Issues',
  'Partnership / Press',
  'Other',
] as const;

type Status = 'idle' | 'submitting' | 'success';

function buildMailto(name: string, email: string, phone: string, subject: string, message: string) {
  const body = [
    `Name: ${name}`,
    `Email: ${email}`,
    ...(phone ? [`Phone: ${phone}`] : []),
    '',
    message,
  ].join('\n');

  return (
    `mailto:${CONTACT_EMAIL}` +
    `?subject=${encodeURIComponent(`[OurFamRoots] ${subject}`)}` +
    `&body=${encodeURIComponent(body)}`
  );
}

export default function ContactPage() {
  const { t } = useTranslation();
  const [name,    setName]    = useState('');
  const [email,   setEmail]   = useState('');
  const [phone,   setPhone]   = useState('');
  const [subject, setSubject] = useState('');
  const [message, setMessage] = useState('');
  const [status,  setStatus]  = useState<Status>('idle');

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setStatus('submitting');

    // 1. Try the API endpoint (works when backend contact route is available)
    try {
      const res = await fetch(`${API_BASE}/contact`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name, email, phone: phone || undefined, subject, message }),
      });
      if (res.ok) {
        setStatus('success');
        return;
      }
    } catch {
      // API unavailable — fall through to mailto:
    }

    // 2. Fallback: open the user's email client with all fields pre-filled
    const link = document.createElement('a');
    link.href = buildMailto(name, email, phone, subject, message);
    link.click();
    setStatus('success');
  }

  return (
    <div className="min-h-screen flex flex-col bg-surface-muted">
      <SEO
        title="Contact Us"
        description="Get in touch with the OurFamRoots team. We're here to help with support, feedback, and partnership enquiries."
        canonical="/contact"
        keywords="contact, support, help, ourfamroots contact"
      />

      {/* ── Top nav ── */}
      <nav className="bg-white border-b border-gray-200 sticky top-0 z-10">
        <div className="max-w-5xl mx-auto px-6 h-14 flex items-center justify-between">
          <Link to="/" className="flex items-center gap-2 font-bold text-gray-900 hover:text-brand-600 transition-colors">
            <span className="text-xl">🌳</span> OurFamRoots
          </Link>
          <Link to="/login" className="text-sm font-medium text-brand-600 hover:text-brand-700">
            Sign in →
          </Link>
        </div>
      </nav>

      {/* ── Main ── */}
      <main className="flex-1 py-12 px-4">
        <div className="max-w-4xl mx-auto">

          {/* Header */}
          <div className="text-center mb-10">
            <div className="text-4xl mb-3">✉️</div>
            <h1 className="text-3xl font-bold text-gray-900 mb-2">{t('contactPage.title')}</h1>
            <p className="text-gray-500 text-base max-w-lg mx-auto">
              {t('contactPage.subtitle')} We'd love to hear from you.
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-8">

            {/* ── Contact info sidebar ── */}
            <div className="md:col-span-1 space-y-5">
              <div className="bg-white rounded-2xl border border-gray-200 p-5">
                <h2 className="text-sm font-bold text-gray-900 mb-4 uppercase tracking-wide">{t('contactPage.getInTouch')}</h2>

                <div className="space-y-4">
                  <div className="flex gap-3">
                    <div className="w-8 h-8 bg-brand-100 rounded-lg flex items-center justify-center text-brand-600 shrink-0">📧</div>
                    <div>
                      <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-0.5">{t('contactPage.email')}</p>
                      <a href={`mailto:${CONTACT_EMAIL}`} className="text-sm text-brand-600 hover:text-brand-700 hover:underline break-all">
                        {CONTACT_EMAIL}
                      </a>
                    </div>
                  </div>

                  <div className="flex gap-3">
                    <div className="w-8 h-8 bg-green-100 rounded-lg flex items-center justify-center text-green-600 shrink-0">⏱</div>
                    <div>
                      <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-0.5">{t('contactPage.responseTime')}</p>
                      <p className="text-sm text-gray-700">Within 1–2 business days</p>
                    </div>
                  </div>

                  <div className="flex gap-3">
                    <div className="w-8 h-8 bg-purple-100 rounded-lg flex items-center justify-center text-purple-600 shrink-0">🌍</div>
                    <div>
                      <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-0.5">{t('contactPage.supportHours')}</p>
                      <p className="text-sm text-gray-700">{t('contactPage.supportHoursValue')}</p>
                    </div>
                  </div>
                </div>
              </div>

              <div className="bg-brand-50 border border-brand-200 rounded-2xl p-5">
                <h3 className="text-sm font-bold text-brand-800 mb-2">💡 {t('contactPage.quickSelfHelp')}</h3>
                <ul className="space-y-2 text-sm text-brand-700">
                  <li>• {t('contactPage.forgotPassword')} Use the <Link to="/forgot-password" className="underline hover:text-brand-900">{t('contactPage.resetLink')}</Link></li>
                  <li>• {t('contactPage.missingMembers')} See the {t('contactPage.troubleshootingGuide')} in our docs</li>
                  <li>• {t('contactPage.inviteIssues')} Check your {t('contactPage.spamFolder')} for the invitation email</li>
                </ul>
              </div>
            </div>

            {/* ── Contact form ── */}
            <div className="md:col-span-2">
              <div className="bg-white rounded-2xl border border-gray-200 p-6 md:p-8">

                {status === 'success' ? (
                  <div className="text-center py-10">
                    <div className="text-5xl mb-4">🎉</div>
                    <h2 className="text-xl font-bold text-gray-900 mb-2">{t('contactPage.sent')}</h2>
                    <p className="text-gray-500 mb-6">
                      {t('contactPage.thanksForReaching')}, <strong>{name}</strong>. {t('contactPage.weWillGetBack')}
                    </p>
                    <button
                      onClick={() => { setStatus('idle'); setName(''); setEmail(''); setPhone(''); setSubject(''); setMessage(''); }}
                      className="px-5 py-2 bg-brand-500 text-white text-sm font-medium rounded-lg hover:bg-brand-600 transition-colors"
                    >
                      {t('contactPage.sendAnother')}
                    </button>
                  </div>
                ) : (
                  <form onSubmit={handleSubmit} className="space-y-5" noValidate>
                    <h2 className="text-lg font-bold text-gray-900 mb-1">{t('contactPage.sendMessage')}</h2>
                    <p className="text-sm text-gray-500 mb-4">{t('contactPage.fieldsRequired')} <span className="text-red-500">*</span> {t('contactPage.areRequired')}</p>

                    {/* Name + Email row */}
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                      <div>
                        <label className="block text-sm font-medium text-gray-700 mb-1.5">
                          {t('contactPage.fullName')} <span className="text-red-500">*</span>
                        </label>
                        <input
                          type="text"
                          value={name}
                          onChange={(e) => setName(e.target.value)}
                          required
                          placeholder="Alice Johnson"
                          className="w-full h-10 px-3 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-brand-500 focus:border-transparent"
                        />
                      </div>
                      <div>
                        <label className="block text-sm font-medium text-gray-700 mb-1.5">
                          {t('contactPage.emailAddress')} <span className="text-red-500">*</span>
                        </label>
                        <input
                          type="email"
                          value={email}
                          onChange={(e) => setEmail(e.target.value)}
                          required
                          placeholder="alice@example.com"
                          className="w-full h-10 px-3 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-brand-500 focus:border-transparent"
                        />
                      </div>
                    </div>

                    {/* Phone + Subject row */}
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                      <div>
                        <label className="block text-sm font-medium text-gray-700 mb-1.5">
                          {t('contactPage.phoneNumber')} <span className="text-xs text-gray-400 font-normal">({t('contactPage.optional')})</span>
                        </label>
                        <input
                          type="tel"
                          value={phone}
                          onChange={(e) => setPhone(e.target.value)}
                          placeholder="+1 555 000 0000"
                          className="w-full h-10 px-3 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-brand-500 focus:border-transparent"
                        />
                      </div>
                      <div>
                        <label className="block text-sm font-medium text-gray-700 mb-1.5">
                          {t('contactPage.subject')} <span className="text-red-500">*</span>
                        </label>
                        <select
                          value={subject}
                          onChange={(e) => setSubject(e.target.value)}
                          required
                          className="w-full h-10 px-3 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-brand-500 focus:border-transparent bg-white"
                        >
                          <option value="">Select a subject…</option>
                          {SUBJECTS.map((s) => (
                            <option key={s} value={s}>{s}</option>
                          ))}
                        </select>
                      </div>
                    </div>

                    {/* Message */}
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-1.5">
                        {t('contactPage.message')} <span className="text-red-500">*</span>
                      </label>
                      <textarea
                        value={message}
                        onChange={(e) => setMessage(e.target.value)}
                        required
                        rows={6}
                        placeholder="Tell us how we can help. The more detail you provide, the faster we can assist you."
                        className="w-full px-3 py-2.5 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-brand-500 focus:border-transparent resize-none"
                      />
                      <p className="text-xs text-gray-400 mt-1">{message.length} / 2000 characters</p>
                    </div>

                    <div className="flex items-center justify-between pt-1">
                      <p className="text-xs text-gray-400 max-w-xs">
                        By submitting this form you agree to our{' '}
                        <Link to="/privacy" className="text-brand-600 hover:underline">{t('contactPage.privacyPolicy')}</Link>.
                      </p>
                      <button
                        type="submit"
                        disabled={status === 'submitting'}
                        className="px-6 py-2.5 bg-brand-500 text-white text-sm font-semibold rounded-lg hover:bg-brand-600 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                      >
                        {status === 'submitting' ? t('contactPage.sending') : t('contactPage.sendButton')}
                      </button>
                    </div>
                  </form>
                )}
              </div>
            </div>

          </div>
        </div>
      </main>

      <Footer />
    </div>
  );
}
