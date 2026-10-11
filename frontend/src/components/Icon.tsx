export type IconName = 'grid' | 'bolt' | 'chart' | 'battery' | 'arrow' | 'plan' | 'sun' | 'shield' | 'clock';

export function Icon({ name, className = '' }: { name: IconName; className?: string }) {
  const paths: Record<IconName, string> = {
    grid: 'M3 3h7v7H3z M14 3h7v7h-7z M3 14h7v7H3z M14 14h7v7h-7z',
    bolt: 'M13 2 4 14h7l-1 8 10-13h-8z',
    chart: 'M3 3v18h18 M6 15l4-5 4 3 6-9',
    battery: 'M3 7h17v10H3z M20 10h2v4 M7 10v4 M5 12h4 M13 12h3',
    arrow: 'M4 12h16 M14 6l6 6-6 6',
    plan: 'M5 3v18 M5 5h14l-3 4 3 4H5',
    sun: 'M12 3v2 M12 19v2 M3 12h2 M19 12h2 M5.6 5.6l1.4 1.4 M17 17l1.4 1.4 M5.6 18.4l1.4-1.4 M17 7l1.4-1.4 M12 7a5 5 0 1 0 0 10 5 5 0 0 0 0-10z',
    shield: 'M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z',
    clock: 'M12 22a10 10 0 1 0 0-20 10 10 0 0 0 0 20z M12 6v6l4 2',
  };
  return (
    <svg 
      className={`icon ${className}`} 
      viewBox="0 0 24 24" 
      fill="none" 
      stroke="currentColor" 
      strokeWidth="1.8" 
      strokeLinecap="round" 
      strokeLinejoin="round" 
      aria-hidden="true"
    >
      <path d={paths[name]} />
    </svg>
  );
}
