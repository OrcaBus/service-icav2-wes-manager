import { defineConfig, globalIgnores } from 'eslint/config';
import globals from 'globals';
import js from '@eslint/js';
import tseslint from 'typescript-eslint';

export default defineConfig([
  { files: ['**/*.{js,mjs,cjs,ts}'] },
  { files: ['**/*.{js,mjs,cjs,ts}'], languageOptions: { globals: globals.browser } },
  { files: ['**/*.{js,mjs,cjs,ts}'], plugins: { js }, extends: ['js/recommended'] },
  tseslint.configs.recommended,
  {
    // CommonJS bootstrap files run under Node and legitimately use require().
    files: ['**/*.cjs'],
    languageOptions: { globals: globals.node },
    rules: {
      '@typescript-eslint/no-require-imports': 'off',
    },
  },
  globalIgnores([
    '.venv/',
    'cdk.out/',
    'node_modules/*',
    'app/*', // App folder should have its own eslint config
  ]),
]);
