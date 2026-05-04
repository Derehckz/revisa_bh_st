import { createContext, useCallback, useContext, useMemo, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";

type ToastTone = "success" | "error" | "info";
type ToastItem = { id: string; title: string; tone: ToastTone };

type ToastContextValue = {
  push: (title: string, tone?: ToastTone) => void;
};

const ToastContext = createContext<ToastContextValue | null>(null);

export function ToastProvider({ children }: { children: React.ReactNode }) {
  const [items, setItems] = useState<ToastItem[]>([]);

  const push = useCallback((title: string, tone: ToastTone = "info") => {
    const id = `${Date.now()}-${Math.random().toString(16).slice(2, 8)}`;
    setItems((prev) => [...prev, { id, title, tone }]);
    setTimeout(() => setItems((prev) => prev.filter((i) => i.id !== id)), 3000);
  }, []);

  const value = useMemo(() => ({ push }), [push]);

  return (
    <ToastContext.Provider value={value}>
      {children}
      <div className="fixed right-4 top-4 z-50 space-y-2" aria-live="polite" aria-atomic="true">
        <AnimatePresence>
          {items.map((item) => (
            <motion.div
              key={item.id}
              initial={{ opacity: 0, y: -8 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -8 }}
              className="rounded-md border border-border bg-card px-3 py-2 text-sm shadow-card"
              role="status"
            >
              <span className={item.tone === "error" ? "text-red-600" : item.tone === "success" ? "text-green-600" : ""}>
                {item.title}
              </span>
            </motion.div>
          ))}
        </AnimatePresence>
      </div>
    </ToastContext.Provider>
  );
}

export function useToast() {
  const ctx = useContext(ToastContext);
  if (!ctx) {
    throw new Error("useToast debe usarse dentro de ToastProvider");
  }
  return ctx;
}
