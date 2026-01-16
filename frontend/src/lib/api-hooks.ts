import { useQuery, useMutation } from '@tanstack/react-query';
import { apiFetch, fetchDatasets } from './api';

export const useDatasets = () => {
    return useQuery({
        queryKey: ['datasets'],
        queryFn: async () => {
            const result = await fetchDatasets();
            return result.datasets ?? [];
        }
    });
};

export const useAnalyticsQuery = () => {
    return useMutation({
        mutationFn: async (payload: any) => {
            return apiFetch('/api/analytics/query', {
                method: 'POST',
                body: JSON.stringify(payload)
            });
        }
    });
};

export const useToolboxOp = (op: 'buffer' | 'union' | 'intersection' | 'difference' | 'mask') => {
    return useMutation({
        mutationFn: async (payload: any) => {
            return apiFetch(`/api/toolbox/${op}`, {
                method: 'POST',
                body: JSON.stringify(payload)
            });
        }
    });
};

export const useZonalStats = () => {
    return useMutation({
        mutationFn: async (payload: any) => {
            return apiFetch('/api/stats/zonal_stats', {
                method: 'POST',
                body: JSON.stringify(payload)
            });
        }
    });
};
