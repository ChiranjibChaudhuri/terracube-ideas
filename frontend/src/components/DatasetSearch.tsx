import React, { useState, useEffect, useRef, useMemo } from 'react';
import { useDatasets } from '../lib/api-hooks';
import { getDatasetMetadata, partitionDatasets } from '../lib/datasetUtils';

interface Dataset {
    id: string;
    name: string;
    description?: string;
    level?: number;
    metadata?: Record<string, any> | string | null;
}

interface DatasetSearchProps {
    onSelect: (dataset: Dataset) => void;
}

export const DatasetSearch: React.FC<DatasetSearchProps> = ({ onSelect }) => {
    const { data: datasets = [], isLoading } = useDatasets();
    const [activeTab, setActiveTab] = useState<'datasets' | 'results'>('datasets');
    const [datasetQuery, setDatasetQuery] = useState('');
    const [resultQuery, setResultQuery] = useState('');
    const [debouncedDatasetQuery, setDebouncedDatasetQuery] = useState('');
    const [debouncedResultQuery, setDebouncedResultQuery] = useState('');
    const [isOpen, setIsOpen] = useState(false);
    const containerRef = useRef<HTMLDivElement>(null);

    // Debounce search query (300ms)
    useEffect(() => {
        const timer = setTimeout(() => setDebouncedDatasetQuery(datasetQuery), 300);
        return () => clearTimeout(timer);
    }, [datasetQuery]);

    useEffect(() => {
        const timer = setTimeout(() => setDebouncedResultQuery(resultQuery), 300);
        return () => clearTimeout(timer);
    }, [resultQuery]);

    // Categorize datasets
    const { data: dataDatasets, results: resultDatasets } = useMemo(() => {
        return partitionDatasets(datasets as Dataset[]);
    }, [datasets]);

    const filterDatasets = (list: Dataset[], query: string) => {
        if (!query) return list;
        const needle = query.toLowerCase();
        return list.filter((ds: Dataset) =>
            ds.name.toLowerCase().includes(needle) ||
            (ds.description?.toLowerCase().includes(needle))
        );
    };

    const filteredDataDatasets = useMemo(
        () => filterDatasets(dataDatasets, debouncedDatasetQuery),
        [dataDatasets, debouncedDatasetQuery]
    );
    const filteredResultDatasets = useMemo(
        () => filterDatasets(resultDatasets, debouncedResultQuery),
        [resultDatasets, debouncedResultQuery]
    );

    // Close dropdown when clicking outside
    useEffect(() => {
        const handleClickOutside = (e: MouseEvent) => {
            if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
                setIsOpen(false);
            }
        };
        document.addEventListener('mousedown', handleClickOutside);
        return () => document.removeEventListener('mousedown', handleClickOutside);
    }, []);

    const handleSelect = (dataset: Dataset) => {
        onSelect(dataset);
        if (activeTab === 'datasets') {
            setDatasetQuery('');
        } else {
            setResultQuery('');
        }
        setIsOpen(false);
    };

    const renderDatasetItem = (dataset: Dataset, label: string) => {
        return (
            <button
                key={dataset.id}
                className="dataset-search__item"
                onClick={() => handleSelect(dataset)}
            >
                <div className="dataset-search__item-main">
                    <span className="dataset-search__item-name">{dataset.name}</span>
                    <span className="dataset-search__item-type">{label}</span>
                </div>
                {dataset.description && (
                    <div className="dataset-search__item-desc">
                        {dataset.description.slice(0, 60)}...
                    </div>
                )}
            </button>
        );
    };

    const activeQuery = activeTab === 'datasets' ? datasetQuery : resultQuery;
    const activeList = activeTab === 'datasets' ? filteredDataDatasets : filteredResultDatasets;
    const activeCount = activeTab === 'datasets' ? dataDatasets.length : resultDatasets.length;

    return (
        <div className="dataset-search" ref={containerRef}>
            <div className="dataset-search__tabs">
                <button
                    className={`dataset-search__tab ${activeTab === 'datasets' ? 'active' : ''}`}
                    onClick={() => {
                        setActiveTab('datasets');
                        setIsOpen(true);
                    }}
                    type="button"
                >
                    Datasets ({dataDatasets.length})
                </button>
                <button
                    className={`dataset-search__tab ${activeTab === 'results' ? 'active' : ''}`}
                    onClick={() => {
                        setActiveTab('results');
                        setIsOpen(true);
                    }}
                    type="button"
                >
                    Results ({resultDatasets.length})
                </button>
            </div>
            <div className="dataset-search__input-wrapper">
                <input
                    type="text"
                    className="dataset-search__input"
                    placeholder={activeTab === 'datasets' ? 'Search datasets...' : 'Search results...'}
                    value={activeQuery}
                    onChange={(e) => {
                        if (activeTab === 'datasets') {
                            setDatasetQuery(e.target.value);
                        } else {
                            setResultQuery(e.target.value);
                        }
                        setIsOpen(true);
                    }}
                    onFocus={() => setIsOpen(true)}
                />
                <span className="dataset-search__icon">🔍</span>
            </div>

            {isOpen && (
                <div className="dataset-search__dropdown">
                    {isLoading ? (
                        <div className="dataset-search__item dataset-search__item--loading">
                            Loading...
                        </div>
                    ) : activeList.length === 0 ? (
                        <div className="dataset-search__item dataset-search__item--empty">
                            {activeQuery ? 'No matches found' : `No ${activeTab === 'datasets' ? 'datasets' : 'results'} available`}
                        </div>
                    ) : (
                        activeList.map((ds: Dataset) => {
                            const metadata = getDatasetMetadata(ds);
                            const typeLabel = activeTab === 'datasets'
                                ? metadata.source_type || 'Data'
                                : metadata.type || 'Result';
                            return renderDatasetItem(ds, String(typeLabel));
                        })
                    )}
                    {!isLoading && activeList.length > 0 && (
                        <div className="dataset-search__footer">
                            {activeCount} total {activeTab === 'datasets' ? 'datasets' : 'results'}
                        </div>
                    )}
                </div>
            )}
        </div>
    );
};
