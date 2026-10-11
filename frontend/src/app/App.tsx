import { useEffect, useState } from 'react';
import { Layout } from './Layout';
import { Overview } from '../pages/Overview';
import { Network } from '../pages/Network';
import { Assessment } from '../pages/Assessment';
import { Planning } from '../pages/Planning';
import { NotFound } from '../pages/NotFound';

function currentPath() { return window.location.hash.slice(1).split('?')[0] || '/'; }
export function App() {
  const [path, setPath] = useState(currentPath);
  useEffect(() => {
    const navigate = () => setPath(currentPath());
    window.addEventListener('hashchange', navigate);
    return () => window.removeEventListener('hashchange', navigate);
  }, []);
  const pages = { '/': <Overview />, '/network': <Network />, '/assessment': <Assessment />, '/planning': <Planning /> };
  return <Layout path={path}>{pages[path as keyof typeof pages] ?? <NotFound />}</Layout>;
}
