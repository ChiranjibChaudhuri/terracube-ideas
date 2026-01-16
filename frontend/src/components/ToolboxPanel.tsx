import React, { useState } from 'react';
import { ToolPalette } from './ToolPalette';
import { ToolModal } from './ToolModal';
import { useAppStore } from '../lib/store';
import { type ToolConfig } from '../lib/toolRegistry';

/**
 * ToolboxPanel - Redesigned with two main sections:
 * 1. Style tab - Apply styling to selected loaded layer
 * 2. Tools tab - Scalable tool palette with categories
 */
export const ToolboxPanel: React.FC = () => {
    const { layers, updateLayer } = useAppStore();
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
        console.log('Executing tool:', toolId, params);
        // TODO: Call backend API based on tool.apiEndpoint
        // This is where you'd integrate with your backend
        return new Promise(resolve => setTimeout(resolve, 1000));
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
