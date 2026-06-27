import React from 'react';
import { Link } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { SEO } from '@shared/components/SEO';
import { Footer } from '@shared/components/layout/Footer';

const CONTACT_EMAIL = 'support@ourfamroots.com';

function Section({ id, title, children }: { id: string; title: string; children: React.ReactNode }) {
  return (
    <section id={id} className="scroll-mt-20">
      <h2 className="text-xl font-bold text-gray-900 mb-3 pb-2 border-b border-gray-100">{title}</h2>
      <div className="space-y-3 text-gray-700 text-sm leading-relaxed">{children}</div>
    </section>
  );
}

export default function TermsPage() {
  const { t } = useTranslation();

  const TOC: readonly (readonly [string, string])[] = [
    ['acceptance',     t('termsPage.toc1')],
    ['service',        t('termsPage.toc2')],
    ['accounts',       t('termsPage.toc3')],
    ['content',        t('termsPage.toc4')],
    ['living',         t('termsPage.toc5')],
    ['acceptable-use', t('termsPage.toc6')],
    ['ip',             t('termsPage.toc7')],
    ['privacy',        t('termsPage.toc8')],
    ['disclaimers',    t('termsPage.toc9')],
    ['security',       t('termsPage.toc10')],
    ['liability',      t('termsPage.toc11')],
    ['indemnification',t('termsPage.toc12')],
    ['termination',    t('termsPage.toc13')],
    ['changes',        t('termsPage.toc14')],
    ['governing-law',  t('termsPage.toc15')],
    ['contact',        t('termsPage.toc16')],
  ];

  return (
    <div className="min-h-screen flex flex-col bg-surface-muted">
      <SEO
        title="Terms & Conditions"
        description="Read the OurFamRoots Terms and Conditions to understand your rights and obligations when using our genealogy platform."
        canonical="/terms"
      />

      <nav className="bg-white border-b border-gray-200 sticky top-0 z-10">
        <div className="max-w-5xl mx-auto px-6 h-14 flex items-center justify-between">
          <Link to="/" className="flex items-center gap-2 font-bold text-gray-900 hover:text-brand-600 transition-colors">
            <span className="text-xl">🌳</span> OurFamRoots
          </Link>
          <Link to="/login" className="text-sm font-medium text-brand-600 hover:text-brand-700">{t('termsPage.signInArrow')}</Link>
        </div>
      </nav>

      <main className="flex-1 py-12 px-4">
        <div className="max-w-5xl mx-auto">

          <div className="mb-8">
            <h1 className="text-3xl font-bold text-gray-900 mb-2">{t('termsPage.title')}</h1>
            <p className="text-sm text-gray-500">{t('termsPage.lastUpdated')}: {t('termsPage.lastUpdatedDate')}</p>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-4 gap-8">

            <aside className="lg:col-span-1 hidden lg:block">
              <div className="bg-white rounded-xl border border-gray-200 p-4 sticky top-20">
                <p className="text-xs font-bold text-gray-500 uppercase tracking-wide mb-3">{t('termsPage.tableOfContents')}</p>
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

              <div className="bg-brand-50 border border-brand-200 rounded-lg px-4 py-3 text-sm text-brand-800">
                {t('termsPage.introBanner')}
              </div>

              <Section id="acceptance" title={t('termsPage.toc1')}>
                <p>{t('termsPage.s1_p1')}</p>
                <p>
                  {t('termsPage.s1_p2_before')}
                  <Link to="/privacy" className="text-brand-600 hover:underline">{t('termsPage.s1_p2_link')}</Link>
                  {t('termsPage.s1_p2_after')}
                </p>
                <p>{t('termsPage.s1_p3')}</p>
              </Section>

              <Section id="service" title={t('termsPage.toc2')}>
                <p>{t('termsPage.s2_p1')}</p>
                <ul className="list-disc pl-5 space-y-1">
                  <li>{t('termsPage.s2_li1')}</li>
                  <li>{t('termsPage.s2_li2')}</li>
                  <li>{t('termsPage.s2_li3')}</li>
                  <li>{t('termsPage.s2_li4')}</li>
                  <li>{t('termsPage.s2_li5')}</li>
                  <li>{t('termsPage.s2_li6')}</li>
                  <li>{t('termsPage.s2_li7')}</li>
                </ul>
                <p>{t('termsPage.s2_p2')}</p>
              </Section>

              <Section id="accounts" title={t('termsPage.toc3')}>
                <p>{t('termsPage.s3_p1')}</p>
                <ul className="list-disc pl-5 space-y-1">
                  <li>{t('termsPage.s3_li1')}</li>
                  <li>{t('termsPage.s3_li2')}</li>
                  <li>{t('termsPage.s3_li3')}</li>
                  <li>{t('termsPage.s3_li4')}</li>
                  <li>{t('termsPage.s3_li5')}<a href={`mailto:${CONTACT_EMAIL}`} className="text-brand-600 hover:underline">{CONTACT_EMAIL}</a></li>
                </ul>
                <p>{t('termsPage.s3_p2')}</p>
                <p>
                  <strong>{t('termsPage.s3_p3_label')}</strong>{t('termsPage.s3_p3')}
                </p>
              </Section>

              <Section id="content" title={t('termsPage.toc4')}>
                <p>
                  <strong>{t('termsPage.s4_p1_label')}</strong>{t('termsPage.s4_p1')}
                </p>
                <p>
                  <strong>{t('termsPage.s4_p2_label')}</strong>{t('termsPage.s4_p2')}
                </p>
                <p>
                  <strong>{t('termsPage.s4_p3_label')}</strong>{t('termsPage.s4_p3')}
                </p>
                <p>
                  <strong>{t('termsPage.s4_p4_label')}</strong>{t('termsPage.s4_p4')}
                </p>
              </Section>

              <Section id="living" title={t('termsPage.toc5')}>
                <p>{t('termsPage.s5_p1')}</p>
                <ul className="list-disc pl-5 space-y-1">
                  <li>{t('termsPage.s5_li1')}</li>
                  <li>{t('termsPage.s5_li2')}</li>
                  <li>{t('termsPage.s5_li3')}</li>
                  <li>{t('termsPage.s5_li4')}</li>
                  <li>{t('termsPage.s5_li5')}</li>
                </ul>
                <p>{t('termsPage.s5_p2')}</p>
              </Section>

              <Section id="acceptable-use" title={t('termsPage.toc6')}>
                <p>{t('termsPage.s6_p1')}</p>
                <ul className="list-disc pl-5 space-y-1">
                  <li>{t('termsPage.s6_li1')}</li>
                  <li>{t('termsPage.s6_li2')}</li>
                  <li>{t('termsPage.s6_li3')}</li>
                  <li>{t('termsPage.s6_li4')}</li>
                  <li>{t('termsPage.s6_li5')}</li>
                  <li>{t('termsPage.s6_li6')}</li>
                  <li>{t('termsPage.s6_li7')}</li>
                  <li>{t('termsPage.s6_li8')}</li>
                  <li>{t('termsPage.s6_li9')}</li>
                </ul>
                <p>{t('termsPage.s6_p2')}</p>
              </Section>

              <Section id="ip" title={t('termsPage.toc7')}>
                <p>{t('termsPage.s7_p1')}</p>
                <p>{t('termsPage.s7_p2')}</p>
                <p>
                  {t('termsPage.s7_p3_before')}
                  <a href={`mailto:${CONTACT_EMAIL}`} className="text-brand-600 hover:underline">{CONTACT_EMAIL}</a>
                  {t('termsPage.s7_p3_after')}
                </p>
              </Section>

              <Section id="privacy" title={t('termsPage.toc8')}>
                <p>
                  {t('termsPage.s8_p1_before')}
                  <Link to="/privacy" className="text-brand-600 hover:underline">{t('termsPage.s8_p1_link')}</Link>
                  {t('termsPage.s8_p1_after')}
                </p>
                <p>{t('termsPage.s8_p2')}</p>
              </Section>

              <Section id="disclaimers" title={t('termsPage.toc9')}>
                <p>{t('termsPage.s9_p1')}</p>
                <p>{t('termsPage.s9_p2')}</p>
                <p>{t('termsPage.s9_p3')}</p>
              </Section>

              <Section id="security" title={t('termsPage.toc10')}>
                <p>
                  <strong>{t('termsPage.s10_p1_label')}</strong>{t('termsPage.s10_p1')}
                </p>
                <p>
                  <strong>{t('termsPage.s10_p2_label')}</strong>{t('termsPage.s10_p2')}<strong>{t('termsPage.s10_p2_bold')}</strong>{t('termsPage.s10_p2_after')}
                </p>
                <ul className="list-disc pl-5 space-y-1">
                  <li>{t('termsPage.s10_li1')}</li>
                  <li>{t('termsPage.s10_li2')}</li>
                  <li>{t('termsPage.s10_li3')}</li>
                  <li>{t('termsPage.s10_li4')}</li>
                  <li>{t('termsPage.s10_li5')}</li>
                  <li>{t('termsPage.s10_li6')}</li>
                </ul>
                <p>
                  <strong>{t('termsPage.s10_p3_label')}</strong>{t('termsPage.s10_p3')}
                </p>
                <p>
                  <strong>{t('termsPage.s10_p4_label')}</strong>{t('termsPage.s10_p4')}
                </p>
                <p>
                  <strong>{t('termsPage.s10_p5_label')}</strong>{t('termsPage.s10_p5')}
                </p>
                <div className="bg-amber-50 border border-amber-200 rounded-lg px-4 py-3 text-sm text-amber-800 mt-2">
                  <strong>{t('termsPage.s10_notice_label')}</strong>{t('termsPage.s10_notice')}
                </div>
              </Section>

              <Section id="liability" title={t('termsPage.toc11')}>
                <p>{t('termsPage.s11_p1')}</p>
                <ul className="list-disc pl-5 space-y-1">
                  <li>{t('termsPage.s11_li1')}</li>
                  <li>{t('termsPage.s11_li2')}</li>
                  <li>{t('termsPage.s11_li3')}</li>
                  <li>{t('termsPage.s11_li4')}</li>
                </ul>
                <p>{t('termsPage.s11_p2')}</p>
              </Section>

              <Section id="indemnification" title={t('termsPage.toc12')}>
                <p>{t('termsPage.s12_p1')}</p>
              </Section>

              <Section id="termination" title={t('termsPage.toc13')}>
                <p>
                  <strong>{t('termsPage.s13_p1_label')}</strong>{t('termsPage.s13_p1')}
                </p>
                <p>
                  <strong>{t('termsPage.s13_p2_label')}</strong>{t('termsPage.s13_p2')}
                </p>
                <p>{t('termsPage.s13_p3')}</p>
              </Section>

              <Section id="changes" title={t('termsPage.toc14')}>
                <p>{t('termsPage.s14_p1')}</p>
                <p>{t('termsPage.s14_p2')}</p>
                <p>{t('termsPage.s14_p3')}</p>
              </Section>

              <Section id="governing-law" title={t('termsPage.toc15')}>
                <p>{t('termsPage.s15_p1')}</p>
                <p>{t('termsPage.s15_p2')}</p>
              </Section>

              <Section id="contact" title={t('termsPage.toc16')}>
                <p>{t('termsPage.s16_p1')}</p>
                <div className="bg-gray-50 rounded-lg p-4 mt-2">
                  <p className="font-semibold text-gray-800">{t('termsPage.s16_company')}</p>
                  <p className="text-sm mt-1">
                    {t('termsPage.s16_email')}<a href={`mailto:${CONTACT_EMAIL}`} className="text-brand-600 hover:underline">{CONTACT_EMAIL}</a>
                  </p>
                  <p className="text-sm mt-1">
                    {t('termsPage.s16_contactForm')}<Link to="/contact" className="text-brand-600 hover:underline">{t('termsPage.s16_contactLink')}</Link>
                  </p>
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
