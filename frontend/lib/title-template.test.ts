import assert from "node:assert/strict";
import { test } from "node:test";
import { resolveTitleEpisodeRequest, titleTemplateState } from "./title-template.ts";

test("series keep episodic navigation and an episode collection", () => {
  assert.deepEqual(titleTemplateState("anime", 24), {
    playbackPresentation: "episodic",
    showEpisodeCount: true,
    showEpisodeTab: true,
    structuredEpisodeCount: 24,
  });
  // One released episode of an airing series must not be mistaken for a film.
  assert.equal(titleTemplateState("anime", 1).playbackPresentation, "episodic");
});

test("movies stay a single playback unit despite polluted part metadata", () => {
  assert.deepEqual(titleTemplateState("movie", 10), {
    playbackPresentation: "single",
    showEpisodeCount: false,
    showEpisodeTab: false,
    structuredEpisodeCount: null,
  });
});

test("single OVA and special titles compact while real collections stay episodic", () => {
  assert.equal(titleTemplateState("ova", 1).playbackPresentation, "single");
  assert.equal(titleTemplateState("special", 0).playbackPresentation, "single");
  assert.equal(titleTemplateState("ova", 3).playbackPresentation, "episodic");
  assert.equal(titleTemplateState("special", 2).showEpisodeTab, true);
});

test("missing or invalid counts never invent an episode collection", () => {
  assert.deepEqual(titleTemplateState("anime", undefined), {
    playbackPresentation: "episodic",
    showEpisodeCount: false,
    showEpisodeTab: false,
    structuredEpisodeCount: null,
  });
  assert.equal(titleTemplateState("anime", -4).showEpisodeTab, false);
});

test("episode query resolution respects single titles and real catalog gaps", () => {
  assert.deepEqual(resolveTitleEpisodeRequest("single", 1, "6", [1, 6]), {
    number: 1,
    corrected: true,
  });
  assert.deepEqual(resolveTitleEpisodeRequest("episodic", 1, "26", [1, 2, 26]), {
    number: 26,
    corrected: false,
  });
  assert.deepEqual(resolveTitleEpisodeRequest("episodic", 1, "3", [1, 2, 26]), {
    number: 1,
    corrected: true,
  });
  assert.deepEqual(resolveTitleEpisodeRequest("episodic", 1, "not-a-number"), {
    number: 1,
    corrected: true,
  });
  // During an old-backend rollout the catalog list can be unknown, so a
  // positive request is verified by the episode detail endpoint instead.
  assert.deepEqual(resolveTitleEpisodeRequest("episodic", 1, "100"), {
    number: 100,
    corrected: false,
  });
});
