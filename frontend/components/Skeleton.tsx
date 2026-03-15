export default function Skeleton({ className = '' }: { className?: string }) {
  return (
    <div
      className={`rounded-md animate-skeleton ${className}`}
      style={{ background: 'var(--border)' }}
    />
  );
}
