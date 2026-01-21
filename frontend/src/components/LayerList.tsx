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

                        <div className="layer-item__opacity">
                            <span>Opacity</span>
                            <input
                                type="range"
                                min="0"
                                max="1"
                                step="0.1"
                                value={layer.opacity}
                                onChange={(e) => updateLayer(layer.id, { opacity: parseFloat(e.target.value) })}
                            />
                        </div>

                        <div
                            className="layer-item__color"
                            style={{
                                background: layer.color
                                    ? `rgb(${layer.color.join(',')})`
                                    : 'linear-gradient(135deg, #440154, #21918c, #fde725)'  // Viridis gradient
                            }}
                            onClick={() => {
                                // Toggle between value-based (undefined) and solid color
                                if (layer.color) {
                                    updateLayer(layer.id, { color: undefined });
                                } else {
                                    const r = Math.floor(Math.random() * 255);
                                    const g = Math.floor(Math.random() * 255);
                                    const b = Math.floor(Math.random() * 255);
                                    updateLayer(layer.id, { color: [r, g, b] });
                                }
                            }}
                            title={layer.color ? "Click for value-based coloring" : "Value-based coloring (click for solid)"}
                        />
                    </div>
                </div>
            ))}
        </div>
    );
};
