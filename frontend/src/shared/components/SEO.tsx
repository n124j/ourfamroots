import { Helmet } from 'react-helmet-async';

const SITE_NAME    = 'OurFamRoots';
const BASE_URL     = import.meta.env.VITE_FRONTEND_BASE_URL ?? 'https://ourfamroots.com';
const OG_IMAGE     = `${BASE_URL}/og-image.svg`;
const DEFAULT_DESC =
  'Free collaborative genealogy platform to build your family tree online. ' +
  'Interactive fan charts, pedigree views, ancestry charts, and relationship mapping tools. ' +
  'Trace 8+ generations of ancestors.';
const DEFAULT_KW   =
  'family tree builder, free genealogy software, ancestry chart, fan chart, pedigree chart, ' +
  'family history, ancestor search, family records, build family tree online, genealogy platform';

interface SEOProps {
  title: string;
  description?: string;
  keywords?: string;
  canonical?: string;
  noIndex?: boolean;
  ogImage?: string;
  ogImageAlt?: string;
  ogType?: 'website' | 'profile' | 'article';
  jsonLd?: object;
}

export function SEO({
  title,
  description = DEFAULT_DESC,
  keywords    = DEFAULT_KW,
  canonical,
  noIndex     = false,
  ogImage     = OG_IMAGE,
  ogImageAlt,
  ogType      = 'website',
  jsonLd,
}: SEOProps) {
  const fullTitle    = `${title} | ${SITE_NAME}`;
  const canonicalUrl = canonical
    ? `${BASE_URL}${canonical}`
    : typeof window !== 'undefined'
      ? window.location.href
      : undefined;
  const imageAlt = ogImageAlt ?? fullTitle;

  return (
    <Helmet>
      {/* Primary */}
      <title>{fullTitle}</title>
      <meta name="description"  content={description} />
      <meta name="keywords"     content={keywords} />
      <meta name="robots"       content={noIndex ? 'noindex, nofollow' : 'index, follow'} />
      {canonicalUrl && <link rel="canonical" href={canonicalUrl} />}

      {/* Open Graph */}
      <meta property="og:site_name"   content={SITE_NAME} />
      <meta property="og:locale"      content="en_US" />
      <meta property="og:type"        content={ogType} />
      <meta property="og:title"       content={fullTitle} />
      <meta property="og:description" content={description} />
      <meta property="og:image"       content={ogImage} />
      <meta property="og:image:width"  content="1200" />
      <meta property="og:image:height" content="630" />
      <meta property="og:image:alt"    content={imageAlt} />
      {canonicalUrl && <meta property="og:url" content={canonicalUrl} />}

      {/* Twitter Card */}
      <meta name="twitter:card"        content="summary_large_image" />
      <meta name="twitter:title"       content={fullTitle} />
      <meta name="twitter:description" content={description} />
      <meta name="twitter:image"       content={ogImage} />
      <meta name="twitter:image:alt"   content={imageAlt} />

      {jsonLd && (
        <script type="application/ld+json">
          {JSON.stringify(jsonLd)}
        </script>
      )}
    </Helmet>
  );
}
