"use client";

import React, { useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { MacTitlebar } from "@/components/MacTitlebar";
import { MacDock, ActiveTab } from "@/components/MacDock";
import { ReceiptCard } from "@/components/ReceiptCard";
import { LivePipelineView } from "@/components/LivePipelineView";
import { ScarTissueView } from "@/components/ScarTissueView";
import { RepairLoopView } from "@/components/RepairLoopView";
import { BenchmarkView } from "@/components/BenchmarkView";
import { CommandPalette } from "@/components/CommandPalette";
import { MOCK_VERIFIED_RECEIPT, MOCK_REJECTED_RECEIPT } from "@/lib/mockData";
import { Receipt } from "@/types";

export default function Home() {
  const [activeTab, setActiveTab] = useState<ActiveTab>("receipt");
  const [currentReceipt, setCurrentReceipt] = useState<Receipt>(MOCK_VERIFIED_RECEIPT);
  const [isLive, setIsLive] = useState(false);
  const [isCommandPaletteOpen, setIsCommandPaletteOpen] = useState(false);

  // Toggle between passing PR #12 and failing subtle-bug PR #13
  const handleTogglePr = () => {
    setCurrentReceipt((prev) =>
      prev.pr.number === 12 ? MOCK_REJECTED_RECEIPT : MOCK_VERIFIED_RECEIPT
    );
  };

  const handleCopyReceipt = () => {
    // Handled by card or keyboard command
    const text = `RECEIPT: ${currentReceipt.repo} PR #${currentReceipt.pr.number} [${currentReceipt.verdict}] Score: ${currentReceipt.score}/100`;
    navigator.clipboard.writeText(text);
  };

  return (
    <div className="min-h-screen bg-[#090a0f] bg-radial-glow bg-grid-pattern text-gray-100 flex flex-col relative selection:bg-emerald-500/30 selection:text-emerald-200">
      {/* macOS Titlebar */}
      <MacTitlebar
        currentReceipt={currentReceipt}
        onTogglePr={handleTogglePr}
        isLive={isLive}
        onToggleLive={() => setIsLive(!isLive)}
        onOpenCommandPalette={() => setIsCommandPaletteOpen(true)}
      />

      {/* Main Content View with Animation Transitions */}
      <main className="flex-1 w-full max-w-7xl mx-auto px-4 py-8 pb-32">
        <AnimatePresence mode="wait">
          {activeTab === "receipt" && (
            <motion.div
              key="receipt"
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -12 }}
              transition={{ duration: 0.2 }}
            >
              <ReceiptCard receipt={currentReceipt} />
            </motion.div>
          )}

          {activeTab === "pipeline" && (
            <motion.div
              key="pipeline"
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -12 }}
              transition={{ duration: 0.2 }}
            >
              <LivePipelineView />
            </motion.div>
          )}

          {activeTab === "scar" && (
            <motion.div
              key="scar"
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -12 }}
              transition={{ duration: 0.2 }}
            >
              <ScarTissueView />
            </motion.div>
          )}

          {activeTab === "repair" && (
            <motion.div
              key="repair"
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -12 }}
              transition={{ duration: 0.2 }}
            >
              <RepairLoopView />
            </motion.div>
          )}

          {activeTab === "benchmarks" && (
            <motion.div
              key="benchmarks"
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -12 }}
              transition={{ duration: 0.2 }}
            >
              <BenchmarkView />
            </motion.div>
          )}
        </AnimatePresence>
      </main>

      {/* Floating macOS Frosted Glass Dock */}
      <MacDock activeTab={activeTab} onSelectTab={setActiveTab} />

      {/* Command Palette Overlay (⌘K) */}
      <CommandPalette
        isOpen={isCommandPaletteOpen}
        onClose={() => setIsCommandPaletteOpen(false)}
        onSelectTab={setActiveTab}
        onTogglePr={handleTogglePr}
        onCopyReceipt={handleCopyReceipt}
      />
    </div>
  );
}
