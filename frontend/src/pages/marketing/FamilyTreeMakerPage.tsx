import React from 'react';
import { SEO } from '@shared/components/SEO';
import { MarketingPageLayout } from './MarketingPageLayout';

const FEATURES = [
  {
    title: 'Multiple tree layouts',
    body: 'Switch between generation-sorted, pedigree, ancestor, descendant, and fan chart views of the same tree — no rebuilding required.',
  },
  {
    title: 'Build it together',
    body: 'Invite relatives as Owner, Admin, Editor, or Viewer. Everyone can help fill in the branches they know best.',
  },
  {
    title: 'Photos and stories',
    body: 'Attach photos and notes to each person, not just names and dates.',
  },
  {
    title: 'Free to start',
    body: 'Create an account and start building your tree in minutes — no credit card required.',
  },
];

export default function FamilyTreeMakerPage() {
  return (
    <>
      <SEO
        title="Free Family Tree Maker"
        description="Build a collaborative family tree online for free. Multiple layouts — generation, pedigree, ancestor, descendant, and fan chart — with role-based collaboration."
        canonical="/family-tree-maker"
        keywords="family tree maker, free family tree builder, online family tree, genealogy tool, build family tree"
      />
      <MarketingPageLayout
        eyebrow="Free tool"
        heading="Build your family tree online, free"
        subheading="Add relatives, attach photos, and switch between generation, pedigree, ancestor, descendant, and fan chart layouts — then invite family to help build it with you."
        demoLabel="See a live example tree"
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
