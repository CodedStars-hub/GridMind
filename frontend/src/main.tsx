import { createRoot } from 'react-dom/client';
import { App } from './app/App';
import { DataProvider } from './app/DataProvider';
import { ErrorBoundary } from './app/ErrorBoundary';
import './styles.css';

const element = document.getElementById('root');
if (!element) throw new Error('The application root is missing.');
createRoot(element).render(<ErrorBoundary><DataProvider><App /></DataProvider></ErrorBoundary>);
