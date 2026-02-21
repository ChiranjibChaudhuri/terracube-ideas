const API_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:4000';

const getToken = () => localStorage.getItem('ideas_token');

/**
 * Decode JWT token payload (without verification - just for expiry check)
 */
const decodeToken = (token: string): { exp?: number } | null => {
    try {
        const base64Url = token.split('.')[1];
        if (!base64Url) return null;
        let base64 = base64Url.replace(/-/g, '+').replace(/_/g, '/');
        const padding = base64.length % 4;
        if (padding) {
            base64 += '='.repeat(4 - padding);
        }
        const payload = atob(base64);
        return JSON.parse(payload);
    } catch {
        return null;
    }
};

/**
 * Check if token is expired (with 30 second buffer)
 */
const isTokenExpired = (token: string): boolean => {
    const payload = decodeToken(token);
    if (!payload?.exp) return true;
    const now = Math.floor(Date.now() / 1000);
    return payload.exp < now + 30; // 30 second buffer
};

/**
 * Handle authentication failure - clear storage and redirect to login
 */
const handleAuthFailure = (reason: string) => {
    localStorage.removeItem('ideas_token');
    // Store reason for login page to display
    sessionStorage.setItem('auth_redirect_reason', reason);
    window.location.href = '/login';
};

export const apiFetch = async (path: string, options: RequestInit = {}) => {
    const headers = new Headers(options.headers);
    headers.set('Accept', 'application/json');
    if (!(options.body instanceof FormData)) {
        headers.set('Content-Type', 'application/json');
    }

    const token = getToken();

    // Check token expiry before making request (skip for auth endpoints)
    if (token && !path.startsWith('/api/auth/')) {
        if (isTokenExpired(token)) {
            handleAuthFailure('Your session has expired. Please log in again.');
            throw new Error('Session expired');
        }
        headers.set('Authorization', `Bearer ${token}`);
    }

    const response = await fetch(`${API_URL}${path}`, {
        ...options,
        headers,
    });

    // Handle 401 Unauthorized
    if (response.status === 401) {
        handleAuthFailure('Your session is no longer valid. Please log in again.');
        throw new Error('Unauthorized');
    }

    if (!response.ok) {
        const payload = await response.json().catch(() => ({}));
        throw new Error(payload.error ?? payload.detail ?? 'Request failed');
    }

    return response.json();
};

export const login = async (email: string, password: string) => {
    const result = await apiFetch('/api/auth/login', {
        method: 'POST',
        body: JSON.stringify({ email, password }),
    });
    localStorage.setItem('ideas_token', result.token);
    return result.user;
};

export const register = async (name: string, email: string, password: string) => {
    const result = await apiFetch('/api/auth/register', {
        method: 'POST',
        body: JSON.stringify({ name, email, password }),
    });
    localStorage.setItem('ideas_token', result.token);
    return result.user;
};

export const logout = () => {
    localStorage.removeItem('ideas_token');
};

export const fetchDatasets = async (search?: string) => {
    const qs = search ? `?search=${encodeURIComponent(search)}` : '';
    return apiFetch(`/api/datasets${qs}`);
};

export const fetchCells = async (
    datasetId: string,
    params: Record<string, string | undefined | null> = {}
) => {
    const filtered = Object.entries(params).filter(([, value]) => value !== undefined && value !== null && value !== '');
    const query = new URLSearchParams(filtered as [string, string][]).toString();
    return apiFetch(`/api/datasets/${datasetId}/cells${query ? `?${query}` : ''}`);
};

export const fetchCellsByDggids = async (
    datasetId: string,
    dggids: string[],
    key?: string,
    tid?: number,
    options: RequestInit = {}
) => {
    return apiFetch(`/api/datasets/${datasetId}/lookup`, {
        method: 'POST',
        body: JSON.stringify({ dggids, key, tid }),
        ...options,
    });
};

