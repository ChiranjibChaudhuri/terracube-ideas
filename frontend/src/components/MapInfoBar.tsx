import React from 'react';

interface MapInfoBarProps {
    coordinates: { lat: number; lng: number } | null;
    zoom: number;
    level?: number;
    cellCount: number;
    status?: string;
}

/**
 * Professional status bar for scientific GIS software
 * Displays coordinates, zoom level, DGGS level, and cell statistics
 */
export const MapInfoBar: React.FC<MapInfoBarProps> = ({
    coordinates,
    zoom,
    level,
    cellCount,
    status
}) => {
    // Format coordinates with precision
    const formatCoord = (val: number, isLat: boolean): string => {
        const abs = Math.abs(val);
        const deg = Math.floor(abs);
        const min = Math.floor((abs - deg) * 60);
        const sec = ((abs - deg - min / 60) * 3600).toFixed(2);
        const dir = isLat ? (val >= 0 ? 'N' : 'S') : (val >= 0 ? 'E' : 'W');
        return `${deg}°${min}'${sec}"${dir}`;
    };

    // Calculate approximate scale based on zoom
    const getScaleText = (z: number): string => {
        // Approximate scale at equator for each zoom level
        const scales: Record<number, string> = {
            0: '1:500M', 1: '1:250M', 2: '1:150M', 3: '1:70M',
            4: '1:35M', 5: '1:15M', 6: '1:10M', 7: '1:4M',
            8: '1:2M', 9: '1:1M', 10: '1:500K', 11: '1:250K',
            12: '1:150K', 13: '1:70K', 14: '1:35K', 15: '1:15K',
            16: '1:8K', 17: '1:4K', 18: '1:2K', 19: '1:1K', 20: '1:500'
        };
        return scales[Math.round(z)] || `1:${Math.round(591657550.5 / Math.pow(2, z))}`;
    };

    return (
        <div className="map-info-bar">
            {/* Coordinates */}
            <div className="info-bar__section info-bar__coords">
                <span className="info-bar__label">Coords:</span>
                {coordinates ? (
                    <>
                        <span className="info-bar__value">
                            {formatCoord(coordinates.lat, true)}
                        </span>
                        <span className="info-bar__separator">,</span>
                        <span className="info-bar__value">
                            {formatCoord(coordinates.lng, false)}
                        </span>
                        <span className="info-bar__decimal">
                            ({coordinates.lat.toFixed(4)}, {coordinates.lng.toFixed(4)})
                        </span>
                    </>
                ) : (
                    <span className="info-bar__placeholder">—</span>
                )}
            </div>

            {/* Divider */}
            <div className="info-bar__divider" />

            {/* Zoom & Scale */}
            <div className="info-bar__section">
                <span className="info-bar__label">Zoom:</span>
                <span className="info-bar__value">{zoom.toFixed(1)}</span>
                <span className="info-bar__scale">{getScaleText(zoom)}</span>
            </div>

            {/* Divider */}
            <div className="info-bar__divider" />

            {/* DGGS Level */}
            <div className="info-bar__section">
                <span className="info-bar__label">DGGS Level:</span>
                <span className="info-bar__value info-bar__level">{level ?? '—'}</span>
            </div>

            {/* Divider */}
            <div className="info-bar__divider" />

            {/* Cell Count */}
            <div className="info-bar__section">
                <span className="info-bar__label">Cells:</span>
                <span className="info-bar__value">{cellCount.toLocaleString()}</span>
            </div>

            {/* Status (right-aligned) */}
            <div className="info-bar__status">
                <span className={`info-bar__status-dot ${status === 'Ready' ? 'ready' : 'busy'}`} />
                <span className="info-bar__status-text">{status || 'Ready'}</span>
            </div>
        </div>
    );
};
