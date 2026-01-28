import React, { useMemo } from 'react';
import { useDatasets } from '../lib/api-hooks';
import { partitionDatasets } from '../lib/datasetUtils';

interface Dataset {
  id: string;
  name: string;
  description?: string;
}

interface OperationResultsListProps {
  onSelect: (dataset: Dataset) => void;
}

export const OperationResultsList: React.FC<OperationResultsListProps> = ({ onSelect }) => {
  const { data: datasets = [], isLoading } = useDatasets();
  const { results } = useMemo(() => partitionDatasets(datasets as Dataset[]), [datasets]);

  if (isLoading) {
    return <div className="empty-state">Loading operation results...</div>;
  }

  if (results.length === 0) {
    return <div className="empty-state">No operation results yet. Run a toolbox op to create one.</div>;
  }

  return (
    <div className="dataset-list">
      {results.map((ds: Dataset) => (
        <button
          key={ds.id}
          onClick={() => onSelect(ds)}
          className="dataset-item"
          title={ds.description}
        >
          <span className="dataset-item__name">{ds.name}</span>
          <span className="dataset-item__add">+</span>
        </button>
      ))}
    </div>
  );
};
