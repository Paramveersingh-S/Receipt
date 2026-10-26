"use client";

import React, { useState } from "react";
import { motion } from "framer-motion";
import {
  RefreshCw,
  CheckCircle2,
  AlertTriangle,
  ArrowRight,
  Code2,
  Bug,
  Sparkles,
} from "lucide-react";

export function RepairLoopView() {
  const [activeIteration, setActiveIteration] = useState<1 | 2>(2);

  return (
    <div className="w-full max-w-5xl mx-auto space-y-6">
      {/* Top Banner */}
      <div className="p-5 rounded-xl glass-panel flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <RefreshCw className="w-5 h-5 text-emerald-400" />
            <h2 className="text-lg font-bold text-gray-100">
              Self-Healing Auto-Repair Loop
            </h2>
          </div>
          <p className="text-xs text-gray-400 mt-1 max-w-2xl">
            When an agent PR fails constraints or proofs, Receipt feeds structured diagnostics back to the LLM for targeted in-place repair (bounded to max 3 iterations).
          </p>
        </div>

        {/* Iteration Selector Tabs */}
        <div className="flex items-center gap-1 bg-black/40 p-1 rounded-lg border border-white/10 text-xs">
          <button
            onClick={() => setActiveIteration(1)}
            className={`px-3 py-1.5 rounded-md flex items-center gap-1.5 transition-colors ${
              activeIteration === 1
                ? "bg-rose-500/20 text-rose-300 border border-rose-500/30 font-semibold"
                : "text-gray-400 hover:text-gray-200"
            }`}
          >
            <AlertTriangle className="w-3.5 h-3.5" />
            <span>Iter 1 (Rejected: 52/100)</span>
          </button>

          <span className="text-gray-600">➔</span>

          <button
            onClick={() => setActiveIteration(2)}
            className={`px-3 py-1.5 rounded-md flex items-center gap-1.5 transition-colors ${
              activeIteration === 2
                ? "bg-emerald-500/20 text-emerald-300 border border-emerald-500/30 font-semibold"
                : "text-gray-400 hover:text-gray-200"
            }`}
          >
            <CheckCircle2 className="w-3.5 h-3.5" />
            <span>Iter 2 (Verified: 92/100)</span>
          </button>
        </div>
      </div>

      {/* Progress & Recovery Curve Card */}
      <div className="p-5 rounded-xl glass-panel space-y-4">
        <div className="flex items-center justify-between text-xs text-gray-400 font-mono">
          <span>REPAIR SCORE CONVERGENCE</span>
          <span className="text-emerald-400 font-bold">+40 PTS RECOVERED IN 1 TURN</span>
        </div>

        {/* Visual Stepper */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {/* Iteration 1 Card */}
          <div
            onClick={() => setActiveIteration(1)}
            className={`p-4 rounded-xl border cursor-pointer transition-all ${
              activeIteration === 1
                ? "bg-rose-950/20 border-rose-500/50 shadow-[0_0_15px_rgba(244,63,94,0.15)]"
                : "bg-black/20 border-white/5 opacity-70 hover:opacity-100"
            }`}
          >
            <div className="flex items-center justify-between mb-2">
              <span className="text-xs font-mono font-bold text-rose-400">
                ITERATION 1 • INITIAL PR
              </span>
              <span className="text-xs px-2 py-0.5 rounded bg-rose-500/20 text-rose-300 border border-rose-500/40 font-bold">
                REJECTED (52/100)
              </span>
            </div>
            <p className="text-xs text-gray-300">
              Agent PR introduced float division in coupon discount computation, violating constraint <code className="text-rose-300 font-mono">sc_001</code>.
            </p>
            <div className="mt-3 flex items-center gap-2 text-[11px] text-rose-400 font-mono">
              <Bug className="w-3.5 h-3.5" />
              <span>1 constraint violation • 1 proof failure</span>
            </div>
          </div>

          {/* Iteration 2 Card */}
          <div
            onClick={() => setActiveIteration(2)}
            className={`p-4 rounded-xl border cursor-pointer transition-all ${
              activeIteration === 2
                ? "bg-emerald-950/20 border-emerald-500/50 shadow-[0_0_15px_rgba(16,185,129,0.15)]"
                : "bg-black/20 border-white/5 opacity-70 hover:opacity-100"
            }`}
          >
            <div className="flex items-center justify-between mb-2">
              <span className="text-xs font-mono font-bold text-emerald-400">
                ITERATION 2 • REPAIR PATCH
              </span>
              <span className="text-xs px-2 py-0.5 rounded bg-emerald-500/20 text-emerald-300 border border-emerald-500/40 font-bold">
                VERIFIED (92/100)
              </span>
            </div>
            <p className="text-xs text-gray-300">
              Receipt injected exact constraint diagnostic; agent re-wrote pricing formula using pure integer cents with half-up rounding.
            </p>
            <div className="mt-3 flex items-center gap-2 text-[11px] text-emerald-400 font-mono">
              <Sparkles className="w-3.5 h-3.5" />
              <span>All 3 proofs passed • 0 regressions • 89% mutation score</span>
            </div>
          </div>
        </div>
      </div>

      {/* Code Diff & Diagnostic Inspector */}
      <div className="rounded-xl glass-panel overflow-hidden border border-white/10">
        <div className="h-10 bg-black/60 border-b border-white/10 px-4 flex items-center justify-between text-xs">
          <div className="flex items-center gap-2 font-mono text-gray-300">
            <Code2 className="w-4 h-4 text-emerald-400" />
            <span>Unified Diff: `demo/demo-shop/shop/pricing.py`</span>
          </div>
          <span className="text-[11px] font-mono text-gray-400">
            {activeIteration === 1 ? "Defect Introduced" : "Auto-Repair Patch Applied"}
          </span>
        </div>

        {activeIteration === 1 ? (
          <div className="p-4 bg-[#08090d] font-mono text-xs space-y-1">
            <div className="text-gray-500">@@ -38,7 +38,12 @@ def calculate_discount(total_cents: int, discount_pct: int) -&gt; int:</div>
            <div className="text-gray-400">     if discount_pct &lt;= 0:</div>
            <div className="text-gray-400">         return 0</div>
            <div className="bg-rose-950/40 text-rose-300 border-l-2 border-rose-500 pl-2 py-0.5">
              -    # Subtly buggy implementation using float math
            </div>
            <div className="bg-rose-950/40 text-rose-300 border-l-2 border-rose-500 pl-2 py-0.5">
              -    discount = int(total_cents * (discount_pct / 100.0))
            </div>
            <div className="bg-rose-950/40 text-rose-300 border-l-2 border-rose-500 pl-2 py-0.5">
              -    return discount
            </div>
            <div className="text-gray-400">     return total_cents</div>
          </div>
        ) : (
          <div className="p-4 bg-[#08090d] font-mono text-xs space-y-1">
            <div className="text-gray-500">@@ -38,7 +38,12 @@ def calculate_discount(total_cents: int, discount_pct: int) -&gt; int:</div>
            <div className="text-gray-400">     if discount_pct &lt;= 0:</div>
            <div className="text-gray-400">         return 0</div>
            <div className="bg-emerald-950/40 text-emerald-300 border-l-2 border-emerald-500 pl-2 py-0.5">
              +    # Fixed: Pure integer arithmetic with half-up rounding (Constraint sc_001)
            </div>
            <div className="bg-emerald-950/40 text-emerald-300 border-l-2 border-emerald-500 pl-2 py-0.5">
              +    discount_cents = (total_cents * discount_pct + 50) // 100
            </div>
            <div className="bg-emerald-950/40 text-emerald-300 border-l-2 border-emerald-500 pl-2 py-0.5">
              +    return min(discount_cents, total_cents)
            </div>
            <div className="text-gray-400">     return total_cents</div>
          </div>
        )}

        {/* Diagnosis Box */}
        <div className="p-4 bg-black/40 border-t border-white/10 text-xs">
          <div className="font-semibold text-gray-300 mb-1 flex items-center gap-1.5">
            <Sparkles className="w-3.5 h-3.5 text-emerald-400" />
            Receipt Automated Diagnostic Prompt:
          </div>
          <p className="text-gray-400 font-mono text-[11px] leading-relaxed">
            {activeIteration === 1
              ? "[ERROR] Failure on test_coupons_hidden.py: For total_cents=1999 and discount_pct=15, expected discount=300 cents ($3.00), got 299 cents ($2.99). Float truncation violates constraint sc_001. Please use integer half-up rounding without float conversion."
              : "[SUCCESS] Invariant satisfied. Both integer cents constraint sc_001 and all 3 acceptance criteria tests passed in isolated sandbox."}
          </p>
        </div>
      </div>
    </div>
  );
}
