import React, { useEffect, useRef } from 'react';
import * as THREE from 'three';

export interface RotatingEarthBackdropProps {
  /** Same NASA Earth Observatory night-lights image already used by PageBackdrop/LoginPage
   * (public domain, U.S. government work) — reused as-is rather than sourcing a new asset.
   * Source: https://eoimages.gsfc.nasa.gov/images/imagerecords/79000/79765/dnb_land_ocean_ice.2012.3600x1800.jpg
   * 3600x1800 source — comfortably above the sphere's on-screen size, not a thumbnail.
   *
   * Chosen over the Blue Marble daytime image: a rotating night-lights globe's city-light
   * glow reads as soft ambient atmosphere behind the form, where a daytime globe's sharper
   * cloud/coastline detail would compete more for attention.
   */
  image?: string;
}

const ROTATION_RADIANS_PER_MS = (2 * Math.PI) / (120 * 1000); // one turn per 2 minutes — ambient, not attention-grabbing

/** Small offscreen-canvas radial-gradient dot — a generated decoration, not a real star
 * catalog asset, so it carries none of the licensing concerns the Earth texture does. */
function createStarSpriteTexture(): THREE.Texture {
  const size = 32;
  const canvas = document.createElement('canvas');
  canvas.width = size;
  canvas.height = size;
  const ctx = canvas.getContext('2d')!;
  const gradient = ctx.createRadialGradient(size / 2, size / 2, 0, size / 2, size / 2, size / 2);
  gradient.addColorStop(0, 'rgba(255,255,255,1)');
  gradient.addColorStop(0.4, 'rgba(255,255,255,0.7)');
  gradient.addColorStop(1, 'rgba(255,255,255,0)');
  ctx.fillStyle = gradient;
  ctx.fillRect(0, 0, size, size);
  const texture = new THREE.CanvasTexture(canvas);
  texture.colorSpace = THREE.SRGBColorSpace;
  return texture;
}

/** A larger, softer, tinted blob — for a faint nebula/Milky-Way haze, not a pinpoint star. */
function createHazeSpriteTexture(color: string): THREE.Texture {
  const size = 256;
  const canvas = document.createElement('canvas');
  canvas.width = size;
  canvas.height = size;
  const ctx = canvas.getContext('2d')!;
  const gradient = ctx.createRadialGradient(size / 2, size / 2, 0, size / 2, size / 2, size / 2);
  gradient.addColorStop(0, `${color}aa`);
  gradient.addColorStop(0.5, `${color}44`);
  gradient.addColorStop(1, `${color}00`);
  ctx.fillStyle = gradient;
  ctx.fillRect(0, 0, size, size);
  const texture = new THREE.CanvasTexture(canvas);
  texture.colorSpace = THREE.SRGBColorSpace;
  return texture;
}

function randomUnitVector(): [number, number, number] {
  // Marsaglia method — uniform points on a unit sphere.
  let x = 0;
  let y = 0;
  let s = 2;
  while (s >= 1) {
    x = Math.random() * 2 - 1;
    y = Math.random() * 2 - 1;
    s = x * x + y * y;
  }
  const factor = 2 * Math.sqrt(1 - s);
  return [x * factor, y * factor, 1 - 2 * s];
}

/** A handful of loose "band" centers (stand-ins for Milky-Way-style density variation) —
 * most stars scatter uniformly, but a fraction cluster loosely near these directions instead
 * of being perfectly evenly spread, which is what reads as a real sky rather than a uniform
 * random scatter. */
function makeDensityBandSampler(bandCount: number, clusterFraction: number) {
  const bandCenters = Array.from({ length: bandCount }, () => randomUnitVector());
  return (): [number, number, number] => {
    const uniform = randomUnitVector();
    if (Math.random() >= clusterFraction) return uniform;
    const center = bandCenters[Math.floor(Math.random() * bandCenters.length)];
    const jitter = 0.35 + Math.random() * 0.3; // how loosely stars scatter around the band
    const mixed: [number, number, number] = [
      center[0] * (1 - jitter) + uniform[0] * jitter,
      center[1] * (1 - jitter) + uniform[1] * jitter,
      center[2] * (1 - jitter) + uniform[2] * jitter,
    ];
    const len = Math.hypot(...mixed) || 1;
    return [mixed[0] / len, mixed[1] / len, mixed[2] / len];
  };
}

