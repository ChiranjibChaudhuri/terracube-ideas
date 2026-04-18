import React, { useState, useEffect, useMemo } from 'react';
import { MarketplaceSidebar } from './MarketplaceSidebar';
import { DynamicForm } from './DynamicForm';
import { useAppStore } from '../lib/store';
import { type Service } from '../types/marketplace';
import { apiFetch } from '../lib/api';
import { getDefaultLayerId, partitionLayers } from '../lib/layerUtils';
import { COLOR_RAMPS } from './ColorLegend';

/**
 * ToolboxPanel - Redesigned with two main sections:
 * 1. Style tab - Apply styling to selected loaded layer
 * 2. Tools tab - Marketplace service browser
 */
export const ToolboxPanel: React.FC = () => {
    const { layers, updateLayer, addLayer, setMaxTid } = useAppStore();
    const [activeTab, setActiveTab] = useState<'style' | 'tools'>('style');
    const [selectedLayerId, setSelectedLayerId] = useState<string | null>(() => getDefaultLayerId(layers));
    const [selectedService, setSelectedService] = useState<Service | null>(null);
    const [status, setStatus] = useState('');
    const [isExecuting, setIsExecuting] = useState(false);
    const [progress, setProgress] = useState(0);
    const [jobId, setJobId] = useState<string | null>(null);

    // Polling effect for background jobs
    useEffect(() => {
        if (!jobId) return;

        let pollCount = 0;
        const poll = async () => {
            try {
                const job = await apiFetch(`/api/jobs/${jobId}`);
                
                if (job.status === 'completed') {
                    setJobId(null);
                    setIsExecuting(false);
                    setStatus('Execution complete. Result added to map.');
                    setProgress(100);

                    if (job.result_dataset_id) {
                        addLayer({
                            id: `layer-${job.result_dataset_id}`,
                            name: `${selectedService?.name || 'Simulation'} Result`,
                            type: 'dggs',
                            data: [], 
                            visible: true,
                            opacity: 0.8,
                            origin: 'operation',
                            datasetId: job.result_dataset_id,
                            dggsName: job.metadata?.dggs_name || 'h3',
                        });

                        // If it's a simulation with timesteps, enable temporal controller
                        if (job.metadata?.timesteps) {
                            setMaxTid(job.metadata.timesteps - 1);
                        }
                    }
                } else if (job.status === 'failed') {
                    setJobId(null);
                    setIsExecuting(false);
                    setStatus(`Error: ${job.metadata?.error || 'Simulation failed'}`);
                    setProgress(0);
                } else {
                    // Running or pending
                    setProgress(job.progress || 0);
                    const stepInfo = job.metadata?.timesteps 
                        ? ` (Step ${Math.floor((job.progress / 100) * job.metadata.timesteps)}/${job.metadata.timesteps})`
                        : '';
                    setStatus(`Executing: ${job.status}${stepInfo}... ${job.progress}%`);
                }
            } catch (error) {
                console.error('Job polling failed:', error);
                pollCount++;
                if (pollCount > 5) { // Stop after 5 consecutive failures
                    setJobId(null);
                    setIsExecuting(false);
                    setStatus('Error: Lost connection to job tracker.');
                }
            }
        };

        const interval = setInterval(poll, 1500);
        return () => clearInterval(interval);
    }, [jobId, addLayer, setMaxTid, selectedService]);

    // Style settings
    const [colorRamp, setColorRamp] = useState('viridis');
    const [opacity, setOpacity] = useState(0.7);
    const [minValue, setMinValue] = useState<string | number>('');
    const [maxValue, setMaxValue] = useState<string | number>('');

    const { datasetLayers, operationLayers } = useMemo(() => partitionLayers(layers), [layers]);

    // Ensure a layer is selected if available and none currently selected
    useEffect(() => {
        if (!selectedLayerId && layers.length > 0) {
            const defaultId = getDefaultLayerId(layers);
            if (defaultId) {
                setSelectedLayerId(defaultId);
            }
        }
    }, [layers, selectedLayerId]);

    // Get selected layer
    const selectedLayer = layers.find(l => l.id === selectedLayerId);

    // Sync state when layer selection changes
    React.useEffect(() => {
        if (selectedLayer) {
            setOpacity(selectedLayer.opacity);
            setColorRamp(selectedLayer.colorRamp ?? 'viridis');
            setMinValue(selectedLayer.minValue ?? '');
            setMaxValue(selectedLayer.maxValue ?? '');
        }
    }, [selectedLayerId, selectedLayer]);

    // Apply style to selected layer
    const handleApplyStyle = () => {
        if (selectedLayerId) {
            const minNum = typeof minValue === 'string' && minValue !== '' ? Number(minValue) : (typeof minValue === 'number' ? minValue : undefined);
            const maxNum = typeof maxValue === 'string' && maxValue !== '' ? Number(maxValue) : (typeof maxValue === 'number' ? maxValue : undefined);

            updateLayer(selectedLayerId, {
                opacity,
                colorRamp,
                minValue: (minNum !== undefined && !isNaN(minNum)) ? minNum : undefined,
                maxValue: (maxNum !== undefined && !isNaN(maxNum)) ? maxNum : undefined
            });
        }
    };

    const formatRangeLabel = (value: string | number, fallback: string) => {
        if (value === '' || value === null || value === undefined) {
            return fallback;
        }
        const num = typeof value === 'number' ? value : Number(value);
        if (!Number.isFinite(num)) {
            return String(value);
        }
        const rounded = Math.round(num * 100) / 100;
        return Number.isInteger(rounded) ? String(rounded) : String(rounded);
    };

    const rampGradient = (COLOR_RAMPS[colorRamp] ?? COLOR_RAMPS.viridis).replace('to top', 'to right');

    // Handle service execution (Marketplace)
    const handleServiceExecute = async (params: Record<string, any>) => {
        if (!selectedService) return;

        setIsExecuting(true);
        setStatus(`Executing ${selectedService.name}...`);
        setProgress(0);
        
        try {
            // Determine endpoint based on service ID
            // For fire-spread, we know it's /api/prediction/fire/spread
            let endpoint = `/api/marketplace/execute/${selectedService.id}`;
            if (selectedService.id === 'fire-spread') {
                endpoint = '/api/prediction/fire/spread';
            }

            const result = await apiFetch(endpoint, {
                method: 'POST',
                body: JSON.stringify(params)
            });

            if (result && result.job_id) {
                // Background job started - polling effect will handle the rest
                setJobId(result.job_id);
                setStatus(`Job started: ${result.job_id}`);
            } else if (result && result.dggids) {
                addLayer({
                    id: `service-${selectedService.id}-${Date.now()}`,
                    name: `${selectedService.name} Result`,
                    type: 'dggs',
                    data: result.dggids,
                    visible: true,
                    opacity: 0.8,
                    origin: 'operation',
                    dggsName: result.dggs_name || 'h3',
                });
                setStatus('Execution complete. Result added to map.');
                setIsExecuting(false);
            } else if (result && result.newDatasetId) {
                // Handle persistent result
                addLayer({
                    id: `layer-${result.newDatasetId}`,
                    name: `${selectedService.name} Result`,
                    type: 'dggs',
                    data: [], 
                    visible: true,
                    opacity: 0.8,
                    origin: 'operation',
                    datasetId: result.newDatasetId,
                    dggsName: 'h3',
                });
                setStatus('Execution complete. Dataset added.');
                setIsExecuting(false);
            } else {
                setStatus('Execution complete.');
                setIsExecuting(false);
            }
        } catch (error) {
            console.error('Service execution failed:', error);
            setStatus(`Error: ${error instanceof Error ? error.message : 'Unknown error'}`);
            setIsExecuting(false);
        }
    };

    return (
        <div className="toolbox-panel">
            {status && (
                <div className="toolbox-status">
                    {status}
                    {isExecuting && (
                        <div className="toolbox-progress">
                            <div 
                                className="toolbox-progress-fill" 
                                style={{ width: `${progress}%` }} 
                            />
                        </div>
                    )}
                </div>
            )}
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
                                        {datasetLayers.length > 0 && (
                                            <optgroup label="Datasets">
                                                {datasetLayers.map(layer => (
                                                    <option key={layer.id} value={layer.id}>
                                                        {layer.name}
                                                    </option>
                                                ))}
                                            </optgroup>
                                        )}
                                        {operationLayers.length > 0 && (
                                            <optgroup label="Operation Results">
                                                {operationLayers.map(layer => (
                                                    <option key={layer.id} value={layer.id}>
                                                        {layer.name}
                                                    </option>
                                                ))}
                                            </optgroup>
                                        )}
                                    </select>
                                </div>

                                {/* Color Ramp Dropdown (New Centralized Control) */}
                                <div className="toolbox-field">
                                    <label className="toolbox-label">Color Ramp</label>
                                    <select
                                        className="toolbox-select"
                                        value={colorRamp}
                                        onChange={(e) => setColorRamp(e.target.value)}
                                    >
                                        <option value="viridis">Viridis (Default)</option>
                                        <option value="plasma">Plasma</option>
                                        <option value="magma">Magma</option>
                                        <option value="inferno">Inferno</option>
                                        <option value="temperature">Temperature (Red-Blue)</option>
                                        <option value="elevation">Elevation (Spectral)</option>
                                        <option value="bathymetry">Bathymetry (Blues)</option>
                                    </select>
                                </div>

                                {/* Data Range Bounds */}
                                <div className="toolbox-field">
                                    <label className="toolbox-label">Data Range (Min / Max)</label>
                                    <div className="toolbox-range-row">
                                        <input
                                            type="number"
                                            className="toolbox-input"
                                            placeholder="Min"
                                            value={minValue}
                                            onChange={(e) => setMinValue(e.target.value)}
                                        />
                                        <input
                                            type="number"
                                            className="toolbox-input"
                                            placeholder="Max"
                                            value={maxValue}
                                            onChange={(e) => setMaxValue(e.target.value)}
                                        />
                                    </div>
                                    <div className="toolbox-colorbar">
                                        <div className="toolbox-colorbar__labels">
                                            <span>{formatRangeLabel(minValue, 'Min')}</span>
                                            <span>{formatRangeLabel(maxValue, 'Max')}</span>
                                        </div>
                                        <div
                                            className="toolbox-colorbar__ramp"
                                            style={{ background: rampGradient }}
                                        />
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
                                            {selectedLayer.datasetId && selectedLayer.data.length === 0
                                                ? (selectedLayer.cellCount !== undefined
                                                    ? `${selectedLayer.cellCount.toLocaleString()} in view`
                                                    : 'streamed')
                                                : (selectedLayer.cellCount ?? selectedLayer.data?.length ?? 0).toLocaleString()}
                                        </span>
                                    </div>
                                )}
                            </>
                        )}
                    </div>
                )}

                {activeTab === 'tools' && (
                    selectedService ? (
                        <DynamicForm 
                            service={selectedService} 
                            onExecute={handleServiceExecute} 
                            onCancel={() => setSelectedService(null)}
                            isRunning={isExecuting}
                        />
                    ) : (
                        <MarketplaceSidebar onSelectService={(service) => setSelectedService(service)} />
                    )
                )}
            </div>
        </div>
    );
};
