export type DatasetLike = {
  metadata?: Record<string, any> | string | null;
  name?: string;
};

const normalizeMetadata = (metadata: DatasetLike['metadata']): Record<string, any> => {
  if (!metadata) return {};
  if (typeof metadata === 'string') {
    try {
      const parsed = JSON.parse(metadata);
      if (parsed && typeof parsed === 'object') {
        return parsed as Record<string, any>;
      }
    } catch {
      return {};
    }
  }
  if (typeof metadata === 'object') {
    return metadata as Record<string, any>;
  }
  return {};
};

export const getDatasetMetadata = (dataset: DatasetLike): Record<string, any> => {
  return normalizeMetadata(dataset.metadata);
};

export const isOperationResultDataset = (dataset: DatasetLike): boolean => {
  const metadata = getDatasetMetadata(dataset);
  const source = typeof metadata.source === 'string' ? metadata.source.toLowerCase() : '';
  const sourceType = typeof metadata.source_type === 'string' ? metadata.source_type.toLowerCase() : '';
  if (source === 'spatial_op' || source === 'operation' || sourceType === 'spatial_op' || sourceType === 'operation') {
    return true;
  }
  if (metadata.type && Array.isArray(metadata.parents)) {
    return true;
  }
  const name = typeof dataset.name === 'string' ? dataset.name.toLowerCase() : '';
  if (name.includes(' result') || name.endsWith('result')) {
    return true;
  }
  return false;
};

export const partitionDatasets = <T extends DatasetLike>(datasets: T[]) => {
  const data: T[] = [];
  const results: T[] = [];

  datasets.forEach((dataset) => {
    if (isOperationResultDataset(dataset)) {
      results.push(dataset);
    } else {
      data.push(dataset);
    }
  });

  return { data, results };
};
