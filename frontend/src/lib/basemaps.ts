export type FlatBasemap = {
  id: string;
  label: string;
  styleUrl: string;
};

export type GlobeBasemap = {
  id: string;
  label: string;
  textureUrl: string;
};

export const FLAT_BASEMAPS: FlatBasemap[] = [
  {
    id: 'carto-dark',
    label: 'Carto Dark',
    styleUrl: 'https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json',
  },
  {
    id: 'carto-light',
    label: 'Carto Light',
    styleUrl: 'https://basemaps.cartocdn.com/gl/positron-gl-style/style.json',
  },
  {
    id: 'carto-voyager',
    label: 'Carto Voyager',
    styleUrl: 'https://basemaps.cartocdn.com/gl/voyager-gl-style/style.json',
  },
  {
    id: 'maplibre-demo',
    label: 'MapLibre Demo',
    styleUrl: 'https://demotiles.maplibre.org/style.json',
  },
];

export const GLOBE_BASEMAPS: GlobeBasemap[] = [
  {
    id: 'blue-marble-hd',
    label: 'Blue Marble HD',
    textureUrl: 'https://eoimages.gsfc.nasa.gov/images/imagerecords/57000/57730/land_ocean_ice_2048.png',
  },
  {
    id: 'blue-marble',
    label: 'Blue Marble (Standard)',
    textureUrl: 'https://unpkg.com/three-globe@2.26.0/example/img/earth-blue-marble.jpg',
  },
  {
    id: 'earth-night',
    label: 'Earth Night Lights',
    textureUrl: 'https://unpkg.com/three-globe@2.26.0/example/img/earth-night.jpg',
  },
];

export const DEFAULT_FLAT_BASEMAP_ID = 'carto-dark';
export const DEFAULT_GLOBE_BASEMAP_ID = 'blue-marble-hd';
