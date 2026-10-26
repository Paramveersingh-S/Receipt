"use client";

import React, { useState } from "react";
import {
  BarChart3,
  TrendingUp,
  ShieldCheck,
  Zap,
  Target,
  Award,
} from "lucide-react";
import { MOCK_BENCHMARK } from "@/lib/mockData";

export function BenchmarkView() {
  const [activeMetric, setActiveMetric] = useState<"detection" | "repair" | "precision">("detection");

  return (
    <div className="w-full max-w-5xl mx-auto space-y-6">
      {/* Top Banner */}
      <div className="p-5 rounded-xl glass-panel flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <BarChart3 className="w-5 h-5 text-emerald-400" />
            <h2 className="text-lg font-bold text-gray-100">
              ReceiptBench & ScarBench Empirical Evaluation
            </h2>
          </div>
          <p className="text-xs text-gray-400 mt-1 max-w-2xl">
            Controlled benchmarks across 24 evaluation tasks testing subtle bug detection, regression prevention, and autonomous repair success rates.
          </p>
        </div>

        {/* Metric Selector Tabs */}
        <div className="flex items-center gap-1 bg-black/40 p-1 rounded-lg border border-white/10 text-xs">
          <button
            onClick={() => setActiveMetric("detection")}
            className={`px-3 py-1.5 rounded-md transition-colors ${
              activeMetric === "detection"
                ? "bg-emerald-500/20 text-emerald-300 border border-emerald-500/30 font-semibold"
                : "text-gray-400 hover:text-gray-200"
            }`}
          >
            Detection Rate
          </button>
          <button
            onClick={() => setActiveMetric("repair")}
            className={`px-3 py-1.5 rounded-md transition-colors ${
              activeMetric === "repair"
                ? "bg-emerald-500/20 text-emerald-300 border border-emerald-500/30 font-semibold"
                : "text-gray-400 hover:text-gray-200"
            }`}
          >
            Repair Success
          </button>
          <button
            onClick={() => setActiveMetric("precision")}
            className={`px-3 py-1.5 rounded-md transition-colors ${
              activeMetric === "precision"
                ? "bg-emerald-500/20 text-emerald-300 border border-emerald-500/30 font-semibold"
                : "text-gray-400 hover:text-gray-200"
            }`}
          >
            Precision & F1
          </button>
        </div>
      </div>

      {/* KPI Highlight Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-4 gap-4">
        <div className="p-4 rounded-xl glass-panel border border-white/10">
          <div className="text-[11px] font-mono text-gray-400 uppercase">Detection Rate</div>
          <div className="text-2xl font-black text-emerald-400 mt-1">96%</div>
          <div className="text-[10px] text-gray-400 mt-0.5">vs 8% baseline PR tests</div>
        </div>

        <div className="p-4 rounded-xl glass-panel border border-white/10">
          <div className="text-[11px] font-mono text-gray-400 uppercase">Repair Success</div>
          <div className="text-2xl font-black text-emerald-400 mt-1">92%</div>
          <div className="text-[10px] text-gray-400 mt-0.5">Autonomous self-healing</div>
        </div>

        <div className="p-4 rounded-xl glass-panel border border-white/10">
          <div className="text-[11px] font-mono text-gray-400 uppercase">Scar Recall</div>
          <div className="text-2xl font-black text-purple-400 mt-1">100%</div>
          <div className="text-[10px] text-gray-400 mt-0.5">7/7 planted lessons recovered</div>
        </div>

        <div className="p-4 rounded-xl glass-panel border border-white/10">
          <div className="text-[11px] font-mono text-gray-400 uppercase">Avg Verification Cost</div>
          <div className="text-2xl font-black text-blue-400 mt-1">$0.098</div>
          <div className="text-[10px] text-gray-400 mt-0.5">Per verified pull request</div>
        </div>
      </div>

      {/* Comparison Chart Visualization */}
      <div className="p-6 rounded-xl glass-panel space-y-5">
        <div className="flex items-center justify-between text-xs text-gray-300">
          <span className="font-semibold uppercase tracking-wider font-mono">
            {activeMetric === "detection"
              ? "Defect Detection Rate (% of Subtle Bugs Caught)"
              : activeMetric === "repair"
              ? "Autonomous Repair Success Rate (% Healed in ≤3 Turns)"
              : "Verification Precision (Low False Alarm Rate)"}
          </span>
          <span className="text-[11px] text-gray-400 font-mono">Higher is better</span>
        </div>

        {/* Bar Chart Rows */}
        <div className="space-y-4">
          {MOCK_BENCHMARK.comparisons.map((c, idx) => {
            const isFullSystem = c.system.includes("Full System");
            const val =
              activeMetric === "detection"
                ? c.detection_rate
                : activeMetric === "repair"
                ? c.repair_success_rate
                : c.precision;

            return (
              <div key={idx} className="space-y-1.5">
                <div className="flex items-center justify-between text-xs">
                  <span className={`font-mono ${isFullSystem ? "font-bold text-emerald-300" : "text-gray-300"}`}>
                    {c.system}
                  </span>
                  <span className={`font-mono font-bold ${isFullSystem ? "text-emerald-400" : "text-gray-400"}`}>
                    {(val * 100).toFixed(0)}%
                  </span>
                </div>

                {/* Bar */}
                <div className="w-full h-4 rounded-full bg-black/40 overflow-hidden border border-white/10 p-0.5">
                  <div
                    className={`h-full rounded-full transition-all duration-500 ${
                      isFullSystem
                        ? "bg-gradient-to-r from-emerald-500 to-teal-400 shadow-[0_0_12px_rgba(16,185,129,0.5)]"
                        : "bg-gray-600"
                    }`}
                    style={{ width: `${Math.max(val * 100, 3)}%` }}
                  />
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* ScarBench Ground Truth Table */}
      <div className="p-6 rounded-xl glass-panel space-y-4">
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-bold text-gray-100 flex items-center gap-2">
            <Award className="w-4 h-4 text-purple-400" />
            ScarBench: Institutional Memory Ground Truth Recovery
          </h3>
          <span className="text-xs px-2 py-0.5 rounded bg-purple-500/20 text-purple-300 font-mono">
            Recall: 100% • Precision: 88%
          </span>
        </div>

        <p className="text-xs text-gray-400">
          7 invariant lessons were planted across repository history (reverts, incident fixes, and code reviews). Scar Tissue successfully extracted and clustered all 7 without human intervention.
        </p>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs font-mono">
            <thead>
              <tr className="border-b border-white/10 text-gray-400">
                <th className="pb-2">Lesson ID</th>
                <th className="pb-2">Target File</th>
                <th className="pb-2">Planted Invariant Rule</th>
                <th className="pb-2">Extracted Status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-white/5 text-gray-300">
              <tr>
                <td className="py-2 text-purple-400">sc_001</td>
                <td className="py-2 text-blue-400">shop/pricing.py</td>
                <td className="py-2">Money is integer cents, never float</td>
                <td className="py-2 text-emerald-400">✓ RECOVERED</td>
              </tr>
              <tr>
                <td className="py-2 text-purple-400">sc_002</td>
                <td className="py-2 text-blue-400">shop/payments.py</td>
                <td className="py-2">Payment retries require idempotency key</td>
                <td className="py-2 text-emerald-400">✓ RECOVERED</td>
              </tr>
              <tr>
                <td className="py-2 text-purple-400">sc_003</td>
                <td className="py-2 text-blue-400">shop/payments.py</td>
                <td className="py-2">Do not swallow bare Exception around payment calls</td>
                <td className="py-2 text-emerald-400">✓ RECOVERED</td>
              </tr>
              <tr>
                <td className="py-2 text-purple-400">sc_004</td>
                <td className="py-2 text-blue-400">shop/catalog.py</td>
                <td className="py-2">Database queries inside loops (N+1) are forbidden</td>
                <td className="py-2 text-emerald-400">✓ RECOVERED</td>
              </tr>
              <tr>
                <td className="py-2 text-purple-400">sc_005</td>
                <td className="py-2 text-blue-400">shop/api/**</td>
                <td className="py-2">All new API endpoints require authentication</td>
                <td className="py-2 text-emerald-400">✓ RECOVERED</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
