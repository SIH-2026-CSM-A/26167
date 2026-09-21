import React, { useEffect, useRef } from 'react';
import * as THREE from 'three';

export interface RotatingEarthBackdropProps {
  /** Same NASA Earth Observatory night-lights image already used by PageBackdrop/LoginPage
   * (public domain, U.S. government work) — reused as-is rather than sourcing a new asset.
   * Source: https://eoimages.gsfc.nasa.gov/images/imagerecords/79000/79765/dnb_land_ocean_ice.2012.3600x1800.jpg
   *
   * Chosen over the Blue Marble daytime image: a rotating night-lights globe reads as
   * ambient atmosphere (soft, dim, low-detail at a glance) where a rotating daytime globe's
   * sharper cloud/coastline detail would compete more for attention behind the form. */
  image?: string;
}

const ROTATION_RADIANS_PER_MS = (2 * Math.PI) / (120 * 1000); // one turn per 2 minutes — ambient, not attention-grabbing

/** Drop-in replacement for PageBackdrop, UploadPage only: a dim, slow-rotating textured
 * sphere instead of a static photo. Same "photo/globe shows in the gaps, panels stay solid on
 * top" rule — this only replaces the backdrop layer, not any panel. Non-interactive (no
 * drag/zoom) and pauses via the Page Visibility API so a backgrounded tab doesn't keep
 * spinning the GPU for nothing. */
export const RotatingEarthBackdrop: React.FC<RotatingEarthBackdropProps> = ({
  image = '/assets/earth-night-lights.jpg',
}) => {
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(45, 1, 0.1, 10);
    camera.position.z = 2.6;

    // WebGL can be unavailable (disabled by the browser/OS, or a test/CI environment with no
    // real GPU context) — degrade to no backdrop rather than crashing the page.
    let renderer: THREE.WebGLRenderer;
    try {
      renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    } catch {
      return;
    }
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    container.appendChild(renderer.domElement);

    // Lightweight geometry (48 segments is smooth enough at this size/distance — this is an
    // ambient backdrop, not a detailed interactive globe) and a modest-opacity unlit material
    // so it reads as dim atmosphere, not a distracting centerpiece.
    const geometry = new THREE.SphereGeometry(1, 48, 48);
    const texture = new THREE.TextureLoader().load(image);
    texture.colorSpace = THREE.SRGBColorSpace;
    const material = new THREE.MeshBasicMaterial({ map: texture, transparent: true, opacity: 0.32 });
    const sphere = new THREE.Mesh(geometry, material);
    scene.add(sphere);

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
      sphere.rotation.y += ROTATION_RADIANS_PER_MS * deltaMs;
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
    document.addEventListener('visibilitychange', handleVisibility);
    if (!document.hidden) start();

    return () => {
      stop();
      window.removeEventListener('resize', resize);
      document.removeEventListener('visibilitychange', handleVisibility);
      geometry.dispose();
      material.dispose();
      texture.dispose();
      renderer.dispose();
      container.removeChild(renderer.domElement);
    };
  }, [image]);

  return (
    <div
      ref={containerRef}
      className="fixed inset-0"
      style={{ pointerEvents: 'none' }}
      aria-hidden="true"
    />
  );
};

export default RotatingEarthBackdrop;
