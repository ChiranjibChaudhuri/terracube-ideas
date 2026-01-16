import React from 'react';

interface ScaleBarProps {
    zoom: number;
    latitude?: number;
}

/**
 * Map scale bar showing metric and imperial measurements
 * Calculates scale based on zoom level and latitude
 */
export const ScaleBar: React.FC<ScaleBarProps> = ({ zoom, latitude = 0 }) => {
    // Calculate meters per pixel at current zoom and latitude
    // Earth circumference at equator = 40075016.686 meters
    const metersPerPixel = (40075016.686 * Math.cos(latitude * Math.PI / 180)) / Math.pow(2, zoom + 8);

    // Target bar width in pixels (aim for 100-150px)
    const targetPixels = 120;
    const roughMeters = metersPerPixel * targetPixels;

    // Round to nice number
    const niceNumbers = [1, 2, 5, 10, 20, 50, 100, 200, 500, 1000, 2000, 5000, 10000, 20000, 50000, 100000, 200000, 500000, 1000000];
    const niceMeters = niceNumbers.reduce((prev, curr) =>
        Math.abs(curr - roughMeters) < Math.abs(prev - roughMeters) ? curr : prev
    );

    // Calculate actual bar width
    const barWidth = niceMeters / metersPerPixel;

    // Format label
    const formatDistance = (m: number): string => {
        if (m >= 1000) return `${(m / 1000).toFixed(0)} km`;
        return `${m} m`;
    };

    // Imperial conversion
    const feet = niceMeters * 3.28084;
    const formatImperial = (f: number): string => {
        if (f >= 5280) return `${(f / 5280).toFixed(1)} mi`;
        return `${Math.round(f)} ft`;
    };

    return (
        <div className="scale-bar">
            <div className="scale-bar__metric">
                <div className="scale-bar__line" style={{ width: `${barWidth}px` }}>
                    <div className="scale-bar__segment scale-bar__segment--light" />
                    <div className="scale-bar__segment scale-bar__segment--dark" />
                </div>
                <div className="scale-bar__labels">
                    <span>0</span>
                    <span>{formatDistance(niceMeters)}</span>
                </div>
            </div>
            <div className="scale-bar__imperial">
                <span className="scale-bar__imperial-text">{formatImperial(feet)}</span>
            </div>
        </div>
    );
};
