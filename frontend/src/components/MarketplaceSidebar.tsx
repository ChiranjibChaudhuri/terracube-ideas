import React, { useState, useMemo } from 'react';
import { useServices } from '../lib/api-hooks';
import { type Service } from '../types/marketplace';

interface MarketplaceSidebarProps {
    onSelectService: (service: Service) => void;
}

export const MarketplaceSidebar: React.FC<MarketplaceSidebarProps> = ({ onSelectService }) => {
    const { data: services = [], isLoading, error } = useServices();
    const [searchQuery, setSearchQuery] = useState('');

    const filteredServices = useMemo(() => {
        const query = searchQuery.toLowerCase();
        return services.filter(s => 
            s.name.toLowerCase().includes(query) || 
            s.description.toLowerCase().includes(query) ||
            s.tags.some(t => t.toLowerCase().includes(query))
        );
    }, [services, searchQuery]);

    if (error) {
        return (
            <div className="toolbox-error">
                Failed to load services. Please try again later.
            </div>
        );
    }

    return (
        <div className="tool-palette">
            {/* Search */}
            <div className="tool-palette__search">
                <span className="tool-palette__search-icon">🔍</span>
                <input
                    type="text"
                    placeholder="Search marketplace..."
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    className="tool-palette__search-input"
                />
                {searchQuery && (
                    <button
                        className="tool-palette__search-clear"
                        onClick={() => setSearchQuery('')}
                    >
                        ✕
                    </button>
                )}
            </div>

            {/* Results */}
            <div className="tool-palette__results">
                {isLoading ? (
                    <div className="loading-indicator">Loading services...</div>
                ) : filteredServices.length === 0 ? (
                    <div className="tool-palette__empty">
                        {searchQuery ? 'No services match your search' : 'No services available in marketplace'}
                    </div>
                ) : (
                    filteredServices.map(service => (
                        <button
                            key={service.id}
                            className="tool-palette__tool"
                            onClick={() => onSelectService(service)}
                        >
                            <span className="tool-palette__tool-icon">
                                {service.type === 'ANALYTIC' ? '⚙️' : '📊'}
                            </span>
                            <div className="tool-palette__tool-info">
                                <span className="tool-palette__tool-name">{service.name}</span>
                                <span className="tool-palette__tool-category">
                                    {service.type.replace('_', ' ')}
                                </span>
                            </div>
                        </button>
                    ))
                )}
            </div>

            <div className="tool-palette__footer">
                <span className="tool-palette__count">{services.length} services available</span>
            </div>
        </div>
    );
};
