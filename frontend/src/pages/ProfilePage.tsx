import React, { useMemo } from 'react';
import { useTranslation } from 'react-i18next';
import { useParams, Link, useLocation } from 'react-router-dom';
import { SEO } from '@shared/components/SEO';
import { useQuery } from '@tanstack/react-query';
import { useAuthStore } from '@store/auth.store';
import { queryKeys } from '@queries/keys';
import { get } from '@api/client';
import type { ApiTreeGraph } from '@features/tree/types';
import { isPreset, presetDataUri } from '@features/tree/avatarPresets';

interface PersonDetail {
  id: string;
  tree_id: string;
  display_given_name: string;
  display_surname: string;
  sex: string;
  is_living: boolean;
  is_deceased: boolean;
  photo_url?: string | null;
  parents: string[];
  children: string[];
  spouses: string[];
  siblings: string[];
}

// SEX_LABEL moved inside component to access t()
const SEX_BADGE: Record<string, string> = {
  MALE:    'bg-blue-100 text-blue-700',
  FEMALE:  'bg-pink-100 text-pink-700',
  OTHER:   'bg-purple-100 text-purple-700',
  UNKNOWN: 'bg-gray-100 text-gray-600',
};
const SEX_AVATAR: Record<string, string> = {
  MALE:    'bg-blue-50 text-blue-600',
  FEMALE:  'bg-pink-50 text-pink-600',
  OTHER:   'bg-purple-50 text-purple-600',
  UNKNOWN: 'bg-gray-100 text-gray-500',
};

// ── Relative list ──────────────────────────────────────────────────────────

function RelativeList({
  ids, label, treeId, nameMap, photoMap,
}: {
  ids: string[];
  label: string;
  treeId: string;
  nameMap: Record<string, string>;
  photoMap: Record<string, string | undefined>;
}) {
  if (ids.length === 0) return null;
  return (
    <div>
      <h3 className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-2">{label}</h3>
      <div className="space-y-1">
        {ids.map((id) => {
          const name = nameMap[id] ?? 'Unknown';
          const initial = name[0]?.toUpperCase() ?? '?';
          const photo = photoMap[id];
          return (
            <Link
              key={id}
              to={`/trees/${treeId}/persons/${id}`}
              className="flex items-center gap-3 px-3 py-2 rounded-lg hover:bg-gray-50 group transition-colors"
            >
              {photo ? (
                <img
                  src={photo}
                  alt={name}
                  className="w-7 h-7 rounded-full object-cover flex-shrink-0"
                />
              ) : (
                <span className="w-7 h-7 rounded-full bg-gray-100 flex items-center justify-center text-xs font-semibold text-gray-500 group-hover:bg-brand-50 group-hover:text-brand-600 transition-colors flex-shrink-0">
                  {initial}
                </span>
              )}
              <span className="text-sm text-gray-800 group-hover:text-brand-600 transition-colors">{name}</span>
            </Link>
          );
        })}
      </div>
    </div>
  );
}

// ── Page ───────────────────────────────────────────────────────────────────

