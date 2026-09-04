import assert from "node:assert/strict";
import { test } from "node:test";
import { titleNameRows } from "./title-names.ts";

test("collapses names repeated across languages", () => {
  const rows = titleNameRows(
    { ru: "Ван-Пис", en: "ONE PIECE", ja: "ONE PIECE" },
    "Ван-Пис",
  );
  assert.deepEqual(
    rows.map((row) => [row.language, row.name]),
    [["ru", "Ван-Пис"], ["en", "ONE PIECE"]],
  );
});

test("keeps the JA tag only for Japanese script", () => {
  const rows = titleNameRows(
    { ru: "Ван-Пис", en: "ONE PIECE", ja: "ワンピース" },
    "Ван-Пис",
  );
  const jaRow = rows.find((row) => row.language === "ja");
  assert.equal(jaRow?.showLanguageTag, true);

  const latin = titleNameRows({ ru: "Ван-Пис", ja: "ONE PIECE" }, "Ван-Пис");
  assert.equal(latin.find((row) => row.language === "ja")?.showLanguageTag, false);
});

test("falls back to the main name and original name", () => {
  const rows = titleNameRows(null, "Наруто", "NARUTO");
  assert.deepEqual(
    rows.map((row) => [row.language, row.name]),
    [["ru", "Наруто"], ["ja", "NARUTO"]],
  );
  assert.equal(rows[1].showLanguageTag, false);
});

test("skips an empty original name", () => {
  const rows = titleNameRows({}, "Наруто", "");
  assert.equal(rows.length, 1);
});