// Per-vertex size/opacity via a small custom shader (rather than one uniform PointsMaterial
// per tier) is what lets brightness vary continuously star-to-star instead of in visible
// steps. Two layers at different radii give a mild sense of depth even though nothing moves.
const STAR_VERTEX_SHADER = `
  attribute float aSize;
  attribute float aOpacity;
  uniform float uPixelRatio;
  varying float vOpacity;
  void main() {
    vOpacity = aOpacity;
    vec4 mvPosition = modelViewMatrix * vec4(position, 1.0);
    gl_PointSize = aSize * uPixelRatio * (60.0 / -mvPosition.z);
    gl_Position = projectionMatrix * mvPosition;
  }
`;
const STAR_FRAGMENT_SHADER = `
  uniform sampler2D pointTexture;
  varying float vOpacity;
  void main() {
    vec4 tex = texture2D(pointTexture, gl_PointCoord);
    gl_FragColor = vec4(vec3(1.0), tex.a * vOpacity);
  }
`;

interface StarLayerConfig {
  count: number;
  radius: number;
  sizeRange: [number, number];
  opacityRange: [number, number];
}

const STAR_LAYERS: StarLayerConfig[] = [
  // Far layer: many small, mostly dim points.
  { count: 2200, radius: 55, sizeRange: [0.4, 1.1], opacityRange: [0.15, 0.6] },
  // Near layer: fewer, larger, brighter — the "foreground" stars that read first.
  { count: 500, radius: 30, sizeRange: [0.7, 1.7], opacityRange: [0.4, 0.9] },
];

function createStarLayer(starTexture: THREE.Texture, pixelRatio: number, config: StarLayerConfig): THREE.Points {
  const { count, radius, sizeRange, opacityRange } = config;
  const sampleDirection = makeDensityBandSampler(3, 0.4);
  const positions = new Float32Array(count * 3);
  const sizes = new Float32Array(count);
  const opacities = new Float32Array(count);
  for (let i = 0; i < count; i++) {
    const [x, y, z] = sampleDirection();
    positions.set([x * radius, y * radius, z * radius], i * 3);
    // Bias toward the small/dim end (pow > 1) — most stars are faint, a few stand out.
    const t = Math.pow(Math.random(), 2.2);
    sizes[i] = sizeRange[0] + (sizeRange[1] - sizeRange[0]) * t;
    opacities[i] = opacityRange[0] + (opacityRange[1] - opacityRange[0]) * Math.random();
  }
  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute('position', new THREE.BufferAttribute(positions, 3));
  geometry.setAttribute('aSize', new THREE.BufferAttribute(sizes, 1));
  geometry.setAttribute('aOpacity', new THREE.BufferAttribute(opacities, 1));
  const material = new THREE.ShaderMaterial({
    vertexShader: STAR_VERTEX_SHADER,
    fragmentShader: STAR_FRAGMENT_SHADER,
    uniforms: { pointTexture: { value: starTexture }, uPixelRatio: { value: pixelRatio } },
    transparent: true,
    depthWrite: false,
  });
  return new THREE.Points(geometry, material);
}

// A couple of large, very-low-opacity tinted blobs, hand-placed in front of the camera —
// a cheap stand-in for a distant nebula/Milky-Way haze band. Subtle on purpose: this is
// atmosphere, not a hero visual, and must not compete with the panels above it.
const NEBULA_SPOTS: { position: [number, number, number]; scale: number; color: string }[] = [
  // Camera vertical FOV is 38deg, so keep |y| comfortably inside d*tan(19deg) at this z or
  // the sprite falls outside the frustum and never renders (that was the previous bug).
  { position: [-8, 4, -30], scale: 22, color: '#3a4a7a' },
  { position: [9, 6, -35], scale: 26, color: '#4a3a6a' },
];

