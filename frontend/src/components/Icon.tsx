export function Icon({ name, className = '' }: { name: 'grid' | 'bolt' | 'chart' | 'battery' | 'arrow' | 'plan'; className?: string }) {
  const paths = {
    grid: 'M3 3h7v7H3z M14 3h7v7h-7z M3 14h7v7H3z M14 14h7v7h-7z',
    bolt: 'M13 2 4 14h7l-1 8 10-13h-8z',
    chart: 'M3 3v18h18 M6 15l4-5 4 3 6-9',
    battery: 'M3 7h17v10H3z M20 10h2v4 M7 10v4 M5 12h4 M13 12h3',
    arrow: 'M4 12h16 M14 6l6 6-6 6',
    plan: 'M5 3v18 M5 5h14l-3 4 3 4H5',
  };
  return <svg className={`icon ${className}`} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d={paths[name]} /></svg>;
}
