import React, { useState } from 'react';
import { useAppStore, type Annotation } from '../lib/store';
import { deleteAnnotation } from '../lib/api';
import { motion, AnimatePresence } from 'framer-motion';

export const AnnotationFeed: React.FC = () => {
    const { annotations, removeAnnotation, currentDatasetId } = useAppStore();
    const [filter, setFilter] = useState('');

    const filtered = annotations.filter(a => 
        a.content.toLowerCase().includes(filter.toLowerCase()) ||
        a.cell_dggid.toLowerCase().includes(filter.toLowerCase())
    );

    const handleDelete = async (id: string) => {
        try {
            await deleteAnnotation(id);
            removeAnnotation(id);
        } catch (err) {
            console.error('Failed to delete annotation:', err);
        }
    };

    return (
        <div className="annotation-feed">
            <input
                type="text"
                className="search-input"
                placeholder="Filter annotations..."
                value={filter}
                onChange={(e) => setFilter(e.target.value)}
            />

            <div className="annotation-list">
                <AnimatePresence>
                    {filtered.map((a) => (
                        <motion.div
                            key={a.id}
                            initial={{ opacity: 0, y: 10 }}
                            animate={{ opacity: 1, y: 0 }}
                            exit={{ opacity: 0, x: -20 }}
                            className="annotation-card"
                        >
                            <div className="annotation-card__header">
                                <span className="annotation-card__cell">{a.cell_dggid}</span>
                                <button 
                                    className="annotation-card__delete"
                                    onClick={() => handleDelete(a.id)}
                                >
                                    ×
                                </button>
                            </div>
                            <p className="annotation-card__content">{a.content}</p>
                            <div className="annotation-card__footer">
                                <span className="annotation-card__type">{a.type}</span>
                                <span className="annotation-card__date">
                                    {a.created_at ? new Date(a.created_at).toLocaleDateString() : 'recent'}
                                </span>
                            </div>
                        </motion.div>
                    ))}
                </AnimatePresence>

                {filtered.length === 0 && (
                    <div className="empty-state">
                        {filter ? 'No annotations match your filter.' : 'No annotations found for this dataset.'}
                    </div>
                )}
            </div>
        </div>
    );
};
