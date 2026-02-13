import React, { useState } from 'react';
import { useAppStore, type LayerConfig } from '../lib/store';
import { partitionLayers } from '../lib/layerUtils';
import { useExportCSV, useExportGeoJSON } from '../lib/api-hooks';

interface LayerItemProps {
    layer: LayerConfig;
    onRemove: (id: string) => void;
    onExport?: (layer: LayerConfig, format: 'csv' | 'geojson') => void;
}

const LayerItem: React.FC<LayerItemProps> = ({ layer, onRemove, onExport }) => {
    const [isExporting, setIsExporting] = useState(false);
    const [exportFormat, setExportFormat] = useState<'csv' | 'geojson' | null>(null);

    const exportCSV = useExportCSV();
    const exportGeoJSON = useExportGeoJSON();

    const isDatasetLayer = Boolean(layer.datasetId);
    const isStreamed = Boolean(layer.datasetId) && layer.data.length === 0;
    const countLabel = isStreamed
        ? (layer.cellCount !== undefined ? `${layer.cellCount} in view` : 'streamed')
        : `${layer.cellCount ?? layer.data.length} cells`;

    const handleExport = async (format: 'csv' | 'geojson') => {
        if (!layer.datasetId || !onExport) return;
        setIsExporting(true);
        setExportFormat(format);
        try {
            if (format === 'csv') {
                await exportCSV.mutateAsync(layer.datasetId);
            } else {
                await exportGeoJSON.mutateAsync(layer.datasetId);
            }
            onExport(layer, format);
        } catch (err) {
            console.error('Export failed:', err);
        } finally {
            setIsExporting(false);
            setExportFormat(null);
        }
    };

    return (
        <div className="layer-item">
            <div className="layer-item__header">
                <span className="layer-item__name" title={layer.name}>
                    {layer.name}
                </span>
                <span className="layer-item__count">{countLabel}</span>
                <button
                    onClick={() => onRemove(layer.id)}
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
                        onChange={(e) => {
                            const { updateLayer } = useAppStore.getState();
                            updateLayer(layer.id, { visible: e.target.checked });
                        }}
                    />
                    <span>Visible</span>
                </label>

                {isDatasetLayer && onExport && (
                    <div className="layer-item__export">
                        {isExporting ? (
                            <span className="layer-item__export-status">
                                Exporting{exportFormat ? ` ${exportFormat.toUpperCase()}...` : '...'}
                            </span>
                        ) : (
                            <>
                                <button
                                    className="layer-item__export-btn"
                                    onClick={() => handleExport('csv')}
                                    title="Export as CSV"
                                    disabled={isExporting}
                                >
                                    CSV
                                </button>
                                <button
                                    className="layer-item__export-btn"
                                    onClick={() => handleExport('geojson')}
                                    title="Export as GeoJSON"
                                    disabled={isExporting}
                                >
                                    GeoJSON
                                </button>
                            </>
                        )}
                    </div>
                )}
            </div>
        </div>
    );
};

export const LayerList = () => {
    const { layers, removeLayer } = useAppStore();

    if (layers.length === 0) {
        return <div className="layer-list-empty">No active layers. Load a dataset to get started.</div>;
    }

    const { datasetLayers, operationLayers } = partitionLayers(layers);

    const handleExport = (layer: LayerConfig, format: 'csv' | 'geojson') => {
        console.log(`Exported ${layer.name} as ${format}`);
    };

    const renderLayerItem = (layer: LayerConfig) => {
        return (
            <LayerItem
                key={layer.id}
                layer={layer}
                onRemove={removeLayer}
                onExport={layer.datasetId ? handleExport : undefined}
            />
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
