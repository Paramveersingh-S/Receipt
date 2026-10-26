"use client";

import React, { useState, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  Search,
  FileText,
  Activity,
  GitBranch,
  RefreshCw,
  BarChart3,
  Copy,
  Radio,
  ArrowRight,
} from "lucide-react";
import { ActiveTab } from "./MacDock";

interface CommandPaletteProps {
  isOpen: boolean;
  onClose: () => void;
  onSelectTab: (tab: ActiveTab) => void;
  onTogglePr: () => void;
  onCopyReceipt: () => void;
}

export function CommandPalette({
  isOpen,
  onClose,
  onSelectTab,
  onTogglePr,
  onCopyReceipt,
}: CommandPaletteProps) {
  const [query, setQuery] = useState("");
  const [selectedIndex, setSelectedIndex] = useState(0);

  const actions = [
    {
      id: "tab-receipt",
      title: "View Evidence Receipt",
      desc: "Skeuomorphic proof receipt, fail-before proofs & mutation score",
      icon: FileText,
      run: () => onSelectTab("receipt"),
    },
    {
      id: "tab-pipeline",
      title: "Open Live Pipeline & SSE Stream",
      desc: "7-stage sandbox execution timeline and real-time logs",
      icon: Activity,
      run: () => onSelectTab("pipeline"),
    },
    {
      id: "tab-scar",
      title: "Explore Scar Tissue Constraints",
      desc: "Historical lessons learned from reverts and incident fixes",
      icon: GitBranch,
      run: () => onSelectTab("scar"),
    },
    {
      id: "tab-repair",
      title: "Inspect Auto-Repair Loop",
      desc: "Self-healing test recovery curve & side-by-side patch diff",
      icon: RefreshCw,
      run: () => onSelectTab("repair"),
    },
    {
      id: "tab-bench",
      title: "View Benchmark Results",
      desc: "ReceiptBench & ScarBench comparison against baselines",
      icon: BarChart3,
      run: () => onSelectTab("benchmarks"),
    },
    {
      id: "act-toggle-pr",
      title: "Toggle PR Sample (Verified #12 vs Rejected #13)",
      desc: "Switch between passing coupon PR and failing subtle bug fixture",
      icon: Radio,
      run: () => onTogglePr(),
    },
    {
      id: "act-copy",
      title: "Tear & Copy Receipt Markdown",
      desc: "Copy deterministic evidence record to clipboard with confetti",
      icon: Copy,
      run: () => onCopyReceipt(),
    },
  ];

  const filtered = actions.filter(
    (a) =>
      query === "" ||
      a.title.toLowerCase().includes(query.toLowerCase()) ||
      a.desc.toLowerCase().includes(query.toLowerCase())
  );

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === "k") {
        e.preventDefault();
        isOpen ? onClose() : undefined;
      }
      if (e.key === "Escape" && isOpen) {
        onClose();
      }
      if (isOpen) {
        if (e.key === "ArrowDown") {
          e.preventDefault();
          setSelectedIndex((prev) => (prev + 1) % filtered.length);
        } else if (e.key === "ArrowUp") {
          e.preventDefault();
          setSelectedIndex((prev) => (prev - 1 + filtered.length) % filtered.length);
        } else if (e.key === "Enter" && filtered[selectedIndex]) {
          e.preventDefault();
          filtered[selectedIndex].run();
          onClose();
        }
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isOpen, selectedIndex, filtered, onClose]);

  if (!isOpen) return null;

  return (
    <AnimatePresence>
      <div className="fixed inset-0 z-50 flex items-start justify-center pt-24 px-4 bg-black/60 backdrop-blur-sm">
        {/* Backdrop click to close */}
        <div className="fixed inset-0" onClick={onClose} />

        <motion.div
          initial={{ opacity: 0, scale: 0.96, y: -10 }}
          animate={{ opacity: 1, scale: 1, y: 0 }}
          exit={{ opacity: 0, scale: 0.96, y: -10 }}
          className="relative w-full max-w-lg glass-panel rounded-2xl overflow-hidden shadow-[0_25px_60px_rgba(0,0,0,0.8)] border border-white/15"
        >
          {/* Search Input Bar */}
          <div className="flex items-center gap-3 px-4 py-3 border-b border-white/10 bg-black/40">
            <Search className="w-4 h-4 text-emerald-400" />
            <input
              type="text"
              autoFocus
              placeholder="Type a command or search..."
              value={query}
              onChange={(e) => {
                setQuery(e.target.value);
                setSelectedIndex(0);
              }}
              className="w-full bg-transparent text-sm text-gray-100 placeholder-gray-500 focus:outline-none"
            />
            <kbd className="px-1.5 py-0.5 text-[10px] font-mono bg-white/10 rounded border border-white/10 text-gray-400">
              ESC
            </kbd>
          </div>

          {/* Action List */}
          <div className="max-h-80 overflow-y-auto p-2 space-y-1">
            {filtered.map((action, idx) => {
              const Icon = action.icon;
              const isSelected = idx === selectedIndex;

              return (
                <button
                  key={action.id}
                  onClick={() => {
                    action.run();
                    onClose();
                  }}
                  onMouseEnter={() => setSelectedIndex(idx)}
                  className={`w-full flex items-center justify-between p-2.5 rounded-xl text-left transition-colors ${
                    isSelected
                      ? "bg-white/15 text-white shadow-inner"
                      : "text-gray-300 hover:bg-white/5"
                  }`}
                >
                  <div className="flex items-center gap-3">
                    <div
                      className={`p-2 rounded-lg ${
                        isSelected
                          ? "bg-emerald-500 text-black font-bold"
                          : "bg-white/5 text-gray-400"
                      }`}
                    >
                      <Icon className="w-4 h-4" />
                    </div>
                    <div>
                      <div className="text-xs font-semibold leading-tight">
                        {action.title}
                      </div>
                      <div className="text-[11px] text-gray-400 mt-0.5">
                        {action.desc}
                      </div>
                    </div>
                  </div>

                  {isSelected && (
                    <ArrowRight className="w-4 h-4 text-emerald-400 mr-1" />
                  )}
                </button>
              );
            })}

            {filtered.length === 0 && (
              <div className="py-8 text-center text-xs text-gray-500">
                No matching actions found.
              </div>
            )}
          </div>

          {/* Footer bar */}
          <div className="px-4 py-2 bg-black/40 border-t border-white/10 flex items-center justify-between text-[11px] text-gray-500 font-mono">
            <span>Navigation: ↑ ↓ Enter</span>
            <span>Receipt OS v1.0</span>
          </div>
        </motion.div>
      </div>
    </AnimatePresence>
  );
}
