// Exercise native sharp/libvips in the final image, not the build stage.
const assert = require("node:assert/strict");
const sharp = require("sharp");

(async () => {
  const input = await sharp({
    create: { width: 64, height: 48, channels: 3, background: "#7e2845" },
  }).png().toBuffer();
  const output = await sharp(input).resize(32, 24).webp().toBuffer();
  const metadata = await sharp(output).metadata();
  assert.equal(metadata.format, "webp");
  assert.equal(metadata.width, 32);
  assert.equal(metadata.height, 24);
  console.log(`Production image encoding verified: sharp ${sharp.versions.sharp}, libvips ${sharp.versions.vips}`);
})().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
