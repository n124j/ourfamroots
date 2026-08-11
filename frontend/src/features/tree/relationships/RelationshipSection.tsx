import React from 'react';
import { useTranslation } from 'react-i18next';
import { PersonAvatar } from '@pages/FamilyTreePage';
import type { ApiPerson, ApiRelationship } from '@features/tree/types';
import { relationshipRowLabel } from './labels';

interface RelationshipSectionProps {
  personId: string;
  relationships: ApiRelationship[];
  personMap: Record<string, ApiPerson>;
  nameMap: Record<string, string>;
  canWrite: boolean;
  onNavigate: (personId: string) => void;
  onAdd: () => void;
  onRemove: (relationshipId: string) => void;
}

export function RelationshipSection({
  personId, relationships, personMap, nameMap, canWrite, onNavigate, onAdd, onRemove,
}: RelationshipSectionProps) {
  const { t } = useTranslation();
  const mine = relationships.filter((r) => r.person1_id === personId || r.person2_id === personId);

  return (
    <div className="rounded-xl border border-gray-100 overflow-hidden">
      <div className="px-4 py-2.5 bg-gray-50 border-b border-gray-100 flex items-center justify-between">
        <span className="text-xs font-semibold text-gray-500 uppercase tracking-wider">{t('treeForm.otherRelationships')}</span>
        {canWrite && (
          <button
            type="button"
            onClick={onAdd}
            className="text-xs font-medium text-brand-600 hover:text-brand-700 transition-colors"
          >
            + {t('treeForm.addRelationship')}
          </button>
        )}
      </div>
      {mine.length > 0 ? (
        <div className="divide-y divide-gray-50 p-1">
          {mine.map((rel) => {
            const otherId = rel.person1_id === personId ? rel.person2_id : rel.person1_id;
            const other = personMap[otherId];
            const name = nameMap[otherId] ?? t('treeForm.unknown');
            const label = relationshipRowLabel(t, rel, personId);
            return (
              <div key={rel.id} className="flex items-center gap-2 w-full px-2 py-1 rounded-lg hover:bg-gray-50 group transition-colors">
                <button
                  type="button"
                  onClick={() => onNavigate(otherId)}
                  className="flex items-center gap-3 flex-1 min-w-0 px-1 py-1 text-left"
                >
                  <PersonAvatar photoUrl={other?.photoUrl} name={name} sex={other?.sex ?? 'UNKNOWN'} size={28} />
                  <div className="flex-1 min-w-0">
                    <span className="text-sm text-gray-800 group-hover:text-brand-600 transition-colors truncate block">{name}</span>
                    <span className="text-[10px] text-gray-400 block truncate">{label}</span>
                  </div>
                </button>
                {canWrite && (
                  <button
                    type="button"
                    onClick={() => onRemove(rel.id)}
                    title={t('treeForm.removeOtherRelationship')}
                    className="w-6 h-6 flex items-center justify-center rounded-lg text-gray-300 hover:text-red-500 hover:bg-red-50 transition-colors flex-shrink-0 sm:opacity-0 sm:group-hover:opacity-100 focus:opacity-100"
                  >
                    ✕
                  </button>
                )}
              </div>
            );
          })}
        </div>
      ) : (
        <p className="px-4 py-6 text-center text-sm text-gray-400">{t('treeForm.noOtherRelationships')}</p>
      )}
    </div>
  );
}
