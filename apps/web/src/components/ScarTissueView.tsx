"use client";

import React, { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  GitBranch,
  ShieldAlert,
  Search,
  ExternalLink,
  ChevronRight,
  Sparkles,
  BookOpen,
  Filter,
  CheckCircle2,
  Tag,
  Code2,
} from "lucide-react";
import { ConstraintItem, GraphData } from "@/types";
import { MOCK_CONSTRAINTS, MOCK_GRAPH } from "@/lib/mockData";

export function ScarTissueView() {
  const [selectedConstraint, setSelectedConstraint] = useState<ConstraintItem>(MOCK_CONSTRAINTS[0]);
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedTag, setSelectedTag] = useState<string>("all");
  const [viewMode, setViewMode] = useState<"cards" | "graph" | "briefing">("cards");

  const tags = ["all", "payments", "pricing", "database", "security", "error-handling"];

  const filteredConstraints = MOCK_CONSTRAINTS.filter((c) => {
    const matchesSearch =
      searchQuery === "" ||
      c.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
      c.rule.toLowerCase().includes(searchQuery.toLowerCase()) ||
      c.id.toLowerCase().includes(searchQuery.toLowerCase());

    const matchesTag =
      selectedTag === "all" ||
      (c.scope?.tags && c.scope.tags.includes(selectedTag));

    return matchesSearch && matchesTag;
  });

  return (
    <div className="w-full max-w-6xl mx-auto space-y-6">
      {/* Top Banner */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 p-5 rounded-xl glass-panel">
        <div>
          <div className="flex items-center gap-2">
            <GitBranch className="w-5 h-5 text-purple-400" />
            <h2 className="text-lg font-bold text-gray-100">
              Scar Tissue — Institutional Memory Graph
            </h2>
          </div>
          <p className="text-xs text-gray-400 mt-1 max-w-2xl">
            Learns repository invariants from past reverts, incident fixes, and review comments. Serves dynamic briefings to coding agents via FastMCP.
          </p>
        </div>

        {/* View Mode Toggle */}
        <div className="flex items-center gap-1 bg-black/40 p-1 rounded-lg border border-white/10 text-xs">
          <button
            onClick={() => setViewMode("cards")}
            className={`px-3 py-1 rounded-md transition-colors ${
              viewMode === "cards"
                ? "bg-white/15 text-white font-semibold"
                : "text-gray-400 hover:text-gray-200"
            }`}
          >
            Constraints List
          </button>
          <button
            onClick={() => setViewMode("graph")}
            className={`px-3 py-1 rounded-md transition-colors ${
              viewMode === "graph"
                ? "bg-white/15 text-white font-semibold"
                : "text-gray-400 hover:text-gray-200"
            }`}
          >
            Knowledge Graph
          </button>
          <button
            onClick={() => setViewMode("briefing")}
            className={`px-3 py-1 rounded-md transition-colors ${
              viewMode === "briefing"
                ? "bg-white/15 text-white font-semibold"
                : "text-gray-400 hover:text-gray-200"
            }`}
          >
            MCP Agent Briefing
          </button>
        </div>
      </div>

      {/* Main Content Area */}
      {viewMode === "cards" && (
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
          {/* Left Column: Filterable Constraints List */}
          <div className="lg:col-span-5 space-y-3">
            {/* Search and Tag filter */}
            <div className="glass-panel p-3 rounded-xl space-y-2.5">
              <div className="relative">
                <Search className="w-3.5 h-3.5 absolute left-3 top-2.5 text-gray-400" />
                <input
                  type="text"
                  placeholder="Search constraints or rules..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="w-full pl-8 pr-3 py-1.5 text-xs bg-black/40 border border-white/10 rounded-lg text-gray-200 focus:outline-none focus:border-purple-500/50"
                />
              </div>

              {/* Tags */}
              <div className="flex items-center gap-1 overflow-x-auto pb-1 text-[11px]">
                {tags.map((t) => (
                  <button
                    key={t}
                    onClick={() => setSelectedTag(t)}
                    className={`px-2 py-0.5 rounded-full capitalize whitespace-nowrap transition-colors ${
                      selectedTag === t
                        ? "bg-purple-500/20 text-purple-300 border border-purple-500/40 font-semibold"
                        : "bg-white/5 text-gray-400 hover:text-gray-200"
                    }`}
                  >
                    {t}
                  </button>
                ))}
              </div>
            </div>

            {/* List */}
            <div className="space-y-2 max-h-[600px] overflow-y-auto pr-1">
              {filteredConstraints.map((c) => {
                const isSelected = selectedConstraint.id === c.id;

                return (
                  <button
                    key={c.id}
                    onClick={() => setSelectedConstraint(c)}
                    className={`w-full text-left p-3.5 rounded-xl border transition-all ${
                      isSelected
                        ? "bg-purple-950/20 border-purple-500/50 shadow-[0_0_15px_rgba(168,85,247,0.15)]"
                        : "glass-card hover:bg-white/5 border-white/5"
                    }`}
                  >
                    <div className="flex items-center justify-between mb-1">
                      <span className="text-[10px] font-mono font-bold text-purple-400">
                        {c.id}
                      </span>
                      <span className="text-[10px] px-1.5 py-0.2 rounded bg-rose-500/15 text-rose-300 border border-rose-500/30 uppercase font-mono">
                        {c.severity}
                      </span>
                    </div>

                    <div className="font-semibold text-xs text-gray-200 leading-snug">
                      {c.title}
                    </div>

                    <div className="flex items-center gap-2 mt-2 text-[10px] text-gray-400 font-mono">
                      <span>Conf: {(c.confidence * 100).toFixed(0)}%</span>
                      <span>•</span>
                      <span>{c.prevented_count} bugs intercepted</span>
                    </div>
                  </button>
                );
              })}
            </div>
          </div>

          {/* Right Column: Detailed Constraint Inspector */}
          <div className="lg:col-span-7">
            <div className="glass-panel p-6 rounded-xl space-y-5 sticky top-16">
              {/* Header */}
              <div className="border-b border-white/10 pb-4">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-mono text-purple-400 font-bold">
                    {selectedConstraint.id} • v{selectedConstraint.version}
                  </span>
                  <div className="flex items-center gap-2">
                    <span className="text-xs px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/30 font-mono">
                      Status: {selectedConstraint.status}
                    </span>
                    <span className="text-xs px-2 py-0.5 rounded-full bg-purple-500/10 text-purple-400 border border-purple-500/30 font-mono">
                      {(selectedConstraint.confidence * 100).toFixed(0)}% Confidence
                    </span>
                  </div>
                </div>

                <h3 className="text-base font-bold text-gray-100 mt-2">
                  {selectedConstraint.title}
                </h3>
              </div>

              {/* The Rule */}
              <div className="space-y-1.5">
                <div className="text-xs font-semibold text-gray-400 uppercase tracking-wider">
                  ENFORCED INVARIANT RULE
                </div>
                <div className="p-3 rounded-lg bg-black/40 border border-white/10 font-mono text-xs text-emerald-300 leading-relaxed">
                  {selectedConstraint.rule}
                </div>
              </div>

              {/* Why */}
              <div className="space-y-1.5">
                <div className="text-xs font-semibold text-gray-400 uppercase tracking-wider">
                  ORIGIN REASONING (WHY THIS RULE EXISTS)
                </div>
                <div className="text-xs text-gray-300 bg-white/5 p-3 rounded-lg border border-white/5 leading-relaxed">
                  {selectedConstraint.why}
                </div>
              </div>

              {/* Scoped Files and Symbols */}
              {selectedConstraint.scope && (
                <div className="space-y-1.5">
                  <div className="text-xs font-semibold text-gray-400 uppercase tracking-wider">
                    SCOPED PATHS & SYMBOLS
                  </div>
                  <div className="flex flex-wrap gap-1.5">
                    {selectedConstraint.scope.paths.map((p, i) => (
                      <span
                        key={i}
                        className="px-2 py-1 rounded bg-blue-500/10 text-blue-300 border border-blue-500/20 font-mono text-[11px]"
                      >
                        {p}
                      </span>
                    ))}
                    {selectedConstraint.scope.symbols.map((s, i) => (
                      <span
                        key={i}
                        className="px-2 py-1 rounded bg-indigo-500/10 text-indigo-300 border border-indigo-500/20 font-mono text-[11px]"
                      >
                        fn {s}()
                      </span>
                    ))}
                  </div>
                </div>
              )}

              {/* Provenance Evidence */}
              <div className="space-y-2">
                <div className="text-xs font-semibold text-gray-400 uppercase tracking-wider">
                  GROUND TRUTH PROVENANCE EVIDENCE
                </div>
                <div className="space-y-2">
                  {selectedConstraint.evidence.map((ev, i) => (
                    <div
                      key={i}
                      className="p-3 rounded-lg bg-black/40 border border-white/10 text-xs space-y-1"
                    >
                      <div className="flex items-center justify-between">
                        <span className="text-[10px] font-mono px-1.5 py-0.2 rounded bg-amber-500/15 text-amber-300 border border-amber-500/30 uppercase">
                          {ev.type}
                        </span>
                        <a
                          href={ev.url}
                          target="_blank"
                          rel="noreferrer"
                          className="text-[11px] text-blue-400 hover:underline flex items-center gap-1 font-mono"
                        >
                          <span>{ev.sha ? `Commit ${ev.sha}` : "PR Reference"}</span>
                          <ExternalLink className="w-3 h-3" />
                        </a>
                      </div>
                      <div className="text-gray-300 text-[11px] italic font-mono pt-1">
                        &quot;{ev.excerpt}&quot;
                      </div>
                      {ev.at && (
                        <div className="text-[10px] text-gray-500">
                          Recorded: {ev.at}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Knowledge Graph Mode */}
      {viewMode === "graph" && (
        <div className="p-6 rounded-xl glass-panel space-y-4">
          <div className="flex items-center justify-between text-xs text-gray-400">
            <span>REPOSITORY KNOWLEDGE TOPOLOGY</span>
            <div className="flex items-center gap-3 text-[11px] font-mono">
              <span className="flex items-center gap-1">
                <span className="w-2.5 h-2.5 rounded-full bg-emerald-400" /> Constraint
              </span>
              <span className="flex items-center gap-1">
                <span className="w-2.5 h-2.5 rounded-full bg-blue-400" /> File Scope
              </span>
              <span className="flex items-center gap-1">
                <span className="w-2.5 h-2.5 rounded-full bg-purple-400" /> Historical PR
              </span>
              <span className="flex items-center gap-1">
                <span className="w-2.5 h-2.5 rounded-full bg-rose-400" /> Incident
              </span>
            </div>
          </div>

          {/* SVG Knowledge Graph */}
          <div className="w-full h-96 bg-black/40 rounded-xl border border-white/10 relative overflow-hidden flex items-center justify-center p-4">
            <svg className="w-full h-full" viewBox="0 0 800 400">
              {/* Lines */}
              <line x1="150" y1="120" x2="400" y2="80" stroke="rgba(255,255,255,0.15)" strokeWidth="1.5" />
              <line x1="150" y1="120" x2="400" y2="180" stroke="rgba(255,255,255,0.15)" strokeWidth="1.5" />
              <line x1="150" y1="120" x2="650" y2="100" stroke="rgba(168,85,247,0.3)" strokeWidth="1.5" strokeDasharray="4 4" />
              <line x1="650" y1="100" x2="650" y2="280" stroke="rgba(244,63,94,0.4)" strokeWidth="1.5" />
              <line x1="150" y1="280" x2="400" y2="280" stroke="rgba(255,255,255,0.15)" strokeWidth="1.5" />
              <line x1="150" y1="280" x2="650" y2="280" stroke="rgba(168,85,247,0.3)" strokeWidth="1.5" strokeDasharray="4 4" />

              {/* Node sc_001 (Constraint) */}
              <g transform="translate(150, 120)">
                <circle r="36" fill="#064e3b" stroke="#10b981" strokeWidth="2" />
                <text textAnchor="middle" y="4" fill="#a7f3d0" fontSize="11" fontWeight="bold">sc_001</text>
                <text textAnchor="middle" y="52" fill="#d1fae5" fontSize="10">Integer Cents</text>
              </g>

              {/* Node sc_002 (Constraint) */}
              <g transform="translate(150, 280)">
                <circle r="36" fill="#064e3b" stroke="#10b981" strokeWidth="2" />
                <text textAnchor="middle" y="4" fill="#a7f3d0" fontSize="11" fontWeight="bold">sc_002</text>
                <text textAnchor="middle" y="52" fill="#d1fae5" fontSize="10">Idempotency</text>
              </g>

              {/* Node pricing.py (File) */}
              <g transform="translate(400, 80)">
                <rect x="-60" y="-18" width="120" height="36" rx="8" fill="#1e3a8a" stroke="#3b82f6" strokeWidth="1.5" />
                <text textAnchor="middle" y="4" fill="#bfdbfe" fontSize="10" fontFamily="monospace">shop/pricing.py</text>
              </g>

              {/* Node checkout.py (File) */}
              <g transform="translate(400, 180)">
                <rect x="-65" y="-18" width="130" height="36" rx="8" fill="#1e3a8a" stroke="#3b82f6" strokeWidth="1.5" />
                <text textAnchor="middle" y="4" fill="#bfdbfe" fontSize="10" fontFamily="monospace">shop/checkout.py</text>
              </g>

              {/* Node payments.py (File) */}
              <g transform="translate(400, 280)">
                <rect x="-65" y="-18" width="130" height="36" rx="8" fill="#1e3a8a" stroke="#3b82f6" strokeWidth="1.5" />
                <text textAnchor="middle" y="4" fill="#bfdbfe" fontSize="10" fontFamily="monospace">shop/payments.py</text>
              </g>

              {/* Node PR #8 (Revert) */}
              <g transform="translate(650, 100)">
                <circle r="30" fill="#581c87" stroke="#a855f7" strokeWidth="2" />
                <text textAnchor="middle" y="4" fill="#e9d5ff" fontSize="10" fontWeight="bold">PR #8</text>
                <text textAnchor="middle" y="45" fill="#e9d5ff" fontSize="9">Revert #7</text>
              </g>

              {/* Node Incident #7 */}
              <g transform="translate(650, 280)">
                <circle r="30" fill="#881337" stroke="#f43f5e" strokeWidth="2" />
                <text textAnchor="middle" y="4" fill="#fecdd3" fontSize="10" fontWeight="bold">INC #7</text>
                <text textAnchor="middle" y="45" fill="#fecdd3" fontSize="9">Double Charge</text>
              </g>
            </svg>
          </div>
        </div>
      )}

      {/* MCP Agent Briefing Preview Mode */}
      {viewMode === "briefing" && (
        <div className="p-6 rounded-xl glass-panel space-y-4">
          <div className="flex items-center justify-between border-b border-white/10 pb-3">
            <div>
              <h3 className="text-sm font-bold text-gray-100 flex items-center gap-2">
                <Code2 className="w-4 h-4 text-emerald-400" />
                FastMCP Tool Output: `get_scar_briefing(paths=[&quot;shop/pricing.py&quot;])`
              </h3>
              <p className="text-xs text-gray-400 mt-0.5">
                This exact prompt context is served automatically to Claude Code or Cursor before file edits.
              </p>
            </div>
            <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-emerald-500/20 text-emerald-300 border border-emerald-500/30">
              FAST-MCP v1.2
            </span>
          </div>

          <pre className="p-4 rounded-xl bg-black/60 border border-white/10 font-mono text-xs text-gray-300 leading-relaxed overflow-x-auto whitespace-pre">
{`# SCAR TISSUE BRIEFING FOR "shop/pricing.py"
The following repository constraints are ACTIVE and will BLOCK PR verification if violated:

## [CRITICAL] sc_001: Money is integer cents, never float
- RULE: Represent and compute all monetary amounts as integer cents; never use float arithmetic for prices, totals or discounts.
- WHY: Rounding drift caused double-charge/penny mismatches in incident #7; reverted in #8.
- EVIDENCE: PR #8 (revert: 9f8e7d2), PR #9 (fix: 11ab33c)

## [CRITICAL] sc_004: Database queries inside loops (N+1) are forbidden
- RULE: Eagerly load related models with joinedload or selectinload. Do not query individual foreign records in loop iterations.
- WHY: Catalog page triggered 250 individual SQL queries for reviews, resulting in a 4.2s latency spike.
- EVIDENCE: PR #4 (revert: 55bb99f)

Remember: Receipt verifies every diff against these rules in an isolated sandbox.`}
          </pre>
        </div>
      )}
    </div>
  );
}
