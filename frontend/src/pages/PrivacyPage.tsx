import React from 'react';
import { Link } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { SEO } from '@shared/components/SEO';
import { Footer } from '@shared/components/layout/Footer';

const LAST_UPDATED  = 'June 3, 2026';
const CONTACT_EMAIL = 'support@ourfamroots.com';

function Section({ id, title, children }: { id: string; title: string; children: React.ReactNode }) {
  return (
    <section id={id} className="scroll-mt-20">
      <h2 className="text-xl font-bold text-gray-900 mb-3 pb-2 border-b border-gray-100">{title}</h2>
      <div className="space-y-3 text-gray-700 text-sm leading-relaxed">{children}</div>
    </section>
  );
}

export default function PrivacyPage() {
  const { t } = useTranslation();

  const TOC: [string, string][] = [
    ['overview',     t('privacyPage.toc1')],
    ['data-collect', t('privacyPage.toc2')],
    ['data-use',     t('privacyPage.toc3')],
    ['data-share',   t('privacyPage.toc4')],
    ['retention',    t('privacyPage.toc5')],
    ['security',     t('privacyPage.toc6')],
    ['cookies',      t('privacyPage.toc7')],
    ['rights',       t('privacyPage.toc8')],
    ['children',     t('privacyPage.toc9')],
    ['transfers',    t('privacyPage.toc10')],
    ['third-party',  t('privacyPage.toc11')],
    ['changes',      t('privacyPage.toc12')],
    ['contact',      t('privacyPage.toc13')],
  ];

  return (
    <div className="min-h-screen flex flex-col bg-surface-muted">
      <SEO
        title={t('privacyPage.title')}
        description={t('privacyPage.seoDescription')}
        canonical="/privacy"
      />

      <nav className="bg-white border-b border-gray-200 sticky top-0 z-10">
        <div className="max-w-5xl mx-auto px-6 h-14 flex items-center justify-between">
          <Link to="/" className="flex items-center gap-2 font-bold text-gray-900 hover:text-brand-600 transition-colors">
            <span className="text-xl">🌳</span> OurFamRoots
          </Link>
          <Link to="/login" className="text-sm font-medium text-brand-600 hover:text-brand-700">{t('auth.signIn')} →</Link>
        </div>
      </nav>

      <main className="flex-1 py-12 px-4">
        <div className="max-w-5xl mx-auto">

          <div className="mb-8">
            <h1 className="text-3xl font-bold text-gray-900 mb-2">{t('privacyPage.title')}</h1>
            <p className="text-sm text-gray-500">{t('privacyPage.lastUpdated')}: {LAST_UPDATED}</p>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-4 gap-8">

            <aside className="lg:col-span-1 hidden lg:block">
              <div className="bg-white rounded-xl border border-gray-200 p-4 sticky top-20">
                <p className="text-xs font-bold text-gray-500 uppercase tracking-wide mb-3">{t('privacyPage.tableOfContents')}</p>
                <nav className="space-y-1">
                  {TOC.map(([id, label]) => (
                    <a key={id} href={`#${id}`} className="block text-xs text-gray-600 hover:text-brand-600 py-0.5 hover:underline">
                      {label}
                    </a>
                  ))}
                </nav>
              </div>
            </aside>

            <div className="lg:col-span-3 bg-white rounded-2xl border border-gray-200 p-6 md:p-8 space-y-8">

              <div className="bg-green-50 border border-green-200 rounded-lg px-4 py-3 text-sm text-green-800">
                {t('privacyPage.introBanner')}
              </div>

              <Section id="overview" title={t('privacyPage.toc1')}>
                <p>{t('privacyPage.s1_p1')}</p>
                <p>{t('privacyPage.s1_p2')}</p>
                <p>{t('privacyPage.s1_p3')}</p>
              </Section>

              <Section id="data-collect" title={t('privacyPage.toc2')}>
                <p><strong>{t('privacyPage.s2_heading1')}</strong></p>
                <ul className="list-disc pl-5 space-y-1">
                  <li><strong>{t('privacyPage.s2_li1_label')}</strong> {t('privacyPage.s2_li1_text')}</li>
                  <li><strong>{t('privacyPage.s2_li2_label')}</strong> {t('privacyPage.s2_li2_text')}</li>
                  <li><strong>{t('privacyPage.s2_li3_label')}</strong> {t('privacyPage.s2_li3_text')}</li>
                  <li><strong>{t('privacyPage.s2_li4_label')}</strong> {t('privacyPage.s2_li4_text')}</li>
                </ul>

                <p className="mt-2"><strong>{t('privacyPage.s2_heading2')}</strong></p>
                <ul className="list-disc pl-5 space-y-1">
                  <li><strong>{t('privacyPage.s2_li5_label')}</strong> {t('privacyPage.s2_li5_text')}</li>
                  <li><strong>{t('privacyPage.s2_li6_label')}</strong> {t('privacyPage.s2_li6_text')}</li>
                  <li><strong>{t('privacyPage.s2_li7_label')}</strong> {t('privacyPage.s2_li7_text')}</li>
                  <li><strong>{t('privacyPage.s2_li8_label')}</strong> {t('privacyPage.s2_li8_text')}</li>
                </ul>

                <p className="mt-2"><strong>{t('privacyPage.s2_heading3')}</strong></p>
                <ul className="list-disc pl-5 space-y-1">
                  <li><strong>{t('privacyPage.s2_li9_label')}</strong> {t('privacyPage.s2_li9_text')}</li>
                </ul>
              </Section>

              <Section id="data-use" title={t('privacyPage.toc3')}>
                <p>{t('privacyPage.s3_p1')}</p>
                <ul className="list-disc pl-5 space-y-1">
                  <li><strong>{t('privacyPage.s3_li1_label')}</strong> {t('privacyPage.s3_li1_text')}</li>
                  <li><strong>{t('privacyPage.s3_li2_label')}</strong> {t('privacyPage.s3_li2_text')}</li>
                  <li><strong>{t('privacyPage.s3_li3_label')}</strong> {t('privacyPage.s3_li3_text')}</li>
                  <li><strong>{t('privacyPage.s3_li4_label')}</strong> {t('privacyPage.s3_li4_text')}</li>
                  <li><strong>{t('privacyPage.s3_li5_label')}</strong> {t('privacyPage.s3_li5_text')}</li>
                  <li><strong>{t('privacyPage.s3_li6_label')}</strong> {t('privacyPage.s3_li6_text')}</li>
                </ul>
                <p>{t('privacyPage.s3_p2')}</p>
              </Section>

              <Section id="data-share" title={t('privacyPage.toc4')}>
                <p>{t('privacyPage.s4_p1')}</p>
                <ul className="list-disc pl-5 space-y-1">
                  <li><strong>{t('privacyPage.s4_li1_label')}</strong> {t('privacyPage.s4_li1_text')}</li>
                  <li><strong>{t('privacyPage.s4_li2_label')}</strong> {t('privacyPage.s4_li2_text')}</li>
                  <li><strong>{t('privacyPage.s4_li3_label')}</strong> {t('privacyPage.s4_li3_text')}</li>
                  <li><strong>{t('privacyPage.s4_li4_label')}</strong> {t('privacyPage.s4_li4_text')}</li>
                </ul>
              </Section>

              <Section id="retention" title={t('privacyPage.toc5')}>
                <p>{t('privacyPage.s5_p1')}</p>
                <ul className="list-disc pl-5 space-y-1">
                  <li><strong>{t('privacyPage.s5_li1_label')}</strong> {t('privacyPage.s5_li1_text')}</li>
                  <li><strong>{t('privacyPage.s5_li2_label')}</strong> {t('privacyPage.s5_li2_text')}</li>
                  <li><strong>{t('privacyPage.s5_li3_label')}</strong> {t('privacyPage.s5_li3_text')}</li>
                  <li><strong>{t('privacyPage.s5_li4_label')}</strong> {t('privacyPage.s5_li4_text')}</li>
                  <li><strong>{t('privacyPage.s5_li5_label')}</strong> {t('privacyPage.s5_li5_text')}</li>
                </ul>
                <p>
                  {t('privacyPage.s5_p2_before')}{' '}
                  <a href={`mailto:${CONTACT_EMAIL}`} className="text-brand-600 hover:underline">{CONTACT_EMAIL}</a>
                  {t('privacyPage.s5_p2_after')}
                </p>
              </Section>

              <Section id="security" title={t('privacyPage.toc6')}>
                <p>{t('privacyPage.s6_p1')}</p>
                <ul className="list-disc pl-5 space-y-1">
                  <li>{t('privacyPage.s6_li1')}</li>
                  <li>{t('privacyPage.s6_li2')}</li>
                  <li>{t('privacyPage.s6_li3')}</li>
                  <li>{t('privacyPage.s6_li4')}</li>
                  <li>{t('privacyPage.s6_li5')}</li>
                  <li>{t('privacyPage.s6_li6')}</li>
                </ul>
                <p>{t('privacyPage.s6_p2')}</p>
              </Section>

              <Section id="cookies" title={t('privacyPage.toc7')}>
                <p>{t('privacyPage.s7_p1')}</p>
                <div className="overflow-x-auto">
                  <table className="w-full text-xs border-collapse border border-gray-200 rounded-lg overflow-hidden">
                    <thead>
                      <tr className="bg-gray-50">
                        <th className="text-left p-3 font-semibold text-gray-700 border-b border-gray-200">{t('privacyPage.s7_colType')}</th>
                        <th className="text-left p-3 font-semibold text-gray-700 border-b border-gray-200">{t('privacyPage.s7_colPurpose')}</th>
                        <th className="text-left p-3 font-semibold text-gray-700 border-b border-gray-200">{t('privacyPage.s7_colDuration')}</th>
                      </tr>
                    </thead>
                    <tbody>
                      {([
                        [t('privacyPage.s7_r1_type'), t('privacyPage.s7_r1_purpose'), t('privacyPage.s7_r1_duration')],
                        [t('privacyPage.s7_r2_type'), t('privacyPage.s7_r2_purpose'), t('privacyPage.s7_r2_duration')],
                        [t('privacyPage.s7_r3_type'), t('privacyPage.s7_r3_purpose'), t('privacyPage.s7_r3_duration')],
                        [t('privacyPage.s7_r4_type'), t('privacyPage.s7_r4_purpose'), t('privacyPage.s7_r4_duration')],
                        [t('privacyPage.s7_r5_type'), t('privacyPage.s7_r5_purpose'), t('privacyPage.s7_r5_duration')],
                      ] as [string, string, string][]).map(([type, purpose, duration], i) => (
                        <tr key={i} className={i % 2 === 0 ? 'bg-white' : 'bg-gray-50'}>
                          <td className="p-3 font-medium text-gray-800 border-b border-gray-100">{type}</td>
                          <td className="p-3 text-gray-600 border-b border-gray-100">{purpose}</td>
                          <td className="p-3 text-gray-600 border-b border-gray-100">{duration}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                <p className="mt-2">{t('privacyPage.s7_p2')}</p>
              </Section>

              <Section id="rights" title={t('privacyPage.toc8')}>
                <p>{t('privacyPage.s8_p1')}</p>
                <ul className="list-disc pl-5 space-y-1">
                  <li><strong>{t('privacyPage.s8_li1_label')}</strong> {t('privacyPage.s8_li1_text')}</li>
                  <li><strong>{t('privacyPage.s8_li2_label')}</strong> {t('privacyPage.s8_li2_text')}</li>
                  <li><strong>{t('privacyPage.s8_li3_label')}</strong> {t('privacyPage.s8_li3_text')}</li>
                  <li><strong>{t('privacyPage.s8_li4_label')}</strong> {t('privacyPage.s8_li4_text')}</li>
                  <li><strong>{t('privacyPage.s8_li5_label')}</strong> {t('privacyPage.s8_li5_text')}</li>
                  <li><strong>{t('privacyPage.s8_li6_label')}</strong> {t('privacyPage.s8_li6_text')}</li>
                  <li><strong>{t('privacyPage.s8_li7_label')}</strong> {t('privacyPage.s8_li7_text')}</li>
                </ul>
                <p>
                  {t('privacyPage.s8_p2_before')}{' '}
                  <a href={`mailto:${CONTACT_EMAIL}`} className="text-brand-600 hover:underline">{CONTACT_EMAIL}</a>
                  {t('privacyPage.s8_p2_after')}
                </p>
                <p>{t('privacyPage.s8_p3')}</p>
              </Section>

              <Section id="children" title={t('privacyPage.toc9')}>
                <p>
                  {t('privacyPage.s9_p1_before')}{' '}
                  <a href={`mailto:${CONTACT_EMAIL}`} className="text-brand-600 hover:underline">{CONTACT_EMAIL}</a>{' '}
                  {t('privacyPage.s9_p1_after')}
                </p>
                <p>{t('privacyPage.s9_p2')}</p>
              </Section>

              <Section id="transfers" title={t('privacyPage.toc10')}>
                <p>{t('privacyPage.s10_p1')}</p>
                <p>{t('privacyPage.s10_p2')}</p>
              </Section>

              <Section id="third-party" title={t('privacyPage.toc11')}>
                <p>{t('privacyPage.s11_p1')}</p>
                <p>{t('privacyPage.s11_p2')}</p>
              </Section>

              <Section id="changes" title={t('privacyPage.toc12')}>
                <p>{t('privacyPage.s12_p1')}</p>
                <ul className="list-disc pl-5 space-y-1">
                  <li>{t('privacyPage.s12_li1')}</li>
                  <li>{t('privacyPage.s12_li2')}</li>
                  <li>{t('privacyPage.s12_li3')}</li>
                </ul>
                <p>{t('privacyPage.s12_p2')}</p>
              </Section>

              <Section id="contact" title={t('privacyPage.toc13')}>
                <p>{t('privacyPage.s13_p1')}</p>
                <div className="bg-gray-50 rounded-lg p-4 mt-2">
                  <p className="font-semibold text-gray-800">{t('privacyPage.s13_orgName')}</p>
                  <p className="text-sm mt-1">
                    {t('privacyPage.s13_emailLabel')}{' '}
                    <a href={`mailto:${CONTACT_EMAIL}`} className="text-brand-600 hover:underline">{CONTACT_EMAIL}</a>
                  </p>
                  <p className="text-sm mt-1">
                    {t('privacyPage.s13_contactFormLabel')}{' '}
                    <Link to="/contact" className="text-brand-600 hover:underline">ourfamroots.com/contact</Link>
                  </p>
                  <p className="text-sm text-gray-500 mt-2">{t('privacyPage.s13_responseTime')}</p>
                </div>
              </Section>

            </div>
          </div>
        </div>
      </main>

      <Footer />
    </div>
  );
}
