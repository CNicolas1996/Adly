/**
 * Adly state configuration.
 * Each state drives animation variants for body, tail, eyes, brows, and ears.
 */

export const ADLY_STATE_CONFIG = {
  idle: {
    label:       'Idle',
    bodyScale:   [1, 1.025, 1],
    bodyDuration: 4,
    tailPath: [
      'M 62 62 Q 78 52 76 66 Q 74 76 64 74',
      'M 62 62 Q 80 50 78 65 Q 76 76 65 74',
      'M 62 62 Q 75 55 73 68 Q 71 78 62 76',
    ],
    tailDuration: 2.8,
    eyeOpenY:    1,    // scaleY for eyelid
    browsY:      0,    // translateY offset for brows
    browAngle:   -8,   // rotate degrees (neg = grumpy inward)
    mouthType:   'grumpy', // path key
    earAngle:    0,
    sparks:      false,
    zzz:         false,
  },
  thinking: {
    label:       'Pensando',
    bodyScale:   [1, 1.015, 1],
    bodyDuration: 6,
    tailPath: [
      'M 62 62 Q 74 58 73 70 Q 72 79 63 78',
      'M 62 62 Q 76 56 75 69 Q 74 78 64 77',
    ],
    tailDuration: 4,
    eyeOpenY:    0.45,
    browsY:      2,
    browAngle:   -6,
    mouthType:   'neutral',
    earAngle:    -5,
    sparks:      false,
    zzz:         false,
  },
  typing: {
    label:       'Escribiendo',
    bodyScale:   [1, 1.02, 1, 1.02, 1],
    bodyDuration: 1,
    tailPath: [
      'M 62 62 Q 82 50 80 65 Q 78 77 67 76',
      'M 62 62 Q 70 52 68 64 Q 66 74 58 74',
      'M 62 62 Q 84 48 82 63 Q 80 75 69 74',
    ],
    tailDuration: 0.6,
    eyeOpenY:    1,
    browsY:      -3,
    browAngle:   3,
    mouthType:   'open',
    earAngle:    8,
    sparks:      true,
    zzz:         false,
  },
  happy: {
    label:       'Contento',
    bodyScale:   [1, 1.04, 0.98, 1.04, 1],
    bodyDuration: 0.5,
    tailPath: [
      'M 62 62 Q 82 50 80 63 Q 78 73 67 72',
      'M 62 62 Q 70 54 68 66 Q 66 76 58 76',
      'M 62 62 Q 84 48 82 61 Q 80 71 68 70',
    ],
    tailDuration: 0.45,
    eyeOpenY:    1.1,
    browsY:      -5,
    browAngle:   8,
    mouthType:   'happy',
    earAngle:    12,
    sparks:      false,
    zzz:         false,
  },
  error: {
    label:       'Error',
    bodyScale:   [1, 1.01, 0.99, 1],
    bodyDuration: 0.15,
    tailPath: [
      'M 62 62 L 74 70 L 72 78',
      'M 62 62 L 73 69 L 71 77',
    ],
    tailDuration: 0.1,
    eyeOpenY:    0.6,
    browsY:      4,
    browAngle:   -15,
    mouthType:   'frown',
    earAngle:    -18,
    sparks:      false,
    zzz:         false,
  },
  sleep: {
    label:       'Dormido',
    bodyScale:   [1, 1.012, 1],
    bodyDuration: 7,
    tailPath: [
      'M 62 62 Q 68 65 66 72',
      'M 62 62 Q 69 64 67 71',
    ],
    tailDuration: 6,
    eyeOpenY:    0,
    browsY:      3,
    browAngle:   0,
    mouthType:   'sleep',
    earAngle:    -8,
    sparks:      false,
    zzz:         true,
  },
}

// Mouth path definitions (all relative to head centered ~40,30 r20)
export const MOUTH_PATHS = {
  grumpy:  'M 33 38 Q 40 35 47 38',
  neutral: 'M 34 38 Q 40 37 46 38',
  open:    'M 33 37 Q 40 40 47 37',
  happy:   'M 32 38 Q 40 44 48 38',
  frown:   'M 33 40 Q 40 36 47 40',
  sleep:   'M 36 38 Q 40 40 44 38',
}
