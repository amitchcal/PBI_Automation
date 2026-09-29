// Story I-04: rules a customer's own uploaded template must meet before it is accepted.
// No image-processing dependency is installed, so PNG/JPEG dimensions are read directly from the file's own
// header bytes -- both formats store width/height in fixed, well-documented places near the start of the file.
export const TEMPLATE_MAX_BYTES = 15 * 1024 * 1024; // 15 MB
export const TEMPLATE_MIN_WIDTH = 800;
export const TEMPLATE_MIN_HEIGHT = 450; // a loose 16:9-ish floor, matching a Power BI report canvas at low resolution
export const TEMPLATE_EXTS = [".png", ".jpg", ".jpeg", ".pdf"];

function pngDims(buf: Buffer): { w: number; h: number } | null {
  // 8-byte signature, then a 4-byte chunk length, 4-byte "IHDR", then 4-byte width, 4-byte height (big-endian).
  if (buf.length < 24 || buf.toString("ascii", 12, 16) !== "IHDR") return null;
  return { w: buf.readUInt32BE(16), h: buf.readUInt32BE(20) };
}

function jpegDims(buf: Buffer): { w: number; h: number } | null {
  // Scan markers for a Start-Of-Frame segment (0xC0-0xCF except C4/C8/CC, which are not SOF); height/width follow
  // a 1-byte precision field, 2 bytes each, big-endian.
  let i = 2; // skip the 0xFFD8 SOI marker
  while (i + 9 < buf.length) {
    if (buf[i] !== 0xff) { i++; continue; }
    const marker = buf[i + 1];
    if (marker >= 0xc0 && marker <= 0xcf && marker !== 0xc4 && marker !== 0xc8 && marker !== 0xcc) {
      return { h: buf.readUInt16BE(i + 5), w: buf.readUInt16BE(i + 7) };
    }
    if (marker === 0xd8 || marker === 0x01 || (marker >= 0xd0 && marker <= 0xd7)) { i += 2; continue; }
    const len = buf.readUInt16BE(i + 2);
    i += 2 + len;
  }
  return null;
}

export interface TemplateCheck { ok: boolean; error?: string; width?: number; height?: number }

// Checks everything that can be checked without a real design tool: type, size, and (for images) minimum
// resolution, so a thumbnail-sized image or an unrelated document is rejected before it reaches the builder.
export function checkTemplate(name: string, size: number, buf: Buffer): TemplateCheck {
  const ext = name.slice(name.lastIndexOf(".")).toLowerCase();
  if (!TEMPLATE_EXTS.includes(ext)) return { ok: false, error: `${name}: this file type is not accepted for a template. Use ${TEMPLATE_EXTS.join(", ")}.` };
  if (size > TEMPLATE_MAX_BYTES) return { ok: false, error: `${name} is larger than ${TEMPLATE_MAX_BYTES / (1024 * 1024)} MB.` };
  if (size === 0) return { ok: false, error: `${name} is empty.` };
  if (ext === ".pdf") return { ok: true }; // a PDF mockup's page size isn't checked; the builder reviews it by eye
  const dims = ext === ".png" ? pngDims(buf) : jpegDims(buf);
  if (!dims) return { ok: false, error: `${name} could not be read as a valid ${ext.slice(1).toUpperCase()} image.` };
  if (dims.w < TEMPLATE_MIN_WIDTH || dims.h < TEMPLATE_MIN_HEIGHT) {
    return { ok: false, error: `${name} is ${dims.w}×${dims.h}px, too small to use as a page layout reference (minimum ${TEMPLATE_MIN_WIDTH}×${TEMPLATE_MIN_HEIGHT}px). Use a full-page screenshot or export, not a thumbnail.`, width: dims.w, height: dims.h };
  }
  return { ok: true, width: dims.w, height: dims.h };
}
