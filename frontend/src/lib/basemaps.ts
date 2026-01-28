export type Basemap = {
  id: string;
  label: string;
  styleUrl: string;
  textureUrl: string;
};

export const BASEMAPS: Basemap[] = [
  {
    id: 'voyager-blue-marble-hd',
    label: 'Voyager + Blue Marble HD',
    styleUrl: 'https://basemaps.cartocdn.com/gl/voyager-gl-style/style.json',
    textureUrl: '/basemaps/blue-marble-hd.png',
  },
  {
    id: 'light-blue-marble',
    label: 'Light + Blue Marble',
    styleUrl: 'https://basemaps.cartocdn.com/gl/positron-gl-style/style.json',
    textureUrl: '/basemaps/blue-marble.jpg',
  },
  {
    id: 'dark-night',
    label: 'Dark + Night Lights',
    styleUrl: 'https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json',
    textureUrl: '/basemaps/earth-night.jpg',
  },
  {
    id: 'maplibre-blue-marble',
    label: 'MapLibre + Blue Marble',
    styleUrl: 'https://demotiles.maplibre.org/style.json',
    textureUrl: '/basemaps/blue-marble.jpg',
  },
];

export const DEFAULT_BASEMAP_ID = 'voyager-blue-marble-hd';
