import React, { useState } from 'react';
import { ToolPalette } from './ToolPalette';
import { ToolModal } from './ToolModal';
import { useAppStore } from '../lib/store';
import { type ToolConfig } from '../lib/toolRegistry';
import { apiFetch } from '../lib/api';

/**
 * ToolboxPanel - Redesigned with two main sections:
 * 1. Style tab - Apply styling to selected loaded layer
 * 2. Tools tab - Scalable tool palette with categories
 */
export const ToolboxPanel: React.FC = () => {
    const { layers, updateLayer, addLayer } = useAppStore();
    const [activeTab, setActiveTab] = useState<'style' | 'tools'>('style');
    const [selectedLayerId, setSelectedLayerId] = useState<string | null>(
        layers.length > 0 ? layers[0].id : null
    );
    const [selectedTool, setSelectedTool] = useState<ToolConfig | null>(null);

    // Style settings
    const [colorRamp, setColorRamp] = useState('viridis');
    const [opacity, setOpacity] = useState(0.7);

    // Get selected layer
    const selectedLayer = layers.find(l => l.id === selectedLayerId);

    // Apply style to selected layer
    const handleApplyStyle = () => {
        if (selectedLayerId) {
            updateLayer(selectedLayerId, { opacity });
        }
    };

    // Handle tool execution
    const handleToolExecute = async (toolId: string, params: Record<string, any>) => {
        const tool = selectedTool;
        if (!tool?.apiEndpoint) {
            throw new Error('This tool is not available yet.');
        }

        const getLayer = (id: string) => layers.find(layer => layer.id === id);
        const layerA = getLayer(params.layerA || params.layer || params.zones || '');
        const layerB = getLayer(params.layerB || params.values || '');

        let payload: Record<string, any> = {};
        if (toolId === 'buffer') {
            if (!layerA) throw new Error('Select a valid layer.');
            payload = {
                dggids: layerA.data,
                iterations: Number(params.rings ?? 1),
                dggsName: layerA.dggsName
            };
        } else if (toolId === 'simplify') {
            if (!layerA) throw new Error('Select a valid layer.');
            payload = {
                dggids: layerA.data,
                levels: Number(params.targetLevel ?? 1),
                dggsName: layerA.dggsName
            };
        } else if (toolId === 'union' || toolId === 'intersection' || toolId === 'difference') {
            if (!layerA || !layerB) throw new Error('Select two valid layers.');
            payload = { set_a: layerA.data, set_b: layerB.data };
        } else if (toolId === 'clip') {
            const maskLayer = getLayer(params.mask || '');
            if (!layerA || !maskLayer) throw new Error('Select input and mask layers.');
            payload = { source_dggids: layerA.data, mask_dggids: maskLayer.data };
        } else if (toolId === 'zonalStats') {
            if (!layerA?.datasetId || !layerB?.datasetId) {
                throw new Error('Zonal stats requires layers loaded from datasets.');
            }
            payload = {
                zone_dataset_id: layerA.datasetId,
                value_dataset_id: layerB.datasetId,
                operation: String(params.statistic ?? 'mean').toUpperCase()
            };
        } else {
            throw new Error('Unsupported tool.');
        }

        const result = await apiFetch(tool.apiEndpoint, {
            method: 'POST',
            body: JSON.stringify(payload)
        });

        if (result?.dggids && Array.isArray(result.dggids)) {
            const dggsName = layerA?.dggsName && layerA?.dggsName === layerB?.dggsName
                ? layerA.dggsName
                : layerA?.dggsName;
            addLayer({
                id: `tool-${toolId}-${Date.now()}`,
                name: `${tool.name}`,
                type: 'dggs',
                data: result.dggids,
                visible: true,
                opacity: 0.6,
                color: [90, 161, 255],
                dggsName
            });
        }
    };

    return (
        <div className="toolbox-panel">
            {/* Tab Headers */}
            <div className="toolbox-tabs">
                <button
                    className={`toolbox-tab ${activeTab === 'style' ? 'active' : ''}`}
                    onClick={() => setActiveTab('style')}
                >
                    🎨 Style
                </button>
                <button
                    className={`toolbox-tab ${activeTab === 'tools' ? 'active' : ''}`}
                    onClick={() => setActiveTab('tools')}
                >
                    🔧 Tools
                </button>
            </div>

            {/* Tab Content */}
            <div className="toolbox-content">
                {activeTab === 'style' && (
                    <div className="toolbox-section">
                        {layers.length === 0 ? (
                            <div className="toolbox-empty">
                                <span className="toolbox-empty-icon">📭</span>
                                <p>No layers loaded</p>
                                <p className="toolbox-empty-hint">Search and add a dataset to style it</p>
                            </div>
                        ) : (
                            <>
                                {/* Layer Selector */}
                                <div className="toolbox-field">
                                    <label className="toolbox-label">Target Layer</label>
                                    <select
                                        className="toolbox-select"
                                        value={selectedLayerId || ''}
                                        onChange={(e) => setSelectedLayerId(e.target.value)}
                                    >
                                        {layers.map(layer => (
                                            <option key={layer.id} value={layer.id}>
                                                {layer.name}
                                            </option>
                                        ))}
                                    </select>
                                </div>

                                {/* Color Ramp */}
                                <div className="toolbox-field">
                                    <label className="toolbox-label">Color Ramp</label>
                                    <div className="color-ramp-options">
                                        {['viridis', 'plasma', 'temperature', 'elevation', 'bathymetry'].map(ramp => (
                                            <button
                                                key={ramp}
                                                className={`color-ramp-btn ${colorRamp === ramp ? 'active' : ''}`}
                                                onClick={() => setColorRamp(ramp)}
                                                title={ramp}
                                            >
                                                <div className={`color-ramp-preview color-ramp--${ramp}`} />
                                            </button>
                                        ))}
                                    </div>
                                </div>

                                {/* Opacity */}
                                <div className="toolbox-field">
                                    <label className="toolbox-label">
                                        Opacity: {Math.round(opacity * 100)}%
                                    </label>
                                    <input
                                        type="range"
                                        min="0"
                                        max="1"
                                        step="0.05"
                                        value={opacity}
                                        onChange={(e) => setOpacity(Number(e.target.value))}
                                        className="toolbox-range"
                                    />
                                </div>

                                {/* Apply Button */}
                                <button
                                    className="toolbox-button"
                                    onClick={handleApplyStyle}
                                    disabled={!selectedLayerId}
                                >
                                    Apply Style
                                </button>

                                {selectedLayer && (
                                    <div className="toolbox-layer-info">
                                        <span className="toolbox-layer-info-label">Cells:</span>
                                        <span className="toolbox-layer-info-value">
                                            {selectedLayer.data?.length?.toLocaleString() ?? 0}
                                        </span>
                                    </div>
                                )}
                            </>
                        )}
                    </div>
                )}

                {activeTab === 'tools' && (
                    <ToolPalette onSelectTool={(tool) => setSelectedTool(tool)} />
                )}
            </div>

            {/* Tool Modal */}
            {selectedTool && (
                <ToolModal
                    tool={selectedTool}
                    onClose={() => setSelectedTool(null)}
                    onExecute={handleToolExecute}
                />
            )}
        </div>
    );
};