export const runOperation = async (payload: Record<string, unknown>) => {
    return apiFetch('/api/ops/query', {
        method: 'POST',
        body: JSON.stringify(payload),
    });
};

export const runSpatialOperation = async (payload: Record<string, unknown>) => {
    return apiFetch('/api/ops/spatial', {
        method: 'POST',
        body: JSON.stringify(payload),
    });
};

export const getNeighbors = async (dggid: string, dggsName?: string) => {
    return apiFetch('/api/topology/topology', {
        method: 'POST',
        body: JSON.stringify({ type: 'neighbors', dggid, dggsName }),
    });
};

export const getParent = async (dggid: string, dggsName?: string) => {
    return apiFetch('/api/topology/topology', {
        method: 'POST',
        body: JSON.stringify({ type: 'parent', dggid, dggsName }),
    });
};

export const getChildren = async (dggid: string, dggsName?: string) => {
    return apiFetch('/api/topology/topology', {
        method: 'POST',
        body: JSON.stringify({ type: 'children', dggid, dggsName }),
    });
};

export const getVertices = async (dggid: string, dggsName?: string) => {
    return apiFetch('/api/topology/topology', {
        method: 'POST',
        body: JSON.stringify({ type: 'vertices', dggid, dggsName }),
    });
};

/**
 * List zone IDs from backend to ensure consistency with stored data.
 * This uses the same DGGAL library as data ingestion.
 */
export const listZonesFromBackend = async (
    level: number,
    bbox: [number, number, number, number],  // [min_lat, min_lon, max_lat, max_lon]
    dggsName?: string,
    maxZones?: number
): Promise<{ level: number; zoneCount: number; zones: string[] }> => {
    return apiFetch('/api/topology/list_zones', {
        method: 'POST',
        body: JSON.stringify({ level, bbox, dggsName, maxZones }),
    });
};

export const uploadDataset = async (
    file: File,
    datasetName?: string,
    datasetDescription?: string,
    options: {
        datasetId?: string;
        attrKey?: string;
        minLevel?: number;
        maxLevel?: number;
        sourceType?: string;
    } = {}
) => {
    const formData = new FormData();
    formData.append('file', file);
    if (datasetName) formData.append('datasetName', datasetName);
    if (datasetDescription) formData.append('datasetDescription', datasetDescription);
    if (options.datasetId) formData.append('dataset_id', options.datasetId);
    if (options.attrKey) formData.append('attrKey', options.attrKey);
    if (options.minLevel !== undefined) formData.append('minLevel', String(options.minLevel));
    if (options.maxLevel !== undefined) formData.append('maxLevel', String(options.maxLevel));
    if (options.sourceType) formData.append('sourceType', options.sourceType);

    return apiFetch('/api/uploads', {
        method: 'POST',
        body: formData,
    });
};

/**
 * Get the status of an upload/job.
 */
export const getUploadStatus = async (uploadId: string) => {
    return apiFetch(`/api/uploads/${uploadId}`);
};

/**
 * List recent uploads for the current user.
 */
export const listUploads = async (limit = 50, offset = 0, status?: string) => {
    const params = new URLSearchParams();
    if (limit) params.append('limit', String(limit));
    if (offset) params.append('offset', String(offset));
    if (status) params.append('status', status);
    const qs = params.toString();
    return apiFetch(`/api/uploads${qs ? `?${qs}` : ''}`);
};

/**
 * Export a dataset as CSV.
 */
export const exportDatasetCSV = async (datasetId: string) => {
    return apiFetch(`/api/datasets/${datasetId}/export`, {
        method: 'POST',
        body: JSON.stringify({ format: 'csv' }),
    });
};

/**
 * Export a dataset as GeoJSON.
 */
export const exportDatasetGeoJSON = async (datasetId: string) => {
    return apiFetch(`/api/datasets/${datasetId}/export`, {
        method: 'POST',
        body: JSON.stringify({ format: 'geojson' }),
    });
};
