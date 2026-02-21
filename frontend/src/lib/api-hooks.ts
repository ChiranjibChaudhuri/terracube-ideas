import { useQuery, useMutation } from '@tanstack/react-query';
import { apiFetch, fetchDatasets, getUploadStatus, listUploads, exportDatasetCSV, exportDatasetGeoJSON } from './api';

export interface UploadStatus {
    id: string;
    status: string;
    filename: string;
    error: string | null;
    dataset_id: string | null;
    created_at: string;
}

export const useDatasets = (search?: string) => {
    return useQuery({
        queryKey: ['datasets', search],
        queryFn: () => fetchDatasets(search),
    });
};

export const useUploads = (limit = 50, offset = 0, status?: string) => {
    return useQuery({
        queryKey: ['uploads', limit, offset, status],
        queryFn: async () => {
            const result = await listUploads(limit, offset, status);
            return result;
        },
        refetchInterval: 5000 // Poll every 5 seconds
    });
};

export const useUploadStatus = (uploadId: string, pollInterval = 2000) => {
    return useQuery({
        queryKey: ['upload-status', uploadId],
        queryFn: async () => {
            const result = await getUploadStatus(uploadId);
            return result as UploadStatus;
        },
        refetchInterval: pollInterval,
        enabled: !!uploadId
    });
};

export const useUploadMutation = () => {
    return useMutation({
        mutationFn: async (formData: FormData) => {
            return apiFetch('/api/uploads', {
                method: 'POST',
                body: formData,
            });
        }
    });
};

export const useExportCSV = () => {
    return useMutation({
        mutationFn: async (datasetId: string) => {
            // Export returns a Response with CSV content
            const API_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:4000';
            const token = localStorage.getItem('ideas_token');

            const response = await fetch(`${API_URL}/api/datasets/${datasetId}/export`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${token}`,
                },
                body: JSON.stringify({ format: 'csv' }),
            });

            if (!response.ok) {
                throw new Error('Export failed');
            }

            // Create blob from response
            const blob = await response.blob();
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `export_${datasetId}.csv`;
            a.click();
            window.URL.revokeObjectURL(url);
            return true;
        }
    });
};

export const useExportGeoJSON = () => {
    return useMutation({
        mutationFn: async (datasetId: string) => {
            // Export returns a Response with GeoJSON content
            const API_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:4000';
            const token = localStorage.getItem('ideas_token');

            const response = await fetch(`${API_URL}/api/datasets/${datasetId}/export`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${token}`,
                },
                body: JSON.stringify({ format: 'geojson' }),
            });

            if (!response.ok) {
                throw new Error('Export failed');
            }

            // Create blob from response
            const blob = await response.blob();
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `export_${datasetId}.geojson`;
            a.click();
            window.URL.revokeObjectURL(url);
            return true;
        }
    });
};
