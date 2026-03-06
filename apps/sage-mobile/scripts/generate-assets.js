#!/usr/bin/env node
/**
 * Generate placeholder PNG assets for Sage Mobile.
 * Uses only Node.js built-in modules (no deps).
 * Creates solid-color PNGs with a centered "S" lettermark.
 */
const fs = require("fs");
const path = require("path");
const zlib = require("zlib");

const BG = { r: 4, g: 12, b: 28 };       // #040c1c
const ACCENT = { r: 47, g: 107, b: 255 }; // #2f6bff

// --- Minimal PNG encoder ---

function crc32(buf) {
  let crc = 0xffffffff;
  for (let i = 0; i < buf.length; i++) {
    crc ^= buf[i];
    for (let j = 0; j < 8; j++) {
      crc = (crc >>> 1) ^ (crc & 1 ? 0xedb88320 : 0);
    }
  }
  return (crc ^ 0xffffffff) >>> 0;
}

function chunk(type, data) {
  const len = Buffer.alloc(4);
  len.writeUInt32BE(data.length, 0);
  const typeAndData = Buffer.concat([Buffer.from(type, "ascii"), data]);
  const crc = Buffer.alloc(4);
  crc.writeUInt32BE(crc32(typeAndData), 0);
  return Buffer.concat([len, typeAndData, crc]);
}

function createPNG(width, height, pixelFn) {
  // Build raw image data (filter byte 0 + RGB per pixel per row)
  const rawRows = [];
  for (let y = 0; y < height; y++) {
    const row = Buffer.alloc(1 + width * 3);
    row[0] = 0; // filter: None
    for (let x = 0; x < width; x++) {
      const { r, g, b } = pixelFn(x, y, width, height);
      const off = 1 + x * 3;
      row[off] = r;
      row[off + 1] = g;
      row[off + 2] = b;
    }
    rawRows.push(row);
  }
  const rawData = Buffer.concat(rawRows);
  const compressed = zlib.deflateSync(rawData, { level: 6 });

  // IHDR
  const ihdr = Buffer.alloc(13);
  ihdr.writeUInt32BE(width, 0);
  ihdr.writeUInt32BE(height, 4);
  ihdr[8] = 8;  // bit depth
  ihdr[9] = 2;  // color type: RGB
  ihdr[10] = 0; // compression
  ihdr[11] = 0; // filter
  ihdr[12] = 0; // interlace

  const signature = Buffer.from([137, 80, 78, 71, 13, 10, 26, 10]);
  return Buffer.concat([
    signature,
    chunk("IHDR", ihdr),
    chunk("IDAT", compressed),
    chunk("IEND", Buffer.alloc(0)),
  ]);
}

// --- "S" lettermark renderer (simple block letter) ---

// Define "S" as a 7x9 bitmap
const S_BITMAP = [
  " ##### ",
  "#     #",
  "#      ",
  "#      ",
  " ##### ",
  "      #",
  "      #",
  "#     #",
  " ##### ",
];

function isInS(nx, ny) {
  // nx, ny in 0..1 range, returns true if inside the "S" glyph
  const col = Math.floor(nx * 7);
  const row = Math.floor(ny * 9);
  if (row < 0 || row >= 9 || col < 0 || col >= 7) return false;
  return S_BITMAP[row][col] === "#";
}

function iconPixel(x, y, w, h) {
  // Center the S in the middle 40% of the image
  const cx = x / w;
  const cy = y / h;
  const margin = 0.30;
  const sx = (cx - margin) / (1 - 2 * margin);
  const sy = (cy - margin) / (1 - 2 * margin);

  if (sx >= 0 && sx <= 1 && sy >= 0 && sy <= 1 && isInS(sx, sy)) {
    return ACCENT;
  }
  return BG;
}

function solidBg() {
  return BG;
}

// --- Generate ---

const assetsDir = path.join(__dirname, "..", "assets");
fs.mkdirSync(assetsDir, { recursive: true });

console.log("Generating icon.png (64x64 → placeholder)...");
const icon = createPNG(64, 64, iconPixel);
fs.writeFileSync(path.join(assetsDir, "icon.png"), icon);

console.log("Generating adaptive-icon.png (64x64 → placeholder)...");
const adaptiveIcon = createPNG(64, 64, iconPixel);
fs.writeFileSync(path.join(assetsDir, "adaptive-icon.png"), adaptiveIcon);

console.log("Generating splash.png (64x138 → placeholder)...");
// Splash: same S centered in portrait aspect ratio
function splashPixel(x, y, w, h) {
  const cx = x / w;
  const cy = y / h;
  // Center S in the middle
  const sSize = 0.3; // S takes 30% of width
  const sLeft = 0.5 - sSize / 2;
  const sTop = 0.5 - (sSize * (w / h) * (9 / 7)) / 2;
  const sBottom = 0.5 + (sSize * (w / h) * (9 / 7)) / 2;

  const sx = (cx - sLeft) / sSize;
  const sy = (cy - sTop) / (sBottom - sTop);

  if (sx >= 0 && sx <= 1 && sy >= 0 && sy <= 1 && isInS(sx, sy)) {
    return ACCENT;
  }
  return BG;
}
const splash = createPNG(64, 138, splashPixel);
fs.writeFileSync(path.join(assetsDir, "splash.png"), splash);

console.log("Done! Assets written to:", assetsDir);
console.log("  icon.png:", icon.length, "bytes");
console.log("  adaptive-icon.png:", adaptiveIcon.length, "bytes");
console.log("  splash.png:", splash.length, "bytes");
