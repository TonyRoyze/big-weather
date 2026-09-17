import {SimpleMeshLayer} from '@deck.gl/mesh-layers';

/** Keep weather colours independent of terrain lighting and camera angle. */
export class WeatherSurfaceLayer extends SimpleMeshLayer {
  static layerName = 'WeatherSurfaceLayer';

  getShaders() {
    const shaders = super.getShaders();
    return {
      ...shaders,
      inject: {
        ...shaders.inject,
        'fs:#main-end': 'fragColor = vec4(color.rgb, color.a * layer.opacity);',
      },
    };
  }
}
