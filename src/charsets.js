/**
 * Character ramps, ordered from darkest (first) to brightest (last).
 * The renderer maps each cell's luminance onto this ramp.
 */
export const CHARSETS = [
  { id: 'standard', label: 'Standard', chars: ' .:-=+*#%@' },
  {
    id: 'detailed',
    label: 'Detailed (70 levels)',
    chars: ' .\'`^",:;Il!i><~+_-?][}{1)(|\\/tfjrxnuvczXYUJCLQ0OZmwqpdbkhao*#MW&8%B@$',
  },
  { id: 'blocks', label: 'Blocks', chars: ' ░▒▓█' },
  { id: 'dots', label: 'Dots', chars: ' ·•●' },
  { id: 'binary', label: 'Binary', chars: ' 01' },
  { id: 'minimal', label: 'Minimal', chars: ' .oO@' },
  { id: 'prism', label: 'Prism', chars: ' .,-~:;=!*#$@' },
];

export const DEFAULT_CHARSET_ID = 'standard';

/** Split a string into user-perceived characters (handles surrogate pairs). */
export function splitChars(str) {
  return Array.from(str);
}
