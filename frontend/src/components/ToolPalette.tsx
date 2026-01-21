import React, { useState, useMemo, useEffect } from 'react';
import { TOOLS, CATEGORY_META, getToolsByCategory, searchTools, type ToolConfig, type ToolCategory } from '../lib/toolRegistry';

interface ToolPaletteProps {
    onSelectTool: (tool: ToolConfig) => void;
}

export const ToolPalette: React.FC<ToolPaletteProps> = ({ onSelectTool }) => {
    const [searchQuery, setSearchQuery] = useState('');
    const [debouncedQuery, setDebouncedQuery] = useState('');
    const [expandedCategories, setExpandedCategories] = useState<Set<ToolCategory>>(
        new Set(['geometry', 'overlay'])
    );

    const categories: ToolCategory[] = ['geometry', 'overlay', 'proximity', 'statistics', 'data'];

    // Debounce search query (200ms)
    useEffect(() => {
        const timer = setTimeout(() => setDebouncedQuery(searchQuery), 200);
        return () => clearTimeout(timer);
    }, [searchQuery]);

    const filteredTools = useMemo(() => {
        if (debouncedQuery.trim()) {
            return searchTools(debouncedQuery);
        }
        return null;
    }, [debouncedQuery]);

    const toggleCategory = (cat: ToolCategory) => {
        setExpandedCategories(prev => {
            const next = new Set(prev);
            if (next.has(cat)) {
                next.delete(cat);
            } else {
                next.add(cat);
            }
            return next;
        });
    };

    return (
        <div className="tool-palette">
            {/* Search */}
            <div className="tool-palette__search">
                <span className="tool-palette__search-icon">🔍</span>
                <input
                    type="text"
                    placeholder="Search tools..."
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

            {/* Search Results */}
            {filteredTools ? (
                <div className="tool-palette__results">
                    <div className="tool-palette__results-header">
                        {filteredTools.length} tool{filteredTools.length !== 1 ? 's' : ''} found
                    </div>
                    {filteredTools.map(tool => (
                        <button
                            key={tool.id}
                            className="tool-palette__tool"
                            onClick={() => onSelectTool(tool)}
                        >
                            <span className="tool-palette__tool-icon">{tool.icon}</span>
                            <div className="tool-palette__tool-info">
                                <span className="tool-palette__tool-name">{tool.name}</span>
                                <span className="tool-palette__tool-category">
                                    {CATEGORY_META[tool.category].label}
                                </span>
                            </div>
                        </button>
                    ))}
                    {filteredTools.length === 0 && (
                        <div className="tool-palette__empty">No tools match your search</div>
                    )}
                </div>
            ) : (
                /* Category List */
                <div className="tool-palette__categories">
                    {categories.map(cat => {
                        const meta = CATEGORY_META[cat];
                        const tools = getToolsByCategory(cat);
                        const isExpanded = expandedCategories.has(cat);

                        return (
                            <div key={cat} className="tool-palette__category">
                                <button
                                    className="tool-palette__category-header"
                                    onClick={() => toggleCategory(cat)}
                                >
                                    <span className="tool-palette__category-icon">{meta.icon}</span>
                                    <span className="tool-palette__category-label">{meta.label}</span>
                                    <span className="tool-palette__category-count">{tools.length}</span>
                                    <span className="tool-palette__category-toggle">
                                        {isExpanded ? '▾' : '▸'}
                                    </span>
                                </button>
                                {isExpanded && (
                                    <div className="tool-palette__tools">
                                        {tools.map(tool => (
                                            <button
                                                key={tool.id}
                                                className="tool-palette__tool"
                                                onClick={() => onSelectTool(tool)}
                                                title={tool.description}
                                            >
                                                <span className="tool-palette__tool-icon">{tool.icon}</span>
                                                <span className="tool-palette__tool-name">{tool.name}</span>
                                            </button>
                                        ))}
                                    </div>
                                )}
                            </div>
                        );
                    })}
                </div>
            )}

            <div className="tool-palette__footer">
                <span className="tool-palette__count">{TOOLS.length} tools available</span>
            </div>
        </div>
    );
};
