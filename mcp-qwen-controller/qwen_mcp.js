const { spawn } = require('child_process');
const path = require('path');

// Caminho absoluto para o interpretador Python (com barras normais para evitar escape)
const pythonExe = 'C:/Users/tiago/AppData/Local/Programs/Python/Python312/python.exe';
const pythonScript = path.join(__dirname, 'qwen_mcp.py');

// Executa o Python repassando os canais stdio (herdando)
const child = spawn(pythonExe, [pythonScript], { stdio: 'inherit' });

child.on('error', (err) => {
  console.error('[JS-WRAPPER] Erro ao iniciar processo Python:', err);
  process.exit(1);
});

child.on('exit', (code) => {
  process.exit(code);
});
