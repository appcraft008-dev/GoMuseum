// eslint.config.js (CommonJS 写法)

const js = require('@eslint/js');
const globals = require('globals');

/**
 * ESLint 配置 (CommonJS 版本)
 * - 使用官方推荐规则
 * - 启用 Node.js 全局变量
 */
module.exports = [
  js.configs.recommended,
  {
    languageOptions: {
      globals: {
        ...globals.node, // Node.js 环境 (console, process 等)
      },
    },
    rules: {
      // 可以根据需要自定义规则：
      'no-unused-vars': 'warn', // 定义未使用的变量 → 警告
      'no-undef': 'error', // 使用未定义的变量 → 报错
      semi: ['error', 'always'], // 强制分号
      quotes: ['error', 'single'], // 强制单引号
    },
  },
];
