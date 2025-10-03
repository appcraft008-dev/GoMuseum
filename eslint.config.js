// eslint.config.js
const js = require('@eslint/js');
const globals = require('globals');

module.exports = [
  // 全局忽略配置必须放在第一位
  {
    ignores: [
      '**/node_modules/**',
      '**/.venv/**',
      '**/venv/**',
      '**/__pycache__/**',
      '**/backend/**',
      '**/docs/**',
      '**/coverage/**',
      '**/htmlcov/**',
      '**/.git/**',
      '**/.husky/**',
      '**/logs/**',
      '**/*.py',
      '**/*.pyc',
      '**/.pytest_cache/**',
      '**/.dart_tool/**',
      '**/.flutter-plugins*',
      '**/build/**',
      'eslint.config.js',
      '*.log',
      '.env*',
    ],
  },
  js.configs.recommended,
  {
    // 只 lint 项目根目录的JS文件和前端目录
    files: ['*.js', 'scripts/**/*.js', 'frontend/gomuseum_app/**/*.{js,ts,jsx,tsx}'],

    languageOptions: {
      globals: {
        ...globals.node,
        ...globals.browser,
      },
    },

    rules: {
      'no-unused-vars': 'warn',
      'no-undef': 'error',
      semi: ['error', 'always'],
      quotes: ['error', 'single'],
    },
  },
];
