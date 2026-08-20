import { createRequire } from "node:module";
import { FlatCompat } from "@eslint/eslintrc";
import { defineConfig, globalIgnores } from "eslint/config";

const require = createRequire(import.meta.url);
const compat = new FlatCompat({ baseDirectory: process.cwd() });

export default defineConfig([
  globalIgnores([".next/**", "node_modules/**"]),
  ...compat.extends("next/core-web-vitals"),
]);
