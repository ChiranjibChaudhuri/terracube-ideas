import React, { useState } from 'react';
import { type ToolConfig } from '../lib/toolRegistry';
import { useAppStore } from '../lib/store';

interface ToolModalProps {
    tool: ToolConfig;
    onClose: () => void;
    onExecute: (toolId: string, params: Record<string, any>) => Promise<void>;
}

export const ToolModal: React.FC<ToolModalProps> = ({ tool, onClose, onExecute }) => {
    const { layers } = useAppStore();
    const [params, setParams] = useState<Record<string, any>>(() => {
        const initial: Record<string, any> = {};
        tool.inputs.forEach(input => {
            if (input.default !== undefined) {
                initial[input.name] = input.default;
            } else if (input.type === 'layer' && layers.length > 0) {
                initial[input.name] = layers[0].id;
            }
        });
        return initial;
    });
    const [isRunning, setIsRunning] = useState(false);
    const [result, setResult] = useState<any>(null);
    const [error, setError] = useState<string | null>(null);

    const handleChange = (name: string, value: any) => {
        setParams(prev => ({ ...prev, [name]: value }));
    };

    const handleRun = async () => {
        setIsRunning(true);
        setError(null);
        setResult(null);
        try {
            await onExecute(tool.id, params);
            setResult({ success: true, message: 'Operation completed successfully' });
        } catch (err) {
            setError(err instanceof Error ? err.message : 'Operation failed');
        } finally {
            setIsRunning(false);
        }
    };

    const renderInput = (input: typeof tool.inputs[0]) => {
        const value = params[input.name] ?? '';

        switch (input.type) {
            case 'layer':
                return (
                    <select
                        className="tool-modal__select"
                        value={value}
                        onChange={(e) => handleChange(input.name, e.target.value)}
                    >
                        <option value="">Select layer...</option>
                        {layers.map(layer => (
                            <option key={layer.id} value={layer.id}>{layer.name}</option>
                        ))}
                    </select>
                );
            case 'number':
                return (
                    <input
                        type="number"
                        className="tool-modal__input"
                        value={value}
                        onChange={(e) => handleChange(input.name, Number(e.target.value))}
                    />
                );
            case 'select':
                return (
                    <select
                        className="tool-modal__select"
                        value={value}
                        onChange={(e) => handleChange(input.name, e.target.value)}
                    >
                        {input.options?.map(opt => (
                            <option key={opt.value} value={opt.value}>{opt.label}</option>
                        ))}
                    </select>
                );
            case 'boolean':
                return (
                    <label className="tool-modal__checkbox">
                        <input
                            type="checkbox"
                            checked={!!value}
                            onChange={(e) => handleChange(input.name, e.target.checked)}
                        />
                        <span>Enabled</span>
                    </label>
                );
            default:
                return (
                    <input
                        type="text"
                        className="tool-modal__input"
                        value={value}
                        onChange={(e) => handleChange(input.name, e.target.value)}
                    />
                );
        }
    };

    return (
        <div className="tool-modal__overlay" onClick={onClose}>
            <div className="tool-modal" onClick={(e) => e.stopPropagation()}>
                <div className="tool-modal__header">
                    <span className="tool-modal__icon">{tool.icon}</span>
                    <h3 className="tool-modal__title">{tool.name}</h3>
                    <button className="tool-modal__close" onClick={onClose}>✕</button>
                </div>

                <p className="tool-modal__description">{tool.description}</p>

                <div className="tool-modal__inputs">
                    {tool.inputs.map(input => (
                        <div key={input.name} className="tool-modal__field">
                            <label className="tool-modal__label">
                                {input.label}
                                {input.required && <span className="tool-modal__required">*</span>}
                            </label>
                            {renderInput(input)}
                            {input.description && (
                                <span className="tool-modal__hint">{input.description}</span>
                            )}
                        </div>
                    ))}
                </div>

                {error && (
                    <div className="tool-modal__error">{error}</div>
                )}

                {result && (
                    <div className="tool-modal__result">
                        <span className="tool-modal__result-icon">✓</span>
                        {result.message}
                    </div>
                )}

                <div className="tool-modal__actions">
                    <button className="tool-modal__cancel" onClick={onClose}>
                        Cancel
                    </button>
                    <button
                        className="tool-modal__run"
                        onClick={handleRun}
                        disabled={isRunning}
                    >
                        {isRunning ? 'Running...' : 'Run Tool'}
                    </button>
                </div>
            </div>
        </div>
    );
};
