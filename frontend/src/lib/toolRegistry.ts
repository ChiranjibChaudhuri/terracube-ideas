/**
 * Tool Registry - Scalable configuration for DGGS spatial operations
 * Add new tools by simply adding to the TOOLS array
 */

export type ToolCategory = 'geometry' | 'overlay' | 'proximity' | 'statistics' | 'data';

export interface ToolInput {
    name: string;
    label: string;
    type: 'layer' | 'number' | 'select' | 'text' | 'boolean';
    options?: { value: string; label: string }[];
    default?: any;
    required?: boolean;
    description?: string;
}

export interface ToolConfig {
    id: string;
    name: string;
    category: ToolCategory;
    icon: string;
    description: string;
    inputs: ToolInput[];
    apiEndpoint?: string;
}

export const CATEGORY_META: Record<ToolCategory, { icon: string; label: string; color: string }> = {
    geometry: { icon: '📐', label: 'Geometry', color: '#3b82f6' },
    overlay: { icon: '🗺️', label: 'Overlay Analysis', color: '#8b5cf6' },
    proximity: { icon: '📏', label: 'Proximity', color: '#06b6d4' },
    statistics: { icon: '📊', label: 'Statistics', color: '#10b981' },
    data: { icon: '🔧', label: 'Data Management', color: '#f59e0b' },
};

