import React, { useState } from 'react';
import { useDatasets, useToolboxOp, useZonalStats } from '../lib/api-hooks';
import { useAppStore, type LayerConfig } from '../lib/store';

type TabType = 'visualization' | 'analysis';

export const ToolboxPanel = () => {
    const { layers, updateLayer } = useAppStore();
    const { data: datasets = [] } = useDatasets();
    const [activeTab, setActiveTab] = useState<TabType>('visualization');

    // Analysis sub-tab
    const [analysisOp, setAnalysisOp] = useState<'buffer' | 'setops' | 'stats'>('buffer');

    // Buffer state
    const [bufferTarget, setBufferTarget] = useState<string>('');
    const [bufferIterations, setBufferIterations] = useState(1);

    // Set ops state
    const [setOpType, setSetOpType] = useState<'union' | 'intersection' | 'difference'>('intersection');
    const [setLayerA, setSetLayerA] = useState<string>('');
    const [setLayerB, setSetLayerB] = useState<string>('');

    // Zonal stats state
    const [zoneDataset, setZoneDataset] = useState<string>('');
    const [valueDataset, setValueDataset] = useState<string>('');
    const [statOp, setStatOp] = useState<'MEAN' | 'MAX' | 'MIN' | 'COUNT' | 'SUM'>('MEAN');
    const [lastStatResult, setLastStatResult] = useState<any>(null);

    // Visualization state
    const [selectedLayer, setSelectedLayer] = useState<string>('');
    const [colorRamp, setColorRamp] = useState<string>('viridis');

    const { addLayer } = useAppStore();
    const bufferMutation = useToolboxOp('buffer');
    const setOpMutation = useToolboxOp(setOpType);
    const statsMutation = useZonalStats();

    const handleBuffer = () => {
        const target = layers.find((l: LayerConfig) => l.id === bufferTarget);
        if (!target) return;
        bufferMutation.mutate({ dggids: target.data, iterations: bufferIterations }, {
            onSuccess: (data: any) => {
                addLayer({
                    id: `buffer-${Date.now()}`,
                    name: `Buffer (${target.name})`,
                    type: 'dggs',
                    data: data.dggids ?? [],
                    visible: true,
                    opacity: 0.6,
                    color: [255, 100, 100]
                });
            }
        });
    };

    const handleSetOp = () => {
        const lA = layers.find((l: LayerConfig) => l.id === setLayerA);
        const lB = layers.find((l: LayerConfig) => l.id === setLayerB);
        if (!lA || !lB) return;
        setOpMutation.mutate({ set_a: lA.data, set_b: lB.data }, {
            onSuccess: (data: any) => {
                addLayer({
                    id: `${setOpType}-${Date.now()}`,
                    name: `${setOpType.charAt(0).toUpperCase() + setOpType.slice(1)}`,
                    type: 'dggs',
                    data: data.dggids ?? [],
                    visible: true,
                    opacity: 0.8,
                    color: [100, 100, 255]
                });
            }
        });
    };

    const handleZonalStats = () => {
        if (!zoneDataset || !valueDataset) return;
        statsMutation.mutate({
            zone_dataset_id: zoneDataset,
            value_dataset_id: valueDataset,
            operation: statOp
        }, {
            onSuccess: (data: any) => setLastStatResult(data)
        });
    };

    const applyColorRamp = () => {
        const layer = layers.find((l: LayerConfig) => l.id === selectedLayer);
        if (!layer) return;
        // Simple color ramp mapping
        const ramps: Record<string, [number, number, number]> = {
            viridis: [68, 1, 84],
            plasma: [240, 249, 33],
            cool: [0, 255, 255],
            warm: [255, 100, 50]
        };
        updateLayer(layer.id, { color: ramps[colorRamp] || [100, 200, 100] });
    };

    return (
        <div className="toolbox-panel">
            {/* Main Tabs */}
            <div className="toolbox-tabs">
                <button
                    className={`toolbox-tab ${activeTab === 'visualization' ? 'active' : ''}`}
                    onClick={() => setActiveTab('visualization')}
                >
                    🎨 Style
                </button>
                <button
                    className={`toolbox-tab ${activeTab === 'analysis' ? 'active' : ''}`}
                    onClick={() => setActiveTab('analysis')}
                >
                    🔬 Analysis
                </button>
            </div>

            <div className="toolbox-content">
                {/* ===================== VISUALIZATION TAB ===================== */}
                {activeTab === 'visualization' && (
                    <div className="toolbox-section">
                        <div className="toolbox-field">
                            <label className="toolbox-label">Target Layer</label>
                            <select
                                className="toolbox-select"
                                value={selectedLayer}
                                onChange={(e) => setSelectedLayer(e.target.value)}
                            >
                                <option value="">Select layer...</option>
                                {layers.map((l: LayerConfig) => (
                                    <option key={l.id} value={l.id}>{l.name}</option>
                                ))}
                            </select>
                        </div>

                        <div className="toolbox-field">
                            <label className="toolbox-label">Color Ramp</label>
                            <select
                                className="toolbox-select"
                                value={colorRamp}
                                onChange={(e) => setColorRamp(e.target.value)}
                            >
                                <option value="viridis">Viridis (Purple→Yellow)</option>
                                <option value="plasma">Plasma (Purple→Orange)</option>
                                <option value="cool">Cool (Cyan→Blue)</option>
                                <option value="warm">Warm (Red→Orange)</option>
                            </select>
                        </div>

                        <button
                            className="toolbox-button"
                            onClick={applyColorRamp}
                            disabled={!selectedLayer}
                        >
                            Apply Style
                        </button>

                        {selectedLayer && (
                            <div className="toolbox-field" style={{ marginTop: '1rem' }}>
                                <label className="toolbox-label">Opacity</label>
                                <input
                                    type="range"
                                    min="0"
                                    max="1"
                                    step="0.1"
                                    value={layers.find((l: LayerConfig) => l.id === selectedLayer)?.opacity ?? 0.5}
                                    onChange={(e) => updateLayer(selectedLayer, { opacity: parseFloat(e.target.value) })}
                                    className="toolbox-range"
                                />
                            </div>
                        )}
                    </div>
                )}

                {/* ===================== ANALYSIS TAB ===================== */}
                {activeTab === 'analysis' && (
                    <div className="toolbox-section">
                        {/* Analysis Operation Selector */}
                        <div className="toolbox-ops">
                            <button
                                className={`toolbox-op-btn ${analysisOp === 'buffer' ? 'active' : ''}`}
                                onClick={() => setAnalysisOp('buffer')}
                            >
                                Buffer
                            </button>
                            <button
                                className={`toolbox-op-btn ${analysisOp === 'setops' ? 'active' : ''}`}
                                onClick={() => setAnalysisOp('setops')}
                            >
                                Set Ops
                            </button>
                            <button
                                className={`toolbox-op-btn ${analysisOp === 'stats' ? 'active' : ''}`}
                                onClick={() => setAnalysisOp('stats')}
                            >
                                Zonal
                            </button>
                        </div>

                        {/* Buffer */}
                        {analysisOp === 'buffer' && (
                            <>
                                <div className="toolbox-field">
                                    <label className="toolbox-label">Input Layer</label>
                                    <select className="toolbox-select" value={bufferTarget} onChange={(e) => setBufferTarget(e.target.value)}>
                                        <option value="">Select...</option>
                                        {layers.map((l: LayerConfig) => <option key={l.id} value={l.id}>{l.name}</option>)}
                                    </select>
                                </div>
                                <div className="toolbox-field">
                                    <label className="toolbox-label">Rings (k)</label>
                                    <input
                                        type="number"
                                        min="1"
                                        max="5"
                                        className="toolbox-input"
                                        value={bufferIterations}
                                        onChange={(e) => setBufferIterations(parseInt(e.target.value))}
                                    />
                                </div>
                                <button className="toolbox-button" onClick={handleBuffer} disabled={!bufferTarget || bufferMutation.isPending}>
                                    {bufferMutation.isPending ? 'Running...' : 'Run Buffer'}
                                </button>
                            </>
                        )}

                        {/* Set Operations */}
                        {analysisOp === 'setops' && (
                            <>
                                <div className="toolbox-field">
                                    <label className="toolbox-label">Operation</label>
                                    <select className="toolbox-select" value={setOpType} onChange={(e) => setSetOpType(e.target.value as any)}>
                                        <option value="union">Union (A ∪ B)</option>
                                        <option value="intersection">Intersect (A ∩ B)</option>
                                        <option value="difference">Difference (A - B)</option>
                                    </select>
                                </div>
                                <div className="toolbox-field">
                                    <label className="toolbox-label">Layer A</label>
                                    <select className="toolbox-select" value={setLayerA} onChange={(e) => setSetLayerA(e.target.value)}>
                                        <option value="">Select...</option>
                                        {layers.map((l: LayerConfig) => <option key={l.id} value={l.id}>{l.name}</option>)}
                                    </select>
                                </div>
                                <div className="toolbox-field">
                                    <label className="toolbox-label">Layer B</label>
                                    <select className="toolbox-select" value={setLayerB} onChange={(e) => setSetLayerB(e.target.value)}>
                                        <option value="">Select...</option>
                                        {layers.map((l: LayerConfig) => <option key={l.id} value={l.id}>{l.name}</option>)}
                                    </select>
                                </div>
                                <button className="toolbox-button" onClick={handleSetOp} disabled={!setLayerA || !setLayerB || setOpMutation.isPending}>
                                    {setOpMutation.isPending ? 'Running...' : 'Run'}
                                </button>
                            </>
                        )}

                        {/* Zonal Statistics */}
                        {analysisOp === 'stats' && (
                            <>
                                <div className="toolbox-field">
                                    <label className="toolbox-label">Zone Dataset</label>
                                    <select className="toolbox-select" value={zoneDataset} onChange={(e) => setZoneDataset(e.target.value)}>
                                        <option value="">Select...</option>
                                        {datasets.map((ds: any) => <option key={ds.id} value={ds.id}>{ds.name}</option>)}
                                    </select>
                                </div>
                                <div className="toolbox-field">
                                    <label className="toolbox-label">Value Dataset</label>
                                    <select className="toolbox-select" value={valueDataset} onChange={(e) => setValueDataset(e.target.value)}>
                                        <option value="">Select...</option>
                                        {datasets.map((ds: any) => <option key={ds.id} value={ds.id}>{ds.name}</option>)}
                                    </select>
                                </div>
                                <div className="toolbox-field">
                                    <label className="toolbox-label">Statistic</label>
                                    <select className="toolbox-select" value={statOp} onChange={(e) => setStatOp(e.target.value as any)}>
                                        <option value="MEAN">Mean</option>
                                        <option value="MAX">Max</option>
                                        <option value="MIN">Min</option>
                                        <option value="SUM">Sum</option>
                                        <option value="COUNT">Count</option>
                                    </select>
                                </div>
                                <button className="toolbox-button" onClick={handleZonalStats} disabled={!zoneDataset || !valueDataset || statsMutation.isPending}>
                                    {statsMutation.isPending ? 'Calculating...' : 'Calculate'}
                                </button>
                                {lastStatResult && (
                                    <div className="toolbox-result">
                                        <span className="toolbox-result__title">{lastStatResult.operation}</span>
                                        <span className="toolbox-result__value">{lastStatResult.result?.toFixed(2) ?? lastStatResult.result}</span>
                                    </div>
                                )}
                            </>
                        )}
                    </div>
                )}
            </div>

            {(bufferMutation.isError || setOpMutation.isError || statsMutation.isError) && (
                <div className="toolbox-error">Operation failed. Check inputs.</div>
            )}
        </div>
    );
};
