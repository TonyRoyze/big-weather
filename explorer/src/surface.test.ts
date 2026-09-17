import {describe, it, expect} from 'vitest';
import {weatherSurface, type WeatherPoint} from './surface';
const point = (longitude: number, latitude: number, value: number | null): WeatherPoint => ({
  longitude, latitude, value, elevation_m: 100, name: 'Sample', location_id: `${longitude}/${latitude}`,
  country: 'LK', region: 'South Asia',
});
describe('weather colour surface', () => {
  it('preserves sample positions, elevation and distinct vertex colours', () => {
    const mesh = weatherSurface([point(80,7,10), point(80.5,7,20), point(80,7.5,30)],10,30,4)!;
    expect(mesh.attributes.positions.value.length).toBe(9);
    expect(mesh.attributes.positions.value[2]).toBe(550);
    expect(new Set(mesh.attributes.colors.value).size).toBeGreaterThan(3);
  });
  it('does not bridge missing observations, distant locations or collinear points', () => {
    expect(weatherSurface([point(80,7,null), point(80.5,7,0), point(80,7.5,10)],0,10,1)).toBeNull();
    expect(weatherSurface([point(80,7,10), point(90,7,20), point(80,20,30)],10,30,1)).toBeNull();
    expect(weatherSurface([point(80,7,10), point(81,7,20), point(82,7,30)],10,30,1)).toBeNull();
  });
  it('handles duplicates and too few samples without inventing a surface', () => {
    expect(weatherSurface([point(80,7,0), point(80,7,0), point(81,7,0)],0,0,1)).toBeNull();
  });
});
