"use client";

import React from "react";
import { motion } from "framer-motion";
import {
  FileText,
  Activity,
  GitBranch,
  RefreshCw,
  BarChart3,
} from "lucide-react";

export type ActiveTab = "receipt" | "pipeline" | "scar" | "repair" | "benchmarks";

interface MacDockProps {
  activeTab: ActiveTab;
  onSelectTab: (tab: ActiveTab) => void;
}

const DOCK_ITEMS: Array<{
  id: ActiveTab;
  label: string;
  icon: React.ComponentType<{ className?: string }>;
  badge?: string;
}> = [
  { id: "receipt", label: "Evidence Receipt", icon: FileText, badge: "Proof" },
  { id: "pipeline", label: "Live Pipeline", icon: Activity, badge: "SSE" },
  { id: "scar", label: "Scar Tissue", icon: GitBranch, badge: "7 Rules" },
  { id: "repair", label: "Auto-Repair", icon: RefreshCw, badge: "Loop" },
  { id: "benchmarks", label: "Benchmarks", icon: BarChart3, badge: "96%" },
];

export function MacDock({ activeTab, onSelectTab }: MacDockProps) {
  return (
    <div className="fixed bottom-5 left-1/2 -translate-x-1/2 z-50">
      <nav className="glass-dock px-3 py-2 rounded-2xl flex items-center gap-1 sm:gap-2 shadow-[0_20px_50px_rgba(0,0,0,0.6)]">
        {DOCK_ITEMS.map((item) => {
          const Icon = item.icon;
          const isActive = activeTab === item.id;

          return (
            <button
              key={item.id}
              onClick={() => onSelectTab(item.id)}
              className="relative group p-2 sm:px-3 sm:py-2.5 rounded-xl transition-all duration-200 flex flex-col items-center select-none"
            >
              {/* Tooltip on hover */}
              <div className="absolute -top-10 scale-90 opacity-0 group-hover:scale-100 group-hover:opacity-100 pointer-events-none transition-all duration-150 px-2.5 py-1 rounded-md bg-neutral-900/95 border border-white/15 text-xs text-white whitespace-nowrap shadow-xl">
                <span>{item.label}</span>
                {item.badge && (
                  <span className="ml-1.5 px-1 py-0.2 text-[10px] bg-emerald-500/20 text-emerald-300 rounded border border-emerald-500/30 font-mono">
                    {item.badge}
                  </span>
                )}
              </div>

              {/* Icon Container with hover bounce */}
              <motion.div
                whileHover={{ scale: 1.18, y: -4 }}
                whileTap={{ scale: 0.95 }}
                transition={{ type: "spring", stiffness: 400, damping: 20 }}
                className={`p-2.5 rounded-xl transition-colors duration-200 relative ${
                  isActive
                    ? "bg-white/15 text-white shadow-[inset_0_1px_0_rgba(255,255,255,0.25)] border border-white/20"
                    : "text-gray-400 hover:text-gray-100 hover:bg-white/5"
                }`}
              >
                <Icon className="w-5 h-5 sm:w-5 sm:h-5" />

                {/* Sub-badge pill */}
                {item.badge && (
                  <span className="absolute -top-1 -right-1 px-1 text-[9px] font-mono rounded bg-emerald-500 text-black font-semibold">
                    {item.badge}
                  </span>
                )}
              </motion.div>

              {/* Active Indicator Dot under icon (macOS dock style) */}
              <div className="h-1 flex items-center justify-center mt-1">
                {isActive ? (
                  <motion.div
                    layoutId="dock-active-dot"
                    className="w-1.5 h-1.5 rounded-full bg-emerald-400 shadow-[0_0_8px_#34d399]"
                    transition={{ type: "spring", stiffness: 500, damping: 30 }}
                  />
                ) : (
                  <div className="w-1 h-1 rounded-full bg-transparent group-hover:bg-white/30 transition-colors" />
                )}
              </div>
            </button>
          );
        })}
      </nav>
    </div>
  );
}
