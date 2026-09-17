import {describe,it,expect} from 'vitest';
import {weatherPixels} from './WeatherTerrainLayer';
import {weatherSurface, type WeatherPoint} from './surface';
const point=(longitude:number,latitude:number,value:number|null):WeatherPoint=>({longitude,latitude,value,elevation_m:100,name:'sample',location_id:String(longitude),country:'LK',region:'Asia'});
describe('terrain texture',()=>{
  it('interpolates colour inside nearby triangles while leaving distant terrain neutral',()=>{
    const mesh=weatherSurface([point(80,7,10),point(81,7,20),point(80,8,30)],10,30,1)!;
    const x=Math.floor((80+180)/360*256),y=Math.floor((1-Math.log(Math.tan(Math.PI/4+7.5*Math.PI/360))/Math.PI)/2*256);
    const pixels=weatherPixels(mesh,{x,y,z:8},1,64);
    let coloured=0;
    for(let i=0;i<pixels.length;i+=4) if(pixels[i]!==225 || pixels[i+1]!==229 || pixels[i+2]!==227) coloured++;
    expect(coloured).toBeGreaterThan(0);
    expect(coloured).toBeLessThan(4096);
    const neutral=weatherPixels(mesh,{x:0,y:0,z:8},1,16);
    expect([...neutral.slice(0,4)]).toEqual([225,229,227,255]);
    expect([...weatherPixels(mesh,{x,y,z:8},0,16).slice(0,4)]).toEqual([225,229,227,255]);
  });
});
