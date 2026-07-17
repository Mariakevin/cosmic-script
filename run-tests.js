const { execSync } = require('child_process');
const path = require('path');
const fs = require('fs');

const venvPython = path.join(__dirname, '.venv', 'Scripts', 'python.exe');

if (!fs.existsSync(venvPython)) {
  console.error('ERROR: Python venv not found at', venvPython);
  process.exit(1);
}

// All CLI args after 'node run-tests.js' go directly to pytest
const extraArgs = process.argv.slice(2).join(' ');
const testArgs = extraArgs || 'tests/ --tb=short -q';

const cmd = `"${venvPython}" -m pytest ${testArgs}`;
console.log(`Running: ${cmd}\n`);
console.log('='.repeat(70));

try {
  const output = execSync(cmd, {
    cwd: __dirname,
    encoding: 'utf-8',
    timeout: 300000,
    stdio: ['pipe', 'pipe', 'pipe']
  });
  process.stdout.write(output);
} catch (e) {
  if (e.stdout) process.stdout.write(e.stdout);
  if (e.stderr) process.stderr.write(e.stderr);
  process.exit(e.status || 1);
}
