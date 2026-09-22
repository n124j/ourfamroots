import React from 'react';
import { SEO } from '@shared/components/SEO';
import { MarketingPageLayout } from './MarketingPageLayout';

const FEATURES = [
  {
    title: 'Automatic, not manual',
    body: 'The fan chart is generated from your family tree data — add an ancestor once and it appears in every view, fan chart included.',
  },
  {
    title: 'Multiple rings of ancestors',
    body: 'See several generations of ancestors radiating outward from one person at a glance.',
  },
  {
    title: 'Switch views anytime',
    body: 'The same tree also renders as a generation-sorted, pedigree, ancestor, or descendant layout — pick whichever view tells the story best.',
  },
  {
    title: 'Free to start',
    body: 'Create an account and start building your tree in minutes — no credit card required.',
  },
];

export default function FanChartGeneratorPage() {
  return (
    <>
      <SEO
        title="Free Fan Chart Generator"
        description="Generate a printable ancestor fan chart from your family tree for free — a circular, multi-ring view of your ancestors, built and updated automatically as you add family members."
        canonical="/fan-chart-generator"
        keywords="fan chart generator, ancestor fan chart, family tree fan chart, free fan chart maker, genealogy fan chart"
      />
      <MarketingPageLayout
        eyebrow="Free tool"
        heading="Turn your family tree into a fan chart"
        subheading="Add ancestors to your OurFamRoots tree and the circular fan chart builds itself — no manual layout work, ready to share."
        demoLabel="See a live fan chart"
      >
        <div className="grid sm:grid-cols-2 gap-6">
          {FEATURES.map((f) => (
            <div key={f.title} className="bg-white rounded-xl border border-gray-200 p-5">
              <h2 className="font-semibold text-gray-900 mb-1.5">{f.title}</h2>
              <p className="text-sm text-gray-600">{f.body}</p>
            </div>
          ))}
        </div>
      </MarketingPageLayout>
    </>
  );
}
