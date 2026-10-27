import assert from "node:assert/strict";
import { test } from "node:test";

import { TRAY_ICON_POINTS, trayIconPixels } from "./trayIcon";

const BYTES_PER_PIXEL = 4;

function alphaAt(pixels: Buffer, size: number, x: number, y: number): number {
  return pixels[(y * size + x) * BYTES_PER_PIXEL + 3];
}

test("the icon is one BGRA pixel per point at each scale", () => {
  for (const scale of [1, 2]) {
    const size = TRAY_ICON_POINTS * scale;
    assert.equal(trayIconPixels(scale).length, size * size * BYTES_PER_PIXEL);
  }
});

test("the icon is black, so macOS can tint it as a template image", () => {
  const pixels = trayIconPixels(2);
  for (let i = 0; i < pixels.length; i += BYTES_PER_PIXEL) {
    assert.deepEqual([pixels[i], pixels[i + 1], pixels[i + 2]], [0, 0, 0]);
  }
});

test("the icon is a ring with a dot: solid centre, clear gap, solid ring, clear corners", () => {
  const size = TRAY_ICON_POINTS * 2;
  const pixels = trayIconPixels(2);
  const centre = Math.floor(size / 2);

  assert.equal(alphaAt(pixels, size, centre, centre), 255);
  assert.equal(alphaAt(pixels, size, centre + Math.round(size * 0.2), centre), 0);
  assert.equal(alphaAt(pixels, size, centre + Math.round(size * 0.38), centre), 255);
  assert.equal(alphaAt(pixels, size, 0, 0), 0);
});
