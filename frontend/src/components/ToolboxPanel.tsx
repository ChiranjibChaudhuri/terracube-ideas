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
    const [status, setStatus] = useState('');

    // Style settings
    const [colorRamp, setColorRamp] = useState('viridis');
    const [opacity, setOpacity] = useState(0.7);

    // Get selected layer
    const selectedLayer = layers.find(l => l.id === selectedLayerId);

    // Sync state when layer selection changes
    React.useEffect(() => {
        if (selectedLayer) {
            setOpacity(selectedLayer.opacity);
            setColorRamp(selectedLayer.colorRamp ?? 'viridis');
        }
    }, [selectedLayerId, selectedLayer]); // Re-run when selection or the layer itself changes (e.g. from other updates)

    // Apply style to selected layer
    const handleApplyStyle = () => {
        if (selectedLayerId) {
            updateLayer(selectedLayerId, { opacity, colorRamp });
        }
    };

    // Handle tool execution
    const handleToolExecute = async (toolId: string, params: Record<string, any>) => {
        const tool = selectedTool;
        // if (!tool?.apiEndpoint && toolId !== 'union' && toolId !== 'intersection' && toolId !== 'difference') {
        //     throw new Error('This tool is not available yet.');
        // }

        const getLayer = (id: string) => layers.find(layer => layer.id === id);
        const layerA = getLayer(params.layerA || params.layer || params.zones || '');
        const layerB = getLayer(params.layerB || params.values || '');

        // Persistent Spatial Operations (Union, Intersection, Difference)
        if (toolId === 'union' || toolId === 'intersection' || toolId === 'difference') {
            if (!layerA?.datasetId || !layerB?.datasetId) {
                throw new Error('Selected layers must be saved datasets (not transient).');
            }

            const payload = {
                type: toolId,
                datasetAId: layerA.datasetId,
                datasetBId: layerB.datasetId,
                keyA: layerA.attrKey || 'value',
                keyB: layerB.attrKey || 'value'
            };

            setStatus(`Running ${toolId}...`);
            const result = await apiFetch('/api/ops/spatial', { // Call generic spatial persist endpoint
                method: 'POST',
                body: JSON.stringify(payload)
            });

            if (result.newDatasetId) {
                // Determine name
                const name = `${toolId} result`;

                // Add as a new Dataset Layer (fetched from DB)
                // We use addLayer properties similar to handleDatasetSelect
                setStatus('Loading result...');

                // Fetch stats/metadata if possible, or just add logic to let MapView load it
                // We can fake a "Dataset" object or just pass params

                addLayer({
                    id: `layer-${result.newDatasetId}`,
                    name: name,
                    type: 'dggs',
                    data: [], // Empty, MapView loads it
                    visible: true,
                    opacity: 0.8,
                    datasetId: result.newDatasetId,
                    attrKey: 'intersection', // or whatever we saved
                    dggsName: layerA.dggsName, // access from layer property
                    // Metadata/Range might be unknown initially, MapView handles it?
                });
                setStatus('Operation complete. Layer added.');
            }
            return;
        }

        // ... Existing logic for other tools (buffer etc) ...
        const apiEndpoint = tool?.apiEndpoint;
        if (!apiEndpoint) throw new Error('Tool endpoint not defined');

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
            // } else if (toolId === 'union' || toolId === 'intersection' || toolId === 'difference') {
            // Handled above
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

        const result = await apiFetch(apiEndpoint, {
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
            {status && <div className="toolbox-status" style={{ padding: '8px', background: '#f0f9ff', borderBottom: '1px solid #bae6fd', fontSize: '0.9em' }}>{status}</div>}
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
                                        {['viridis', 'plasma', 'magma', 'inferno', 'temperature', 'elevation', 'bathymetry'].map(ramp => (
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
