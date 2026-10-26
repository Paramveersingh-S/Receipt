"use client";

import React from "react";
import { Terminal, Radio, Search, ExternalLink, ShieldCheck, AlertCircle } from "lucide-react";
import { Receipt } from "@/types";

interface MacTitlebarProps {
  currentReceipt: Receipt;
  onTogglePr: () => void;
  isLive: boolean;
  onToggleLive: () => void;
  onOpenCommandPalette: () => void;
}

export function MacTitlebar({
  currentReceipt,
  onTogglePr,
  isLive,
  onToggleLive,
  onOpenCommandPalette,
}: MacTitlebarProps) {
  const isVerified = currentReceipt.verdict === "VERIFIED";

  return (
    <header className="h-12 w-full glass-panel border-b border-white/10 flex items-center justify-between px-4 sticky top-0 z-40 select-none">
      {/* macOS Traffic Lights & Repo Title */}
      <div className="flex items-center gap-4">
        <div className="flex items-center gap-2">
          <div className="w-3 h-3 rounded-full bg-[#ff5f56] border border-[#e0443e] cursor-pointer hover:opacity-80 transition-opacity flex items-center justify-center group">
            <span className="text-[8px] text-black font-bold opacity-0 group-hover:opacity-100 transition-opacity">✕</span>
          </div>
          <div className="w-3 h-3 rounded-full bg-[#ffbd2e] border border-[#dea123] cursor-pointer hover:opacity-80 transition-opacity flex items-center justify-center group">
            <span className="text-[8px] text-black font-bold opacity-0 group-hover:opacity-100 transition-opacity">−</span>
          </div>
          <div className="w-3 h-3 rounded-full bg-[#27c93f] border border-[#1aab29] cursor-pointer hover:opacity-80 transition-opacity flex items-center justify-center group">
            <span className="text-[8px] text-black font-bold opacity-0 group-hover:opacity-100 transition-opacity">＋</span>
          </div>
        </div>

        <div className="h-4 w-[1px] bg-white/15" />

        <div className="flex items-center gap-2 text-xs font-mono">
          <span className="text-gray-400">{currentReceipt.repo}</span>
          <span className="text-gray-600">/</span>
          <span className="text-gray-200 font-semibold flex items-center gap-1.5">
            <Terminal className="w-3.5 h-3.5 text-emerald-400" />
            PR #{currentReceipt.pr.number}
          </span>
          <span className="text-xs px-2 py-0.5 rounded-full bg-white/5 border border-white/10 text-gray-300">
            {currentReceipt.pr.author}
          </span>
        </div>
      </div>

      {/* Center Search / Command Palette Trigger */}
      <div className="flex items-center">
        <button
          onClick={onOpenCommandPalette}
          className="flex items-center gap-3 px-3 py-1.5 rounded-lg bg-black/40 hover:bg-black/60 border border-white/10 text-xs text-gray-400 hover:text-gray-200 transition-all shadow-inner group"
        >
          <Search className="w-3.5 h-3.5 text-gray-400 group-hover:text-emerald-400 transition-colors" />
          <span className="hidden sm:inline">Search constraints, proofs & runs...</span>
          <span className="sm:hidden">Search...</span>
          <kbd className="hidden sm:inline-flex items-center gap-0.5 px-1.5 py-0.5 text-[10px] font-mono bg-white/10 rounded border border-white/15 text-gray-300">
            ⌘K
          </kbd>
        </button>
      </div>

      {/* Right Controls: PR Switcher, Live Mode & Status */}
      <div className="flex items-center gap-3 text-xs">
        {/* Toggle Sample PR */}
        <button
          onClick={onTogglePr}
          className={`flex items-center gap-1.5 px-2.5 py-1 rounded-md font-medium border transition-all ${
            isVerified
              ? "bg-emerald-950/40 border-emerald-500/30 text-emerald-300 hover:bg-emerald-900/40"
              : "bg-rose-950/40 border-rose-500/30 text-rose-300 hover:bg-rose-900/40"
          }`}
          title="Switch between passing and failing PR demo fixtures"
        >
          {isVerified ? (
            <ShieldCheck className="w-3.5 h-3.5 text-emerald-400" />
          ) : (
            <AlertCircle className="w-3.5 h-3.5 text-rose-400" />
          )}
          <span>PR #{currentReceipt.pr.number} ({currentReceipt.verdict})</span>
          <span className="text-[10px] opacity-60 underline ml-0.5">switch</span>
        </button>

        {/* Live / Mock SSE Toggle */}
        <button
          onClick={onToggleLive}
          className={`flex items-center gap-1.5 px-2.5 py-1 rounded-md border font-mono transition-all ${
            isLive
              ? "bg-emerald-500/10 border-emerald-500/40 text-emerald-300"
              : "bg-white/5 border-white/10 text-gray-400 hover:text-gray-200"
          }`}
          title={isLive ? "Connected to live SSE stream (localhost:8000)" : "Using offline verification fixtures"}
        >
          <span className="relative flex h-2 w-2">
            {isLive && (
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
            )}
            <span
              className={`relative inline-flex rounded-full h-2 w-2 ${
                isLive ? "bg-emerald-500" : "bg-gray-500"
              }`}
            ></span>
          </span>
          <Radio className="w-3 h-3" />
          <span>{isLive ? "LIVE SSE" : "OFFLINE MOCK"}</span>
        </button>

        <a
          href={currentReceipt.pr.url}
          target="_blank"
          rel="noopener noreferrer"
          className="p-1.5 text-gray-400 hover:text-gray-200 transition-colors"
          title="View on GitHub"
        >
          <ExternalLink className="w-3.5 h-3.5" />
        </a>
      </div>
    </header>
  );
}
