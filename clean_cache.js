const { spawn } = require('child_process');
const path = require('path');

const venvPython = path.join(__dirname, '.venv', 'Scripts', 'python.exe');
const code = `import shutil, glob; [shutil.rmtree(d, True) for d in glob.glob('cosmic_script/**/__pycache__', recursive=True)]`;

const proc = spawn(venvPython, ['-c', code], { cwd: __dirname, stdio: 'inherit' });
proc.on('close', (code) => process.exit(code));
