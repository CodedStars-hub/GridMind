import { useState } from 'react';

/**
 * GridMind brand logo component.
 * Uses the supplied /logo.svg asset, with an inline high-contrast fallback
 * if the SVG is empty or still being supplied.
 */
export function BrandLogo({ className = 'brand-logo' }: { className?: string }) {
  const [imgFailed, setImgFailed] = useState(false);

  if (imgFailed) {
    return (
      <svg
        className={className}
        viewBox="0 0 32 32"
        fill="none"
        xmlns="http://www.w3.org/2000/svg"
        aria-label="GridMind Logo"
      >
        <rect width="32" height="32" rx="8" fill="#0f172a" />
        <path
          d="M6 16H11L14 8L18 24L21 16H26"
          stroke="#38bdf8"
          strokeWidth="2.5"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
        <circle cx="14" cy="8" r="2" fill="#fbbf24" />
        <circle cx="18" cy="24" r="2" fill="#10b981" />
        <circle cx="21" cy="16" r="2" fill="#38bdf8" />
      </svg>
    );
  }

  return (
    <img
      src="/logo.svg"
      alt="GridMind Logo"
      className={className}
      onError={() => setImgFailed(true)}
    />
  );
}
