export const TRAY_ICON_POINTS = 18;

const BLACK_BGR = [0, 0, 0] as const;
const OPAQUE = 255;
const DOT_RADIUS = 0.14;
const RING_INNER_RADIUS = 0.32;
const RING_OUTER_RADIUS = 0.45;
const HALF_PIXEL = 0.5;

/** The menu-bar icon at the scale as BGRA pixels: black, opaque in a dot and a ring around it, clear elsewhere. */
export function trayIconPixels(scale: number): Buffer {
  const size = TRAY_ICON_POINTS * scale;
  const alphas = Array.from({ length: size * size }, (_, i) => alphaAt(i % size, Math.floor(i / size), size));
  return Buffer.from(alphas.flatMap((alpha) => [...BLACK_BGR, alpha]));
}

function alphaAt(x: number, y: number, size: number): number {
  const centre = size / 2;
  const distance = Math.hypot(x + HALF_PIXEL - centre, y + HALF_PIXEL - centre);
  return Math.round(OPAQUE * coverage(distance, size));
}

/** How much of a pixel at the distance from the centre the dot and the ring cover, from 0 to 1. */
function coverage(distance: number, size: number): number {
  const dot = insideCircle(distance, DOT_RADIUS * size);
  const ring = insideCircle(distance, RING_OUTER_RADIUS * size) - insideCircle(distance, RING_INNER_RADIUS * size);
  return dot + ring;
}

/** How much of a pixel lies inside the circle: 1 within it, 0 beyond it, and a one-pixel ramp across its edge. */
function insideCircle(distance: number, radius: number): number {
  return Math.min(1, Math.max(0, radius - distance + HALF_PIXEL));
}
