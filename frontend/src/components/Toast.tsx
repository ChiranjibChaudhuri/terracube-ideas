import React, { useEffect, useState } from 'react';

export interface ToastMessage {
    id: string;
    message: string;
    type: 'info' | 'success' | 'warning' | 'error';
    duration?: number;
}

interface ToastProps {
    message: ToastMessage;
    onRemove: (id: string) => void;
}

const Toast: React.FC<ToastProps> = ({ message, onRemove }) => {
    const [isLeaving, setIsLeaving] = useState(false);

    useEffect(() => {
        const duration = message.duration ?? 4000;
        const leaveTimer = setTimeout(() => {
            setIsLeaving(true);
        }, duration - 300);

        const removeTimer = setTimeout(() => {
            onRemove(message.id);
        }, duration);

        return () => {
            clearTimeout(leaveTimer);
            clearTimeout(removeTimer);
        };
    }, [message, onRemove]);

    const baseClasses = "toast";
    const typeClasses = {
        info: "toast--info",
        success: "toast--success",
        warning: "toast--warning",
        error: "toast--error",
    };

    const icons = {
        info: "ℹ️",
        success: "✓",
        warning: "⚠️",
        error: "❌",
    };

    return (
        <div className={`${baseClasses} ${typeClasses[message.type]} ${isLeaving ? 'toast--leaving' : ''}`}>
            <span className="toast__icon">{icons[message.type]}</span>
            <span className="toast__message">{message.message}</span>
            <button
                className="toast__close"
                onClick={() => onRemove(message.id)}
                title="Dismiss"
            >
                ×
            </button>
        </div>
    );
};

interface ToastContainerProps {
    messages: ToastMessage[];
    onRemove: (id: string) => void;
}

export const ToastContainer: React.FC<ToastContainerProps> = ({ messages, onRemove }) => {
    if (messages.length === 0) return null;

    return (
        <div className="toast-container">
            {messages.map((msg) => (
                <Toast key={msg.id} message={msg} onRemove={onRemove} />
            ))}
        </div>
    );
};

// Global toast store
let toastListeners: Set<(messages: ToastMessage[]) => void> = new Set();
let toastMessages: ToastMessage[] = [];

export const showToast = (message: string, type: ToastMessage['type'] = 'info', duration?: number) => {
    const id = `toast-${Date.now()}-${Math.random()}`;
    const toast: ToastMessage = { id, message, type, duration };
    toastMessages = [...toastMessages, toast];
    toastListeners.forEach((listener) => listener([...toastMessages]));

    // Auto-remove after duration
    setTimeout(() => {
        removeToast(id);
    }, duration ?? 4000);
};

export const removeToast = (id: string) => {
    toastMessages = toastMessages.filter((m) => m.id !== id);
    toastListeners.forEach((listener) => listener([...toastMessages]));
};

export const useToast = () => {
    const [messages, setMessages] = useState<ToastMessage[]>(toastMessages);

    useEffect(() => {
        const listener = (newMessages: ToastMessage[]) => {
            setMessages(newMessages);
        };
        toastListeners.add(listener);
        return () => {
            toastListeners.delete(listener);
        };
    }, []);

    return { messages, remove: removeToast, show: showToast };
};
