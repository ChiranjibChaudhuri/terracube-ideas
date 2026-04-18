import React, { useState, useEffect, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { useAppStore } from '../lib/store';

export const TemporalController: React.FC = () => {
    const { currentTid, maxTid, setTid } = useAppStore();
    const [isPlaying, setIsPlaying] = useState(false);
    const playbackInterval = useRef<NodeJS.Timeout | null>(null);

    useEffect(() => {
        if (isPlaying) {
            playbackInterval.current = setInterval(() => {
                setTid((currentTid + 1) % (maxTid + 1));
            }, 1000);
        } else if (playbackInterval.current) {
            clearInterval(playbackInterval.current);
        }

        return () => {
            if (playbackInterval.current) clearInterval(playbackInterval.current);
        };
    }, [isPlaying, currentTid, maxTid, setTid]);

    const handleSliderChange = (e: React.ChangeEvent<HTMLInputElement>) => {
        setTid(parseInt(e.target.value, 10));
    };

    const togglePlay = () => setIsPlaying(!isPlaying);

    if (maxTid === 0) return null;

    return (
        <AnimatePresence>
            <motion.div
                initial={{ y: 100, opacity: 0 }}
                animate={{ y: 0, opacity: 1 }}
                exit={{ y: 100, opacity: 0 }}
                className="temporal-controller"
            >
                <div className="temporal-controller__inner">
                    <button 
                        className={`temporal-controller__play-btn ${isPlaying ? 'active' : ''}`}
                        onClick={togglePlay}
                    >
                        {isPlaying ? (
                            <svg viewBox="0 0 24 24" fill="currentColor">
                                <path d="M6 19h4V5H6v14zm8-14v14h4V5h-4z"/>
                            </svg>
                        ) : (
                            <svg viewBox="0 0 24 24" fill="currentColor">
                                <path d="M8 5v14l11-7z"/>
                            </svg>
                        )}
                    </button>

                    <div className="temporal-controller__slider-container">
                        <div className="temporal-controller__info">
                            <span className="temporal-controller__label">Temporal Step</span>
                            <span className="temporal-controller__value">{currentTid} / {maxTid}</span>
                        </div>
                        <input
                            type="range"
                            min="0"
                            max={maxTid}
                            value={currentTid}
                            onChange={handleSliderChange}
                            className="temporal-controller__slider"
                        />
                    </div>
                </div>

                <style>{`
                    .temporal-controller {
                        position: absolute;
                        bottom: 2rem;
                        left: 50%;
                        transform: translateX(-50%);
                        z-index: 1000;
                        width: min(600px, 90vw);
                    }

                    .temporal-controller__inner {
                        background: var(--panel-dark-solid);
                        backdrop-filter: blur(12px);
                        border: 1px solid var(--glass-border-light);
                        border-radius: 16px;
                        padding: 1rem 1.5rem;
                        display: flex;
                        align-items: center;
                        gap: 1.5rem;
                        box-shadow: var(--shadow-lg), var(--shadow-glow);
                    }

                    .temporal-controller__play-btn {
                        background: var(--signal-600);
                        color: white;
                        border: none;
                        width: 40px;
                        height: 40px;
                        border-radius: 50%;
                        display: flex;
                        align-items: center;
                        justify-content: center;
                        cursor: pointer;
                        transition: all 0.2s var(--ease-out);
                        flex-shrink: 0;
                        box-shadow: 0 0 15px var(--signal-glow);
                    }

                    .temporal-controller__play-btn:hover {
                        background: var(--signal-500);
                        transform: scale(1.05);
                    }

                    .temporal-controller__play-btn svg {
                        width: 20px;
                        height: 20px;
                    }

                    .temporal-controller__slider-container {
                        flex: 1;
                        display: flex;
                        flex-direction: column;
                        gap: 0.5rem;
                    }

                    .temporal-controller__info {
                        display: flex;
                        justify-content: space-between;
                        align-items: baseline;
                    }

                    .temporal-controller__label {
                        font-size: 0.65rem;
                        text-transform: uppercase;
                        letter-spacing: 0.1em;
                        color: var(--stone-400);
                        font-weight: 600;
                    }

                    .temporal-controller__value {
                        font-family: var(--font-mono);
                        font-size: 0.85rem;
                        color: var(--signal-400);
                        font-weight: 600;
                    }

                    .temporal-controller__slider {
                        width: 100%;
                        height: 4px;
                        background: rgba(255, 255, 255, 0.1);
                        border-radius: 2px;
                        appearance: none;
                        outline: none;
                        cursor: pointer;
                    }

                    .temporal-controller__slider::-webkit-slider-thumb {
                        appearance: none;
                        width: 14px;
                        height: 14px;
                        background: var(--signal-500);
                        border-radius: 50%;
                        cursor: grab;
                        box-shadow: 0 0 10px var(--signal-glow);
                        transition: transform 0.1s ease;
                    }

                    .temporal-controller__slider::-webkit-slider-thumb:active {
                        transform: scale(1.2);
                        cursor: grabbing;
                    }
                `}</style>
            </motion.div>
        </AnimatePresence>
    );
};
