import { afterEach } from 'vitest';
import { cleanup } from '@testing-library/react';
afterEach(() => { cleanup(); if (typeof window !== 'undefined') window.location.hash = '#/'; });
