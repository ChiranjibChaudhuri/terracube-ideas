import React, { useState, useMemo } from 'react';
import { type Service } from '../types/marketplace';
import { useAppStore } from '../lib/store';
import { partitionLayers } from '../lib/layerUtils';

interface DynamicFormProps {
    service: Service;
    onExecute: (params: Record<string, any>) => void;
    onCancel: () => void;
    isRunning?: boolean;
}

export const DynamicForm: React.FC<DynamicFormProps> = ({ 
    service, 
    onExecute, 
    onCancel,
    isRunning = false 
}) => {
    const { layers } = useAppStore();
    const { datasetLayers, operationLayers } = useMemo(() => partitionLayers(layers), [layers]);

    const schema = service.input_schema;
    const properties = schema?.properties || {};
    const required = schema?.required || [];

    const [params, setParams] = useState<Record<string, any>>(() => {
        const initial: Record<string, any> = {};
        Object.entries(properties).forEach(([key, value]: [string, any]) => {
            if (value.default !== undefined) {
                initial[key] = value.default;
            } else if (key.endsWith('dataset_id') && layers.length > 0) {
                // Try to find a default layer
                const firstDataset = datasetLayers[0] || layers[0];
                if (firstDataset.datasetId) {
                    initial[key] = firstDataset.datasetId;
                }
            }
        });
        return initial;
    });

    const handleChange = (name: string, value: any) => {
        setParams(prev => ({ ...prev, [name]: value }));
    };

    const handleSubmit = (e: React.FormEvent) => {
        e.preventDefault();
        onExecute(params);
    };

    const renderInput = (name: string, prop: any) => {
        const isRequired = required.includes(name);
        const value = params[name] ?? '';

        // Smart Picker: If it ends with dataset_id
        if (name.endsWith('dataset_id')) {
            return (
                <div key={name} className="toolbox-field">
                    <label className="toolbox-label">
                        {prop.description || name}
                        {isRequired && <span className="toolbox-required">*</span>}
                    </label>
                    <select
                        className="toolbox-select"
                        value={value}
                        onChange={(e) => handleChange(name, e.target.value)}
                        required={isRequired}
                    >
                        <option value="">Select a layer...</option>
                        {datasetLayers.length > 0 && (
                            <optgroup label="Datasets">
                                {datasetLayers.map(l => (
                                    l.datasetId && <option key={l.id} value={l.datasetId}>{l.name}</option>
                                ))}
                            </optgroup>
                        )}
                        {operationLayers.length > 0 && (
                            <optgroup label="Operation Results">
                                {operationLayers.map(l => (
                                    l.datasetId && <option key={l.id} value={l.datasetId}>{l.name}</option>
                                ))}
                            </optgroup>
                        )}
                    </select>
                </div>
            );
        }

        // Handle number
        if (prop.type === 'number' || prop.type === 'integer') {
            return (
                <div key={name} className="toolbox-field">
                    <label className="toolbox-label">
                        {prop.description || name}
                        {isRequired && <span className="toolbox-required">*</span>}
                    </label>
                    <input
                        type="number"
                        className="toolbox-input"
                        value={value}
                        onChange={(e) => handleChange(name, e.target.value === '' ? '' : Number(e.target.value))}
                        step="any"
                        required={isRequired}
                    />
                </div>
            );
        }

        // Default to text
        return (
            <div key={name} className="toolbox-field">
                <label className="toolbox-label">
                    {prop.description || name}
                    {isRequired && <span className="toolbox-required">*</span>}
                </label>
                <input
                    type="text"
                    className="toolbox-input"
                    value={value}
                    onChange={(e) => handleChange(name, e.target.value)}
                    required={isRequired}
                />
            </div>
        );
    };

    return (
        <form className="dynamic-form" onSubmit={handleSubmit}>
            <div className="dynamic-form__header">
                <button type="button" className="dynamic-form__back" onClick={onCancel}>
                    ← Back to Marketplace
                </button>
                <h3 className="dynamic-form__title">{service.name}</h3>
                <p className="dynamic-form__description">{service.description}</p>
            </div>

            <div className="dynamic-form__fields">
                {Object.entries(properties).map(([name, prop]) => renderInput(name, prop))}
            </div>

            <div className="dynamic-form__actions">
                <button 
                    type="submit" 
                    className="toolbox-button"
                    disabled={isRunning}
                >
                    {isRunning ? 'Executing...' : 'Execute'}
                </button>
            </div>
        </form>
    );
};
