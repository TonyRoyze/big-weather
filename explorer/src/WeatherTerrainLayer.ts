import {TerrainLayer} from '@deck.gl/geo-layers';
import type {weatherSurface} from './surface';

type Mesh = NonNullable<ReturnType<typeof weatherSurface>>;
type Tile = {x: number; y: number; z: number};
let neutralTexture: HTMLCanvasElement | undefined;
const textures = new WeakMap<Mesh, Map<string, HTMLCanvasElement>>();
const mercatorY = (lat: number) => (1 - Math.log(Math.tan(Math.PI / 4 + lat * Math.PI / 360)) / Math.PI) / 2;

/** Rasterize barycentric weather colours into the DEM tile's own texture coordinates. */
export function weatherPixels(mesh: Mesh, tile: Tile, opacity: number, size = 256) {
  const pixels = new Uint8ClampedArray(size * size * 4);
  for (let i=0;i<pixels.length;i+=4) pixels.set([225,229,227,255],i);
  const positions = mesh.attributes.positions.value, colors = mesh.attributes.colors.value;
  const n=2**tile.z;
  for(let i=0;i<positions.length;i+=9) {
    const v=[0,3,6].map(j=>[( (positions[i+j]+180)/360*n-tile.x)*size,
      (mercatorY(positions[i+j+1])*n-tile.y)*size]);
    const [[ax,ay],[bx,by],[cx,cy]]=v;
    const denominator=(by-cy)*(ax-cx)+(cx-bx)*(ay-cy);
    if(Math.abs(denominator)<1e-9) continue;
    const left=Math.max(0,Math.floor(Math.min(ax,bx,cx))), right=Math.min(size-1,Math.ceil(Math.max(ax,bx,cx)));
    const top=Math.max(0,Math.floor(Math.min(ay,by,cy))), bottom=Math.min(size-1,Math.ceil(Math.max(ay,by,cy)));
    for(let y=top;y<=bottom;y++) for(let x=left;x<=right;x++) {
      const a=((by-cy)*(x+.5-cx)+(cx-bx)*(y+.5-cy))/denominator;
      const b=((cy-ay)*(x+.5-cx)+(ax-cx)*(y+.5-cy))/denominator;
      const c=1-a-b;
      if(Math.min(a,b,c)<-1e-6) continue;
      const index=(y*size+x)*4;
      for(let channel=0;channel<3;channel++) {
        const value=255*(a*colors[i+channel]+b*colors[i+3+channel]+c*colors[i+6+channel]);
        pixels[index+channel]=pixels[index+channel]*(1-opacity)+value*opacity;
      }
    }
  }
  return pixels;
}

export class WeatherTerrainLayer extends TerrainLayer<{weatherMesh: Mesh | null; weatherOpacity: number}> {
  static layerName = 'WeatherTerrainLayer';
  renderLayers() {
    const layer=super.renderLayers();
    if(!layer || Array.isArray(layer)) return layer;
    return layer.clone({updateTriggers:{...layer.props.updateTriggers,
      weatherColors:[this.props.weatherMesh,this.props.weatherOpacity]}});
  }
  renderSubLayers(props: Parameters<TerrainLayer['renderSubLayers']>[0]) {
    const layer = super.renderSubLayers(props);
    const mesh=this.props.weatherMesh;
    if(!layer) return layer;
    if(!mesh) {
      if(!neutralTexture) {
        neutralTexture=document.createElement('canvas'); neutralTexture.width=neutralTexture.height=2;
        const context=neutralTexture.getContext('2d')!;
        context.fillStyle='rgb(225,229,227)'; context.fillRect(0,0,2,2);
      }
      return layer.clone({texture:neutralTexture,getColor:[255,255,255]});
    }
    let cache=textures.get(mesh);
    if(!cache) {cache=new Map(); textures.set(mesh,cache);}
    const tile=props.tile.index;
    const key=`${tile.z}/${tile.x}/${tile.y}/${this.props.weatherOpacity}`;
    let canvas=cache.get(key);
    if(!canvas) {
      canvas=document.createElement('canvas'); canvas.width=canvas.height=256;
      const context=canvas.getContext('2d')!;
      context.putImageData(new ImageData(weatherPixels(mesh,tile,this.props.weatherOpacity),256,256),0,0);
      if(cache.size>=160) cache.delete(cache.keys().next().value!);
      cache.set(key,canvas);
    }
    return layer.clone({texture:canvas, getColor:[255,255,255]});
  }
}
