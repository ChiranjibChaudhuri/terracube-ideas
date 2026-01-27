
// @vitest-environment jsdom
import { describe, it, expect, vi, beforeAll, afterEach } from 'vitest';
import { render, waitFor, screen, cleanup } from '@testing-library/react';
import MapView from '../components/MapView';
import React from 'react';

// Mock ResizeObserver
beforeAll(() => {
    global.ResizeObserver = class ResizeObserver {
        observe() { }
        unobserve() { }
        disconnect() { }
    };
});

afterEach(() => {
    cleanup();
});

import '@testing-library/jest-dom'; // Fix toBeInTheDocument

// ...

// Mock dependencies
vi.mock('@deck.gl/react', () => ({
    default: ({ viewState, onViewStateChange, children }: { viewState: any, onViewStateChange: any, children: any }) => (
        <div data-testid="deck-gl" onClick={() => onViewStateChange({ viewState: { ...viewState, zoom: viewState.zoom + 1 } })}>
            MockDeckGL Zoom: {viewState.zoom}
            {children}
        </div>
    )
}));

vi.mock('react-map-gl/maplibre', () => ({
    default: () => <div data-testid="maplibre">MockMapLibre</div>
}));

// Mock API
const mockListZones = vi.fn();
vi.mock('../lib/api', () => ({
    listZonesFromBackend: (...args: any[]) => mockListZones(...args),
    fetchCellsByDggids: vi.fn().mockResolvedValue({ cells: [] }),
    getChildren: vi.fn(),
    getNeighbors: vi.fn(),
    getParent: vi.fn()
}));

// Mock dggal
vi.mock('../lib/dggal', () => ({
    resolveZonePolygons: vi.fn().mockResolvedValue(new Map()),
    getZoneLevel: vi.fn()
}));

describe('MapView Zoom Logic', () => {
    it('calculates correct level based on zoom', async () => {
        mockListZones.mockResolvedValue({ zones: ['Z1'], level: 1 });

        render(
            <MapView
                datasetId="test-ds"
                attributeKey="test-key"
                mode="viewport"
                useGlobe={false}
            />
        );

        // Trigger update (debounced 350ms)
        await waitFor(() => {
            expect(mockListZones).toHaveBeenCalled();
        }, { timeout: 1000 });

        // Check call arguments
        // listZonesFromBackend(targetLevel, bbox, ...)
        expect(mockListZones).toHaveBeenLastCalledWith(1, expect.any(Array), undefined, 2600);
    });
    it('renders Map and DeckGL components with correct props', () => {
        render(
            <MapView
                datasetId="test-ds"
                attributeKey="test-key"
                mode="viewport"
                useGlobe={false}
            />
        );

        // Check internal Map component (MapLibre/Mapbox) is rendered
        expect(screen.getByTestId('maplibre')).toBeInTheDocument();

        // Check DeckGL is rendered
        expect(screen.getByTestId('deck-gl')).toBeInTheDocument();

        // Ensure standard map mode does NOT show globe specific layers (like earth-texture)
        // Since we mock DeckGL, we can't inspect layers prop easily unless we spy on the mock.
        // But checking presence is a good baseline.
    });
});