export default function ProfilePage() {
  const { t } = useTranslation();
  const { treeId, personId } = useParams<{ treeId: string; personId: string }>();
  const accessToken = useAuthStore((s) => s.accessToken);
  const location = useLocation();
  const fromSearch = location.state?.from === 'search';
  const backTo    = fromSearch ? (location.state.searchUrl as string) : `/trees/${treeId}`;
  const backLabel = fromSearch ? '← Back to results' : t('profilePage.backToTree');

  const SEX_LABEL: Record<string, string> = {
    MALE: t('profilePage.male'), FEMALE: t('profilePage.female'), OTHER: t('profilePage.other'), UNKNOWN: t('profilePage.unknown'),
  };

  const { data: person, isLoading, error } = useQuery<PersonDetail>({
    queryKey: queryKeys.persons.detail(treeId ?? '', personId ?? ''),
    queryFn: () => get<PersonDetail>(`/trees/${treeId}/persons/${personId}`),
    enabled: !!treeId && !!personId && !!accessToken,
    staleTime: 5 * 60_000,
  });

  // Graph is cached by FamilyTreePage — no extra network cost when navigated from there
  const { data: graph } = useQuery<ApiTreeGraph>({
    queryKey: queryKeys.trees.detail(treeId ?? ''),
    queryFn: () => get<ApiTreeGraph>(`/trees/${treeId}/graph`),
    enabled: !!treeId && !!accessToken,
    staleTime: 5 * 60_000,
  });

  const nameMap = useMemo(() => {
    const map: Record<string, string> = {};
    graph?.persons.forEach((p) => {
      map[p.id] = `${p.displayGivenName} ${p.displaySurname}`.trim() || 'Unknown';
    });
    return map;
  }, [graph]);

  const photoMap = useMemo(() => {
    const map: Record<string, string | undefined> = {};
    graph?.persons.forEach((p) => {
      map[p.id] = p.photoUrl ?? undefined;
    });
    return map;
  }, [graph]);

  if (isLoading) {
    return (
      <div className="flex justify-center items-center py-32">
        <div className="w-7 h-7 border-2 border-brand-500 border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  if (error || !person) {
    return (
      <div className="p-8 max-w-3xl mx-auto">
        <Link to={backTo} className="text-sm text-gray-500 hover:text-gray-800 mb-6 inline-block">
          {backLabel}
        </Link>
        <p className="text-sm text-red-600">{t('profilePage.failedToLoad')}</p>
      </div>
    );
  }

  const fullName = `${person.display_given_name} ${person.display_surname}`.trim() || 'Unknown';
  const initial  = (person.display_given_name?.[0] ?? person.display_surname?.[0] ?? '?').toUpperCase();
  const avatarCls = SEX_AVATAR[person.sex] ?? SEX_AVATAR.UNKNOWN;
  const badgeCls  = SEX_BADGE[person.sex]  ?? SEX_BADGE.UNKNOWN;

  const hasRelatives =
    person.parents.length + person.spouses.length +
    person.children.length + person.siblings.length > 0;

  return (
    <div className="p-4 md:p-8 max-w-3xl mx-auto">
      <SEO
        title={fullName}
        description={`View ${fullName}'s profile — family connections, relatives, and biographical details on OurFamRoots.`}
        ogType="profile"
        noIndex
      />
      {/* Back */}
      <Link
        to={backTo}
        className="inline-flex items-center gap-1 text-sm text-gray-500 hover:text-gray-800 mb-6 transition-colors"
      >
        {t('profilePage.backToTree')}
      </Link>

      {/* Header card */}
      <div className="bg-white rounded-2xl border border-gray-200 p-4 md:p-6 mb-4 md:mb-5 flex flex-col sm:flex-row sm:items-start gap-4">
        {person.photo_url ? (
          <img
            src={isPreset(person.photo_url) ? presetDataUri(person.photo_url)! : person.photo_url}
            alt={fullName}
            className="w-16 h-16 rounded-xl object-cover flex-shrink-0"
          />
        ) : (
          <div className={`w-16 h-16 rounded-xl flex items-center justify-center text-2xl font-bold flex-shrink-0 ${avatarCls}`}>
            {initial}
          </div>
        )}

        <div className="flex-1 min-w-0">
          <h1 className="text-2xl font-bold text-gray-900 mb-2">{fullName}</h1>
          <div className="flex flex-wrap items-center gap-2">
            <span className={`text-xs font-medium px-2.5 py-0.5 rounded-full ${badgeCls}`}>
              {SEX_LABEL[person.sex] ?? person.sex}
            </span>
            {person.is_deceased ? (
              <span className="text-xs font-medium px-2.5 py-0.5 rounded-full bg-gray-100 text-gray-600">
                {t('profilePage.deceased')}
              </span>
            ) : person.is_living ? (
              <span className="text-xs font-medium px-2.5 py-0.5 rounded-full bg-green-100 text-green-700">
                {t('profilePage.living')}
              </span>
            ) : null}
          </div>
        </div>
      </div>

      {/* Relationships card */}
      <div className="bg-white rounded-2xl border border-gray-200 p-6">
        <h2 className="text-sm font-semibold text-gray-900 mb-4">{t('profilePage.relationships')}</h2>
        {hasRelatives ? (
          <div className="space-y-5">
            <RelativeList ids={person.parents}  label={t('profilePage.parents')}  treeId={treeId ?? ''} nameMap={nameMap} photoMap={photoMap} />
            <RelativeList ids={person.spouses}  label={t('profilePage.spouses')}  treeId={treeId ?? ''} nameMap={nameMap} photoMap={photoMap} />
            <RelativeList ids={person.children} label={t('profilePage.children')} treeId={treeId ?? ''} nameMap={nameMap} photoMap={photoMap} />
            <RelativeList ids={person.siblings} label={t('profilePage.siblings')} treeId={treeId ?? ''} nameMap={nameMap} photoMap={photoMap} />
          </div>
        ) : (
          <div className="text-center py-8 text-gray-400">
            <p className="text-sm">{t('profilePage.noRelationships')}</p>
            <Link to={`/trees/${treeId}`} className="text-xs text-brand-500 hover:underline mt-1 inline-block">
              {t('profilePage.addFromCanvas')}
            </Link>
          </div>
        )}
      </div>
    </div>
  );
}
