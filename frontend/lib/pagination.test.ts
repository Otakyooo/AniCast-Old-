import assert from "node:assert/strict";
import { test } from "node:test";
import { paginationWindow } from "./pagination.ts";

test("short lists render every page without gaps", () => {
  assert.deepEqual(paginationWindow(1, 1), [1]);
  assert.deepEqual(paginationWindow(2, 3), [1, 2, 3]);
});

test("long lists keep the edges and a radius around the current page", () => {
  assert.deepEqual(paginationWindow(1, 40), [1, 2, 3, 40]);
  assert.deepEqual(paginationWindow(20, 40), [1, 18, 19, 20, 21, 22, 40]);
  assert.deepEqual(paginationWindow(40, 40), [1, 38, 39, 40]);
});

test("the window radius stays configurable", () => {
  assert.deepEqual(paginationWindow(10, 40, 1), [1, 9, 10, 11, 40]);
});
