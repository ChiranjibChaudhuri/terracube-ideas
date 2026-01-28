import React from 'react';
import { useAppStore, type LayerConfig } from '../lib/store';

export const LayerList = () => {
    const { layers, updateLayer, removeLayer } = useAppStore();

    if (layers.length === 0) {
        return <div className="layer-list-empty">No active layers. Load a dataset to get started.</div>;
    }

    return (
        <div className="layer-list">
            {layers.map((layer: LayerConfig) => (
                <div key={layer.id} className="layer-item">
                    <div className="layer-item__header">
                        <span className="layer-item__name" title={layer.name}>
                            {layer.name}
                        </span>
                        <span className="layer-item__count">{layer.data.length} cells</span>
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
            ))}
        </div>
    );
};