function createSky(pixelRatio: number): { group: THREE.Group; dispose: () => void } {
  const group = new THREE.Group();
  const starTexture = createStarSpriteTexture();
  const layers = STAR_LAYERS.map((config) => createStarLayer(starTexture, pixelRatio, config));
  layers.forEach((layer) => group.add(layer));

  const nebulaTextures = new Map<string, THREE.Texture>();
  const nebulaSprites = NEBULA_SPOTS.map(({ position, scale, color }) => {
    let texture = nebulaTextures.get(color);
    if (!texture) {
      texture = createHazeSpriteTexture(color);
      nebulaTextures.set(color, texture);
    }
    const material = new THREE.SpriteMaterial({
      map: texture,
      transparent: true,
      opacity: 0.5,
      depthWrite: false,
      blending: THREE.AdditiveBlending,
    });
    const sprite = new THREE.Sprite(material);
    sprite.position.set(...position);
    sprite.scale.set(scale, scale, 1);
    return sprite;
  });
  nebulaSprites.forEach((sprite) => group.add(sprite));

  const dispose = () => {
    layers.forEach((layer) => {
      layer.geometry.dispose();
      (layer.material as THREE.Material).dispose();
    });
    nebulaSprites.forEach((sprite) => (sprite.material as THREE.Material).dispose());
    nebulaTextures.forEach((texture) => texture.dispose());
    starTexture.dispose();
  };

  return { group, dispose };
}

// Classic three.js Fresnel "atmosphere" glow: a slightly larger, back-face sphere whose
// brightness peaks at grazing angles and fades toward the center — cheaper and far less
// compile-risk than a physically-based scattering shader, and the standard technique for
// exactly this look.
const ATMOSPHERE_VERTEX_SHADER = `
  varying vec3 vNormal;
  varying vec3 vPositionNormal;
  void main() {
    vNormal = normalize(normalMatrix * normal);
    vPositionNormal = normalize((modelViewMatrix * vec4(position, 1.0)).xyz);
    gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
  }
`;
const ATMOSPHERE_FRAGMENT_SHADER = `
  varying vec3 vNormal;
  varying vec3 vPositionNormal;
  uniform vec3 glowColor;
  void main() {
    float intensity = pow(0.62 + dot(vNormal, vPositionNormal), 7.0);
    gl_FragColor = vec4(glowColor, 1.0) * intensity * 0.35;
  }
`;

/** Drop-in replacement for PageBackdrop, UploadPage only: a slowly auto-rotating textured
 * globe instead of a static photo. Same "backdrop shows in the gaps, panels stay solid on
 * top" rule — this only replaces the backdrop layer, not any panel. Non-interactive (no
 * drag/zoom) and pauses via the Page Visibility API so a backgrounded tab doesn't keep
 * spinning the GPU for nothing. Subtlety comes from composition (a half-planet silhouette
 * anchored to the bottom edge, per art direction) rather than a flat low-opacity material —
 * the sphere itself is fully lit/rendered so it actually looks like a planet, not a
 * washed-out decal. */
