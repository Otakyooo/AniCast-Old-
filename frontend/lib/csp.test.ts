import assert from "node:assert/strict";
import test from "node:test";
import { contentSecurityPolicy } from "./csp.ts";

test("production scripts require a nonce and reject inline handlers/eval", () => {
  const policy = contentSecurityPolicy("a".repeat(32));
  const scripts = policy.split("; ").find((part) => part.startsWith("script-src "))!;
  assert.ok(scripts.includes("'nonce-" + "a".repeat(32) + "'"));
  assert.ok(!scripts.includes("unsafe-inline") && !scripts.includes("unsafe-eval"));
  assert.ok(policy.includes("script-src-attr 'none'"));
  assert.ok(policy.includes("frame-src 'self' https://kodikplayer.com"));
});
test("nonce input cannot inject a policy directive", () => {
  for (const nonce of ["", "short", "a".repeat(32) + "'; script-src *"]) {
    assert.throws(() => contentSecurityPolicy(nonce));
  }
});
