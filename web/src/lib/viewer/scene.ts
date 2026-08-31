import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";
import { RoomEnvironment } from "three/addons/environments/RoomEnvironment.js";
import { GLTFLoader } from "three/addons/loaders/GLTFLoader.js";

/**
 * The build's 3D-relevant data: the GLB plus the camera framing `catalog.yaml` pins per
 * platform, plus one `OptionModelEffect` per option slug that has one. React owns which slugs
 * are selected; this owns what selecting them does to the WebGL scene.
 */
export type ViewerEffect = {
  nodes: string[];
  materialTarget: string | null;
  baseColorHex: string | null;
  metalness: number | null;
  roughness: number | null;
};

export type ViewerModel = {
  url: string;
  cameraOrbitDeg: number;
  cameraDistanceM: number;
  cameraTargetYM: number;
  effects: Record<string, ViewerEffect>;
};

export type ViewerHandle = {
  applySelection: (selected: string[]) => void;
  resize: () => void;
  dispose: () => void;
};

type MaterialOverride = {
  baseColorHex: string | null;
  metalness: number | null;
  roughness: number | null;
};

/**
 * Which node names should end up visible and which material targets get which override, for a
 * given selection -- in plain data, no `THREE` in sight. `applySelection` below is the only
 * caller; it is split out because this is the part worth unit-testing without a canvas.
 *
 * A node named by more than one effect (there is none today, but nothing rules it out) stays
 * visible if any selected option asks for it -- hiding is the default, not something a selected
 * option can override for a sibling option's node.
 */
export function resolveSelection(
  effects: Record<string, ViewerEffect>,
  selected: string[],
): {
  visibleNodes: Set<string>;
  hiddenNodes: Set<string>;
  materialOverrides: Map<string, MaterialOverride>;
} {
  const chosen = new Set(selected);
  const allEffectNodes = new Set<string>();
  for (const effect of Object.values(effects)) {
    for (const node of effect.nodes) allEffectNodes.add(node);
  }

  const visibleNodes = new Set<string>();
  const materialOverrides = new Map<string, MaterialOverride>();

  for (const [slug, effect] of Object.entries(effects)) {
    if (!chosen.has(slug)) continue;
    for (const node of effect.nodes) visibleNodes.add(node);
    if (effect.materialTarget) {
      materialOverrides.set(effect.materialTarget, {
        baseColorHex: effect.baseColorHex,
        metalness: effect.metalness,
        roughness: effect.roughness,
      });
    }
  }

  const hiddenNodes = new Set([...allEffectNodes].filter((node) => !visibleNodes.has(node)));
  return { visibleNodes, hiddenNodes, materialOverrides };
}

const COLOR_LERP_SECONDS = 0.25;

function readCssColor(name: string, fallback: string): THREE.Color {
  if (typeof window === "undefined") return new THREE.Color(fallback);
  const value = getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  return new THREE.Color(value || fallback);
}

/**
 * Framework-free and imperative: React owns the selection, this owns the WebGL, and the two
 * meet at `applySelection`. Node and material lookups are resolved once, at load, into a `Map`,
 * so a toggle costs exactly the nodes and materials the selected options name rather than a
 * scene traversal per click.
 */