export const TOOLS: ToolConfig[] = [
    // === GEOMETRY ===
    {
        id: 'buffer',
        name: 'Buffer',
        category: 'geometry',
        icon: '⭕',
        description: 'Create buffer zones around DGGS cells using k-ring expansion',
        inputs: [
            { name: 'layer', label: 'Input Layer', type: 'layer', required: true },
            { name: 'rings', label: 'Buffer Rings (k)', type: 'number', default: 1, description: 'Number of cell rings' },
        ],
        apiEndpoint: '/api/ops/spatial',
    },
    {
        id: 'simplify',
        name: 'Simplify',
        category: 'geometry',
        icon: '✂️',
        description: 'Reduce cell count by moving to coarser resolution',
        inputs: [
            { name: 'layer', label: 'Input Layer', type: 'layer', required: true },
            { name: 'targetLevel', label: 'Target Resolution', type: 'number', default: 2 },
        ],
        apiEndpoint: '/api/ops/spatial',
    },
    {
        id: 'convexHull',
        name: 'Convex Hull',
        category: 'geometry',
        icon: '🔷',
        description: 'Compute convex hull of cell set',
        inputs: [
            { name: 'layer', label: 'Input Layer', type: 'layer', required: true },
        ],
        apiEndpoint: '/api/ops/spatial',
    },
    {
        id: 'centroid',
        name: 'Centroid',
        category: 'geometry',
        icon: '🎯',
        description: 'Find center cell of layer',
        inputs: [
            { name: 'layer', label: 'Input Layer', type: 'layer', required: true },
        ],
        apiEndpoint: '/api/ops/spatial',
    },
    {
        id: 'boundingBox',
        name: 'Bounding Box',
        category: 'geometry',
        icon: '⬜',
        description: 'Get rectangular bounds of cell set',
        inputs: [
            { name: 'layer', label: 'Input Layer', type: 'layer', required: true },
        ],
        apiEndpoint: '/api/ops/spatial',
    },

    // === OVERLAY ===
    {
        id: 'union',
        name: 'Union',
        category: 'overlay',
        icon: '⊕',
        description: 'Combine cells from two layers',
        inputs: [
            { name: 'layerA', label: 'Layer A', type: 'layer', required: true },
            { name: 'layerB', label: 'Layer B', type: 'layer', required: true },
        ],
        apiEndpoint: '/api/ops/spatial',
    },
    {
        id: 'intersection',
        name: 'Intersection',
        category: 'overlay',
        icon: '⊗',
        description: 'Find cells common to both layers',
        inputs: [
            { name: 'layerA', label: 'Layer A', type: 'layer', required: true },
            { name: 'layerB', label: 'Layer B', type: 'layer', required: true },
        ],
        apiEndpoint: '/api/ops/spatial',
    },
    {
        id: 'difference',
        name: 'Difference',
        category: 'overlay',
        icon: '⊖',
        description: 'Remove Layer B cells from Layer A',
        inputs: [
            { name: 'layerA', label: 'Layer A', type: 'layer', required: true },
            { name: 'layerB', label: 'Layer B', type: 'layer', required: true },
        ],
        apiEndpoint: '/api/ops/spatial',
    },
    {
        id: 'symmetricDifference',
        name: 'Symmetric Difference',
        category: 'overlay',
        icon: '⊘',
        description: 'Cells in either layer but not both',
        inputs: [
            { name: 'layerA', label: 'Layer A', type: 'layer', required: true },
            { name: 'layerB', label: 'Layer B', type: 'layer', required: true },
        ],
        apiEndpoint: undefined,
    },
    {
        id: 'clip',
        name: 'Clip',
        category: 'overlay',
        icon: '✂️',
        description: 'Clip layer to boundary of mask layer',
        inputs: [
            { name: 'layer', label: 'Input Layer', type: 'layer', required: true },
            { name: 'mask', label: 'Mask Layer', type: 'layer', required: true },
        ],
        apiEndpoint: '/api/ops/spatial',
    },

    // === PROXIMITY ===
    {
        id: 'kRing',
        name: 'K-Ring Neighbors',
        category: 'proximity',
        icon: '🔘',
        description: 'Get cells within k rings of input cells',
        inputs: [
            { name: 'layer', label: 'Input Layer', type: 'layer', required: true },
            { name: 'k', label: 'Ring Distance (k)', type: 'number', default: 1 },
        ],
        apiEndpoint: '/api/ops/spatial',
    },
    {
        id: 'hexDistance',
        name: 'Hex Distance',
        category: 'proximity',
        icon: '📏',
        description: 'Calculate grid distance between cells',
        inputs: [
            { name: 'cellA', label: 'Cell A ID', type: 'text', required: true },
            { name: 'cellB', label: 'Cell B ID', type: 'text', required: true },
        ],
    },
    {
        id: 'nearestNeighbor',
        name: 'Nearest Neighbor',
        category: 'proximity',
        icon: '🎯',
        description: 'Find nearest cells between two layers',
        inputs: [
            { name: 'source', label: 'Source Layer', type: 'layer', required: true },
            { name: 'target', label: 'Target Layer', type: 'layer', required: true },
        ],
    },

    // === STATISTICS ===
    {
        id: 'zonalStats',
        name: 'Zonal Statistics',
        category: 'statistics',
        icon: '📈',
        description: 'Calculate statistics (mean, max, sum) within zones',
        inputs: [
            { name: 'zones', label: 'Zone Layer', type: 'layer', required: true },
            { name: 'values', label: 'Value Layer', type: 'layer', required: true },
            {
                name: 'statistic', label: 'Statistic', type: 'select', options: [
                    { value: 'mean', label: 'Mean' },
                    { value: 'sum', label: 'Sum' },
                    { value: 'max', label: 'Maximum' },
                    { value: 'min', label: 'Minimum' },
                    { value: 'count', label: 'Count' },
                ], default: 'mean'
            },
        ],
        apiEndpoint: '/api/stats/zonal_stats',
    },
    {
        id: 'summaryStats',
        name: 'Summary Statistics',
        category: 'statistics',
        icon: '📊',
        description: 'Get min, max, mean, std for layer values',
        inputs: [
            { name: 'layer', label: 'Input Layer', type: 'layer', required: true },
        ],
    },
    {
        id: 'histogram',
        name: 'Histogram',
        category: 'statistics',
        icon: '📶',
        description: 'Generate value distribution histogram',
        inputs: [
            { name: 'layer', label: 'Input Layer', type: 'layer', required: true },
            { name: 'bins', label: 'Number of Bins', type: 'number', default: 10 },
        ],
    },
    {
        id: 'cellCount',
        name: 'Cell Count',
        category: 'statistics',
        icon: ' '#️⃣',
        description: 'Count cells in layer',
        inputs: [
            { name: 'layer', label: 'Input Layer', type: 'layer', required: true },
        ],
    },

    // === DATA MANAGEMENT ===
    {
        id: 'resolutionChange',
        name: 'Change Resolution',
        category: 'data',
        icon: '🔍',
        description: 'Resample to different DGGS resolution level',
        inputs: [
            { name: 'layer', label: 'Input Layer', type: 'layer', required: true },
            { name: 'targetLevel', label: 'Target Level', type: 'number', default: 3 },
            {
                name: 'method', label: 'Method', type: 'select', options: [
                    { value: 'parent', label: 'To Parent (coarser)' },
                    { value: 'children', label: 'To Children (finer)' },
                ], default: 'parent'
            },
        ],
    },
    {
        id: 'mergeLayers',
        name: 'Merge Layers',
        category: 'data',
        icon: '🔗',
        description: 'Combine multiple layers into one',
        inputs: [
            { name: 'layers', label: 'Select Layers', type: 'layer', required: true },
        ],
    },
    {
        id: 'splitByAttribute',
        name: 'Split by Attribute',
        category: 'data',
        icon: '📂',
        description: 'Split layer into multiple based on attribute values',
        inputs: [
            { name: 'layer', label: 'Input Layer', type: 'layer', required: true },
            { name: 'attribute', label: 'Attribute', type: 'text', required: true },
        ],
    },
    {
        id: 'exportGeoJSON',
        name: 'Export GeoJSON',
        category: 'data',
        icon: '💾',
        description: 'Export layer as GeoJSON file',
        inputs: [
            { name: 'layer', label: 'Input Layer', type: 'layer', required: true },
        ],
    },
    {
        id: 'exportCSV',
        name: 'Export CSV',
        category: 'data',
        icon: '📄',
        description: 'Export layer data as CSV',
        inputs: [
            { name: 'layer', label: 'Input Layer', type: 'layer', required: true },
        ],
    },
];

// Helper to get tools by category
export const getToolsByCategory = (category: ToolCategory): ToolConfig[] =>
    TOOLS.filter(t => t.category === category);

// Helper to search tools
export const searchTools = (query: string): ToolConfig[] => {
    const q = query.toLowerCase();
    return TOOLS.filter(t =>
        t.name.toLowerCase().includes(q) ||
        t.description.toLowerCase().includes(q)
    );
};
