interface UserAvatarProps {
  avatarUrl?: string | null;
  displayName?: string;
  email?: string;
  size?: 'sm' | 'md' | 'lg';
}

const SIZE_MAP = {
  sm: 'w-8 h-8 text-xs',
  md: 'w-10 h-10 text-sm',
  lg: 'w-16 h-16 text-lg',
} as const;

export function UserAvatar({ avatarUrl, displayName, email, size = 'md' }: UserAvatarProps) {
  const initials = (displayName || email || '?')
    .split(' ')
    .map((w) => w[0])
    .join('')
    .slice(0, 2)
    .toUpperCase();

  const sizeClass = SIZE_MAP[size];

  return (
    <div className={`${sizeClass} rounded-full bg-brand-100 flex items-center justify-center text-brand-700 font-semibold flex-shrink-0 overflow-hidden`}>
      {avatarUrl ? (
        <img src={avatarUrl} alt="" className="w-full h-full object-cover" referrerPolicy="no-referrer" />
      ) : (
        initials
      )}
    </div>
  );
}
