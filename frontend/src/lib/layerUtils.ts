import type { LayerConfig } from './store';

export const partitionLayers = (layers: LayerConfig[]) => {
  const datasetLayers: LayerConfig[] = [];
  const operationLayers: LayerConfig[] = [];

  layers.forEach((layer) => {
    if (layer.origin === 'operation') {
      operationLayers.push(layer);
    } else {
      datasetLayers.push(layer);
    }
  });

  return { datasetLayers, operationLayers };
};

export const getDefaultLayerId = (layers: LayerConfig[]): string | null => {
  const datasetLayer = layers.find((layer) => layer.origin !== 'operation');
  if (datasetLayer) return datasetLayer.id;
  return layers[0]?.id ?? null;
};
