import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
const frontend = fileURLToPath(new URL('..', import.meta.url));
const root = fileURLToPath(new URL('../..', import.meta.url));
const commands = [
  ['npm', ['test', '--', '--reporter=verbose'], frontend],
  ['npm', ['run', 'typecheck'], frontend],
  ['npm', ['run', 'build'], frontend],
  ['.venv/bin/python', ['-m', 'pytest', 'engine/tests', '-v'], root],
  ['git', ['diff', '--check'], root],
  ['node', ['--experimental-strip-types', 'scripts/smoke-api.mjs', ...(process.argv[2] ? [process.argv[2]] : [])], frontend],
];
for (const [command, args, cwd] of commands) {
  console.log(`\n$ ${command} ${args.join(' ')}`);
  const result = spawnSync(command, args, { cwd, stdio: 'inherit' });
  if (result.error) console.error(result.error.message);
  if (result.status !== 0) process.exit(result.status || 1);
}
console.log('Automated gate passed. Browser review remains mandatory; see frontend/README.md.');
