/**
 * Thin wrapper around MediaPipe's Hand Landmarker. Returns just what the app
 * needs: the thumb tip and index-finger tip of every detected hand, in
 * normalized video coordinates (0..1, origin top-left, un-mirrored).
 */
import {
  FilesetResolver,
  HandLandmarker,
} from 'https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@1.0.1/vision_bundle.mjs';

const WASM_ROOT = 'https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@1.0.1/wasm';
const MODEL_URL =
  'https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task';

// Landmark indices from the MediaPipe hand model.
export const THUMB_TIP = 4;
export const INDEX_TIP = 8;

export async function createHandTracker({ onProgress } = {}) {
  onProgress?.('Loading vision runtime…');
  const vision = await FilesetResolver.forVisionTasks(WASM_ROOT);

  const options = (delegate) => ({
    baseOptions: { modelAssetPath: MODEL_URL, delegate },
    runningMode: 'VIDEO',
    numHands: 2,
    minHandDetectionConfidence: 0.5,
    minHandPresenceConfidence: 0.5,
    minTrackingConfidence: 0.5,
  });

  onProgress?.('Loading hand model…');
  let landmarker;
  try {
    landmarker = await HandLandmarker.createFromOptions(vision, options('GPU'));
  } catch (err) {
    console.warn('GPU delegate unavailable, falling back to CPU', err);
    landmarker = await HandLandmarker.createFromOptions(vision, options('CPU'));
  }

  let lastTimestamp = -1;

  return {
    /**
     * Run detection on the current video frame.
     * @returns {{ thumb: {x,y}, index: {x,y}, handedness: string }[]}
     */
    detect(video, timestampMs) {
      // MediaPipe requires strictly increasing timestamps.
      if (timestampMs <= lastTimestamp) timestampMs = lastTimestamp + 1;
      lastTimestamp = timestampMs;
      const result = landmarker.detectForVideo(video, timestampMs);
      return result.landmarks.map((lm, i) => ({
        thumb: { x: lm[THUMB_TIP].x, y: lm[THUMB_TIP].y },
        index: { x: lm[INDEX_TIP].x, y: lm[INDEX_TIP].y },
        handedness: result.handedness?.[i]?.[0]?.categoryName ?? 'Unknown',
      }));
    },
    close() {
      landmarker.close();
    },
  };
}
