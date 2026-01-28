import React from 'react';

interface ColorLegendProps {
    title: string;
    min: number;
    max: number;
    unit?: string;
    colorRamp?: string;
}

export const COLOR_RAMPS: Record<string, string> = {
    viridis: 'linear-gradient(to top, #440154, #482878, #3e4989, #31688e, #26828e, #1f9e89, #35b779, #6ece58, #b5de2b, #fde725)',
    plasma: 'linear-gradient(to top, #0d0887, #46039f, #7201a8, #9c179e, #bd3786, #d8576b, #ed7953, #fb9f3a, #fdca26, #f0f921)',
    magma: 'linear-gradient(to top, #000004, #180f3d, #440f76, #721f81, #9e2f7f, #cd4071, #f1605d, #fd9668, #fcfdbf)',
    inferno: 'linear-gradient(to top, #000004, #1b0c41, #4a0c6b, #781c6d, #a52c60, #cf4446, #ed6925, #fb9b06, #fcffa4)',
    temperature: 'linear-gradient(to top, #313695, #4575b4, #74add1, #abd9e9, #e0f3f8, #fee090, #fdae61, #f46d43, #d73027, #a50026)',
    elevation: 'linear-gradient(to top, #1a472a, #2d5a3f, #4a7c59, #6b9b6b, #a8c686, #d4e09b, #f2e8a0, #e8c77b, #c9a066, #8b6914)',
    bathymetry: 'linear-gradient(to top, #08306b, #08519c, #2171b5, #4292c6, #6baed6, #9ecae1, #c6dbef, #deebf7, #f7fbff, #ffffff)'
};

/**
 * Color legend for raster data visualization
 * Shows continuous color ramp with value labels
 */
export const ColorLegend: React.FC<ColorLegendProps> = ({
    title,
    min,
    max,
    unit = '',
    colorRamp = 'viridis'
}) => {
    // Generate tick values
    const range = max - min;
    const ticks = [
        { value: max, label: max.toFixed(1) },
        { value: min + range * 0.75, label: (min + range * 0.75).toFixed(1) },
        { value: min + range * 0.5, label: (min + range * 0.5).toFixed(1) },
        { value: min + range * 0.25, label: (min + range * 0.25).toFixed(1) },
        { value: min, label: min.toFixed(1) }
    ];

    return (
        <div className="color-legend">
            <div className="color-legend__title">{title}</div>
            <div className="color-legend__body">
                <div
                    className="color-legend__ramp"
                    style={{ background: COLOR_RAMPS[colorRamp] ?? COLOR_RAMPS.viridis }}
                />
                <div className="color-legend__ticks">
                    {ticks.map((tick, i) => (
                        <div key={i} className="color-legend__tick">
                            <span className="color-legend__tick-line" />
                            <span className="color-legend__tick-label">
                                {tick.label}{unit && ` ${unit}`}
                            </span>
                        </div>
                    ))}
                </div>
            </div>
        </div>
    );
};
