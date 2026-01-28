import React from 'react';
import { useAppStore, type LayerConfig } from '../lib/store';
import { partitionLayers } from '../lib/layerUtils';

export const LayerList = () => {
    const { layers, updateLayer, removeLayer } = useAppStore();

    if (layers.length === 0) {
        return <div className="layer-list-empty">No active layers. Load a dataset to get started.</div>;
    }

    const { datasetLayers, operationLayers } = partitionLayers(layers);

    const renderLayerItem = (layer: LayerConfig) => {
        const isStreamed = Boolean(layer.datasetId) && layer.data.length === 0;
        const countLabel = isStreamed
            ? (layer.cellCount !== undefined ? `${layer.cellCount} in view` : 'streamed')
            : `${layer.cellCount ?? layer.data.length} cells`;

        return (
            <div key={layer.id} className="layer-item">
                <div className="layer-item__header">
                    <span className="layer-item__name" title={layer.name}>
                        {layer.name}
                    </span>
                    <span className="layer-item__count">{countLabel}</span>
                    <button
                        onClick={() => removeLayer(layer.id)}
                        className="layer-item__remove"
                        title="Remove layer"
                    >
                        ×
                    </button>
                </div>

                <div className="layer-item__controls">
                    <label className="layer-item__checkbox">
                        <input
                            type="checkbox"
                            checked={layer.visible}
                            onChange={(e) => updateLayer(layer.id, { visible: e.target.checked })}
                        />
                        <span>Visible</span>
                    </label>
                </div>
            </div>
        );
    };

    return (
        <div className="layer-group-list">
            <div className="layer-group">
                <div className="layer-group__title">Dataset Layers</div>
                {datasetLayers.length === 0 ? (
                    <div className="layer-list-empty">No dataset layers loaded yet.</div>
                ) : (
                    <div className="layer-list">
                        {datasetLayers.map(renderLayerItem)}
                    </div>
                )}
            </div>
            <div className="layer-group">
                <div className="layer-group__title">Operation Results</div>
                {operationLayers.length === 0 ? (
                    <div className="layer-list-empty">No operation results yet.</div>
                ) : (
                    <div className="layer-list">
                        {operationLayers.map(renderLayerItem)}
                    </div>
                )}
            </div>
        </div>
    );
};