export async function createScene(
  canvas: HTMLCanvasElement,
  model: ViewerModel,
  callbacks: {
    onFirstFrame?: () => void;
    onError?: (error: unknown) => void;
    onProgress?: (loaded: number, total: number) => void;
  } = {},
): Promise<ViewerHandle> {
  const reducedMotion =
    typeof window !== "undefined" && window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: true });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  renderer.toneMapping = THREE.ACESFilmicToneMapping;
  renderer.toneMappingExposure = 1.05;

  const onContextLost = (event: Event) => {
    event.preventDefault();
    callbacks.onError?.(new Error("WebGL context lost"));
  };
  canvas.addEventListener("webglcontextlost", onContextLost);

  const scene = new THREE.Scene();
  scene.fog = new THREE.FogExp2(readCssColor("--color-canvas", "#0b0b0c").getHex(), 0.035);

  const pmrem = new THREE.PMREMGenerator(renderer);
  scene.environment = pmrem.fromScene(new RoomEnvironment(), 0.04).texture;

  // A cool sky / warm ground hemisphere reads as outdoor daylight rather than a studio box,
  // which fits an expedition truck; the accent-tinted key light is the one deliberately
  // branded choice, echoing `--color-accent` the way a logo would in a real product shoot.
  scene.add(new THREE.HemisphereLight(0x8ea6c2, 0x2a2016, 0.9));
  const key = new THREE.DirectionalLight(0xfff3e0, 2.2);
  key.position.set(6, 9, 4);
  scene.add(key);
  const rim = new THREE.DirectionalLight(readCssColor("--color-accent", "#f5a524").getHex(), 0.6);
  rim.position.set(-5, 3, -6);
  scene.add(rim);

  const camera = new THREE.PerspectiveCamera(35, 1, 0.1, 100);
  const target = new THREE.Vector3(0, model.cameraTargetYM, 0);
  const orbitRad = THREE.MathUtils.degToRad(model.cameraOrbitDeg);
  camera.position.set(
    target.x + model.cameraDistanceM * Math.sin(orbitRad),
    target.y + model.cameraDistanceM * 0.35,
    target.z + model.cameraDistanceM * Math.cos(orbitRad),
  );

  const controls = new OrbitControls(camera, canvas);
  controls.target.copy(target);
  controls.enableDamping = !reducedMotion;
  controls.autoRotate = !reducedMotion;
  controls.autoRotateSpeed = 0.6;
  controls.minDistance = model.cameraDistanceM * 0.4;
  controls.maxDistance = model.cameraDistanceM * 2;
  controls.maxPolarAngle = Math.PI * 0.85;
  controls.update();

  // OrbitControls re-derives its spherical state from `camera.position` at the top of every
  // `update()` call, so nudging the position directly here is enough -- the next animation
  // frame's `controls.update()` picks it up with no separate "keyboard mode" to keep in sync.
  const ORBIT_STEP = THREE.MathUtils.degToRad(4);
  const ARROW_KEYS = new Set(["ArrowLeft", "ArrowRight", "ArrowUp", "ArrowDown"]);
  const onKeyDown = (event: KeyboardEvent) => {
    if (!ARROW_KEYS.has(event.key)) return;
    event.preventDefault();
    const offset = camera.position.clone().sub(controls.target);
    const spherical = new THREE.Spherical().setFromVector3(offset);
    if (event.key === "ArrowLeft") spherical.theta -= ORBIT_STEP;
    if (event.key === "ArrowRight") spherical.theta += ORBIT_STEP;
    if (event.key === "ArrowUp") {
      spherical.phi = THREE.MathUtils.clamp(
        spherical.phi - ORBIT_STEP,
        0.1,
        controls.maxPolarAngle,
      );
    }
    if (event.key === "ArrowDown") {
      spherical.phi = THREE.MathUtils.clamp(
        spherical.phi + ORBIT_STEP,
        0.1,
        controls.maxPolarAngle,
      );
    }
    offset.setFromSpherical(spherical);
    camera.position.copy(controls.target).add(offset);
  };
  canvas.addEventListener("keydown", onKeyDown);

  const nodesByName = new Map<string, THREE.Object3D>();
  const materialsByName = new Map<string, THREE.MeshStandardMaterial>();
  const materialDefaults = new Map<
    string,
    { color: THREE.Color; metalness: number; roughness: number }
  >();
  const colorTweens = new Map<
    string,
    { material: THREE.MeshStandardMaterial; from: THREE.Color; to: THREE.Color; elapsed: number }
  >();

  let gltf;
  try {
    // `total` is only meaningful when the response declared a length; a `Content-Encoding` on
    // the GLB makes it 0, which the readout renders as an indeterminate bar rather than 0%.
    gltf = await new GLTFLoader().loadAsync(model.url, (event) =>
      callbacks.onProgress?.(event.loaded, event.lengthComputable ? event.total : 0),
    );
  } catch (error) {
    canvas.removeEventListener("webglcontextlost", onContextLost);
    pmrem.dispose();
    renderer.dispose();
    renderer.forceContextLoss();
    throw error;
  }
  scene.add(gltf.scene);

  gltf.scene.traverse((object) => {
    if (object.name) nodesByName.set(object.name, object);
    if (object instanceof THREE.Mesh) {
      const materials = Array.isArray(object.material) ? object.material : [object.material];
      for (const material of materials) {
        if (material instanceof THREE.MeshStandardMaterial && material.name) {
          materialsByName.set(material.name, material);
          materialDefaults.set(material.name, {
            color: material.color.clone(),
            metalness: material.metalness,
            roughness: material.roughness,
          });
        }
      }
    }
  });

  function applySelection(selected: string[]) {
    const { visibleNodes, hiddenNodes, materialOverrides } = resolveSelection(
      model.effects,
      selected,
    );
    for (const name of visibleNodes) {
      const node = nodesByName.get(name);
      if (node) node.visible = true;
    }
    for (const name of hiddenNodes) {
      const node = nodesByName.get(name);
      if (node) node.visible = false;
    }

    for (const [materialName, material] of materialsByName) {
      const override = materialOverrides.get(materialName);
      const fallback = materialDefaults.get(materialName)!;
      const target = override?.baseColorHex
        ? new THREE.Color(override.baseColorHex)
        : fallback.color;
      material.metalness = override?.metalness ?? fallback.metalness;
      material.roughness = override?.roughness ?? fallback.roughness;

      if (reducedMotion) {
        material.color.copy(target);
        continue;
      }
      colorTweens.set(materialName, {
        material,
        from: material.color.clone(),
        to: target,
        elapsed: 0,
      });
    }
  }

  applySelection([]);

  function resize() {
    const width = canvas.clientWidth || 1;
    const height = canvas.clientHeight || 1;
    renderer.setSize(width, height, false);
    camera.aspect = width / height;
    camera.updateProjectionMatrix();
  }
  resize();

  let disposed = false;
  let firstFrame = false;
  const clock = new THREE.Clock();

  function tick() {
    if (disposed) return;
    const delta = clock.getDelta();

    for (const [name, tween] of colorTweens) {
      tween.elapsed += delta;
      const t = Math.min(tween.elapsed / COLOR_LERP_SECONDS, 1);
      tween.material.color.copy(tween.from).lerp(tween.to, t);
      if (t >= 1) colorTweens.delete(name);
    }

    controls.update();
    renderer.render(scene, camera);

    if (!firstFrame) {
      firstFrame = true;
      callbacks.onFirstFrame?.();
    }
    requestAnimationFrame(tick);
  }
  requestAnimationFrame(tick);

  function dispose() {
    disposed = true;
    canvas.removeEventListener("webglcontextlost", onContextLost);
    canvas.removeEventListener("keydown", onKeyDown);
    controls.dispose();
    pmrem.dispose();
    scene.traverse((object) => {
      if (object instanceof THREE.Mesh) {
        object.geometry.dispose();
        const materials = Array.isArray(object.material) ? object.material : [object.material];
        for (const material of materials) {
          for (const value of Object.values(material)) {
            if (value instanceof THREE.Texture) value.dispose();
          }
          material.dispose();
        }
      }
    });
    renderer.dispose();
    renderer.forceContextLoss();
  }

  return { applySelection, resize, dispose };
}
