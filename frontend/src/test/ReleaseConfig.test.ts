import { expect, it } from 'vitest';
import { productionApiBase } from '../api/releaseConfig';
it.each([undefined, '', '/api', 'http://localhost:8000', '//example.com', 'https://user:password@example.com', 'https://example.com?token=unsafe', 'https://example.com#fragment'])('rejects unsafe or development-only production API base %s', value => {
  expect(() => productionApiBase(value)).toThrow();
});
it('accepts an explicit HTTPS production API with a base path', () => {
  expect(productionApiBase('https://example.com/api')).toBe('https://example.com/api');
});