export const RotatingEarthBackdrop: React.FC<RotatingEarthBackdropProps> = ({
  image = '/assets/earth-night-lights.jpg',
}) => {
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    const scene = new THREE.Scene();
    // Wider FOV + shorter distance than a corner-box framing needs, since this container
    // spans the full viewport width but only its bottom ~58vh.
    const camera = new THREE.PerspectiveCamera(38, 1, 0.1, 100);
    camera.position.z = 3.3;

    // WebGL can be unavailable (disabled by the browser/OS, or a test/CI environment with no
    // real GPU context) — degrade to no backdrop rather than crashing the page.
    let renderer: THREE.WebGLRenderer;
    try {
      renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    } catch {
      return;
    }
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    // A default/unadjusted exposure reads dull against a pure-black page — ACES + a modest
    // exposure bump is what makes the lit hemisphere and the atmosphere glow read as bright
    // and rich rather than flat.
    renderer.toneMapping = THREE.ACESFilmicToneMapping;
    renderer.toneMappingExposure = 1.3;
    renderer.outputColorSpace = THREE.SRGBColorSpace;
    container.appendChild(renderer.domElement);

    // Lighting: the previous version used an unlit MeshBasicMaterial — no shading model at
    // all, which is exactly why it read flat/dull. A dim ambient plus one directional light
    // raking across the sphere produces a real day/night terminator and a specular-less but
    // clearly lit hemisphere.
    const ambientLight = new THREE.AmbientLight(0xffffff, 0.3);
    scene.add(ambientLight);
    const sunLight = new THREE.DirectionalLight(0xffffff, 3.2);
    sunLight.position.set(3, 6, 5); // from upper-front — the visible cap is the top of the sphere
    scene.add(sunLight);

    // 48 segments is smooth enough at this size/distance — this is an ambient backdrop, not
    // a detailed interactive globe.
    const geometry = new THREE.SphereGeometry(1, 48, 48);
    const texture = new THREE.TextureLoader().load(image);
    texture.colorSpace = THREE.SRGBColorSpace;
    texture.anisotropy = renderer.capabilities.getMaxAnisotropy();
    // map (lit side, shaded by the directional light) + emissiveMap (same texture, constant
    // brightness) is what keeps the night-lights city-glow visible on the unlit hemisphere
    // instead of it just going to black — a real day/night blend would need a second
    // daytime texture, which is out of scope here (one NASA asset only).
    const material = new THREE.MeshStandardMaterial({
      map: texture,
      emissiveMap: texture,
      emissive: new THREE.Color(0xffffff),
      emissiveIntensity: 0.55,
      roughness: 1,
      metalness: 0,
    });
    const sphere = new THREE.Mesh(geometry, material);
    scene.add(sphere);

    // Fresnel atmosphere glow — see ATMOSPHERE_*_SHADER comment above. A tight gap (1.03 vs
    // the sphere's 1.0) and a warm-white-blue rather than saturated blue keeps this a thin
    // edge highlight instead of a thick halo.
    const atmosphereGeometry = new THREE.SphereGeometry(1.03, 48, 48);
    const atmosphereMaterial = new THREE.ShaderMaterial({
      vertexShader: ATMOSPHERE_VERTEX_SHADER,
      fragmentShader: ATMOSPHERE_FRAGMENT_SHADER,
      uniforms: { glowColor: { value: new THREE.Color(0xcfe8ff) } },
      blending: THREE.AdditiveBlending,
      side: THREE.BackSide,
      transparent: true,
      depthWrite: false,
    });
    const atmosphere = new THREE.Mesh(atmosphereGeometry, atmosphereMaterial);
    scene.add(atmosphere);

    // Push the planet down so only its upper cap sits inside the bottom-anchored viewport —
    // "half-Earth at the bottom edge," not a full ball resting on the page.
    const PLANET_Y_OFFSET = -0.95;
    sphere.position.y = PLANET_Y_OFFSET;
    atmosphere.position.y = PLANET_Y_OFFSET;

    const sky = createSky(renderer.getPixelRatio());
    scene.add(sky.group);

    const resize = () => {
      const { clientWidth, clientHeight } = container;
      camera.aspect = clientWidth / clientHeight;
      camera.updateProjectionMatrix();
      renderer.setSize(clientWidth, clientHeight);
    };
    resize();
    window.addEventListener('resize', resize);

    let rafId: number | null = null;
    let lastTime = performance.now();

    const tick = (now: number) => {
      const deltaMs = now - lastTime;
      lastTime = now;
      const delta = ROTATION_RADIANS_PER_MS * deltaMs;
      sphere.rotation.y += delta;
      atmosphere.rotation.y += delta;
      renderer.render(scene, camera);
      rafId = requestAnimationFrame(tick);
    };

    const start = () => {
      if (rafId !== null) return;
      lastTime = performance.now();
      rafId = requestAnimationFrame(tick);
    };
    const stop = () => {
      if (rafId === null) return;
      cancelAnimationFrame(rafId);
      rafId = null;
    };

    const handleVisibility = () => {
      if (document.hidden) stop();
      else start();
    };

    // Respect prefers-reduced-motion: render one static frame instead of a continuous
    // ambient rotation for users who've asked the OS/browser to cut non-essential motion.
    const prefersReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    if (prefersReducedMotion) {
      renderer.render(scene, camera);
    } else {
      document.addEventListener('visibilitychange', handleVisibility);
      if (!document.hidden) start();
    }

    return () => {
      stop();
      window.removeEventListener('resize', resize);
      if (!prefersReducedMotion) document.removeEventListener('visibilitychange', handleVisibility);
      geometry.dispose();
      material.dispose();
      texture.dispose();
      atmosphereGeometry.dispose();
      atmosphereMaterial.dispose();
      sky.dispose();
      renderer.dispose();
      container.removeChild(renderer.domElement);
    };
  }, [image]);

  return (
    // Full width, bottom-anchored band — combined with the sphere's own downward Y offset,
    // this is what produces "half-planet at the bottom edge" rather than a full ball resting
    // on the page or a corner accent.
    <div
      ref={containerRef}
      className="fixed inset-x-0 bottom-0"
      style={{ height: '58vh', pointerEvents: 'none' }}
      aria-hidden="true"
    />
  );
};

export default RotatingEarthBackdrop;
