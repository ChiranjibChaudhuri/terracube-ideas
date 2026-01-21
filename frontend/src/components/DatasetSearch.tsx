import React, { useState, useEffect, useRef, useMemo } from 'react';
import { useDatasets } from '../lib/api-hooks';

interface Dataset {
    id: string;
    name: string;
    description?: string;
    level?: number;
    metadata?: {
        source_type?: string;
        attr_key?: string;
    };
}

interface DatasetSearchProps {
    onSelect: (dataset: Dataset) => void;
}

export const DatasetSearch: React.FC<DatasetSearchProps> = ({ onSelect }) => {
    const { data: datasets = [], isLoading } = useDatasets();
    const [query, setQuery] = useState('');
    const [debouncedQuery, setDebouncedQuery] = useState('');
    const [isOpen, setIsOpen] = useState(false);
    const containerRef = useRef<HTMLDivElement>(null);

    // Debounce search query (300ms)
    useEffect(() => {
        const timer = setTimeout(() => setDebouncedQuery(query), 300);
        return () => clearTimeout(timer);
    }, [query]);

    // Filter datasets based on debounced search query
    const filteredDatasets = useMemo(() =>
        datasets.filter((ds: Dataset) =>
            ds.name.toLowerCase().includes(debouncedQuery.toLowerCase()) ||
            (ds.description?.toLowerCase().includes(debouncedQuery.toLowerCase()))
        ), [datasets, debouncedQuery]);

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
        setQuery('');
        setIsOpen(false);
    };

    return (
        <div className="dataset-search" ref={containerRef}>
            <div className="dataset-search__input-wrapper">
                <input
                    type="text"
                    className="dataset-search__input"
                    placeholder="Search datasets..."
                    value={query}
                    onChange={(e) => {
                        setQuery(e.target.value);
                        setIsOpen(true);
                    }}
                    onFocus={() => setIsOpen(true)}
                />
                <span className="dataset-search__icon">🔍</span>
            </div>

            {isOpen && (query || !isLoading) && (
                <div className="dataset-search__dropdown">
                    {isLoading ? (
                        <div className="dataset-search__item dataset-search__item--loading">
                            Loading datasets...
                        </div>
                    ) : filteredDatasets.length === 0 ? (
                        <div className="dataset-search__item dataset-search__item--empty">
                            {query ? 'No datasets found' : 'Type to search...'}
                        </div>
                    ) : (
                        filteredDatasets.slice(0, 8).map((ds: Dataset) => (
                            <button
                                key={ds.id}
                                className="dataset-search__item"
                                onClick={() => handleSelect(ds)}
                            >
                                <div className="dataset-search__item-main">
                                    <span className="dataset-search__item-name">{ds.name}</span>
                                    <span className="dataset-search__item-type">
                                        {ds.metadata?.source_type || 'data'}
                                    </span>
                                </div>
                                {ds.description && (
                                    <div className="dataset-search__item-desc">
                                        {ds.description.slice(0, 60)}...
                                    </div>
                                )}
                            </button>
                        ))
                    )}
                </div>
            )}
        </div>
    );
};
