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

function randomPointOnSphereShell(radius: number): [number, number, number] {
  // Marsaglia method — uniform points on a sphere shell.
  let x = 0;
  let y = 0;
  let s = 2;
  while (s >= 1) {
    x = Math.random() * 2 - 1;
    y = Math.random() * 2 - 1;
    s = x * x + y * y;
  }
  const factor = 2 * Math.sqrt(1 - s);
  return [x * factor * radius, y * factor * radius, (1 - 2 * s) * radius];
}

// Three size/brightness tiers (mostly small+dim, a few bright+larger) rather than one uniform
// PointsMaterial for every star — real starfields vary; a single size/opacity read as
// mechanically generated next to the photographic Earth texture (hallmark audit finding).
const STAR_TIERS: { count: number; size: number; opacity: number }[] = [
  { count: 420, size: 0.14, opacity: 0.5 },
  { count: 150, size: 0.22, opacity: 0.75 },
  { count: 30, size: 0.34, opacity: 1 },
];

function createStarfield(starTexture: THREE.Texture): THREE.Points[] {
  const radius = 40;
  return STAR_TIERS.map(({ count, size, opacity }) => {
    const positions = new Float32Array(count * 3);
    for (let i = 0; i < count; i++) {
      positions.set(randomPointOnSphereShell(radius), i * 3);
    }
    const geometry = new THREE.BufferGeometry();
    geometry.setAttribute('position', new THREE.BufferAttribute(positions, 3));
    const material = new THREE.PointsMaterial({
      size,
      map: starTexture,
      transparent: true,
      depthWrite: false,
      sizeAttenuation: true,
      opacity,
    });
    return new THREE.Points(geometry, material);
  });
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

    const starTexture = createStarSpriteTexture();
    const stars = createStarfield(starTexture);
    stars.forEach((tier) => scene.add(tier));

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
      stars.forEach((tier) => {
        tier.geometry.dispose();
        (tier.material as THREE.Material).dispose();
      });
      starTexture.dispose();
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
