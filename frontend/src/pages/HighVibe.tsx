import React, { useState, useEffect, useMemo } from 'react';
import { fetchDatasets, apiFetch } from '../lib/api';
import { zoneToPolygon } from '../lib/dggal';
import DeckGL from '@deck.gl/react';
import { PolygonLayer } from '@deck.gl/layers';
import { Map } from 'react-map-gl';
import maplibregl from 'maplibre-gl';
import 'maplibre-gl/dist/maplibre-gl.css';
import { scaleSequential } from 'd3-scale';
import { interpolateViridis } from 'd3-scale-chromatic';
import { color as d3Color } from 'd3-color';

const MAP_STYLE = "https://basemaps.cartocdn.com/gl/positron-gl-style/style.json";

export default function HighVibe() {
  const [datasets, setDatasets] = useState<any[]>([]);
  const [selectedDataset, setSelectedDataset] = useState<string>("");
  const [zoneId, setZoneId] = useState<string>("A0-0-A");
  const [depth, setDepth] = useState<number>(3);
  const [data, setData] = useState<any>(null);
  const [polygons, setPolygons] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [dataRange, setDataRange] = useState<[number, number]>([0, 1]);

  useEffect(() => {
    fetchDatasets().then(setDatasets).catch(console.error);
  }, []);

  const handleFetch = async () => {
    if (!selectedDataset) return;
    setLoading(true);
    try {
        const url = `/api/high-vibes/zones/${zoneId}/data?depth=${depth}&dataset_id=${selectedDataset}`;
        const result = await apiFetch(url);
        setData(result);
    } catch (e) {
        console.error(e);
        alert("Error fetching data");
    } finally {
        setLoading(false);
    }
  };

  useEffect(() => {
    if (!data) return;
    const process = async () => {
        // Extract the first value key found
        const valueKeys = Object.keys(data.values || {});
        if (valueKeys.length === 0) return;

        const valuesEntry = data.values[valueKeys[0]];
        if (!valuesEntry || !valuesEntry.length) return;

        // Find the entry matching our requested depth
        const entry = valuesEntry.find((e: any) => e.depth === depth);
        if (!entry) return;

        const ids = entry.ids as string[];
        const vals = entry.data as (number | null)[];

        if (!ids || !vals) return;

        // Calculate min/max for coloring
        let min = Infinity;
        let max = -Infinity;
        const validVals = vals.filter(v => v !== null && v !== undefined) as number[];
        if (validVals.length > 0) {
            min = Math.min(...validVals);
            max = Math.max(...validVals);
        }
        if (min === Infinity) { min = 0; max = 1; }
        if (min === max) { max = min + 1; }
        setDataRange([min, max]);

        const promises = ids.map(async (id: string, i: number) => {
            const val = vals[i];
            if (val !== null && val !== undefined) {
                const poly = await zoneToPolygon(id);
                if (poly) {
                    return {
                        polygon: poly,
                        value: val,
                        id: id
                    };
                }
            }
            return null;
        });

        const results = await Promise.all(promises);
        setPolygons(results.filter((p: any) => p !== null));
    };
    process();
  }, [data, depth]);

  const layers = [
    new PolygonLayer({
        id: 'dggs-layer',
        data: polygons,
        getPolygon: (d: any) => d.polygon,
        getFillColor: (d: any) => {
            const val = d.value;
            const normalized = (val - dataRange[0]) / (dataRange[1] - dataRange[0]);
            const colorStr = interpolateViridis(normalized);
            const c = d3Color(colorStr);
            return c ? [c.r, c.g, c.b, 200] : [0, 0, 0, 0];
        },
        getLineColor: [255, 255, 255, 100],
        getLineWidth: 1,
        lineWidthMinPixels: 1,
        pickable: true,
        autoHighlight: true
    })
  ];

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', width: '100%' }}>
      <div style={{ padding: '10px', borderBottom: '1px solid #ccc', backgroundColor: '#f0f0f0' }}>
        <h2 style={{margin: '0 0 10px 0'}}>High Vibes Visualization</h2>
        <div style={{ display: 'flex', gap: '10px', alignItems: 'center', flexWrap: 'wrap' }}>
            <select value={selectedDataset} onChange={e => setSelectedDataset(e.target.value)} style={{padding: '5px'}}>
                <option value="">Select Dataset</option>
                {datasets.map(d => <option key={d.id} value={d.id}>{d.name}</option>)}
            </select>
            <input
                type="text"
                value={zoneId}
                onChange={e => setZoneId(e.target.value)}
                placeholder="Zone ID"
                style={{padding: '5px'}}
            />
            <input
                type="number"
                value={depth}
                onChange={e => setDepth(Number(e.target.value))}
                placeholder="Depth"
                style={{ width: '60px', padding: '5px' }}
            />
            <button
                onClick={handleFetch}
                disabled={loading || !selectedDataset}
                style={{padding: '5px 10px', cursor: 'pointer'}}
            >
                {loading ? 'Loading...' : 'Fetch'}
            </button>
        </div>
      </div>
      <div style={{ flex: 1, position: 'relative' }}>
        <DeckGL
            initialViewState={{
                longitude: 0,
                latitude: 0,
                zoom: 1,
                pitch: 0,
                bearing: 0
            }}
            controller={true}
            layers={layers}
            getTooltip={({object}) => object && `Zone: ${object.id}\nValue: ${object.value}`}
        >
            <Map mapStyle={MAP_STYLE} mapLib={maplibregl} />
        </DeckGL>
      </div>
    </div>
  );
}
