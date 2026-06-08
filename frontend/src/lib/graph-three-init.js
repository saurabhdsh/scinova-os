/** Share one THREE instance with 3d-force-graph (avoids black-screen custom objects). */
import * as THREE from 'three';

if (typeof window !== 'undefined') {
  window.THREE = THREE;
}

export { THREE };
